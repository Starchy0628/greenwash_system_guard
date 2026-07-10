"""行业基准计算服务"""
import sys
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.models.analysis import AnalysisRecord
from app.models.industry import IndustryBenchmark


def compute_industry_benchmarks(db: Session, year: int):
    """计算指定年份的行业基准"""
    # 1. 按行业分组计算中位数
    records = (
        db.query(AnalysisRecord)
        .filter(
            AnalysisRecord.year == year,
            AnalysisRecord.tone_score.isnot(None),
            AnalysisRecord.analysis_status == "completed",
        )
        .all()
    )

    if not records:
        return

    # 按行业分组
    industry_tones: dict[str, list[float]] = {}
    for r in records:
        if r.company and r.company.industry:
            ind = r.company.industry
            if ind not in industry_tones:
                industry_tones[ind] = []
            industry_tones[ind].append(r.tone_score)

    # 计算各行业基准
    for industry, tones in industry_tones.items():
        if len(tones) < 2:
            continue
        sorted_tones = sorted(tones)
        n = len(sorted_tones)
        median = sorted_tones[n // 2] if n % 2 == 1 else (sorted_tones[n // 2 - 1] + sorted_tones[n // 2]) / 2
        mean = sum(sorted_tones) / n
        std = (sum((t - mean) ** 2 for t in sorted_tones) / n) ** 0.5
        p20 = sorted_tones[max(0, int(n * 0.2))]
        p80 = sorted_tones[min(n - 1, int(n * 0.8))]

        # 更新或创建行业基准
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
                tone_median=round(median, 6),
                tone_mean=round(mean, 6),
                tone_std=round(std, 6),
                tone_p20=round(p20, 6),
                tone_p80=round(p80, 6),
                calculated_at=datetime.now(),
            )
            db.add(benchmark)

    db.commit()

    # 2. 更新全市场预警阈值（后20%分位）
    _update_warn_thresholds(db, year)


def _update_warn_thresholds(db: Session, year: int):
    """更新全市场GW指数预警阈值"""
    records = (
        db.query(AnalysisRecord)
        .filter(
            AnalysisRecord.year == year,
            AnalysisRecord.gw_index.isnot(None),
            AnalysisRecord.analysis_status == "completed",
            AnalysisRecord.is_latest == True,
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