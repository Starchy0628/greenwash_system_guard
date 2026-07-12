"""行业基准计算服务"""
import sys
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.models.analysis import AnalysisRecord
from app.models.company import Company, FINANCIAL_INDUSTRIES
from app.models.industry import IndustryBenchmark

MIN_REAL_SAMPLES = 5  # 真实企业数 ≥ 5 时不用种子数据


def compute_industry_benchmarks(db: Session, year: int):
    """计算指定年份的行业基准

    动态规则：
    - 若某行业真实企业数 ≥ 5，只用真实数据计算
    - 若 < 5，真实数据 + 种子数据一起计算
    """
    # 1. 先计算各行业真实企业数量
    real_counts = _count_real_companies_by_industry(db, year)

    # 2. 按行业分组计算（剔除金融类、ST类企业）
    records = (
        db.query(AnalysisRecord)
        .join(Company, AnalysisRecord.company_id == Company.id)
        .filter(
            AnalysisRecord.year == year,
            AnalysisRecord.tone_score.isnot(None),
            AnalysisRecord.analysis_status == "completed",
            Company.is_st == False,
            Company.industry.notin_(FINANCIAL_INDUSTRIES),
        )
        .all()
    )

    if not records:
        return

    # 按行业分组，按 is_seed 分开
    industry_real_tones: dict[str, list[float]] = {}
    industry_seed_tones: dict[str, list[float]] = {}

    for r in records:
        if not r.company or not r.company.industry:
            continue
        ind = r.company.industry
        if r.company.is_seed:
            if ind not in industry_seed_tones:
                industry_seed_tones[ind] = []
            industry_seed_tones[ind].append(r.tone_score)
        else:
            if ind not in industry_real_tones:
                industry_real_tones[ind] = []
            industry_real_tones[ind].append(r.tone_score)

    # 计算各行业基准
    industries = set(list(industry_real_tones.keys()) + list(industry_seed_tones.keys()))

    for industry in industries:
        real_tones = industry_real_tones.get(industry, [])
        seed_tones = industry_seed_tones.get(industry, [])

        if len(real_tones) >= MIN_REAL_SAMPLES:
            # 真实数据足够，只用真实数据
            tones = real_tones
            used_seed = False
        else:
            # 真实数据不足，合并种子数据
            tones = real_tones + seed_tones
            used_seed = True

        if len(tones) < 2:
            continue

        sorted_tones = sorted(tones)
        n = len(sorted_tones)
        median = sorted_tones[n // 2] if n % 2 == 1 else (sorted_tones[n // 2 - 1] + sorted_tones[n // 2]) / 2
        mean = sum(sorted_tones) / n
        std = (sum((t - mean) ** 2 for t in sorted_tones) / n) ** 0.5
        p20 = sorted_tones[max(0, int(n * 0.2))]
        p80 = sorted_tones[min(n - 1, int(n * 0.8))]

        benchmark = (
            db.query(IndustryBenchmark)
            .filter(
                IndustryBenchmark.industry == industry,
                IndustryBenchmark.year == year,
            )
            .first()
        )

        if benchmark:
            benchmark.sample_count = n
            benchmark.real_sample_count = len(real_tones)
            benchmark.used_seed_data = used_seed
            benchmark.tone_median = round(median, 6)
            benchmark.tone_mean = round(mean, 6)
            benchmark.tone_std = round(std, 6)
            benchmark.tone_p20 = round(p20, 6)
            benchmark.tone_p80 = round(p80, 6)
            benchmark.calculated_at = datetime.now()
        else:
            benchmark = IndustryBenchmark(
                industry=industry,
                year=year,
                sample_count=n,
                real_sample_count=len(real_tones),
                used_seed_data=used_seed,
                tone_median=round(median, 6),
                tone_mean=round(mean, 6),
                tone_std=round(std, 6),
                tone_p20=round(p20, 6),
                tone_p80=round(p80, 6),
                calculated_at=datetime.now(),
            )
            db.add(benchmark)

    db.commit()

    # 3. 更新全市场预警阈值
    _update_warn_thresholds(db, year)


def _count_real_companies_by_industry(db: Session, year: int) -> dict[str, int]:
    """统计各行业真实企业数量（非种子，剔除金融类、ST类）"""
    results = (
        db.query(Company.industry, func.count(func.distinct(Company.id)))
        .join(AnalysisRecord, AnalysisRecord.company_id == Company.id)
        .filter(
            Company.is_seed == False,
            Company.is_active == True,
            Company.is_st == False,
            Company.industry.notin_(FINANCIAL_INDUSTRIES),
            AnalysisRecord.year == year,
            AnalysisRecord.analysis_status == "completed",
        )
        .group_by(Company.industry)
        .all()
    )
    return {ind: cnt for ind, cnt in results if ind}


def _update_warn_thresholds(db: Session, year: int):
    """更新全市场GW指数预警阈值（剔除金融类、ST类企业）"""
    records = (
        db.query(AnalysisRecord)
        .join(Company, AnalysisRecord.company_id == Company.id)
        .filter(
            AnalysisRecord.year == year,
            AnalysisRecord.gw_index.isnot(None),
            AnalysisRecord.analysis_status == "completed",
            AnalysisRecord.is_latest == True,
            Company.is_st == False,
            Company.industry.notin_(FINANCIAL_INDUSTRIES),
        )
        .all()
    )

    if len(records) < 5:
        return

    gw_values = sorted([r.gw_index for r in records])
    n = len(gw_values)
    warn_threshold = gw_values[min(n - 1, int(n * 0.8))]  # 80%分位

    # 更新所有行业基准的预警阈值
    benchmarks = db.query(IndustryBenchmark).filter(IndustryBenchmark.year == year).all()
    for b in benchmarks:
        b.gw_warn_threshold = round(warn_threshold, 6)

    db.commit()


def get_industry_median(db: Session, industry: str, year: int) -> float:
    """获取指定行业指定年份的语调中位数

    优先从行业基准表取，没有则实时计算
    """
    benchmark = (
        db.query(IndustryBenchmark)
        .filter(
            IndustryBenchmark.industry == industry,
            IndustryBenchmark.year == year,
        )
        .first()
    )
    if benchmark and benchmark.tone_median is not None:
        return benchmark.tone_median

    # 实时计算（剔除金融类、ST类企业）
    records = (
        db.query(AnalysisRecord.tone_score)
        .join(Company, AnalysisRecord.company_id == Company.id)
        .filter(
            Company.industry == industry,
            Company.is_st == False,
            AnalysisRecord.year == year,
            AnalysisRecord.tone_score.isnot(None),
            AnalysisRecord.analysis_status == "completed",
        )
        .all()
    )

    if not records:
        return 0.55  # 默认值

    tones = sorted([r[0] for r in records])
    n = len(tones)
    if n < 2:
        return tones[0]

    if n % 2 == 1:
        return tones[n // 2]
    return (tones[n // 2 - 1] + tones[n // 2]) / 2


def get_warn_threshold(db: Session, year: int) -> float:
    """获取当前年度预警阈值"""
    benchmark = (
        db.query(IndustryBenchmark)
        .filter(IndustryBenchmark.year == year)
        .first()
    )
    if benchmark and benchmark.gw_warn_threshold is not None:
        return benchmark.gw_warn_threshold
    return 0.0


def update_risk_levels(db: Session, year: int):
    """根据最新阈值更新所有分析记录的风险等级"""
    threshold = get_warn_threshold(db, year)
    if threshold == 0.0:
        return

    records = (
        db.query(AnalysisRecord)
        .filter(
            AnalysisRecord.year == year,
            AnalysisRecord.gw_index.isnot(None),
        )
        .all()
    )

    for r in records:
        r.risk_level = "预警" if r.gw_index >= threshold else "正常"

    db.commit()