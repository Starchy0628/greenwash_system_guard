"""
语境感知情感计算模块
基于句内语义依存的情感评分，输出[-1,1]区间连续值
"""
import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from app.services.llm_client import (
    BaseLLMClient,
    LLMResponse,
    create_llm_client,
    DEFAULT_LLM_MODELS,
    SENTIMENT_PROMPT,
)


@dataclass
class SentimentResult:
    """单语句情感分析结果"""
    sentence: str
    model_scores: Dict[str, float] = field(default_factory=dict)
    final_score: float = 0.0
    score_std: float = 0.0
    agreement_level: str = ""
    model_responses: Dict[str, LLMResponse] = field(default_factory=dict)


class SentimentAnalyzer:
    """情感分析器 — 三模型独立打分 + 集成平均"""

    def __init__(
        self,
        model_configs: List[Dict] = None,
        api_keys: Dict = None,
        use_mock: bool = True,
    ):
        self.model_configs = model_configs or DEFAULT_LLM_MODELS
        self.clients: Dict[str, BaseLLMClient] = {}
        self.use_mock = use_mock

        for config in self.model_configs:
            if use_mock:
                config = dict(config)
                config["client_type"] = "mock"
            client = create_llm_client(config, api_keys, use_mock=use_mock)
            self.clients[config["name"]] = client

    def analyze_single(
        self, sentence: str, return_details: bool = False
    ) -> SentimentResult:
        """对单条语句进行情感分析（同步串行）"""
        result = SentimentResult(sentence=sentence)

        for model_name, client in self.clients.items():
            try:
                prompt = SENTIMENT_PROMPT.format(sentence=sentence)
                response = client.call(prompt)

                if response.success:
                    score = client._parse_sentiment(response.raw_response)
                    result.model_scores[model_name] = score
                    response.parsed_result = score
                else:
                    result.model_scores[model_name] = 0.0

                if return_details:
                    result.model_responses[model_name] = response

            except Exception:
                result.model_scores[model_name] = 0.0

        self._calculate_final_score(result)
        return result

    async def analyze_single_async(
        self, sentence: str, return_details: bool = False
    ) -> SentimentResult:
        """对单条语句进行情感分析（三模型并行调用）"""
        result = SentimentResult(sentence=sentence)
        prompt = SENTIMENT_PROMPT.format(sentence=sentence)

        async def _call_model(model_name: str, client: BaseLLMClient):
            try:
                response = await asyncio.to_thread(client.call, prompt)
                if response.success:
                    score = client._parse_sentiment(response.raw_response)
                    response.parsed_result = score
                    return model_name, score, response if return_details else None
                else:
                    return model_name, 0.0, None
            except Exception:
                return model_name, 0.0, None

        tasks = [
            _call_model(name, client)
            for name, client in self.clients.items()
        ]
        results = await asyncio.gather(*tasks)

        for model_name, score, response in results:
            result.model_scores[model_name] = score
            if return_details and response:
                result.model_responses[model_name] = response

        self._calculate_final_score(result)
        return result

    def analyze_batch(
        self, sentences: List[str], return_details: bool = False
    ) -> List[SentimentResult]:
        """批量情感分析（同步串行）"""
        results = []
        for sent in sentences:
            result = self.analyze_single(sent, return_details=return_details)
            results.append(result)
        return results

    async def analyze_batch_async(
        self, sentences: List[str], return_details: bool = False, max_concurrency: int = 3
    ) -> List[SentimentResult]:
        """批量情感分析（异步并发，控制并发度）"""
        semaphore = asyncio.Semaphore(max_concurrency)

        async def _analyze_one(sent: str):
            async with semaphore:
                return await self.analyze_single_async(sent, return_details=return_details)

        tasks = [_analyze_one(sent) for sent in sentences]
        results = await asyncio.gather(*tasks)
        return list(results)

    def _calculate_final_score(self, result: SentimentResult):
        """集成平均法计算最终评分"""
        scores = list(result.model_scores.values())
        if not scores:
            result.final_score = 0.0
            result.score_std = 0.0
            result.agreement_level = "unknown"
            return

        result.final_score = sum(scores) / len(scores)

        if len(scores) > 1:
            mean = result.final_score
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            result.score_std = variance ** 0.5
        else:
            result.score_std = 0.0

        if result.score_std < 0.1:
            result.agreement_level = "high"
        elif result.score_std < 0.3:
            result.agreement_level = "medium"
        else:
            result.agreement_level = "low"

    def get_stats(self, results: List[SentimentResult]) -> Dict:
        """统计情感分析结果"""
        if not results:
            return {}
        scores = [r.final_score for r in results]
        return {
            "total": len(results),
            "mean_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "high_agreement": sum(1 for r in results if r.agreement_level == "high"),
            "medium_agreement": sum(1 for r in results if r.agreement_level == "medium"),
            "low_agreement": sum(1 for r in results if r.agreement_level == "low"),
            "positive_ratio": sum(1 for s in scores if s > 0) / len(scores),
            "negative_ratio": sum(1 for s in scores if s < 0) / len(scores),
            "neutral_ratio": sum(1 for s in scores if s == 0) / len(scores),
        }