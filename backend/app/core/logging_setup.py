"""
日志配置模块 — 结构化日志、请求追踪、关键指标记录

特性：
- JSON 格式结构化日志（可选）
- 请求 ID 追踪（X-Request-ID）
- 按级别和模块过滤
- 文件日志 + 控制台输出
- LLM 调用指标统计
"""
import sys
import logging
import json
import uuid
import time
from pathlib import Path
from typing import Optional, Dict, Any
from contextvars import ContextVar
from datetime import datetime

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    """获取当前请求ID"""
    return _request_id_var.get()


def set_request_id(request_id: str = "") -> str:
    """设置当前请求ID，返回设置的ID"""
    if not request_id:
        request_id = str(uuid.uuid4())[:8]
    _request_id_var.set(request_id)
    return request_id


def clear_request_id():
    """清除当前请求ID"""
    _request_id_var.set("")


class JsonFormatter(logging.Formatter):
    """JSON 格式日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id() or "-",
        }

        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


class StructuredLoggerAdapter(logging.LoggerAdapter):
    """结构化日志适配器 — 支持附加上下文字段"""

    def process(self, msg, kwargs):
        extra = kwargs.get("extra", {})
        extra_fields = extra.get("extra_fields", {})
        if self.extra:
            extra_fields.update(self.extra)
        extra["extra_fields"] = extra_fields
        kwargs["extra"] = extra
        return msg, kwargs


def setup_logging(
    log_level: str = "INFO",
    log_dir: Optional[str] = None,
    json_format: bool = False,
    app_name: str = "greenwash-guard",
):
    """
    配置全局日志系统

    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: 日志文件目录，为None则只输出到控制台
        json_format: 是否使用JSON格式
        app_name: 应用名称（用于日志文件名）
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    formatter_class = JsonFormatter if json_format else logging.Formatter
    if json_format:
        formatter = formatter_class()
    else:
        fmt = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
        datefmt = "%Y-%m-%d %H:%M:%S"
        formatter = formatter_class(fmt, datefmt=datefmt)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if log_dir:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y%m%d")
        file_handler = logging.FileHandler(
            log_path / f"{app_name}_{today}.log",
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        error_handler = logging.FileHandler(
            log_path / f"{app_name}_error_{today}.log",
            encoding="utf-8",
        )
        error_handler.setFormatter(formatter)
        error_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_handler)

    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


class RequestLoggingMiddleware:
    """
    请求日志中间件

    功能：
    - 为每个请求生成/传递请求ID
    - 记录请求开始和结束
    - 记录请求耗时、状态码
    """

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger("request")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = ""
        for header_name, header_value in scope.get("headers", []):
            if header_name.decode("latin1").lower() == "x-request-id":
                request_id = header_value.decode("latin1")
                break

        request_id = set_request_id(request_id)

        path = scope.get("path", "")
        method = scope.get("method", "")
        client = scope.get("client", ("", 0))
        client_ip = client[0] if client else ""

        start_time = time.time()
        self.logger.info(
            f"REQ START {method} {path} from {client_ip}",
            extra={"extra_fields": {
                "method": method,
                "path": path,
                "client_ip": client_ip,
            }}
        )

        status_code = 500

        async def wrapped_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                message.setdefault("headers", [])
                message["headers"].append(
                    (b"x-request-id", request_id.encode("latin1"))
                )
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        except Exception:
            status_code = 500
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            level = logging.INFO if status_code < 400 else logging.WARNING if status_code < 500 else logging.ERROR
            self.logger.log(
                level,
                f"REQ END {method} {path} {status_code} {duration_ms:.1f}ms",
                extra={"extra_fields": {
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 2),
                }}
            )


class LLMMetricsCollector:
    """
    LLM 调用指标收集器

    统计：
    - 总调用次数
    - 成功/失败次数
    - 平均延迟
    - Token 消耗量
    - 各模型调用分布
    """

    def __init__(self):
        self._lock = None
        self._stats: Dict[str, Any] = {
            "total_calls": 0,
            "success_calls": 0,
            "failed_calls": 0,
            "total_tokens": 0,
            "total_latency": 0.0,
            "by_model": {},
        }

    @property
    def lock(self):
        if self._lock is None:
            import threading
            self._lock = threading.Lock()
        return self._lock

    def record_call(self, model_name: str, success: bool, latency: float, tokens: int = 0):
        """记录一次LLM调用"""
        with self.lock:
            self._stats["total_calls"] += 1
            self._stats["total_latency"] += latency
            self._stats["total_tokens"] += tokens

            if success:
                self._stats["success_calls"] += 1
            else:
                self._stats["failed_calls"] += 1

            if model_name not in self._stats["by_model"]:
                self._stats["by_model"][model_name] = {
                    "calls": 0, "success": 0, "failed": 0,
                    "total_tokens": 0, "total_latency": 0.0,
                }
            model_stats = self._stats["by_model"][model_name]
            model_stats["calls"] += 1
            model_stats["total_latency"] += latency
            model_stats["total_tokens"] += tokens
            if success:
                model_stats["success"] += 1
            else:
                model_stats["failed"] += 1

    def get_stats(self) -> Dict[str, Any]:
        """获取统计数据"""
        with self.lock:
            stats = dict(self._stats)
            if stats["total_calls"] > 0:
                stats["avg_latency"] = round(
                    stats["total_latency"] / stats["total_calls"], 3
                )
                stats["success_rate"] = round(
                    stats["success_calls"] / stats["total_calls"], 4
                )
            else:
                stats["avg_latency"] = 0.0
                stats["success_rate"] = 0.0
            return stats

    def reset(self):
        """重置统计"""
        with self.lock:
            self._stats = {
                "total_calls": 0,
                "success_calls": 0,
                "failed_calls": 0,
                "total_tokens": 0,
                "total_latency": 0.0,
                "by_model": {},
            }


llm_metrics = LLMMetricsCollector()


def get_logger(name: str, **extra_fields) -> StructuredLoggerAdapter:
    """获取带额外字段的结构化日志器"""
    logger = logging.getLogger(name)
    return StructuredLoggerAdapter(logger, extra_fields)
