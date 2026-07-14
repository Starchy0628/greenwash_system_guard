"""日志系统和指标收集器单元测试"""
import sys
from pathlib import Path
import unittest
import logging
import time
import threading

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.logging_setup import (
    setup_logging,
    get_request_id,
    set_request_id,
    clear_request_id,
    LLMMetricsCollector,
    JsonFormatter,
    StructuredLoggerAdapter,
)


class TestRequestIdContext(unittest.TestCase):
    """请求ID上下文测试"""

    def setUp(self):
        clear_request_id()

    def test_default_empty(self):
        """默认请求ID为空"""
        self.assertEqual(get_request_id(), "")

    def test_set_and_get(self):
        """设置和获取请求ID"""
        rid = set_request_id("test-123")
        self.assertEqual(rid, "test-123")
        self.assertEqual(get_request_id(), "test-123")

    def test_auto_generate(self):
        """自动生成请求ID"""
        rid = set_request_id("")
        self.assertTrue(len(rid) > 0)
        self.assertEqual(get_request_id(), rid)


class TestJsonFormatter(unittest.TestCase):
    """JSON日志格式化器测试"""

    def test_format_basic(self):
        """基础日志格式化"""
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="测试消息",
            args=(),
            exc_info=None,
        )
        import json
        output = formatter.format(record)
        parsed = json.loads(output)
        self.assertEqual(parsed["message"], "测试消息")
        self.assertEqual(parsed["level"], "INFO")
        self.assertEqual(parsed["logger"], "test")
        self.assertIn("timestamp", parsed)
        self.assertIn("request_id", parsed)


class TestLLMMetricsCollector(unittest.TestCase):
    """LLM指标收集器测试"""

    def setUp(self):
        self.metrics = LLMMetricsCollector()

    def test_initial_stats(self):
        """初始统计为空"""
        stats = self.metrics.get_stats()
        self.assertEqual(stats["total_calls"], 0)
        self.assertEqual(stats["success_calls"], 0)
        self.assertEqual(stats["failed_calls"], 0)
        self.assertEqual(stats["avg_latency"], 0.0)
        self.assertEqual(stats["success_rate"], 0.0)

    def test_record_success(self):
        """记录成功调用"""
        self.metrics.record_call(
            model_name="test-model",
            success=True,
            latency=0.5,
            tokens=100,
        )
        stats = self.metrics.get_stats()
        self.assertEqual(stats["total_calls"], 1)
        self.assertEqual(stats["success_calls"], 1)
        self.assertEqual(stats["failed_calls"], 0)
        self.assertEqual(stats["total_tokens"], 100)
        self.assertAlmostEqual(stats["avg_latency"], 0.5, places=3)
        self.assertAlmostEqual(stats["success_rate"], 1.0, places=3)

    def test_record_failure(self):
        """记录失败调用"""
        self.metrics.record_call(
            model_name="test-model",
            success=False,
            latency=0.1,
            tokens=0,
        )
        stats = self.metrics.get_stats()
        self.assertEqual(stats["total_calls"], 1)
        self.assertEqual(stats["success_calls"], 0)
        self.assertEqual(stats["failed_calls"], 1)
        self.assertAlmostEqual(stats["success_rate"], 0.0, places=3)

    def test_mixed_calls(self):
        """混合成功失败"""
        for i in range(10):
            self.metrics.record_call(
                model_name="test-model",
                success=(i < 8),
                latency=0.1 * i,
                tokens=50,
            )
        stats = self.metrics.get_stats()
        self.assertEqual(stats["total_calls"], 10)
        self.assertEqual(stats["success_calls"], 8)
        self.assertEqual(stats["failed_calls"], 2)
        self.assertAlmostEqual(stats["success_rate"], 0.8, places=3)
        self.assertEqual(stats["total_tokens"], 500)

    def test_by_model_breakdown(self):
        """按模型分类统计"""
        self.metrics.record_call("model-a", True, 0.5, 100)
        self.metrics.record_call("model-a", True, 0.3, 80)
        self.metrics.record_call("model-b", False, 0.1, 0)

        stats = self.metrics.get_stats()
        self.assertIn("model-a", stats["by_model"])
        self.assertIn("model-b", stats["by_model"])
        self.assertEqual(stats["by_model"]["model-a"]["calls"], 2)
        self.assertEqual(stats["by_model"]["model-a"]["success"], 2)
        self.assertEqual(stats["by_model"]["model-b"]["calls"], 1)
        self.assertEqual(stats["by_model"]["model-b"]["failed"], 1)

    def test_reset(self):
        """重置统计"""
        self.metrics.record_call("test", True, 0.5, 100)
        self.metrics.reset()
        stats = self.metrics.get_stats()
        self.assertEqual(stats["total_calls"], 0)
        self.assertEqual(len(stats["by_model"]), 0)

    def test_thread_safety(self):
        """多线程安全"""
        errors = []

        def worker(n):
            try:
                for i in range(n):
                    self.metrics.record_call(
                        model_name="test",
                        success=(i % 2 == 0),
                        latency=0.01,
                        tokens=10,
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(100,)) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        stats = self.metrics.get_stats()
        self.assertEqual(stats["total_calls"], 1000)


class TestSetupLogging(unittest.TestCase):
    """日志配置测试"""

    def test_setup_does_not_crash(self):
        """日志配置不崩溃"""
        try:
            setup_logging(log_level="DEBUG", log_dir=None, json_format=False)
            setup_logging(log_level="INFO", log_dir=None, json_format=True)
        except Exception as e:
            self.fail(f"setup_logging raised exception: {e}")

    def test_logger_level(self):
        """日志级别设置"""
        setup_logging(log_level="WARNING", log_dir=None)
        root = logging.getLogger()
        self.assertEqual(root.level, logging.WARNING)


if __name__ == "__main__":
    unittest.main(verbosity=2)
