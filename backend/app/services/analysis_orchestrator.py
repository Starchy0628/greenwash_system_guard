"""
分析流程编排器 — 编排完整分析流程，通过 SSE 推送阶段性状态

流程:
1. 查询数据库 → 已有记录 → 直接返回完整结果
2. 抓取披露文本 → 推送阶段状态
3. 语句切分与环保相关性过滤 → 推送阶段状态
4. 三模型分类 → 推送进度百分比
5. 多数投票确权 → 推送阶段状态
6. 语境情感打分 → 推送阶段状态
7. GW 指数合成 + 行业基准修正 → 推送阶段状态
8. 保存数据库 → 推送最终结果
"""
import json
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from fastapi.responses import StreamingResponse
from app.models.company import Company
from app.models.analysis import AnalysisRecord
from app.models.sentence import Sentence
from app.services.mock_service import run_mock_analysis
from app.services.industry_service import compute_industry_benchmarks, update_risk_levels


class AnalysisOrchestrator:
    """分析流程编排器 — 管理 SSE 事件流推送"""

    @staticmethod
    async def analyze_stream(
        company: Company,
        db: Session,
        force_refresh: bool = False,
    ) -> AsyncGenerator[str, None]:
        """流式推送分析流程"""

        # 阶段 0: 检查已有记录
        yield sse("status", {
            "phase": "checking",
            "message": "正在查询数据库...",
        })

        existing = (
            db.query(AnalysisRecord)
            .filter(
                AnalysisRecord.company_id == company.id,
                AnalysisRecord.is_latest == True,
            )
            .first()
        )

        if existing and not force_refresh:
            # 直接返回缓存结果
            result = AnalysisOrchestrator._build_result_dict(existing, db)
            yield sse("result", {
                "cached": True,
                "result": result,
            })
            return

        # 不是 A 股企业，直接返回错误
        if not company.is_a_share:
            yield sse("analysis_error", {
                "phase": "not_found",
                "message": "该企业不是A股上市公司，无法进行分析",
                "retryable": False,
            })
            return

        # 阶段 1: 抓取文本
        yield sse("status", {
            "phase": "fetching",
            "message": "正在抓取企业最新披露文本（ESG报告优先，就高原则）...",
        })

        text = AnalysisOrchestrator._get_mock_text()

        # 阶段 2: 语句切分和过滤
        yield sse("status", {
            "phase": "segmenting",
            "message": "语句切分与环保相关性过滤...",
        })

        from app.services.text_utils import split_sentences, filter_env_sentences
        raw_sentences = split_sentences(text)
        if not raw_sentences:
            raw_sentences = [text]
        env_sentences, _ = filter_env_sentences(raw_sentences)

        total_env = len(env_sentences)
        if total_env == 0:
            yield sse("analysis_error", {
                "phase": "segmenting",
                "message": "未找到任何含环境关键词的语句，请检查报告内容",
                "retryable": True,
            })
            return

        # 阶段 3: 三模型分类
        yield sse("status", {
            "phase": "classifying",
            "message": f"三模型独立分类投票中... ({total_env} 句环境相关语句)",
            "total": total_env,
            "done": 0,
        })

        result = run_mock_analysis(text, company.industry)

        yield sse("progress", {
            "phase": "classifying",
            "message": f"三模型独立分类投票中... ({total_env}/{total_env} 句)",
            "total": total_env,
            "done": total_env,
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

        # 保存到数据库
        current_year = datetime.now().year

        db.query(AnalysisRecord).filter(
            AnalysisRecord.company_id == company.id,
            AnalysisRecord.is_latest == True,
        ).update({"is_latest": False})

        record = AnalysisRecord(
            company_id=company.id,
            year=current_year,
            data_source_type="ESG",
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
                pangu_result=s["pangu_result"],
                final_category=s["final_category"],
                vote_type=s["vote_type"],
                confidence=s["confidence"],
                sentiment_score=s["sentiment_score"],
                sentiment_std=s["sentiment_std"],
                needs_review=s["needs_review"],
            )
            db.add(sentence)

        db.commit()

        compute_industry_benchmarks(db, current_year)
        update_risk_levels(db, current_year)
        db.commit()

        db.refresh(record)

        final_result = AnalysisOrchestrator._build_result_dict(record, db)
        yield sse("result", {
            "cached": False,
            "result": final_result,
        })

    @staticmethod
    def _get_mock_text() -> str:
        """获取模拟文本"""
        return """公司本年度环保投入达到5000万元，同比增长15%。通过ISO14001环境管理体系认证，
二氧化硫排放量减少15%，达到行业领先水平。公司高度重视环境保护工作，积极履行企业社会责任。
我们持续推动绿色低碳转型，实现可持续发展。报告期内单位产值能耗同比下降4.2%。
公司致力于打造绿色工厂，践行生态文明理念。积极推进环境治理工作，提升绿色发展水平。
公司全年实现营业收入稳步增长，净利润同比增长。董事会审议通过了年度利润分配方案。
坚持绿色发展理念，为美丽中国贡献力量。公司持续加大研发投入，提升核心竞争力。
清洁能源使用比例提升至12%，碳排放强度降低8.5%。报告期内投入3000万元用于污染防治设施建设。
公司治理结构持续优化，内部控制体系不断完善。积极参与公益环保活动。"""

    @staticmethod
    def _build_result_dict(record: AnalysisRecord, db: Session) -> Dict[str, Any]:
        """构建完整结果字典"""
        from app.models.sentence import Sentence

        # 获取企业趋势
        trend = (
            db.query(AnalysisRecord)
            .filter(
                AnalysisRecord.company_id == record.company_id,
                AnalysisRecord.analysis_status == "completed",
                AnalysisRecord.gw_index.isnot(None),
            )
            .order_by(AnalysisRecord.year.desc())
            .limit(5)
            .all()
        )

        # 获取所有语句
        sentences = (
            db.query(Sentence)
            .filter(Sentence.analysis_record_id == record.id)
            .order_by(Sentence.sentence_order)
            .all()
        )

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
            "trend": _build_trend_list(trend),
            "sentences": [
                {
                    "id": s.id,
                    "sentence_text": s.sentence_text,
                    "sentence_order": s.sentence_order,
                    "deepseek_result": s.deepseek_result,
                    "qwen_result": s.qwen_result,
                    "pangu_result": s.pangu_result,
                    "final_category": s.final_category,
                    "vote_type": s.vote_type,
                    "confidence": s.confidence,
                    "sentiment_score": s.sentiment_score,
                    "needs_review": s.needs_review,
                }
                for s in sentences
            ],
        }

        # 分离已确权和待复核语句
        # 已确权：仅包含 final_category == "substantive" 且 needs_review == False
        # 待复核：所有 needs_review == True（不考虑其分类结果）
        # descriptive 和 non_environmental 不在任何清单中展示
        confirmed = [
            s for s in result["sentences"]
            if not s["needs_review"] and s["final_category"] == "substantive"
        ]
        disputed = [s for s in result["sentences"] if s["needs_review"]]
        result["confirmed_sentences"] = confirmed
        result["dispute_sentences"] = disputed

        return result


def sse(event_type: str, data: Dict[str, Any]) -> str:
    """生成 SSE 事件格式（纯文本，调用方 yield）"""
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_trend_list(trend):
    """构建趋势列表（按年份升序，取最近5年）"""
    records = list(trend)
    records.reverse()
    records = records[:5]
    return [
        {
            "year": r.year,
            "gw_index": r.gw_index,
            "tone_score": r.tone_score,
            "risk_level": r.risk_level,
        }
        for r in records
    ]