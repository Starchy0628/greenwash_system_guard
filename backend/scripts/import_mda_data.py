"""
导入本地 MD&A 数据 — 处理 CNRDS CMDA 管理层讨论与分析文本

数据来源: CNRDS (中国研究数据服务平台)
数据格式: 按年份分目录，每家企业一个 txt 文件
目录结构: 年份/文本/股票代码_公司名_日期.txt

用法:
    python scripts/import_mda_data.py                    # Mock模式，全量导入
    python scripts/import_mda_data.py --year 2024        # 仅处理指定年份
    python scripts/import_mda_data.py --company 000002   # 仅处理指定企业
    python scripts/import_mda_data.py --real             # 真实 LLM 模式
    python scripts/import_mda_data.py --force            # 强制重新分析
    python scripts/import_mda_data.py --resume           # 断点续传
    python scripts/import_mda_data.py --dry-run          # 仅统计，不执行分析
"""
import sys
import os
import re
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent))

from app.core.database import SessionLocal, init_db
from app.models.company import Company, FINANCIAL_INDUSTRIES
from app.models.analysis import AnalysisRecord
from app.models.sentence import Sentence
from app.services.text_utils import split_sentences, filter_env_sentences
from app.services.mock_service import run_mock_analysis
from app.services.industry_service import (
    compute_industry_benchmarks,
    update_risk_levels,
    get_industry_median,
)

import json
from scripts.sw_industry_mapping import fetch_sw_industry_map

# 申万行业缓存文件（避免每次下载）
SW_CACHE_FILE = BASE_DIR / "sw_industry_cache.json"

# ============================================================
# 配置
# ============================================================
# MD&A 数据根目录
MDA_ROOT = Path(r"E:\固定快速访问\下载\CMDA_管理层讨论与分析_ALL")

# 处理年份范围
DEFAULT_YEARS = list(range(2012, 2026))

# 进度文件
PROGRESS_FILE = BASE_DIR / "import_mda_progress.txt"

# 文本子目录名
TEXT_SUBDIR = "文本"

# 文件名模式: 000002_万科A_2012-12-31.txt
FILE_PATTERN = re.compile(r"^(\d{6})_(.+?)_(\d{4}-\d{2}-\d{2})\.txt$")


def load_progress() -> set:
    """加载已完成进度"""
    if not PROGRESS_FILE.exists():
        return set()
    completed = set()
    with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                parts = line.split(",")
                if len(parts) == 2:
                    completed.add((parts[0], int(parts[1])))
    return completed


def save_progress(stock_code: str, year: int):
    """记录完成进度"""
    with open(PROGRESS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{stock_code},{year}\n")


def scan_mda_files(years: list = None) -> Dict[str, Dict[int, Path]]:
    """扫描 MD&A 数据目录，建立文件索引

    Returns:
        {stock_code: {year: file_path}}
    """
    if years is None:
        years = DEFAULT_YEARS

    file_index: Dict[str, Dict[int, Path]] = {}

    for year in years:
        year_dir = MDA_ROOT / str(year) / TEXT_SUBDIR
        if not year_dir.exists():
            print(f"  ⚠ 年份 {year} 目录不存在: {year_dir}")
            continue

        for f in year_dir.iterdir():
            if not f.suffix.lower() == ".txt":
                continue
            m = FILE_PATTERN.match(f.name)
            if not m:
                continue
            stock_code = m.group(1)
            file_year = int(m.group(3)[:4])  # 从日期中提取年份

            if file_year != year:
                continue

            if stock_code not in file_index:
                file_index[stock_code] = {}
            file_index[stock_code][year] = f

    return file_index


def register_companies(db, file_index: Dict[str, Dict[int, Path]]) -> Dict[str, Company]:
    """将 MD&A 数据中的企业注册到 Company 表

    从文件索引中提取所有企业，创建或更新 Company 记录。
    行业信息从已有数据库中的 Company 表获取，缺失的用默认行业。

    Returns:
        {stock_code: Company}
    """
    # 获取所有 stock_code
    all_codes = sorted(file_index.keys())

    # 从数据库获取已有企业
    existing = {
        c.stock_code: c
        for c in db.query(Company).filter(Company.stock_code.in_(all_codes)).all()
    }

    # 获取行业映射（优先从本地缓存，其次从申万研究所下载）
    print("  → 获取申万行业分类...")
    sw_map = {}
    if SW_CACHE_FILE.exists():
        with open(SW_CACHE_FILE, "r", encoding="utf-8") as f:
            sw_map = json.load(f)
        print(f"    ✓ 从本地缓存加载 {len(sw_map)} 条行业映射")
    else:
        sw_map = fetch_sw_industry_map()
        if sw_map:
            with open(SW_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(sw_map, f, ensure_ascii=False)
            print(f"    ✓ 从申万下载并缓存 {len(sw_map)} 条行业映射")
        else:
            print(f"    ⚠️ 申万行业映射获取失败，将使用通用行业分类")

    code_to_industry = {}
    for code, c in existing.items():
        if c.industry:
            code_to_industry[code] = c.industry

    # 申万映射覆盖已有数据库的行业（申万更权威）
    code_to_industry.update(sw_map)

    # 行业默认值（按股票代码前缀粗略分配）
    default_industry = "制造业"

    # 需要排除的行业（金融类）
    EXCLUDED_INDUSTRIES = {"银行", "非银金融"}

    # ST/*ST/PT 正则
    ST_PATTERN = re.compile(r"[*]?ST|PT", re.IGNORECASE)

    new_count = 0
    skipped_finance = 0
    skipped_st = 0
    company_map: Dict[str, Company] = {}

    codes_to_remove = []

    for code in all_codes:
        # 获取公司名（从文件名或已有数据库）
        if code in existing:
            company_name = existing[code].company_name
        else:
            first_file = list(file_index[code].values())[0]
            m = FILE_PATTERN.match(first_file.name)
            company_name = m.group(2) if m else code

        # 过滤 ST/*ST/PT
        if ST_PATTERN.search(company_name):
            skipped_st += 1
            codes_to_remove.append(code)
            continue

        # 获取行业
        industry = code_to_industry.get(code, default_industry)

        # 过滤金融类行业
        if industry in EXCLUDED_INDUSTRIES:
            skipped_finance += 1
            codes_to_remove.append(code)
            continue

        if code in existing:
            company_map[code] = existing[code]
        else:
            company = Company(
                stock_code=code,
                company_name=company_name,
                short_name=company_name,
                industry=industry,
                is_a_share=True,
                is_seed=False,
                is_st=False,
                is_active=True,
            )
            db.add(company)
            db.flush()
            company_map[code] = company
            new_count += 1

    # 从 file_index 中移除被排除的企业
    for code in codes_to_remove:
        file_index.pop(code, None)

    if new_count > 0:
        db.commit()
    print(f"  → 新增 {new_count} 家企业")
    print(f"  → 已排除: ST/*ST/PT {skipped_st}家, 金融类 {skipped_finance}家")

    return company_map


def read_mda_text(file_path: Path) -> str:
    """读取 MD&A 文本文件"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
        return text.strip()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="gbk") as f:
            text = f.read()
        return text.strip()


def run_analysis_for_company_year(
    db,
    company: Company,
    year: int,
    text: str,
    use_real_llm: bool = False,
) -> Optional[AnalysisRecord]:
    """对单个企业在单一年份执行完整分析流程"""
    print(f"  [{company.stock_code} {company.company_name}] {year}年 ", end="", flush=True)

    if not text or len(text.strip()) < 50:
        print(f"⚠️ 文本过短（{len(text)}字符），跳过")
        return None

    # 1. 语句切分与环保关键词过滤
    raw_sentences = split_sentences(text)
    if not raw_sentences:
        raw_sentences = [text]
    env_sentences, _ = filter_env_sentences(raw_sentences)

    if not env_sentences:
        print(f"⚠️ 无环境关键词语句（共{len(raw_sentences)}句），跳过")
        return None

    # 2. 分类与情感打分
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

    # 3. 计算语调分数
    descriptive_results = [
        r for r in result["sentence_results"]
        if r["final_category"] == "descriptive"
    ]
    if descriptive_results:
        tone_score = sum(r["sentiment_score"] for r in descriptive_results) / len(descriptive_results)
    else:
        tone_score = 0.5

    # 4. 获取行业中位数
    industry_median = get_industry_median(db, company.industry, year)

    # 5. 计算 GW 指数
    gw_index = max(0.0, tone_score - industry_median)

    # 6. 保存到数据库
    db.query(AnalysisRecord).filter(
        AnalysisRecord.company_id == company.id,
        AnalysisRecord.year == year,
        AnalysisRecord.is_latest == True,
    ).update({"is_latest": False})

    is_latest = (year == max(DEFAULT_YEARS))

    record = AnalysisRecord(
        company_id=company.id,
        year=year,
        data_source_type="MD&A",
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

    # 保存语句（仅最新年份）
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

    print(f"✅ GW={gw_index:.4f} tone={tone_score:.4f} "
          f"{result['substantive_count']}实/{result['descriptive_count']}描/"
          f"{result['non_env_count']}非")
    return record


def run_import_pipeline(
    years: list = None,
    company_code: str = None,
    use_real_llm: bool = False,
    force_refresh: bool = False,
    resume: bool = True,
    dry_run: bool = False,
):
    """主流程"""
    if years is None:
        years = DEFAULT_YEARS

    init_db()
    db = SessionLocal()

    # 1. 扫描文件
    print("=" * 60)
    print("  导入 MD&A 数据 — 论文方法处理管道")
    print("=" * 60)
    print(f"  数据根目录: {MDA_ROOT}")
    print(f"  年份范围: {years[0]}-{years[-1]} ({len(years)}年)")
    print(f"  LLM模式: {'真实LLM' if use_real_llm else 'Mock模拟'}")
    print(f"  断点续传: {'开启' if resume else '关闭'}")
    print()

    print("→ 扫描 MD&A 文件...")
    file_index = scan_mda_files(years)

    total_files = sum(len(years_map) for years_map in file_index.values())
    total_companies = len(file_index)
    print(f"  ✓ 发现 {total_companies} 家企业，{total_files} 个文件")
    print()

    if company_code:
        if company_code not in file_index:
            print(f"❌ 未找到企业 {company_code} 的 MD&A 文件")
            db.close()
            return
        file_index = {company_code: file_index[company_code]}
        total_files = len(file_index[company_code])

    # 2. 注册企业
    print("→ 注册企业信息...")
    company_map = register_companies(db, file_index)
    print(f"  ✓ 共 {len(company_map)} 家企业")
    print()

    if dry_run:
        print("=" * 60)
        print("  DRY-RUN 模式 — 仅统计，不执行分析")
        print("=" * 60)
        for code in sorted(file_index.keys())[:20]:
            comp = company_map.get(code)
            cname = comp.company_name if comp else code
            yrs = sorted(file_index[code].keys())
            print(f"  {code} {cname}: {len(yrs)}年 ({yrs[0]}-{yrs[-1]})")
        if len(file_index) > 20:
            print(f"  ... 还有 {len(file_index) - 20} 家企业")
        print(f"\n  总计: {total_companies} 家企业, {total_files} 个文件")
        db.close()
        return

    # 3. 加载进度
    completed = load_progress() if resume else set()

    # 4. 逐企业处理
    processed = 0
    skipped = 0
    failed = 0
    start_time = time.time()

    companies_sorted = sorted(file_index.keys())

    for idx, code in enumerate(companies_sorted):
        company = company_map.get(code)
        if not company:
            print(f"  ⚠ 企业 {code} 未注册，跳过")
            continue

        years_available = sorted(file_index[code].keys())
        company_start = time.time()

        print(f"[{idx+1}/{total_companies}] {code} {company.company_name} ({company.industry}) "
              f"→ {len(years_available)}年数据")

        for year in years_available:
            task_key = (code, year)

            if task_key in completed:
                skipped += 1
                continue

            if not force_refresh:
                existing = (
                    db.query(AnalysisRecord)
                    .filter(
                        AnalysisRecord.company_id == company.id,
                        AnalysisRecord.year == year,
                        AnalysisRecord.analysis_status == "completed",
                    )
                    .first()
                )
                if existing:
                    save_progress(code, year)
                    skipped += 1
                    continue

            # 读取文本
            file_path = file_index[code][year]
            text = read_mda_text(file_path)

            # 执行分析
            record = run_analysis_for_company_year(
                db, company, year, text, use_real_llm
            )
            if record:
                save_progress(code, year)
                processed += 1
            else:
                failed += 1

            time.sleep(0.05)

        company_elapsed = time.time() - company_start
        total_elapsed = time.time() - start_time
        remaining = (total_companies - idx - 1) * (company_elapsed if company_elapsed > 0 else 5)

        print(f"  ⏱ {company_elapsed:.1f}s | 累计: {processed}成/{skipped}跳/{failed}败 "
              f"| 预计剩余: {remaining/60:.0f}分")
        print()

        if idx % 50 == 49:
            db.commit()

    # 5. 更新行业基准
    print("=" * 60)
    print("  计算行业基准和风险等级...")
    for year in years:
        compute_industry_benchmarks(db, year)
        update_risk_levels(db, year)
    db.commit()

    total_elapsed = time.time() - start_time
    print("=" * 60)
    print(f"  ✅ 导入完成！")
    print(f"  成功: {processed}  跳过: {skipped}  失败: {failed}")
    print(f"  总耗时: {total_elapsed/60:.1f} 分钟")
    print("=" * 60)

    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="导入本地 MD&A 数据并按照论文方法处理")
    parser.add_argument("--year", type=int, help="仅处理指定年份")
    parser.add_argument("--years", type=str, help="年份范围，如 '2020-2024'")
    parser.add_argument("--company", type=str, help="仅处理指定股票代码")
    parser.add_argument("--real", action="store_true", help="使用真实 LLM")
    parser.add_argument("--force", action="store_true", help="强制重新分析")
    parser.add_argument("--no-resume", action="store_true", help="不从断点继续")
    parser.add_argument("--dry-run", action="store_true", help="仅统计文件，不执行分析")

    args = parser.parse_args()

    if args.year:
        years = [args.year]
    elif args.years:
        parts = args.years.split("-")
        years = list(range(int(parts[0]), int(parts[1]) + 1))
    else:
        years = DEFAULT_YEARS

    run_import_pipeline(
        years=years,
        company_code=args.company,
        use_real_llm=args.real,
        force_refresh=args.force,
        resume=not args.no_resume,
        dry_run=args.dry_run,
    )