"""
LLM 模型客户端模块
支持 OpenAI 兼容接口 + 本地 Mock 模式
增强：指数退避重试、令牌桶限流、熔断降级
"""
import re
import time
import logging
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass
from collections import deque

from app.core.config import get_settings
from app.core.logging_setup import llm_metrics

settings = get_settings()
logger = logging.getLogger(__name__)


class TokenBucketRateLimiter:
    """令牌桶限流器 — 控制 LLM API 调用频率"""

    def __init__(self, rate: float = 10.0, capacity: int = 20):
        """
        Args:
            rate: 每秒生成令牌数（QPS）
            capacity: 桶容量（最大突发请求数）
        """
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def acquire(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """获取令牌，阻塞直到获取成功或超时"""
        start = time.time()
        while True:
            with self._lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
            if time.time() - start > timeout:
                return False
            time.sleep(0.1)

    def try_acquire(self, tokens: int = 1) -> bool:
        """非阻塞获取令牌"""
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def _refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(
            self.capacity,
            self.tokens + elapsed * self.rate
        )
        self.last_refill = now


class CircuitBreaker:
    """熔断器 — 连续失败后自动熔断，避免无效调用"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        """
        Args:
            failure_threshold: 连续失败次数阈值
            recovery_timeout: 熔断后恢复等待时间（秒）
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self._lock = threading.Lock()

    def can_execute(self) -> bool:
        """检查是否可以执行请求"""
        with self._lock:
            if self.state == self.CLOSED:
                return True
            elif self.state == self.OPEN:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.state = self.HALF_OPEN
                    return True
                return False
            else:
                return False

    def record_success(self):
        """记录成功调用"""
        with self._lock:
            if self.state == self.HALF_OPEN:
                self.state = self.CLOSED
            self.failure_count = 0

    def record_failure(self):
        """记录失败调用"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                if self.state != self.OPEN:
                    logger.warning(
                        f"熔断器触发：连续失败 {self.failure_count} 次，"
                        f"进入熔断状态，{self.recovery_timeout}秒后恢复"
                    )
                self.state = self.OPEN

    @property
    def current_state(self) -> str:
        with self._lock:
            return self.state


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


_rate_limiters: Dict[str, TokenBucketRateLimiter] = {}
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_rl_lock = threading.Lock()


def _get_rate_limiter(model_name: str) -> TokenBucketRateLimiter:
    """获取模型对应的限流器（单例）"""
    with _rl_lock:
        if model_name not in _rate_limiters:
            rate = settings.llm_rate_limit if hasattr(settings, 'llm_rate_limit') else 10.0
            capacity = settings.llm_rate_capacity if hasattr(settings, 'llm_rate_capacity') else 20
            _rate_limiters[model_name] = TokenBucketRateLimiter(rate=rate, capacity=capacity)
        return _rate_limiters[model_name]


def _get_circuit_breaker(model_name: str) -> CircuitBreaker:
    """获取模型对应的熔断器（单例）"""
    with _rl_lock:
        if model_name not in _circuit_breakers:
            threshold = settings.llm_circuit_threshold if hasattr(settings, 'llm_circuit_threshold') else 5
            timeout = settings.llm_circuit_timeout if hasattr(settings, 'llm_circuit_timeout') else 60.0
            _circuit_breakers[model_name] = CircuitBreaker(
                failure_threshold=threshold,
                recovery_timeout=timeout,
            )
        return _circuit_breakers[model_name]


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
        self.retry_backoff = 2.0
        self.rate_limiter = _get_rate_limiter(self.name)
        self.circuit_breaker = _get_circuit_breaker(self.name)

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

    def _is_retryable_error(self, error: Exception) -> bool:
        """判断错误是否可重试"""
        error_str = str(error).lower()
        retryable_keywords = [
            "timeout", "timed out", "connection", "network",
            "rate limit", "429", "503", "502", "504",
            "too many requests", "server error", "unavailable",
            "重置", "连接", "超时", "限流", "繁忙",
        ]
        return any(kw in error_str for kw in retryable_keywords)

    def _retry_call(self, func, *args, **kwargs) -> LLMResponse:
        """带指数退避重试 + 限流 + 熔断的调用"""
        last_error = ""

        if not self.circuit_breaker.can_execute():
            logger.warning(f"[{self.name}] 熔断器已打开，跳过调用")
            llm_metrics.record_call(
                model_name=self.name,
                success=False,
                latency=0.0,
                tokens=0,
            )
            return LLMResponse(
                model_name=self.name,
                raw_response="",
                success=False,
                error="circuit_breaker_open",
            )

        if not self.rate_limiter.acquire(timeout=10.0):
            logger.warning(f"[{self.name}] 获取限流令牌超时")
            llm_metrics.record_call(
                model_name=self.name,
                success=False,
                latency=0.0,
                tokens=0,
            )
            return LLMResponse(
                model_name=self.name,
                raw_response="",
                success=False,
                error="rate_limit_timeout",
            )

        try:
            for attempt in range(self.max_retries):
                try:
                    response = func(*args, **kwargs)
                    if response.success:
                        self.circuit_breaker.record_success()
                        logger.debug(
                            f"[{self.name}] 调用成功 latency={response.latency:.3f}s "
                            f"tokens={response.tokens_used}"
                        )
                    else:
                        self.circuit_breaker.record_failure()
                    llm_metrics.record_call(
                        model_name=self.name,
                        success=response.success,
                        latency=response.latency,
                        tokens=response.tokens_used,
                    )
                    return response
                except Exception as e:
                    last_error = str(e)
                    is_retryable = self._is_retryable_error(e)

                    if attempt < self.max_retries - 1 and is_retryable:
                        delay = self.retry_delay * (self.retry_backoff ** attempt)
                        logger.warning(
                            f"[{self.name}] 第{attempt+1}次调用失败，{delay:.1f}s后重试: {e}"
                        )
                        time.sleep(delay)
                    else:
                        logger.error(f"[{self.name}] 调用失败（不可重试或已达最大重试次数）: {e}")
                        break

            self.circuit_breaker.record_failure()
            llm_metrics.record_call(
                model_name=self.name,
                success=False,
                latency=0.0,
                tokens=0,
            )
            return LLMResponse(
                model_name=self.name,
                raw_response="",
                success=False,
                error=last_error,
            )
        finally:
            pass


class OpenAICompatibleClient(BaseLLMClient):
    """OpenAI 兼容接口客户端"""

    def __init__(self, model_config: Dict, api_key: str = None, fallback_model_id: str = None):
        super().__init__(model_config)
        self.api_key = api_key or model_config.get("api_key", "")
        self.fallback_model_id = fallback_model_id

    def call(self, prompt: str, system_prompt: str = None, **kwargs) -> LLMResponse:
        return self._retry_call(self._call_impl, prompt, system_prompt, **kwargs)

    def _call_impl(self, prompt: str, system_prompt: str = None, **kwargs) -> LLMResponse:
        import requests

        start_time = time.time()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        def _do_request(model_id: str) -> LLMResponse:
            payload = {
                "model": model_id,
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

        try:
            return _do_request(self.model_id)
        except Exception as primary_error:
            if self.fallback_model_id and self.fallback_model_id != self.model_id:
                try:
                    return _do_request(self.fallback_model_id)
                except Exception:
                    pass
            raise primary_error


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


def create_llm_client(model_config: Dict, api_keys: Dict = None, use_mock: bool = True, fallback_model_ids: Dict = None) -> BaseLLMClient:
    """工厂方法：创建 LLM 客户端"""
    api_keys = api_keys or {}
    fallback_model_ids = fallback_model_ids or {}
    model_name = model_config.get("name", "")

    if use_mock:
        return MockLLMClient(model_config)

    api_key = api_keys.get(model_name, "")
    fallback = fallback_model_ids.get(model_name)
    return OpenAICompatibleClient(model_config, api_key=api_key, fallback_model_id=fallback)


# ============================================================
#  默认三模型配置
# ============================================================
DEFAULT_LLM_MODELS = [
    {
        "name": "deepseek-r1",
        "display_name": "DeepSeek-R1",
        "type": "decoder_only",
        "api_base": "https://api.deepseek.com/v1",
        "model_id": "deepseek-reasoner",
    },
    {
        "name": "qwen-max",
        "display_name": "Qwen-Max",
        "type": "decoder_only",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model_id": "qwen-max",
    },
    {
        "name": "glm-4.7",
        "display_name": "GLM-4.7",
        "type": "decoder_only",
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
        "model_id": "glm-4.7",
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