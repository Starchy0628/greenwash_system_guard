"""核心配置管理 — 从 .env 读取所有配置"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # 应用模式
    app_mode: str = "mock"  # mock / real

    # 数据库
    database_url: str = "sqlite:///./data/db/greenwash_guard.db"

    # API 配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # LLM API Keys
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-reasoner"

    qwen_api_key: str = ""
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-max"

    glm_api_key: str = ""
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    glm_model: str = "glm-ocr"
    glm_fallback_model: str = "glm-4.7"

    # 前端地址（CORS）
    frontend_url: str = "http://localhost:5173"

    # 日志级别
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # 搜索 .env 的路径优先级
        @classmethod
        def customise_sources(cls, init_settings, env_settings, file_secret_settings):
            return env_settings, init_settings, file_secret_settings


@lru_cache()
def get_settings() -> Settings:
    # 尝试多个路径加载 .env
    env_paths = [
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(".env"),
    ]
    for p in env_paths:
        if p.exists():
            from dotenv import load_dotenv
            load_dotenv(p, override=True)
            break
    return Settings()