"""
PDF 上传分析 API — 接收 PDF 文件，解析文本，执行分析，SSE 流式返回结果
"""
import json
import asyncio
from datetime import datetime
from typing import AsyncGenerator
from fastapi import APIRouter, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import get_settings
from app.services.pdf_parser import parse_report_full, get_analysis_text
from app.services.text_utils import split_sentences, filter_env_sentences
from app.services.mock_service import run_mock_analysis
from app.services.industry_service import compute_industry_benchmarks, update_risk_levels
from app.models.company import Company
from app.models.analysis import AnalysisRecord
from app.models.sentence import Sentence

router = APIRouter(prefix="/api/pdf", tags=["pdf_analysis"])


@router.post("/analyze")
async def analyze_pdf(
    file: UploadFile = File(...),
    force_refresh: bool = Form(False),
    db: Session = Depends(get_db),
):
    """上传 PDF 并执行分析（SSE 流式返回）"""
    return StreamingResponse(
        _analyze_pdf_stream(file, force_refresh, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _analyze_pdf_stream(
    file: UploadFile,
    force_refresh: bool,
    db: Session,
) -> AsyncGenerator[str, None]:
    """PDF 分析 SSE 流"""

    # 阶段 0: 校验文件
    yield sse("status", {"phase": "uploading", "message": "正在接收文件..."})

    if not file.filename or not file.filename.lower().endswith('.pdf'):
        yield sse("analysis_error", {
            "phase": "upload",
            "message": "仅支持 PDF 格式文件，请上传 .pdf 文件",
            "retryable": False,
        })
        yield sse("done", {"status": "error"})
        return

    # 读取文件内容
    try:
        file_bytes = await file.read()
    except Exception as e:
        yield sse("analysis_error", {
            "phase": "upload",
            "message": f"文件读取失败：{str(e)}",
            "retryable": False,
        })
        yield sse("done", {"status": "error"})
        return

    if len(file_bytes) > 50 * 1024 * 1024:  # 50MB 限制
        yield sse("analysis_error", {
            "phase": "upload",
            "message": "文件过大（超过50MB），请压缩后重试",
            "retryable": False,
        })
        yield sse("done", {"status": "error"})
        return

    if len(file_bytes) < 100:
        yield sse("analysis_error", {
            "phase": "upload",
            "message": "文件内容为空或过小，请检查文件",
            "retryable": False,
        })
        yield sse("done", {"status": "error"})
        return

    # 阶段 1: 解析 PDF
    yield sse("status", {
        "phase": "parsing",
        "message": "正在解析 PDF 文件，提取文本内容...",
    })

    parsed = parse_report_full(file_bytes, file.filename)
    if not parsed.full_text:
        yield sse("analysis_error", {
            "phase": "parsing",
            "message": "PDF 解析失败，无法提取文本内容。请确认文件为文本型 PDF（非扫描图片）。",
            "retryable": False,
        })
        yield sse("done", {"status": "error"})
        return

    text = get_analysis_text(parsed)
    report_type = parsed.report_type
    company_name = parsed.company_name
    key_indicators = parsed.key_indicators

    yield sse("status", {
        "phase": "parsed",
        "message": f"PDF 解析完成，识别为 {report_type} 报告"
        + (f"，企业：{company_name}" if company_name else ""),
        "report_type": report_type,
        "company_name": company_name,
        "text_length": len(text),
    })

    # 阶段 2: 语句切分与过滤
    yield sse("status", {
        "phase": "segmenting",
        "message": "语句切分与环保相关性过滤...",
    })

    raw_sentences = split_sentences(text)
    if not raw_sentences:
        raw_sentences = [text]
    env_sentences, _ = filter_env_sentences(raw_sentences)

    total = len(env_sentences)
    if total == 0:
        yield sse("analysis_error", {
            "phase": "segmenting",
            "message": "未找到任何含环境关键词的语句，请确认报告内容包含环境相关信息",
            "retryable": True,
        })
        yield sse("done", {"status": "error"})
        return

    total_sentences = len(raw_sentences)

    # 阶段 3: 三模型分类
    yield sse("status", {
        "phase": "classifying",
        "message": f"三模型独立分类投票中... ({total} 句环境相关语句)",
        "total": total,
        "done": 0,
    })

    # PDF 上传时无法自动确定行业，默认为综合
    industry = "综合"
    settings = get_settings()

    if settings.app_mode == "real":
        # 真实模式
        from app.services.analysis_orchestrator import AnalysisOrchestrator
        result = await AnalysisOrchestrator._run_real_classification(
            env_sentences, industry, db
        )
    else:
        # Mock 模式
        result = run_mock_analysis(text, industry)

    yield sse("progress", {
        "phase": "classifying",
        "message": f"三模型独立分类投票中... ({total}/{total} 句)",
        "total": total,
        "done": total,
    })

    # 阶段 4: 多数投票确权
    yield sse("status", {
        "phase": "voting",
        "message": "多数投票确权，标记分歧语句...",
    })

    # 阶段 5: 情感打分 + GW指数合成
    yield sse("status", {
        "phase": "scoring",
        "message": "语境情感打分 + 行业基准修正，合成GW指数...",
    })

    # 尝试查找或创建企业记录
    company = None
    if company_name:
        company = (
            db.query(Company)
            .filter(
                (Company.company_name == company_name)
                | (Company.short_name == company_name)
                | (Company.company_name.contains(company_name))
            )
            .first()
        )

    if not company:
        # 创建临时企业记录
        company = Company(
            stock_code=f"PDF_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            company_name=company_name or f"PDF上传企业_{file.filename[:10]}",
            industry=industry,
            short_name=company_name,
            is_a_share=False,
            is_active=True,
        )
        db.add(company)
        db.flush()

    # 保存分析记录
    current_year = datetime.now().year

    db.query(AnalysisRecord).filter(
        AnalysisRecord.company_id == company.id,
        AnalysisRecord.is_latest == True,
    ).update({"is_latest": False})

    record = AnalysisRecord(
        company_id=company.id,
        year=current_year,
        data_source_type="MD&A",
        source_file_name=file.filename,
        total_sentences=total_sentences,
        env_sentences=total,
        substantive_count=result["substantive_count"],
        descriptive_count=result["descriptive_count"],
        non_env_count=result["non_env_count"],
        tone_score=result["tone_score"],
        industry_median_tone=result["industry_median_tone"],
        gw_index=result["gw_index"],
        risk_level="正常",
        fleiss_kappa=result["fleiss_kappa"],
        dispute_count=result["divergence_count"],
        analysis_status="completed",
        is_latest=True,
        analyzed_at=datetime.now(),
    )
    db.add(record)
    db.flush()

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

    # 构建返回结果
    final_result = {
        "id": record.id,
        "company_id": company.id,
        "company_name": company.company_name,
        "stock_code": company.stock_code,
        "industry": company.industry,
        "year": record.year,
        "data_source_type": record.data_source_type,
        "source_file_name": record.source_file_name,
        "total_sentences": total_sentences,
        "env_sentences": total,
        "substantive_count": result["substantive_count"],
        "descriptive_count": result["descriptive_count"],
        "non_env_count": result["non_env_count"],
        "tone_score": result["tone_score"],
        "industry_median_tone": result["industry_median_tone"],
        "gw_index": result["gw_index"],
        "risk_level": "正常",
        "fleiss_kappa": result["fleiss_kappa"],
        "dispute_count": result["divergence_count"],
        "analysis_status": "completed",
        "analyzed_at": record.analyzed_at.isoformat() if record.analyzed_at else None,
        "trend": [],
        "sentences": [
            {
                "id": i,
                "sentence_text": s["sentence_text"],
                "sentence_order": s["sentence_order"],
                "deepseek_result": s["deepseek_result"],
                "qwen_result": s["qwen_result"],
                "glm_result": s["glm_result"],
                "final_category": s["final_category"],
                "vote_type": s["vote_type"],
                "confidence": s["confidence"],
                "sentiment_score": s["sentiment_score"],
                "needs_review": s["needs_review"],
            }
            for i, s in enumerate(result["sentence_results"])
        ],
    }

    # 分离已确权和待复核
    # 已确权：仅包含 final_category == "substantive" 且 needs_review == False
    # 待复核：所有 needs_review == True（不考虑其分类结果）
    # descriptive 和 non_environmental 不在任何清单中展示
    confirmed = [
        s for s in final_result["sentences"]
        if not s["needs_review"] and s["final_category"] == "substantive"
    ]
    disputed = [s for s in final_result["sentences"] if s["needs_review"]]
    final_result["confirmed_sentences"] = confirmed
    final_result["dispute_sentences"] = disputed
    final_result["key_indicators"] = key_indicators

    yield sse("result", {
        "cached": False,
        "result": final_result,
    })

    yield sse("done", {"status": "success"})


def sse(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"