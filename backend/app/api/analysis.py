"""分析相关 API — 单企业分析 + 语句详情"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
import random

from app.core.database import get_db
from app.core.config import get_settings
from app.models.company import Company, FINANCIAL_INDUSTRIES
from app.models.analysis import AnalysisRecord
from app.models.sentence import Sentence
from app.schemas import AnalysisRecordResponse, SentenceResponse, AnalysisQuery
from app.services.mock_service import run_mock_analysis
from app.services.industry_service import compute_industry_benchmarks, update_risk_levels

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# 模拟分析进度存储
_analysis_progress: dict[str, dict] = {}

# 示例文本（用于模拟）
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


@router.post("/query", response_model=dict)
def query_or_analyze(
    body: AnalysisQuery,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """查询企业最新分析结果，若无则触发分析"""
    settings = get_settings()
    company = None

    if body.stock_code:
        company = db.query(Company).filter(Company.stock_code == body.stock_code).first()
    elif body.company_name:
        company = db.query(Company).filter(Company.company_name.contains(body.company_name)).first()

    if not company:
        raise HTTPException(status_code=404, detail="未找到该企业，请先确认企业信息")

    # 拒绝金融类、ST类企业
    if company.industry in FINANCIAL_INDUSTRIES:
        raise HTTPException(status_code=400, detail="金融类上市公司不在分析范围内")
    if company.is_st:
        raise HTTPException(status_code=400, detail="ST/*ST/PT 类公司不在分析范围内")

    # 查找已有分析记录
    existing = (
        db.query(AnalysisRecord)
        .filter(
            AnalysisRecord.company_id == company.id,
            AnalysisRecord.is_latest == True,
        )
        .first()
    )

    if existing and not body.force_refresh:
        return {
            "type": "cached",
            "analysis_id": existing.id,
            "company": {
                "id": company.id,
                "stock_code": company.stock_code,
                "company_name": company.company_name,
                "industry": company.industry,
            },
            "result": _analysis_to_dict(existing),
        }

    # 触发实时分析
    analysis_id = f"analysis_{company.id}_{random.randint(1000, 9999)}"
    _analysis_progress[analysis_id] = {
        "step": 0,
        "company_id": company.id,
        "status": "pending",
    }

    # 后台执行分析
    background_tasks.add_task(
        _run_analysis_flow, analysis_id, company, db
    )

    return {
        "type": "live",
        "analysis_id": analysis_id,
        "company": {
            "id": company.id,
            "stock_code": company.stock_code,
            "company_name": company.company_name,
            "industry": company.industry,
        },
        "message": "分析流程已启动",
    }


@router.get("/{analysis_id}/progress")
def get_analysis_progress(analysis_id: str):
    """获取分析进度"""
    if analysis_id not in _analysis_progress:
        raise HTTPException(status_code=404, detail="分析任务不存在")

    progress = _analysis_progress[analysis_id]
    return {
        "analysis_id": analysis_id,
        "step": progress.get("step", 0),
        "status": progress.get("status", "pending"),
        "message": progress.get("message", ""),
        "result_id": progress.get("result_id"),
    }


@router.get("/{analysis_id}/result")
def get_analysis_result(analysis_id: str, db: Session = Depends(get_db)):
    """获取完整分析结果"""
    if analysis_id not in _analysis_progress:
        raise HTTPException(status_code=404, detail="分析任务不存在")

    progress = _analysis_progress[analysis_id]
    if progress.get("status") != "completed":
        raise HTTPException(status_code=400, detail="分析尚未完成")

    result_id = progress.get("result_id")
    if not result_id:
        raise HTTPException(status_code=404, detail="分析结果不存在")

    record = db.query(AnalysisRecord).filter(AnalysisRecord.id == result_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="分析记录不存在")

    return _analysis_to_dict(record, include_sentences=True)


@router.get("/{analysis_id}/sentences", response_model=list[dict])
def get_analysis_sentences(
    analysis_id: str,
    category: str = None,
    needs_review: bool = None,
    db: Session = Depends(get_db),
):
    """获取语句列表"""
    if analysis_id not in _analysis_progress:
        raise HTTPException(status_code=404, detail="分析任务不存在")

    result_id = _analysis_progress[analysis_id].get("result_id")
    if not result_id:
        raise HTTPException(status_code=404, detail="分析结果不存在")

    query = db.query(Sentence).filter(Sentence.analysis_record_id == result_id)
    if category:
        query = query.filter(Sentence.final_category == category)
    if needs_review is not None:
        query = query.filter(Sentence.needs_review == needs_review)

    sentences = query.order_by(Sentence.sentence_order).all()
    return [
        {
            "id": s.id,
            "sentence_text": s.sentence_text,
            "sentence_order": s.sentence_order,
            "deepseek_result": s.deepseek_result,
            "qwen_result": s.qwen_result,
            "glm_result": s.glm_result,
            "final_category": s.final_category,
            "vote_type": s.vote_type,
            "confidence": s.confidence,
            "sentiment_score": s.sentiment_score,
            "needs_review": s.needs_review,
        }
        for s in sentences
    ]


def _analysis_to_dict(record: AnalysisRecord, include_sentences: bool = False) -> dict:
    """将分析记录转为字典"""
    result = {
        "id": record.id,
        "company_id": record.company_id,
        "company_name": record.company.company_name if record.company else "",
        "stock_code": record.company.stock_code if record.company else "",
        "industry": record.company.industry if record.company else "",
        "year": record.year,
        "data_source_type": record.data_source_type,
        "total_sentences": record.total_sentences,
        "env_sentences": record.env_sentences,
        "substantive_count": record.substantive_count,
        "descriptive_count": record.descriptive_count,
        "non_env_count": record.non_env_count,
        "tone_score": record.tone_score,
        "industry_median_tone": record.industry_median_tone,
        "gw_index": record.gw_index,
        "risk_level": record.risk_level,
        "fleiss_kappa": record.fleiss_kappa,
        "dispute_count": record.dispute_count,
        "analysis_status": record.analysis_status,
        "analyzed_at": record.analyzed_at.isoformat() if record.analyzed_at else None,
    }
    if include_sentences:
        result["sentences"] = [
            {
                "id": s.id,
                "sentence_text": s.sentence_text,
                "sentence_order": s.sentence_order,
                "deepseek_result": s.deepseek_result,
                "qwen_result": s.qwen_result,
                "glm_result": s.glm_result,
                "final_category": s.final_category,
                "vote_type": s.vote_type,
                "confidence": s.confidence,
                "sentiment_score": s.sentiment_score,
                "needs_review": s.needs_review,
            }
            for s in sorted(record.sentences, key=lambda x: x.sentence_order or 0)
        ]
    return result


def _run_analysis_flow(analysis_id: str, company: Company, db_session: Session):
    """后台执行分析流程（阶段式进度更新）"""
    from app.core.database import SessionLocal
    from app.services.analysis_orchestrator import AnalysisOrchestrator

    db = SessionLocal()
    try:
        # 阶段1: 读取本地真实MD&A文本
        _analysis_progress[analysis_id].update({"step": 0, "status": "running", "message": "读取企业最新MD&A文本"})
        text = AnalysisOrchestrator._get_local_mda_text(company)
        if not text:
            text = MOCK_REPORT_TEXT

        # 阶段2: 语句切分与过滤
        _analysis_progress[analysis_id].update({"step": 1, "status": "running", "message": "语句切分与环保相关性过滤"})

        # 阶段3: 三模型分类投票
        _analysis_progress[analysis_id].update({"step": 2, "status": "running", "message": "三模型独立分类投票中"})

        result = run_mock_analysis(text, company.industry)

        # 阶段4: 合成指数
        _analysis_progress[analysis_id].update({"step": 3, "status": "running", "message": "语境情感打分 + 行业基准修正"})

        # 保存到数据库
        current_year = datetime.now().year

        # 将该企业旧记录的 is_latest 置为 False
        db.query(AnalysisRecord).filter(
            AnalysisRecord.company_id == company.id,
            AnalysisRecord.is_latest == True,
        ).update({"is_latest": False})

        record = AnalysisRecord(
            company_id=company.id,
            year=current_year,
            data_source_type="MD&A",
            total_sentences=result["total_sentences"],
            env_sentences=result["env_sentences"],
            substantive_count=result["substantive_count"],
            descriptive_count=result["descriptive_count"],
            non_env_count=result["non_env_count"],
            tone_score=result["tone_score"],
            industry_median_tone=result["industry_median_tone"],
            gw_index=result["gw_index"],
            risk_level="正常",
            fleiss_kappa=result["fleiss_kappa"],
            dispute_count=result["dispute_count"],
            analysis_status="completed",
            is_latest=True,
            analyzed_at=datetime.now(),
        )
        db.add(record)
        db.flush()

        # 保存语句记录
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

        # 重新计算行业基准和风险等级
        compute_industry_benchmarks(db, current_year)
        update_risk_levels(db, current_year)

        _analysis_progress[analysis_id].update({
            "step": 4,
            "status": "completed",
            "message": "分析完成",
            "result_id": record.id,
        })

    except Exception as e:
        _analysis_progress[analysis_id].update({
            "status": "failed",
            "message": str(e),
        })
    finally:
        db.close()