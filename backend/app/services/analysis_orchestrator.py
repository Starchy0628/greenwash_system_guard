"""
分析流程编排器 — 编排完整分析流程，通过 SSE 推送阶段性状态

流程:
1. 查询数据库 → 已有记录 → 直接返回完整结果
2. 抓取披露文本（巨潮资讯爬虫 → 失败降级提示上传 PDF）
3. 语句切分与环保相关性过滤
4. 三模型分类（真实 LLM → 失败降级 Mock）
5. 多数投票确权
6. 语境情感打分
7. GW 指数合成 + 行业基准修正
8. 保存数据库 → 返回结果
"""
import json
import asyncio
from typing import AsyncGenerator, Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
from fastapi.responses import StreamingResponse
from app.models.company import Company
from app.models.analysis import AnalysisRecord
from app.models.sentence import Sentence
from app.services.mock_service import run_mock_analysis
from app.services.industry_service import compute_industry_benchmarks, update_risk_levels
from app.core.config import get_settings


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
            "message": "正在从巨潮资讯抓取企业最新披露文本（ESG报告优先，就高原则）...",
        })

        settings = get_settings()
        text = ""
        data_source = "ESG"
        fetch_error = None
        key_indicators = []

        if settings.app_mode == "real":
            # 真实模式：尝试巨潮资讯爬虫
            try:
                from app.services.cninfo_crawler import fetch_report_with_fallback
                from app.services.pdf_parser import parse_report_full, get_analysis_text

                pdf_bytes, error, ann = fetch_report_with_fallback(company.stock_code)
                if pdf_bytes and not error:
                    parsed = parse_report_full(pdf_bytes, ann.title if ann else "")
                    text = get_analysis_text(parsed)
                    data_source = parsed.report_type or "ESG"
                    key_indicators = parsed.key_indicators
                else:
                    fetch_error = error or "无法获取年报"
                    yield sse("analysis_error", {
                        "phase": "fetching",
                        "message": f"无法从巨潮资讯获取年报：{fetch_error}。请手动上传 PDF 文件进行分析。",
                        "retryable": True,
                        "fallback": "pdf_upload",
                    })
                    return
            except Exception as e:
                fetch_error = str(e)
                yield sse("analysis_error", {
                    "phase": "fetching",
                    "message": f"获取年报失败：{fetch_error}。请手动上传 PDF 文件进行分析。",
                    "retryable": True,
                    "fallback": "pdf_upload",
                })
                return
        else:
            # Mock 模式
            text = AnalysisOrchestrator._get_mock_text()
            data_source = "ESG"

        if not text or len(text.strip()) < 50:
            yield sse("analysis_error", {
                "phase": "fetching",
                "message": "获取到的报告内容过短，请检查报告完整性或手动上传 PDF。",
                "retryable": True,
                "fallback": "pdf_upload",
            })
            return

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

        if settings.app_mode == "real":
            # 真实模式：调用三模型 LLM API
            result = await AnalysisOrchestrator._run_real_classification(
                env_sentences, company.industry, db
            )
        else:
            # Mock 模式
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
            data_source_type=data_source,
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

        compute_industry_benchmarks(db, current_year)
        update_risk_levels(db, current_year)
        db.commit()

        db.refresh(record)

        final_result = AnalysisOrchestrator._build_result_dict(record, db)
        final_result["key_indicators"] = key_indicators
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
    async def _run_real_classification(
        sentences: List[str],
        industry: str,
        db: Session,
    ) -> Dict[str, Any]:
        """
        真实模式：调用三个 LLM 模型进行分类和情感打分

        Returns:
            与 mock_service 返回结构一致的字典
        """
        from app.services.llm_client import (
            DEFAULT_LLM_MODELS,
            create_llm_client,
        )
        from app.services.classifier import SentenceClassifier
        from app.services.sentiment import SentimentAnalyzer
        from app.services.fusion import majority_vote, compute_fleiss_kappa
        from app.services.calculator import calculate_greenwash_index
        from app.services.industry_service import get_industry_median

        settings = get_settings()

        # 构建 API Key 字典
        api_keys = {
            "deepseek-r1": settings.deepseek_api_key,
            "qwen-max": settings.qwen_api_key,
            "glm-ocr": settings.glm_api_key,
        }

        # 构建 fallback model 字典
        fallback_models = {
            "glm-ocr": settings.glm_fallback_model,
        }

        # 创建三个 LLM 客户端
        clients = []
        for model_config in DEFAULT_LLM_MODELS:
            client = create_llm_client(
                model_config,
                api_keys=api_keys,
                use_mock=False,
                fallback_model_ids=fallback_models,
            )
            clients.append(client)

        # 创建分类器和情感分析器
        classifier = SentenceClassifier(clients)
        sentiment_analyzer = SentimentAnalyzer(clients)

        # 逐句分类（分批处理，避免单次调用太长）
        all_classifications = []
        batch_size = 10
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i:i + batch_size]
            batch_results = classifier.classify_batch(batch)
            all_classifications.extend(batch_results)
            await asyncio.sleep(0.1)

        # 多数投票确权
        voted_results = majority_vote(all_classifications)

        # 计算 Fleiss' Kappa
        fleiss_kappa = compute_fleiss_kappa(all_classifications)

        # 对描述性和实质性语句做情感打分
        descriptive_substantive = [
            r for r in voted_results
            if r["final_category"] in ("descriptive", "substantive")
        ]

        if descriptive_substantive:
            texts_for_sentiment = [r["sentence_text"] for r in descriptive_substantive]
            sentiment_results = sentiment_analyzer.analyze_batch(texts_for_sentiment)

            # 把情感分数回填
            sentiment_map = {s["sentence_text"]: s for s in sentiment_results}
            for r in voted_results:
                if r["sentence_text"] in sentiment_map:
                    r["sentiment_score"] = sentiment_map[r["sentence_text"]]["avg_score"]
                    r["sentiment_std"] = sentiment_map[r["sentence_text"]].get("std", 0.0)
                else:
                    r["sentiment_score"] = 0.5
                    r["sentiment_std"] = 0.0
        else:
            for r in voted_results:
                r["sentiment_score"] = 0.5
                r["sentiment_std"] = 0.0

        # 统计数量
        substantive_count = sum(1 for r in voted_results if r["final_category"] == "substantive")
        descriptive_count = sum(1 for r in voted_results if r["final_category"] == "descriptive")
        non_env_count = sum(1 for r in voted_results if r["final_category"] == "non_environmental")
        divergence_count = sum(1 for r in voted_results if r["needs_review"])

        # 计算语调分数（描述性语句的平均情感分）
        descriptive_results = [r for r in voted_results if r["final_category"] == "descriptive"]
        if descriptive_results:
            tone_score = sum(r["sentiment_score"] for r in descriptive_results) / len(descriptive_results)
        else:
            tone_score = 0.5

        # 获取行业中位数
        current_year = datetime.now().year
        industry_median = get_industry_median(db, industry, current_year)

        # 计算 GW 指数
        gw_index = calculate_greenwash_index(tone_score, industry_median)

        # 构造 sentence_results
        sentence_results = []
        for idx, r in enumerate(voted_results):
            sentence_results.append({
                "sentence_text": r["sentence_text"],
                "sentence_order": idx,
                "deepseek_result": r["model_results"][0] if len(r["model_results"]) > 0 else "non_environmental",
                "qwen_result": r["model_results"][1] if len(r["model_results"]) > 1 else "non_environmental",
                "glm_result": r["model_results"][2] if len(r["model_results"]) > 2 else "non_environmental",
                "final_category": r["final_category"],
                "vote_type": r.get("vote_type", "unanimous"),
                "confidence": r.get("confidence", 1.0),
                "sentiment_score": r["sentiment_score"],
                "sentiment_std": r["sentiment_std"],
                "needs_review": r["needs_review"],
            })

        return {
            "total_sentences": len(sentence_results),
            "env_sentences": len(sentence_results),
            "substantive_count": substantive_count,
            "descriptive_count": descriptive_count,
            "non_env_count": non_env_count,
            "tone_score": round(tone_score, 6),
            "industry_median_tone": round(industry_median, 6),
            "gw_index": round(gw_index, 6),
            "fleiss_kappa": round(fleiss_kappa, 4),
            "divergence_count": divergence_count,
            "sentence_results": sentence_results,
        }

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
                    "glm_result": s.glm_result,
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