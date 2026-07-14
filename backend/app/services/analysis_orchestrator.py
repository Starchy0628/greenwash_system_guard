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
import logging
import time
from typing import AsyncGenerator, Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse
from app.models.company import Company
from app.models.analysis import AnalysisRecord
from app.models.sentence import Sentence
from app.services.mock_service import run_mock_analysis, generate_mock_company_text
from app.services.industry_service import compute_industry_benchmarks, update_risk_levels
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.logging_setup import get_request_id

logger = logging.getLogger(__name__)


class AnalysisOrchestrator:
    """分析流程编排器 — 管理 SSE 事件流推送"""

    @staticmethod
    async def analyze_stream(
        company: Company,
        db: Session,
        force_refresh: bool = False,
    ) -> AsyncGenerator[str, None]:
        """流式推送分析流程（全异步架构）"""
        queue: asyncio.Queue[str] = asyncio.Queue()

        def _push(event_type: str, data: Dict[str, Any]):
            """向队列推送 SSE 事件"""
            msg = f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            queue.put_nowait(msg)

        async def _run_async():
            """异步执行完整分析流程"""
            async_db = SessionLocal()
            try:
                await AnalysisOrchestrator._run_analysis_async(
                    company.id, force_refresh, _push, async_db
                )
            except Exception as e:
                logger.exception(f"分析流程异常: {e}")
                _push("analysis_error", {
                    "phase": "unknown",
                    "message": f"分析异常：{str(e)}",
                    "retryable": False,
                })
                _push("done", {"status": "error"})
            finally:
                async_db.close()
                queue.put_nowait(None)

        task = asyncio.create_task(_run_async())

        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            if not task.done():
                task.cancel()

    @staticmethod
    async def _run_analysis_async(
        company_id: int,
        force_refresh: bool,
        push_fn,
        db: Session,
    ):
        """异步执行完整分析流程"""
        start_time = time.time()
        req_id = get_request_id()

        company = db.query(Company).filter(Company.id == company_id).first()
        if not company:
            logger.error(f"分析失败：未找到企业 company_id={company_id}")
            push_fn("analysis_error", {
                "phase": "not_found",
                "message": "未找到企业信息",
                "retryable": False,
            })
            push_fn("done", {"status": "error"})
            return

        company_name = company.company_name
        stock_code = company.stock_code
        logger.info(
            f"开始分析企业: {company_name} ({stock_code}), force_refresh={force_refresh}",
            extra={"extra_fields": {
                "company_id": company_id,
                "stock_code": stock_code,
                "company_name": company_name,
                "force_refresh": force_refresh,
            }}
        )

        push_fn("status", {
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
            result = AnalysisOrchestrator._build_result_dict(existing, db)
            duration = time.time() - start_time
            logger.info(
                f"分析完成（缓存命中）: {company_name}, 耗时={duration:.2f}s",
                extra={"extra_fields": {
                    "stock_code": stock_code,
                    "cached": True,
                    "duration": round(duration, 3),
                    "gw_index": existing.gw_index,
                }}
            )
            push_fn("result", {
                "cached": True,
                "result": result,
            })
            push_fn("done", {"status": "success"})
            return

        if not company.is_a_share:
            push_fn("analysis_error", {
                "phase": "not_found",
                "message": "该企业不是A股上市公司，无法进行分析",
                "retryable": False,
            })
            push_fn("done", {"status": "error"})
            return

        push_fn("status", {
            "phase": "fetching",
            "message": "正在从巨潮资讯抓取企业最新年报MD&A章节...",
        })

        settings = get_settings()
        text = ""
        data_source = "MD&A"
        fetch_error = None
        key_indicators = []

        if settings.app_mode == "real":
            try:
                from app.services.cninfo_crawler import fetch_report_with_fallback
                from app.services.pdf_parser import parse_report_full, get_analysis_text

                def _fetch_sync():
                    return fetch_report_with_fallback(
                        company.stock_code, stock_name=company.company_name
                    )

                pdf_bytes, error, ann = await asyncio.to_thread(_fetch_sync)
                if pdf_bytes and not error:
                    parsed = await asyncio.to_thread(
                        parse_report_full, pdf_bytes, ann.title if ann else ""
                    )
                    text = get_analysis_text(parsed)
                    data_source = "MD&A"
                    key_indicators = parsed.key_indicators
                else:
                    fetch_error = error or "无法获取年报"
                    push_fn("analysis_error", {
                        "phase": "fetching",
                        "message": f"无法从巨潮资讯获取年报：{fetch_error}。请手动上传 PDF 文件进行分析。",
                        "retryable": True,
                        "fallback": "pdf_upload",
                    })
                    push_fn("done", {"status": "error"})
                    return
            except Exception as e:
                logger.warning(f"获取年报失败，降级到Mock模式: {e}")
                target_gw = existing.gw_index if existing else None
                text = AnalysisOrchestrator._get_mock_text(company, target_gw=target_gw)
                data_source = "MD&A(Mock降级)"
        else:
            target_gw = existing.gw_index if existing else None
            text = AnalysisOrchestrator._get_mock_text(company, target_gw=target_gw)
            data_source = "MD&A"

        if not text or len(text.strip()) < 50:
            push_fn("analysis_error", {
                "phase": "fetching",
                "message": "获取到的报告内容过短，请检查报告完整性或手动上传 PDF。",
                "retryable": True,
                "fallback": "pdf_upload",
            })
            push_fn("done", {"status": "error"})
            return

        push_fn("status", {
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
            push_fn("analysis_error", {
                "phase": "segmenting",
                "message": "未找到任何含环境关键词的语句，请检查报告内容",
                "retryable": True,
            })
            push_fn("done", {"status": "error"})
            return

        push_fn("status", {
            "phase": "classifying",
            "message": f"三模型独立分类投票中... ({total_env} 句环境相关语句)",
            "total": total_env,
            "done": 0,
        })

        if settings.app_mode == "real":
            try:
                result = await AnalysisOrchestrator._run_real_classification_with_progress(
                    env_sentences, company.industry, db, push_fn, total_env
                )
            except Exception as e:
                logger.warning(f"真实LLM分类失败，降级到Mock模式: {e}")
                push_fn("status", {
                    "phase": "classifying",
                    "message": f"真实LLM调用失败，降级到模拟模式...",
                    "total": total_env,
                    "done": 0,
                })
                result = run_mock_analysis(text, company.industry)
        else:
            result = run_mock_analysis(text, company.industry)
            await asyncio.sleep(0.3)

        push_fn("progress", {
            "phase": "classifying",
            "message": f"三模型独立分类投票中... ({total_env}/{total_env} 句)",
            "total": total_env,
            "done": total_env,
        })

        push_fn("status", {
            "phase": "voting",
            "message": "多数投票确权，标记分歧语句...",
        })

        push_fn("status", {
            "phase": "scoring",
            "message": "语境情感打分 + 行业基准修正，合成GW指数...",
        })

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

        duration = time.time() - start_time
        logger.info(
            f"分析完成: {company_name} ({stock_code}), "
            f"GW指数={record.gw_index:.3f}, "
            f"语句数={total_env}, "
            f"耗时={duration:.2f}s",
            extra={"extra_fields": {
                "stock_code": stock_code,
                "company_name": company_name,
                "gw_index": round(record.gw_index, 4),
                "sentence_count": total_env,
                "substantive_count": record.substantive_count,
                "descriptive_count": record.descriptive_count,
                "data_source": data_source,
                "duration": round(duration, 3),
                "risk_level": record.risk_level,
            }}
        )

        push_fn("result", {
            "cached": False,
            "result": final_result,
        })
        push_fn("done", {"status": "success"})

    @staticmethod
    async def _run_real_classification_with_progress(
        sentences: List[str],
        industry: str,
        db: Session,
        push_fn,
        total: int,
    ) -> Dict[str, Any]:
        """真实模式分类 + 实时进度推送"""
        from app.services.llm_client import DEFAULT_LLM_MODELS
        from app.services.classifier import SentenceClassifier
        from app.services.sentiment import SentimentAnalyzer
        from app.services.fusion import MajorityVotingFuser
        from app.services.calculator import GreenwashIndexCalculator
        from app.services.industry_service import get_industry_median

        settings = get_settings()

        api_keys = {
            "deepseek-r1": settings.deepseek_api_key,
            "qwen-max": settings.qwen_api_key,
            "glm-4.7": settings.glm_api_key,
        }

        classifier = SentenceClassifier(
            model_configs=DEFAULT_LLM_MODELS,
            api_keys=api_keys,
            use_mock=False,
        )
        sentiment_analyzer = SentimentAnalyzer(
            model_configs=DEFAULT_LLM_MODELS,
            api_keys=api_keys,
            use_mock=False,
        )

        all_classifications = []
        batch_size = 3
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i:i + batch_size]
            batch_results = await classifier.classify_batch_async(
                batch,
                return_details=True,
                max_concurrency=batch_size,
            )
            all_classifications.extend(batch_results)

            done = min(i + batch_size, total)
            push_fn("progress", {
                "phase": "classifying",
                "message": f"三模型独立分类投票中... ({done}/{total} 句)",
                "total": total,
                "done": done,
            })

        voter = MajorityVotingFuser()
        voted_data_list = []
        for cr in all_classifications:
            fusion = voter.fuse(cr.model_results)
            final_cat = fusion.final_result
            if final_cat == "non_environmental":
                final_cat = "non_env"
            voted_data_list.append({
                "sentence_text": cr.sentence,
                "model_results_list": [
                    cr.model_results.get("deepseek-r1", "descriptive"),
                    cr.model_results.get("qwen-max", "descriptive"),
                    cr.model_results.get("glm-4.7", "descriptive"),
                ],
                "final_category": final_cat,
                "vote_type": "unanimous" if fusion.confidence == 1.0 else "majority" if fusion.confidence >= 0.5 else "full_divergence",
                "confidence": fusion.confidence,
                "needs_review": fusion.is_ambiguous,
            })

        batch_for_kappa = [cr.model_results for cr in all_classifications]
        fleiss_kappa = voter.calculate_overall_kappa(batch_for_kappa)

        descriptive_substantive = [
            r for r in voted_data_list
            if r["final_category"] in ("descriptive", "substantive")
        ]

        sentiment_map = {}
        if descriptive_substantive:
            texts_for_sentiment = [r["sentence_text"] for r in descriptive_substantive]
            sentiment_results = await sentiment_analyzer.analyze_batch_async(
                texts_for_sentiment,
                return_details=True,
                max_concurrency=3,
            )
            for sr in sentiment_results:
                sentiment_map[sr.sentence] = {
                    "avg_score": sr.final_score,
                    "std": sr.score_std,
                }

        for r in voted_data_list:
            if r["sentence_text"] in sentiment_map:
                r["sentiment_score"] = sentiment_map[r["sentence_text"]]["avg_score"]
                r["sentiment_std"] = sentiment_map[r["sentence_text"]]["std"]
            else:
                r["sentiment_score"] = 0.0
                r["sentiment_std"] = 0.0

        substantive_count = sum(1 for r in voted_data_list if r["final_category"] == "substantive")
        descriptive_count = sum(1 for r in voted_data_list if r["final_category"] == "descriptive")
        non_env_count = sum(1 for r in voted_data_list if r["final_category"] == "non_env")
        divergence_count = sum(1 for r in voted_data_list if r["needs_review"])

        descriptive_results = [r for r in voted_data_list if r["final_category"] == "descriptive"]
        if descriptive_results:
            tone_score = sum(r["sentiment_score"] for r in descriptive_results) / len(descriptive_results)
        else:
            tone_score = 0.0

        current_year = datetime.now().year
        industry_median = get_industry_median(db, industry, current_year)

        calc = GreenwashIndexCalculator()
        gw_index = calc.calculate_greenwash_index(tone_score, industry_median)

        sentence_results = []
        for idx, r in enumerate(voted_data_list):
            sentence_results.append({
                "sentence_text": r["sentence_text"],
                "sentence_order": idx + 1,
                "deepseek_result": r["model_results_list"][0],
                "qwen_result": r["model_results_list"][1],
                "glm_result": r["model_results_list"][2],
                "final_category": r["final_category"],
                "vote_type": r["vote_type"],
                "confidence": r["confidence"],
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
    def _get_mock_text(company: Company = None, target_gw: float = None) -> str:
        """获取模拟文本（企业特定，确保与种子数据一致）"""
        if company:
            return generate_mock_company_text(
                company.company_name, 
                company.industry,
                seed=hash(company.stock_code + str(2025)) % 100000,
                target_gw=target_gw
            )
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
        from app.services.llm_client import DEFAULT_LLM_MODELS
        from app.services.classifier import SentenceClassifier
        from app.services.sentiment import SentimentAnalyzer
        from app.services.fusion import MajorityVotingFuser
        from app.services.calculator import GreenwashIndexCalculator
        from app.services.industry_service import get_industry_median

        settings = get_settings()

        api_keys = {
            "deepseek-r1": settings.deepseek_api_key,
            "qwen-max": settings.qwen_api_key,
            "glm-4.7": settings.glm_api_key,
        }

        classifier = SentenceClassifier(
            model_configs=DEFAULT_LLM_MODELS,
            api_keys=api_keys,
            use_mock=False,
        )
        sentiment_analyzer = SentimentAnalyzer(
            model_configs=DEFAULT_LLM_MODELS,
            api_keys=api_keys,
            use_mock=False,
        )

        # 逐句分类（分批异步并行，每批3句并发，每句内三模型并行）
        all_classifications = []
        batch_size = 3
        for i in range(0, len(sentences), batch_size):
            batch = sentences[i:i + batch_size]
            batch_results = await classifier.classify_batch_async(
                batch,
                return_details=True,
                max_concurrency=batch_size,
            )
            all_classifications.extend(batch_results)
            await asyncio.sleep(0.1)

        # 多数投票确权（使用 MajorityVotingFuser）
        voter = MajorityVotingFuser()
        voted_data_list = []
        for cr in all_classifications:
            fusion = voter.fuse(cr.model_results)
            voted_data_list.append({
                "sentence_text": cr.sentence,
                "model_results_list": [
                    cr.model_results.get("deepseek-r1", "descriptive"),
                    cr.model_results.get("qwen-max", "descriptive"),
                    cr.model_results.get("glm-4.7", "descriptive"),
                ],
                "final_category": fusion.final_result,
                "vote_type": "unanimous" if fusion.confidence == 1.0 else "majority" if fusion.confidence >= 0.5 else "full_divergence",
                "confidence": fusion.confidence,
                "needs_review": fusion.is_ambiguous,
            })

        # 计算整体 Fleiss' Kappa
        batch_for_kappa = [cr.model_results for cr in all_classifications]
        fleiss_kappa = voter.calculate_overall_kappa(batch_for_kappa)

        # 对描述性和实质性语句做情感打分
        descriptive_substantive = [
            r for r in voted_data_list
            if r["final_category"] in ("descriptive", "substantive")
        ]

        sentiment_map = {}
        if descriptive_substantive:
            texts_for_sentiment = [r["sentence_text"] for r in descriptive_substantive]
            sentiment_results = await sentiment_analyzer.analyze_batch_async(
                texts_for_sentiment,
                return_details=True,
                max_concurrency=3,
            )
            for sr in sentiment_results:
                sentiment_map[sr.sentence] = {
                    "avg_score": sr.final_score,
                    "std": sr.score_std,
                }

        for r in voted_data_list:
            if r["sentence_text"] in sentiment_map:
                r["sentiment_score"] = sentiment_map[r["sentence_text"]]["avg_score"]
                r["sentiment_std"] = sentiment_map[r["sentence_text"]]["std"]
            else:
                r["sentiment_score"] = 0.0
                r["sentiment_std"] = 0.0

        # 统计数量
        substantive_count = sum(1 for r in voted_data_list if r["final_category"] == "substantive")
        descriptive_count = sum(1 for r in voted_data_list if r["final_category"] == "descriptive")
        non_env_count = sum(1 for r in voted_data_list if r["final_category"] == "non_environmental")
        divergence_count = sum(1 for r in voted_data_list if r["needs_review"])

        # 计算语调分数（描述性语句的平均情感分）
        descriptive_results = [r for r in voted_data_list if r["final_category"] == "descriptive"]
        if descriptive_results:
            tone_score = sum(r["sentiment_score"] for r in descriptive_results) / len(descriptive_results)
        else:
            tone_score = 0.0

        # 获取行业中位数
        current_year = datetime.now().year
        industry_median = get_industry_median(db, industry, current_year)

        # 计算 GW 指数
        calc = GreenwashIndexCalculator()
        gw_index = calc.calculate_greenwash_index(tone_score, industry_median)

        # 构造 sentence_results
        sentence_results = []
        for idx, r in enumerate(voted_data_list):
            sentence_results.append({
                "sentence_text": r["sentence_text"],
                "sentence_order": idx,
                "deepseek_result": r["model_results_list"][0],
                "qwen_result": r["model_results_list"][1],
                "glm_result": r["model_results_list"][2],
                "final_category": r["final_category"],
                "vote_type": r["vote_type"],
                "confidence": r["confidence"],
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
        from app.models.industry import IndustryBenchmark
        from datetime import datetime

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

        # 获取行业年度样本量
        current_year = record.year or datetime.now().year
        industry = record.company.industry if record.company else ""
        industry_benchmark = (
            db.query(IndustryBenchmark)
            .filter(
                IndustryBenchmark.industry == industry,
                IndustryBenchmark.year == current_year,
            )
            .first()
        )
        industry_sample_count = industry_benchmark.sample_count if industry_benchmark else 0
        industry_used_seed = industry_benchmark.used_seed_data if industry_benchmark else False

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
            "industry_sample_count": industry_sample_count,
            "industry_used_seed_data": bool(industry_used_seed),
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
        confirmed = [
            s for s in result["sentences"]
            if not s["needs_review"] and s["final_category"] == "substantive"
        ]
        disputed = [s for s in result["sentences"] if s["needs_review"]]
        # 环境语句：所有非 non_env 的语句（实质性 + 描述性 + 分歧）
        env_all = [s for s in result["sentences"] if s["final_category"] != "non_env"]
        result["confirmed_sentences"] = confirmed
        result["dispute_sentences"] = disputed
        result["env_sentences_list"] = env_all

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
