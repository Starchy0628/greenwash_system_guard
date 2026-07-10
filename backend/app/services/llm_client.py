"""
LLM 模型客户端模块
支持 OpenAI 兼容接口 + 本地 Mock 模式
"""
import re
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass

from app.core.config import get_settings

settings = get_settings()


@dataclass
class LLMResponse:
    """LLM 调用响应"""
    model_name: str
    raw_response: str
    parsed_result: Any = None
    success: bool = True
    error: str = ""
    latency: float = 0.0
    tokens_used: int = 0


class BaseLLMClient(ABC):
    """LLM 客户端基类"""

    def __init__(self, model_config: Dict):
        self.model_config = model_config
        self.name = model_config.get("name", "unknown")
        self.display_name = model_config.get("display_name", self.name)
        self.api_base = model_config.get("api_base", "")
        self.model_id = model_config.get("model_id", "")
        self.max_retries = 3
        self.retry_delay = 2.0

    @abstractmethod
    def call(self, prompt: str, system_prompt: str = None, **kwargs) -> LLMResponse:
        pass

    def _parse_classification(self, response: str) -> str:
        """从 LLM 响应中解析分类结果"""
        match = re.search(r"分类[：:]\s*(\w+)", response)
        if match:
            result = match.group(1).strip().lower()
            if result in ["substantive", "descriptive", "non_environmental"]:
                return result

        patterns = [
            (r"实质性陈述", "substantive"),
            (r"描述性陈述", "descriptive"),
            (r"非环保语句", "non_environmental"),
            (r"substantive", "substantive"),
            (r"descriptive", "descriptive"),
            (r"non[_\-]environmental", "non_environmental"),
        ]
        for pattern, label in patterns:
            if re.search(pattern, response, re.IGNORECASE):
                return label

        return "descriptive"

    def _parse_sentiment(self, response: str) -> float:
        """从 LLM 响应中解析情感评分"""
        match = re.search(r"情感评分[：:]\s*(-?\d+\.?\d*)", response)
        if match:
            try:
                score = float(match.group(1))
                return max(-1.0, min(1.0, score))
            except ValueError:
                pass

        numbers = re.findall(r"(-?\d+\.\d+|-?\d+)", response)
        for num in numbers:
            try:
                score = float(num)
                if -1.0 <= score <= 1.0:
                    return score
            except ValueError:
                continue

        return 0.0

    def _retry_call(self, func, *args, **kwargs) -> LLMResponse:
        """带重试的调用"""
        last_error = ""
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))

        return LLMResponse(
            model_name=self.name,
            raw_response="",
            success=False,
            error=last_error,
        )


class OpenAICompatibleClient(BaseLLMClient):
    """OpenAI 兼容接口客户端"""

    def __init__(self, model_config: Dict, api_key: str = None):
        super().__init__(model_config)
        self.api_key = api_key or model_config.get("api_key", "")

    def call(self, prompt: str, system_prompt: str = None, **kwargs) -> LLMResponse:
        return self._retry_call(self._call_impl, prompt, system_prompt, **kwargs)

    def _call_impl(self, prompt: str, system_prompt: str = None, **kwargs) -> LLMResponse:
        import requests

        start_time = time.time()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model_id,
            "messages": messages,
            "temperature": kwargs.get("temperature", 0.1),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            f"{self.api_base}/chat/completions",
            json=payload,
            headers=headers,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()

        latency = time.time() - start_time
        content = data["choices"][0]["message"]["content"]
        tokens_used = data.get("usage", {}).get("total_tokens", 0)

        return LLMResponse(
            model_name=self.name,
            raw_response=content,
            success=True,
            latency=latency,
            tokens_used=tokens_used,
        )


class MockLLMClient(BaseLLMClient):
    """
    模拟 LLM 客户端 — 基于规则的分类和情感分析
    用于演示和测试，无需 API Key
    """

    def __init__(self, model_config: Dict):
        super().__init__(model_config)
        self._substantive_indicators = [
            "万元", "亿元", "吨", "千瓦时", "%", "达到", "完成",
            "ISO", "认证", "通过", "建成", "投产", "实现",
            "具体数据", "实际投入", "减排量", "投入资金",
        ]
        self._positive_words = [
            "积极", "显著", "有效", "大幅", "持续", "不断",
            "优良", "优秀", "领先", "先进", "创新", "突破",
            "成效", "成果", "成就", "贡献", "改善", "提升",
            "圆满完成", "顺利实现", "成功",
        ]
        self._negative_words = [
            "不足", "问题", "困难", "挑战", "风险", "压力",
            "有待", "需要改进", "差距", "缺陷", "未能",
            "污染", "排放超标", "事故", "处罚",
        ]

    def call(self, prompt: str, system_prompt: str = None, **kwargs) -> LLMResponse:
        start_time = time.time()
        time.sleep(0.05)

        sentence = self._extract_sentence(prompt)

        if "分类" in prompt or "classification" in prompt.lower():
            classification = self._mock_classify(sentence)
            raw_response = f"""推理：对语句进行语义分析，判断其类型。
该语句{"包含具体数据和可验证事实" if classification == "substantive" else "主要是定性描述和口号式表述" if classification == "descriptive" else "虽含有关键词但非实质性环境内容"}。
分类：{classification}"""
            result = classification
        else:
            sentiment = self._mock_sentiment(sentence)
            raw_response = f"""语义分析：分析句内的语义依存关系和情感倾向。
评分理由：语句整体倾向为{"正面" if sentiment > 0 else "负面" if sentiment < 0 else "中性"}。
情感评分：{sentiment:.2f}"""
            result = sentiment

        latency = time.time() - start_time

        return LLMResponse(
            model_name=self.name,
            raw_response=raw_response,
            parsed_result=result,
            success=True,
            latency=latency,
            tokens_used=len(prompt) // 2 + 100,
        )

    def _extract_sentence(self, prompt: str) -> str:
        lines = prompt.split("\n")
        for line in lines:
            if line.strip().startswith("语句："):
                return line.replace("语句：", "").strip()
        return prompt

    def _mock_classify(self, sentence: str) -> str:
        substantive_count = sum(
            1 for kw in self._substantive_indicators if kw in sentence
        )
        if substantive_count >= 2:
            return "substantive"
        elif len(sentence) < 15:
            return "non_environmental"
        else:
            return "descriptive"

    def _mock_sentiment(self, sentence: str) -> float:
        pos_count = sum(1 for w in self._positive_words if w in sentence)
        neg_count = sum(1 for w in self._negative_words if w in sentence)
        total = pos_count + neg_count
        if total == 0:
            return 0.1
        score = (pos_count - neg_count) / total
        return max(-1.0, min(1.0, score))


def create_llm_client(model_config: Dict, api_keys: Dict = None, use_mock: bool = True) -> BaseLLMClient:
    """工厂方法：创建 LLM 客户端"""
    api_keys = api_keys or {}
    model_name = model_config.get("name", "")

    if use_mock:
        return MockLLMClient(model_config)

    api_key = api_keys.get(model_name, "")
    return OpenAICompatibleClient(model_config, api_key=api_key)


# ============================================================
#  默认三模型配置
# ============================================================
DEFAULT_LLM_MODELS = [
    {
        "name": "deepseek-r1-32b",
        "display_name": "DeepSeek-R1-32B",
        "type": "decoder_only",
        "api_base": "https://api.deepseek.com/v1",
        "model_id": "deepseek-reasoner",
    },
    {
        "name": "qwen-3-32b",
        "display_name": "Qwen-3-32B",
        "type": "decoder_only",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_id": "qwen-max",
    },
    {
        "name": "openpangu-pro-moe-72b",
        "display_name": "OpenPangu-Pro-MoE-72B",
        "type": "moe",
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
        "model_id": "glm-4-plus",
    },
]

# ============================================================
#  Prompt 模板
# ============================================================
CLASSIFICATION_PROMPT = """你是一名环境信息披露分析专家。请对以下语句进行分类，判断其属于哪一类。

分类规则：
1. 实质性陈述（substantive）：包含可验证的定量数据、具体的环保设施/技术、具体的认证成果、明确的减排目标及完成情况、具体的环保投入金额等有实质性内容的表述。
2. 描述性陈述（descriptive）：仅有定性的口号、模糊的承诺、泛泛而谈的环保理念、没有具体数据或行动支撑的积极表述，是企业可能进行漂绿的主要载体。
3. 非环保语句（non_environmental）：虽包含环境相关关键词，但实际讨论的是其他内容，或与环境治理无实质关联的语句。

请仔细分析语句的语义、是否有具体数据支撑、是否有可验证的事实，并进行推理后给出分类。

语句：{sentence}

请按以下格式输出：
1. 先进行推理分析（Chain-of-Thought）
2. 最后给出明确的分类结果：substantive / descriptive / non_environmental

输出格式：
推理：<你的推理过程>
分类：<substantive/descriptive/non_environmental>
"""

SENTIMENT_PROMPT = """你是一名环境信息披露情感分析专家。请对以下环境描述性陈述进行情感评分，评估其修辞倾向。

评分规则：
- 评分范围：-1 到 1 之间的连续值
- -1：完全负面，主要是风险揭示、问题承认、环境负面信息披露
- 0：中性，客观陈述，无明显情感倾向
- 1：完全正面，大量积极修辞、成就宣扬、自我表扬

请仔细分析：
1. 词汇的情感色彩（积极/消极）
2. 转折连词的逻辑指向（如"虽然...但是..."）
3. 否定词的管辖范围
4. 修辞强度的级差
5. 整体语调和语气

语句：{sentence}

请按以下格式输出：
1. 先进行语义依存分析（Intra-sentence Semantic Dependency）
2. 给出详细的评分理由
3. 最后给出具体的评分值（保留两位小数）

输出格式：
语义分析：<你的分析过程>
评分理由：<理由说明>
情感评分：<x.xx>
"""


class ClassificationType:
    SUBSTANTIVE = "substantive"
    DESCRIPTIVE = "descriptive"
    NON_ENVIRONMENTAL = "non_environmental"


class VoteResultType:
    MAJORITY = "majority"
    FULL_DIVERGENCE = "full_divergence"
    UNANIMOUS = "unanimous"