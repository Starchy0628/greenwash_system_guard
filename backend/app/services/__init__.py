"""服务层包 — 业务逻辑、算法实现、外部集成"""

from app.services.text_utils import (
    split_sentences,
    filter_env_sentences,
    clean_text,
    ALL_ENV_KEYWORDS,
    ENVIRONMENT_KEYWORDS,
)
from app.services.llm_client import (
    BaseLLMClient,
    MockLLMClient,
    OpenAICompatibleClient,
    LLMResponse,
    create_llm_client,
    DEFAULT_LLM_MODELS,
    CLASSIFICATION_PROMPT,
    SENTIMENT_PROMPT,
    ClassificationType,
    VoteResultType,
)
from app.services.classifier import SentenceClassifier, SentenceClassificationResult
from app.services.sentiment import SentimentAnalyzer, SentimentResult
from app.services.fusion import (
    MajorityVotingFuser,
    EnsembleAveragingFuser,
    FusionResult,
)
from app.services.calculator import (
    GreenwashIndexCalculator,
    CompanyGreenwashResult,
    SentenceLevelResult,
)
from app.services.parser import AnnualReportParser
from app.services.cleaner import DataCleaner, DataStandardizer, CleaningStats
from app.services.mock_service import run_mock_analysis
from app.services.industry_service import (
    compute_industry_benchmarks,
    update_risk_levels,
    get_warn_threshold,
)