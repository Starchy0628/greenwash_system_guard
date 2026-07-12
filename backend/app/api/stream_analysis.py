"""分析相关 API — 流式分析接口"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.company import Company, FINANCIAL_INDUSTRIES
from app.services.analysis_orchestrator import AnalysisOrchestrator

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/stream")
async def stream_analysis(
    stock_code: str | None = None,
    company_name: str | None = None,
    force_refresh: bool = False,
    db: Session = Depends(get_db),
):
    """
    流式分析接口 - SSE 推送实时进度
    参数：
    - stock_code: 股票代码（精确匹配）
    - company_name: 企业名称（模糊匹配）
    - force_refresh: 是否强制刷新重新分析
    """
    # 查找企业
    company = None
    if stock_code:
        company = db.query(Company).filter(Company.stock_code == stock_code).first()
    elif company_name:
        company = db.query(Company).filter(Company.company_name.contains(company_name)).first()

    if not company:
        # 流式返回未找到错误
        async def not_found():
            yield f"event: analysis_error\ndata: {{\"phase\":\"not_found\",\"message\":\"未找到该企业，请确认股票代码或名称是否正确\",\"retryable\":false}}\n\n"
        return StreamingResponse(not_found(), media_type="text/event-stream")

    # 拒绝金融类、ST类企业
    if company.industry in FINANCIAL_INDUSTRIES:
        async def financial_error():
            yield f"event: analysis_error\ndata: {{\"phase\":\"not_found\",\"message\":\"金融类上市公司不在分析范围内\",\"retryable\":false}}\n\n"
        return StreamingResponse(financial_error(), media_type="text/event-stream")
    if company.is_st:
        async def st_error():
            yield f"event: analysis_error\ndata: {{\"phase\":\"not_found\",\"message\":\"ST/*ST/PT 类公司不在分析范围内\",\"retryable\":false}}\n\n"
        return StreamingResponse(st_error(), media_type="text/event-stream")

    if not company.is_active:
        async def inactive():
            yield f"event: analysis_error\ndata: {{\"phase\":\"not_found\",\"message\":\"该企业已不活跃，请核对信息\",\"retryable\":false}}\n\n"
        return StreamingResponse(inactive(), media_type="text/event-stream")

    return StreamingResponse(
        AnalysisOrchestrator.analyze_stream(company, db, force_refresh),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )