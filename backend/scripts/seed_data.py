"""种子数据脚本 — 创建示例企业并运行 Mock 分析，包含5年历史趋势"""
import sys
from pathlib import Path
from datetime import datetime
import random

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.database import SessionLocal, init_db
from app.models.company import Company
from app.models.analysis import AnalysisRecord
from app.models.sentence import Sentence
from app.services.mock_service import run_mock_analysis
from app.services.industry_service import compute_industry_benchmarks, update_risk_levels

# 示例企业数据（含预置 GW 指数，用于演示）
SEED_COMPANIES = [
    {"stock_code": "600519", "company_name": "贵州茅台", "industry": "白酒", "short_name": "茅台", "gw": 0.0013},
    {"stock_code": "000858", "company_name": "五粮液", "industry": "白酒", "short_name": "五粮液", "gw": 0.0180},
    {"stock_code": "300750", "company_name": "宁德时代", "industry": "电池", "short_name": "宁德时代", "gw": 0.0370},
    {"stock_code": "002594", "company_name": "比亚迪", "industry": "新能源汽车", "short_name": "比亚迪", "gw": 0.1461},
    {"stock_code": "000002", "company_name": "万科A", "industry": "房地产", "short_name": "万科", "gw": -0.4194},
    {"stock_code": "600028", "company_name": "中国石化", "industry": "能源化工", "short_name": "中石化", "gw": -0.3621},
    {"stock_code": "601857", "company_name": "中国石油", "industry": "能源化工", "short_name": "中石油", "gw": -0.3701},
    {"stock_code": "600036", "company_name": "招商银行", "industry": "银行", "short_name": "招行", "gw": 0.3244},
    {"stock_code": "601012", "company_name": "隆基绿能", "industry": "光伏", "short_name": "隆基", "gw": -0.5086},
    {"stock_code": "600309", "company_name": "万华化学", "industry": "化工", "short_name": "万华", "gw": -0.4293},
    {"stock_code": "600048", "company_name": "保利发展", "industry": "房地产", "short_name": "保利", "gw": 0.0746},
    {"stock_code": "000725", "company_name": "京东方A", "industry": "电子", "short_name": "京东方", "gw": -0.4499},
]

MOCK_REPORT_TEXT = """
公司本年度环保投入达到5000万元，同比增长15%。通过ISO14001环境管理体系认证，
二氧化硫排放量减少15%，达到行业领先水平。公司高度重视环境保护工作，积极履行企业社会
责任。我们持续推动绿色低碳转型，实现可持续发展。报告期内单位产值能耗同比下降4.2%。
公司致力于打造绿色工厂，践行生态文明理念。积极推进环境治理工作，提升绿色发展水平。
公司全年实现营业收入稳步增长，净利润同比增长。董事会审议通过了年度利润分配方案。
坚持绿色发展理念，为美丽中国贡献力量。公司持续加大研发投入，提升核心竞争力。
清洁能源使用比例提升至12%，碳排放强度降低8.5%。报告期内投入3000万元用于污染防治
设施建设。公司治理结构持续优化，内部控制体系不断完善。
"""


def _generate_trend(base_gw: float) -> list[dict]:
    """生成5年历史趋势数据"""
    # 每个企业用预置 GW 作为最近一年，前面4年用随机波动生成
    random.seed(hash(base_gw) % 10000)
    years = [2021, 2022, 2023, 2024, 2025]
    trend = []
    for i, year in enumerate(years):
        if year == 2025:
            trend.append({"year": year, "gw": base_gw, "tone": 0.55 + base_gw / 2})
        else:
            variation = random.uniform(-0.05, 0.05)
            gw = round(base_gw * (0.5 + i * 0.12) + variation, 4)
            trend.append({"year": year, "gw": gw, "tone": 0.5 + gw / 2})
    return trend


def seed():
    init_db()
    db = SessionLocal()
    current_year = 2025

    try:
        # 1. 创建企业
        print("创建企业...")
        for c_data in SEED_COMPANIES:
            existing = db.query(Company).filter(Company.stock_code == c_data["stock_code"]).first()
            if existing:
                print(f"  跳过已存在: {c_data['company_name']}")
                continue
            company = Company(
                stock_code=c_data["stock_code"],
                company_name=c_data["company_name"],
                industry=c_data["industry"],
                short_name=c_data.get("short_name"),
                is_a_share=True,
            )
            db.add(company)
            print(f"  创建: {c_data['company_name']} ({c_data['stock_code']})")
        db.commit()

        companies = db.query(Company).all()
        print(f"\n运行 Mock 分析与历史趋势生成（共 {len(companies)} 家企业）...")

        for company in companies:
            # 找到预置的 GW 值
            c_data = next((c for c in SEED_COMPANIES if c["stock_code"] == company.stock_code), None)
            base_gw = c_data["gw"] if c_data else 0.0

            # 生成5年趋势
            trend_data = _generate_trend(base_gw)

            for t in trend_data:
                # 将旧记录的 is_latest 置为 False
                db.query(AnalysisRecord).filter(
                    AnalysisRecord.company_id == company.id,
                    AnalysisRecord.year == t["year"],
                ).delete()

                # 运行 mock 分析（仅最近一年）
                if t["year"] == current_year:
                    result = run_mock_analysis(MOCK_REPORT_TEXT, company.industry)
                    record = AnalysisRecord(
                        company_id=company.id,
                        year=t["year"],
                        data_source_type="ESG" if t["year"] >= 2023 else "MDA",
                        total_sentences=result["total_sentences"],
                        env_sentences=result["env_sentences"],
                        substantive_count=result["substantive_count"],
                        descriptive_count=result["descriptive_count"],
                        non_env_count=result["non_env_count"],
                        tone_score=t["tone"],
                        industry_median_tone=round(t["tone"] - t["gw"], 4),
                        gw_index=t["gw"],
                        risk_level="正常",
                        fleiss_kappa=result["fleiss_kappa"],
                        dispute_count=result["dispute_count"],
                        analysis_status="completed",
                        is_latest=True,
                        analyzed_at=datetime.now(),
                    )
                    db.add(record)
                    db.flush()

                    for s in result["sentence_results"]:
                        db.add(Sentence(
                            analysis_record_id=record.id,
                            sentence_text=s["sentence_text"],
                            sentence_order=s["sentence_order"],
                            deepseek_result=s["deepseek_result"],
                            qwen_result=s["qwen_result"],
                            pangu_result=s["pangu_result"],
                            final_category=s["final_category"],
                            vote_type=s["vote_type"],
                            confidence=s["confidence"],
                            sentiment_score=s["sentiment_score"],
                            sentiment_std=s["sentiment_std"],
                            needs_review=s["needs_review"],
                        ))
                else:
                    # 历史年份：仅存入汇总数据，不存语句
                    record = AnalysisRecord(
                        company_id=company.id,
                        year=t["year"],
                        data_source_type="MDA",
                        total_sentences=random.randint(80, 150),
                        env_sentences=random.randint(20, 50),
                        substantive_count=random.randint(5, 20),
                        descriptive_count=random.randint(10, 30),
                        non_env_count=random.randint(0, 10),
                        tone_score=t["tone"],
                        industry_median_tone=round(t["tone"] - t["gw"], 4),
                        gw_index=t["gw"],
                        risk_level="正常",
                        fleiss_kappa=round(random.uniform(0.80, 0.87), 4),
                        dispute_count=random.randint(0, 3),
                        analysis_status="completed",
                        is_latest=(t["year"] == current_year),
                        analyzed_at=datetime(t["year"], 6, 30),
                    )
                    db.add(record)

            db.commit()
            print(f"  {company.company_name}: GW(2025)={base_gw:.4f}")

        # 计算行业基准和风险等级
        print("\n计算行业基准与风险等级...")
        compute_industry_benchmarks(db, current_year)
        update_risk_levels(db, current_year)
        db.commit()
        print("行业基准计算完成！")

        print(f"\n✅ 种子数据初始化完成！共 {len(companies)} 家企业，5年历史趋势")
    finally:
        db.close()


if __name__ == "__main__":
    seed()