"""关注列表 API"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.company import Company, FINANCIAL_INDUSTRIES
from app.models.watchlist import Watchlist
from app.models.analysis import AnalysisRecord

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("")
def get_watchlist(db: Session = Depends(get_db)):
    """获取关注列表（剔除金融类、ST类企业）"""
    items = (
        db.query(Watchlist, Company, AnalysisRecord)
        .join(Company, Watchlist.company_id == Company.id)
        .outerjoin(
            AnalysisRecord,
            (AnalysisRecord.company_id == Company.id) & (AnalysisRecord.is_latest == True),
        )
        .filter(
            Company.is_st == False,
            Company.industry.notin_(FINANCIAL_INDUSTRIES),
        )
        .order_by(Watchlist.added_at.desc())
        .all()
    )

    result = []
    for wl, company, analysis in items:
        result.append({
            "company_id": company.id,
            "stock_code": company.stock_code,
            "company_name": company.company_name,
            "industry": company.industry,
            "latest_gw_index": analysis.gw_index if analysis else None,
            "latest_risk_level": analysis.risk_level if analysis else None,
            "added_at": wl.added_at.isoformat() if wl.added_at else None,
        })
    return result


@router.post("/{stock_code}")
def add_to_watchlist(stock_code: str, db: Session = Depends(get_db)):
    """添加关注"""
    company = db.query(Company).filter(Company.stock_code == stock_code).first()
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")

    # 拒绝金融类、ST类企业
    if company.industry in FINANCIAL_INDUSTRIES:
        raise HTTPException(status_code=400, detail="金融类上市公司不在关注范围内")
    if company.is_st:
        raise HTTPException(status_code=400, detail="ST/*ST/PT 类公司不在关注范围内")

    existing = db.query(Watchlist).filter(Watchlist.company_id == company.id).first()
    if existing:
        return {"message": "已在关注列表中", "company_id": company.id}

    wl = Watchlist(company_id=company.id)
    db.add(wl)
    db.commit()
    return {"message": "已添加关注", "company_id": company.id}


@router.delete("/{stock_code}")
def remove_from_watchlist(stock_code: str, db: Session = Depends(get_db)):
    """取消关注"""
    company = db.query(Company).filter(Company.stock_code == stock_code).first()
    if not company:
        raise HTTPException(status_code=404, detail="企业不存在")

    wl = db.query(Watchlist).filter(Watchlist.company_id == company.id).first()
    if not wl:
        raise HTTPException(status_code=404, detail="未在关注列表中")

    db.delete(wl)
    db.commit()
    return {"message": "已取消关注", "company_id": company.id}