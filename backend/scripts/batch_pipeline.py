"""
批量年报采集与分析管道 — 模拟论文方法论的全市场覆盖

功能:
1. 遍历数据库中所有符合条件的企业（剔除金融类、ST类）
2. 对每家企业逐一下载 2012-2025 年度年报 PDF（从巨潮资讯）
3. 解析并提取 MD&A 章节
4. 执行语句分类 + 情感打分 + GW 指数计算
5. 结果存入数据库，支持断点续传、进度追踪

用法:
    python scripts/batch_pipeline.py                    # mock 模式，全量处理
    python scripts/batch_pipeline.py --year 2024        # 仅处理指定年份
    python scripts/batch_pipeline.py --company 600519   # 仅处理指定企业
    python scripts/batch_pipeline.py --real             # 真实 LLM 模式（需要 API Key）
    python scripts/batch_pipeline.py --force            # 强制重新分析已处理的记录
    python scripts/batch_pipeline.py --resume           # 从断点继续

论文参考规模:
    - 3600+ 家企业 × 24 年 = 45,104 条观测值
    - 924,617 条环境语句 → 167,316 条描述性语句
    - 三模型一致率 Fleiss' Kappa = 0.84
"""
import sys
import os
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent))

from app.core.database import SessionLocal, init_db
from app.core.config import get_settings
from app.models.company import Company, FINANCIAL_INDUSTRIES
from app.models.analysis import AnalysisRecord
from app.models.sentence import Sentence
from app.services.cninfo_crawler import fetch_report_with_fallback
from app.services.pdf_parser import parse_report_full, get_analysis_text
from app.services.text_utils import split_sentences, filter_env_sentences
from app.services.mock_service import run_mock_analysis
from app.services.industry_service import compute_industry_benchmarks, update_risk_levels, get_industry_median
# GW指数 = max(0, 企业语调 - 行业中位数)，与论文公式一致

# 进度文件路径
PROGRESS_FILE = BASE_DIR / "batch_progress.txt"

# 默认处理年份范围（论文: 2001-2024，系统: 2012-2025）
DEFAULT_YEARS = list(range(2012, 2026))


def load_progress() -> set:
    """加载已完成的 (company_id, year) 集合"""
    if not PROGRESS_FILE.exists():
        return set()
    completed = set()
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split(",")
                if len(parts) == 2:
                    completed.add((int(parts[0]), int(parts[1])))
    return completed


def save_progress(company_id: int, year: int):
    """记录完成进度"""
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{company_id},{year}\n")


def get_companies(db, company_code: str = None) -> list:
    """获取待处理企业列表（剔除金融类、ST类）"""
    query = db.query(Company).filter(
        Company.is_active == True,
        Company.is_st == False,
        Company.industry.notin_(FINANCIAL_INDUSTRIES),
    )
    if company_code:
        query = query.filter(Company.stock_code == company_code)
    return query.order_by(Company.id).all()


def company_has_analysis(db, company_id: int, year: int) -> bool:
    """检查企业某年是否已有分析记录"""
    return db.query(AnalysisRecord).filter(
        AnalysisRecord.company_id == company_id,
        AnalysisRecord.year == year,
        AnalysisRecord.analysis_status == "completed",
    ).count() > 0


def fetch_and_parse_report(company: Company, year: int, use_real_crawler: bool = False) -> tuple:
    """
    获取并解析年报

    Args:
        use_real_crawler: 是否使用真实爬虫（需要网络 + 巨潮资讯可访问）

    Returns:
        (text, data_source_type, key_indicators, error_message)
    """
    if use_real_crawler:
        # 真实模式：尝试巨潮资讯爬虫
        try:
            pdf_bytes, error, ann = fetch_report_with_fallback(company.stock_code, year=year)
            if pdf_bytes and not error:
                parsed = parse_report_full(pdf_bytes, ann.title if ann else "")
                text = get_analysis_text(parsed)
                data_source = "MD&A"
                key_indicators = parsed.key_indicators
                return text, data_source, key_indicators, None
            else:
                return "", "", [], error or "无法获取年报"
        except Exception as e:
            return "", "", [], str(e)
    else:
        # Mock 模式：使用模拟 MD&A 文本
        text = _get_mock_text(company.company_name, year)
        return text, "MD&A", [], None


def run_analysis_for_company_year(
    db,
    company: Company,
    year: int,
    use_real_llm: bool = False,
    use_real_crawler: bool = False,
) -> Optional[AnalysisRecord]:
    """
    对单个企业在单一年份执行完整分析流程

    Returns:
        AnalysisRecord 或 None（失败时）
    """
    print(f"  [{company.stock_code} {company.company_name}] {year}年 ", end="", flush=True)

    # 1. 获取文本
    text, data_source, key_indicators, fetch_error = fetch_and_parse_report(company, year, use_real_crawler)
    if fetch_error or not text or len(text.strip()) < 50:
        print(f"❌ 文本获取失败: {fetch_error or '内容过短'}")
        return None

    # 2. 语句切分与环保关键词过滤
    raw_sentences = split_sentences(text)
    if not raw_sentences:
        raw_sentences = [text]
    env_sentences, _ = filter_env_sentences(raw_sentences)

    if not env_sentences:
        print(f"⚠️ 无环境关键词语句（共{len(raw_sentences)}句），跳过")
        return None

    # 3. 分类与情感打分
    if use_real_llm:
        try:
            from app.services.analysis_orchestrator import AnalysisOrchestrator
            import asyncio
            result = asyncio.run(
                AnalysisOrchestrator._run_real_classification(env_sentences, company.industry, db)
            )
        except Exception as e:
            print(f"❌ LLM分类失败: {e}")
            return None
    else:
        result = run_mock_analysis(text, company.industry)

    # 4. 计算语调分数
    descriptive_results = [
        r for r in result["sentence_results"]
        if r["final_category"] == "descriptive"
    ]
    if descriptive_results:
        tone_score = sum(r["sentiment_score"] for r in descriptive_results) / len(descriptive_results)
    else:
        tone_score = 0.5

    # 5. 获取行业中位数
    industry_median = get_industry_median(db, company.industry, year)

    # 6. 计算 GW 指数（论文公式: GW = max(0, 企业语调 - 行业中位数)）
    gw_index = max(0.0, tone_score - industry_median)

    # 7. 保存到数据库
    # 先将旧记录标记为非最新
    db.query(AnalysisRecord).filter(
        AnalysisRecord.company_id == company.id,
        AnalysisRecord.year == year,
        AnalysisRecord.is_latest == True,
    ).update({"is_latest": False})

    # 判断是否是该企业最新年份
    is_latest = (year == max(DEFAULT_YEARS))

    record = AnalysisRecord(
        company_id=company.id,
        year=year,
        data_source_type=data_source,
        total_sentences=result["total_sentences"],
        env_sentences=result["env_sentences"],
        substantive_count=result["substantive_count"],
        descriptive_count=result["descriptive_count"],
        non_env_count=result["non_env_count"],
        tone_score=round(tone_score, 6),
        industry_median_tone=round(industry_median, 6),
        gw_index=round(gw_index, 6),
        risk_level="正常",
        fleiss_kappa=result["fleiss_kappa"],
        dispute_count=result["divergence_count"],
        analysis_status="completed",
        is_latest=is_latest,
        analyzed_at=datetime.now(),
    )
    db.add(record)
    db.flush()

    # 保存语句（仅最新年份保存完整语句，节省空间）
    if is_latest:
        for s in result["sentence_results"]:
            sentence = Sentence(
                analysis_record_id=record.id,
                sentence_text=s["sentence_text"],
                sentence_order=s["sentence_order"],
                deepseek_result=s["deepseek_result"],
                qwen_result=s["qwen_result"],
                glm_result=s["glm_result"],
                final_category=s["final_category"],
                vote_type=s["vote_type"],
                confidence=s["confidence"],
                sentiment_score=s["sentiment_score"],
                sentiment_std=s["sentiment_std"],
                needs_review=s["needs_review"],
            )
            db.add(sentence)

    db.commit()

    print(f"✅ GW={gw_index:.4f} tone={tone_score:.4f} {result['substantive_count']}实/{result['descriptive_count']}描/{result['non_env_count']}非")
    return record


def _get_mock_text(company_name: str, year: int) -> str:
    """生成模拟 MD&A 文本（mock 模式使用）"""
    return f"""{company_name}在{year}年度高度重视环境保护工作，积极践行绿色发展理念。
报告期内公司环保投入达到5000万元，同比增长15%。通过ISO14001环境管理体系认证。
二氧化硫排放量减少15%，达到行业领先水平。公司高度重视环境保护工作，积极履行企业社会责任。
我们持续推动绿色低碳转型，实现可持续发展。报告期内单位产值能耗同比下降4.2%。
公司致力于打造绿色工厂，践行生态文明理念。积极推进环境治理工作，提升绿色发展水平。
公司全年实现营业收入稳步增长，净利润同比增长。董事会审议通过了年度利润分配方案。
坚持绿色发展理念，为美丽中国贡献力量。公司持续加大研发投入，提升核心竞争力。
清洁能源使用比例提升至12%，碳排放强度降低8.5%。报告期内投入3000万元用于污染防治设施建设。
公司治理结构持续优化，内部控制体系不断完善。积极参与公益环保活动。"""


def run_batch_pipeline(
    years: list = None,
    company_code: str = None,
    use_real_llm: bool = False,
    use_real_crawler: bool = False,
    force_refresh: bool = False,
    resume: bool = True,
    delay_between_companies: float = 0.5,
):
    """
    批量处理主函数

    Args:
        years: 要处理的年份列表
        company_code: 仅处理指定企业（None = 全量）
        use_real_llm: 是否使用真实 LLM（需要 API Key）
        use_real_crawler: 是否使用真实爬虫（需要网络 + 巨潮资讯可访问）
        force_refresh: 是否强制重新分析
        resume: 是否从断点继续
        delay_between_companies: 企业间延迟（秒），避免触发反爬
    """
    if years is None:
        years = DEFAULT_YEARS

    init_db()
    db = SessionLocal()

    # 加载进度
    completed = load_progress() if resume else set()

    # 获取企业列表
    companies = get_companies(db, company_code)
    total_companies = len(companies)
    total_tasks = total_companies * len(years)

    print("=" * 60)
    print("  批量年报采集与分析管道")
    print("=" * 60)
    print(f"  企业总数: {total_companies}")
    print(f"  年份范围: {years[0]}-{years[-1]} ({len(years)}年)")
    print(f"  总任务数: {total_tasks}")
    print(f"  LLM模式: {'真实LLM' if use_real_llm else 'Mock模拟'}")
    print(f"  爬虫模式: {'真实爬虫' if use_real_crawler else 'Mock模拟'}")
    print(f"  断点续传: {'开启' if resume else '关闭'}")
    print(f"  强制刷新: {'开启' if force_refresh else '关闭'}")
    print(f"  已完成: {len(completed)} 条")
    print("=" * 60)
    print()

    processed = 0
    skipped = 0
    failed = 0
    start_time = time.time()

    for idx, company in enumerate(companies):
        company_start = time.time()

        print(f"[{idx + 1}/{total_companies}] {company.stock_code} {company.company_name} ({company.industry})")

        for year in years:
            task_key = (company.id, year)

            # 跳过已完成的
            if task_key in completed:
                skipped += 1
                continue

            # 跳过已有分析（非强制模式）
            if not force_refresh and company_has_analysis(db, company.id, year):
                save_progress(company.id, year)
                skipped += 1
                continue

            # 执行分析
            record = run_analysis_for_company_year(db, company, year, use_real_llm, use_real_crawler)
            if record:
                save_progress(company.id, year)
                processed += 1
            else:
                failed += 1

            # 小延迟避免触发反爬
            time.sleep(0.1)

        company_elapsed = time.time() - company_start
        total_elapsed = time.time() - start_time
        remaining = (total_companies - idx - 1) * (company_elapsed if company_elapsed > 0 else 10)

        print(f"  ⏱ 本企业耗时 {company_elapsed:.1f}s | 累计: {processed}成/{skipped}跳/{failed}败 | 预计剩余: {remaining/60:.0f}分")
        print()

        # 企业间延迟
        if idx < total_companies - 1:
            time.sleep(delay_between_companies)

    # 最后统一更新行业基准
    print("=" * 60)
    print("  重新计算行业基准和风险等级...")
    for year in years:
        compute_industry_benchmarks(db, year)
        update_risk_levels(db, year)
    db.commit()

    total_elapsed = time.time() - start_time
    print("=" * 60)
    print(f"  ✅ 批量处理完成！")
    print(f"  成功: {processed}  跳过: {skipped}  失败: {failed}")
    print(f"  总耗时: {total_elapsed/60:.1f} 分钟")
    print("=" * 60)

    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="批量年报采集与分析管道")
    parser.add_argument("--year", type=int, help="仅处理指定年份")
    parser.add_argument("--years", type=str, help="年份范围，如 '2020-2024'")
    parser.add_argument("--company", type=str, help="仅处理指定股票代码")
    parser.add_argument("--real", action="store_true", help="使用真实 LLM（需要 API Key）")
    parser.add_argument("--crawler", action="store_true", help="使用真实爬虫（需要网络）")
    parser.add_argument("--force", action="store_true", help="强制重新分析")
    parser.add_argument("--no-resume", action="store_true", help="不从断点继续")
    parser.add_argument("--delay", type=float, default=0.5, help="企业间延迟（秒）")

    args = parser.parse_args()

    # 解析年份
    if args.year:
        years = [args.year]
    elif args.years:
        parts = args.years.split("-")
        years = list(range(int(parts[0]), int(parts[1]) + 1))
    else:
        years = DEFAULT_YEARS

    run_batch_pipeline(
        years=years,
        company_code=args.company,
        use_real_llm=args.real,
        use_real_crawler=args.crawler,
        force_refresh=args.force,
        resume=not args.no_resume,
        delay_between_companies=args.delay,
    )