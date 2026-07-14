"""LLM客户端、限流器、熔断器单元测试"""
import sys
from pathlib import Path
import unittest
import time
import threading

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.llm_client import (
    TokenBucketRateLimiter,
    CircuitBreaker,
    MockLLMClient,
    BaseLLMClient,
)


class TestTokenBucketRateLimiter(unittest.TestCase):
    """令牌桶限流器测试"""

    def test_initial_capacity(self):
        """初始令牌数等于桶容量"""
        limiter = TokenBucketRateLimiter(rate=10.0, capacity=5)
        self.assertTrue(limiter.try_acquire(5))
        self.assertFalse(limiter.try_acquire(1))

    def test_try_acquire_success(self):
        """非阻塞获取成功"""
        limiter = TokenBucketRateLimiter(rate=10.0, capacity=10)
        self.assertTrue(limiter.try_acquire())

    def test_try_acquire_fail(self):
        """非阻塞获取失败"""
        limiter = TokenBucketRateLimiter(rate=1.0, capacity=1)
        self.assertTrue(limiter.try_acquire())
        self.assertFalse(limiter.try_acquire())

    def test_acquire_with_timeout(self):
        """阻塞获取带超时"""
        limiter = TokenBucketRateLimiter(rate=100.0, capacity=1)
        self.assertTrue(limiter.try_acquire())
        self.assertTrue(limiter.acquire(timeout=0.5))

    def test_token_refill(self):
        """令牌补充"""
        limiter = TokenBucketRateLimiter(rate=100.0, capacity=2)
        self.assertTrue(limiter.try_acquire(2))
        self.assertFalse(limiter.try_acquire())
        time.sleep(0.05)
        self.assertTrue(limiter.try_acquire())

    def test_capacity_limit(self):
        """令牌数不超过容量"""
        limiter = TokenBucketRateLimiter(rate=100.0, capacity=5)
        time.sleep(0.1)
        self.assertTrue(limiter.try_acquire(5))
        self.assertFalse(limiter.try_acquire(2))

    def test_thread_safety(self):
        """多线程安全"""
        limiter = TokenBucketRateLimiter(rate=1000.0, capacity=100)
        acquired = []
        lock = threading.Lock()

        def worker():
            for _ in range(10):
                if limiter.try_acquire():
                    with lock:
                        acquired.append(1)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertLessEqual(len(acquired), 100 + 20)


class TestCircuitBreaker(unittest.TestCase):
    """熔断器测试"""

    def test_initial_closed(self):
        """初始状态为关闭"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        self.assertEqual(cb.current_state, CircuitBreaker.CLOSED)
        self.assertTrue(cb.can_execute())

    def test_opens_after_failures(self):
        """达到失败阈值后熔断"""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=10.0)
        for _ in range(2):
            cb.record_failure()
            self.assertTrue(cb.can_execute())
        cb.record_failure()
        self.assertFalse(cb.can_execute())
        self.assertEqual(cb.current_state, CircuitBreaker.OPEN)

    def test_half_open_after_timeout(self):
        """超时后进入半开状态"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        self.assertFalse(cb.can_execute())
        time.sleep(0.15)
        self.assertTrue(cb.can_execute())
        self.assertEqual(cb.current_state, CircuitBreaker.HALF_OPEN)

    def test_success_closes_circuit(self):
        """成功后关闭熔断器"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        self.assertTrue(cb.can_execute())
        cb.record_success()
        self.assertEqual(cb.current_state, CircuitBreaker.CLOSED)
        self.assertEqual(cb.failure_count, 0)

    def test_failure_reopens_circuit(self):
        """半开状态下失败重新熔断"""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        self.assertTrue(cb.can_execute())
        cb.record_failure()
        self.assertFalse(cb.can_execute())

    def test_success_resets_failure_count(self):
        """成功重置失败计数"""
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=1.0)
        cb.record_failure()
        cb.record_failure()
        self.assertEqual(cb.failure_count, 2)
        cb.record_success()
        self.assertEqual(cb.failure_count, 0)


class TestMockLLMClient(unittest.TestCase):
    """Mock LLM客户端测试"""

    def setUp(self):
        config = {"name": "test-mock", "display_name": "Test Mock", "model_id": "test"}
        self.client = MockLLMClient(config)

    def test_classification_substantive(self):
        """Mock分类：实质性陈述"""
        prompt = "请分类：环保投入达5000万元，同比增长15%。"
        response = self.client.call(prompt)
        self.assertTrue(response.success)
        self.assertEqual(response.parsed_result, "substantive")

    def test_classification_descriptive(self):
        """Mock分类：描述性陈述"""
        from app.services.llm_client import CLASSIFICATION_PROMPT
        sentence = "公司高度重视环境保护工作。"
        prompt = CLASSIFICATION_PROMPT.format(sentence=sentence)
        response = self.client.call(prompt)
        self.assertTrue(response.success)
        self.assertIn(response.parsed_result, ["substantive", "descriptive", "non_environmental"])

    def test_sentiment_positive(self):
        """Mock情感分析：正面"""
        from app.services.llm_client import SENTIMENT_PROMPT
        sentence = "公司积极推动绿色发展，取得显著成效。"
        prompt = SENTIMENT_PROMPT.format(sentence=sentence)
        response = self.client.call(prompt)
        self.assertTrue(response.success)
        self.assertIsInstance(response.parsed_result, float)
        self.assertGreater(response.parsed_result, 0)

    def test_response_fields(self):
        """响应包含所有字段"""
        response = self.client.call("测试")
        self.assertTrue(hasattr(response, 'model_name'))
        self.assertTrue(hasattr(response, 'raw_response'))
        self.assertTrue(hasattr(response, 'success'))
        self.assertTrue(hasattr(response, 'latency'))
        self.assertTrue(hasattr(response, 'tokens_used'))
        self.assertGreater(response.latency, 0)


class TestClassificationParsing(unittest.TestCase):
    """分类结果解析测试"""

    def setUp(self):
        config = {"name": "test", "model_id": "test"}
        self.client = MockLLMClient(config)

    def test_parse_explicit_format(self):
        """解析明确格式的分类结果"""
        response_text = "推理：这是一个测试。\n分类：substantive"
        result = self.client._parse_classification(response_text)
        self.assertEqual(result, "substantive")

    def test_parse_chinese_label(self):
        """解析中文分类标签"""
        result = self.client._parse_classification("这是实质性陈述。")
        self.assertEqual(result, "substantive")

    def test_parse_descriptive_chinese(self):
        """解析中文描述性标签"""
        result = self.client._parse_classification("这是描述性陈述。")
        self.assertEqual(result, "descriptive")

    def test_parse_non_env_chinese(self):
        """解析中文非环保标签"""
        result = self.client._parse_classification("这是非环保语句。")
        self.assertEqual(result, "non_environmental")

    def test_parse_default_fallback(self):
        """无法解析时返回descriptive"""
        result = self.client._parse_classification("无法识别的内容")
        self.assertEqual(result, "descriptive")


class TestSentimentParsing(unittest.TestCase):
    """情感评分解析测试"""

    def setUp(self):
        config = {"name": "test", "model_id": "test"}
        self.client = MockLLMClient(config)

    def test_parse_explicit_format(self):
        """解析明确格式的情感评分"""
        response_text = "语义分析：测试。\n评分理由：正面。\n情感评分：0.75"
        result = self.client._parse_sentiment(response_text)
        self.assertAlmostEqual(result, 0.75, places=2)

    def test_parse_negative(self):
        """解析负面评分"""
        result = self.client._parse_sentiment("情感评分：-0.5")
        self.assertAlmostEqual(result, -0.5, places=2)

    def test_parse_clamped(self):
        """超出范围的值被截断"""
        result = self.client._parse_sentiment("情感评分：2.0")
        self.assertAlmostEqual(result, 1.0, places=2)

    def test_parse_default_zero(self):
        """无法解析时返回0"""
        result = self.client._parse_sentiment("没有数字")
        self.assertEqual(result, 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
