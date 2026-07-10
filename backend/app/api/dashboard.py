"""仪表盘 API"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.database import get_db
from app.models.company import Company
from app.models.analysis import AnalysisRecord
from app.models.sentence import Sentence
from app.schemas import DashboardMetrics, RiskThresholdInfo
from app.services.industry_service import get_warn_threshold

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/top10", response_model=list[dict])
def get_top10_risk(db: Session = Depends(get_db)):
    """获取GW指数最高的10家企业"""
    records = (
        db.query(AnalysisRecord)
        .join(Company)
        .filter(
            AnalysisRecord.is_latest == True,
            AnalysisRecord.gw_index.isnot(None),
            AnalysisRecord.analysis_status == "completed",
        )
        .order_by(AnalysisRecord.gw_index.desc())
        .limit(10)
        .all()
    )

    return [
        {
            "id": r.company_id,
            "stock_code": r.company.stock_code,
            "company_name": r.company.company_name,
            "industry": r.company.industry,
            "gw_index": r.gw_index,
            "risk_level": r.risk_level,
            "year": r.year,
        }
        for r in records
    ]


@router.get("/metrics", response_model=DashboardMetrics)
def get_metrics(db: Session = Depends(get_db)):
    """获取仪表盘关键指标"""
    total_companies = db.query(func.count(Company.id)).filter(Company.is_active == True).scalar() or 0
    total_sentences = db.query(func.count(Sentence.id)).scalar() or 0
    current_year = 2024

    return DashboardMetrics(
        fleiss_kappa=0.84,
        human_agreement=94.22,
        total_sentences=total_sentences,
        total_companies=total_companies,
        warn_threshold=get_warn_threshold(db, current_year),
    )


@router.get("/risk-threshold", response_model=RiskThresholdInfo)
def get_risk_threshold(db: Session = Depends(get_db)):
    """获取当前预警阈值详情"""
    current_year = 2024
    threshold = get_warn_threshold(db, current_year)

    records = (
        db.query(AnalysisRecord)
        .filter(
            AnalysisRecord.is_latest == True,
            AnalysisRecord.gw_index.isnot(None),
            AnalysisRecord.analysis_status == "completed",
        )
        .all()
    )

    warn_count = sum(1 for r in records if r.gw_index and r.gw_index >= threshold)
    normal_count = len(records) - warn_count

    return RiskThresholdInfo(
        threshold=threshold,
        total_companies=len(records),
        warn_count=warn_count,
        normal_count=normal_count,
    )