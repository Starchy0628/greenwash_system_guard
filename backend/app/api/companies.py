"""企业相关 API"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from app.core.database import get_db
from app.models.company import Company
from app.models.analysis import AnalysisRecord
from app.schemas import CompanyResponse, CompanySearchResult, SearchQuery

router = APIRouter(prefix="/api/companies", tags=["companies"])


@router.get("/search", response_model=list[CompanySearchResult])
def search_companies(
    q: str = Query("", description="搜索关键词（名称或代码）"),
    db: Session = Depends(get_db),
):
    """搜索企业"""
    if not q:
        return []

    companies = (
        db.query(Company)
        .filter(
            Company.is_active == True,
            or_(
                Company.company_name.contains(q),
                Company.stock_code.contains(q),
                Company.short_name.contains(q),
            ),
        )
        .order_by(Company.id)
        .limit(10)
        .all()
    )

    results = []
    for company in companies:
        latest = (
            db.query(AnalysisRecord)
            .filter(
                AnalysisRecord.company_id == company.id,
                AnalysisRecord.is_latest == True,
            )
            .first()
        )
        results.append(
            CompanySearchResult(
                id=company.id,
                stock_code=company.stock_code,
                company_name=company.company_name,
                industry=company.industry,
                latest_gw_index=latest.gw_index if latest else None,
                latest_risk_level=latest.risk_level if latest else None,
            )
        )
    return results


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(company_id: int, db: Session = Depends(get_db)):
    """获取企业详情"""
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="企业不存在")

    latest = (
        db.query(AnalysisRecord)
        .filter(
            AnalysisRecord.company_id == company_id,
            AnalysisRecord.is_latest == True,
        )
        .first()
    )

    return CompanyResponse(
        id=company.id,
        stock_code=company.stock_code,
        company_name=company.company_name,
        industry=company.industry,
        short_name=company.short_name,
        is_active=company.is_active,
        has_analysis=latest is not None,
        latest_gw_index=latest.gw_index if latest else None,
        latest_risk_level=latest.risk_level if latest else None,
    )


@router.get("/{company_id}/trend", response_model=list[dict])
def get_company_trend(company_id: int, db: Session = Depends(get_db)):
    """获取企业近5年GW指数趋势"""
    records = (
        db.query(AnalysisRecord)
        .filter(
            AnalysisRecord.company_id == company_id,
            AnalysisRecord.gw_index.isnot(None),
            AnalysisRecord.analysis_status == "completed",
        )
        .order_by(AnalysisRecord.year)
        .limit(5)
        .all()
    )

    return [
        {
            "year": r.year,
            "gw_index": r.gw_index,
            "tone_score": r.tone_score,
            "risk_level": r.risk_level,
        }
        for r in records
    ]