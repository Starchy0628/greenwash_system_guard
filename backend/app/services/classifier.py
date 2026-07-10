"""
语句分类器 — 基于异构大语言模型的环境语句分类
将环境语句划分为：实质性陈述、描述性陈述、非环保语句
"""
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from app.services.llm_client import (
    BaseLLMClient,
    LLMResponse,
    create_llm_client,
    DEFAULT_LLM_MODELS,
    CLASSIFICATION_PROMPT,
    ClassificationType,
)


@dataclass
class SentenceClassificationResult:
    """单语句分类结果"""
    sentence: str
    model_results: Dict[str, str] = field(default_factory=dict)
    final_label: str = ""
    confidence: float = 0.0
    vote_type: str = ""
    is_ambiguous: bool = False
    model_responses: Dict[str, LLMResponse] = field(default_factory=dict)


class SentenceClassifier:
    """语句分类器 — 三模型独立推理 + 多数投票"""

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

    def classify_single(
        self, sentence: str, return_details: bool = False
    ) -> SentenceClassificationResult:
        """对单条语句进行分类"""
        result = SentenceClassificationResult(sentence=sentence)

        for model_name, client in self.clients.items():
            try:
                prompt = CLASSIFICATION_PROMPT.format(sentence=sentence)
                response = client.call(prompt)

                if response.success:
                    label = client._parse_classification(response.raw_response)
                    result.model_results[model_name] = label
                    response.parsed_result = label
                else:
                    result.model_results[model_name] = ClassificationType.DESCRIPTIVE

                if return_details:
                    result.model_responses[model_name] = response

            except Exception:
                result.model_results[model_name] = ClassificationType.DESCRIPTIVE

        self._determine_final_label(result)
        return result

    def classify_batch(
        self, sentences: List[str], return_details: bool = False
    ) -> List[SentenceClassificationResult]:
        """批量分类"""
        results = []
        for sent in sentences:
            result = self.classify_single(sent, return_details=return_details)
            results.append(result)
        return results

    def _determine_final_label(self, result: SentenceClassificationResult):
        """多数投票确权"""
        labels = list(result.model_results.values())
        if not labels:
            result.final_label = ClassificationType.DESCRIPTIVE
            result.confidence = 0.0
            result.vote_type = "unknown"
            return

        label_counts = {}
        for label in labels:
            label_counts[label] = label_counts.get(label, 0) + 1

        max_count = max(label_counts.values())
        majority_labels = [l for l, c in label_counts.items() if c == max_count]
        total_models = len(labels)

        if max_count == total_models:
            result.vote_type = "unanimous"
            result.confidence = 1.0
            result.final_label = majority_labels[0]
            result.is_ambiguous = False
        elif len(majority_labels) == 1:
            result.vote_type = "majority"
            result.confidence = max_count / total_models
            result.final_label = majority_labels[0]
            result.is_ambiguous = False
        else:
            result.vote_type = "full_divergence"
            result.confidence = max_count / total_models
            result.final_label = ClassificationType.DESCRIPTIVE
            result.is_ambiguous = True

    def get_stats(self, results: List[SentenceClassificationResult]) -> Dict:
        """统计分类结果"""
        stats = {
            "total": len(results),
            "substantive": 0,
            "descriptive": 0,
            "non_environmental": 0,
            "unanimous": 0,
            "majority": 0,
            "full_divergence": 0,
            "ambiguous": 0,
        }
        for r in results:
            stats[r.final_label] = stats.get(r.final_label, 0) + 1
            stats[r.vote_type] = stats.get(r.vote_type, 0) + 1
            if r.is_ambiguous:
                stats["ambiguous"] += 1
        return stats