"""Pydantic 数据校验模型"""

# ---- 企业相关 ----
from pydantic import BaseModel


class CompanyBase(BaseModel):
    stock_code: str
    company_name: str
    industry: str
    short_name: str | None = None


class CompanyResponse(CompanyBase):
    id: int
    is_active: bool
    has_analysis: bool = False
    latest_gw_index: float | None = None
    latest_risk_level: str | None = None

    class Config:
        from_attributes = True


class CompanySearchResult(BaseModel):
    id: int
    stock_code: str
    company_name: str
    industry: str
    latest_gw_index: float | None = None
    latest_risk_level: str | None = None


# ---- 分析记录 ----
class AnalysisRecordResponse(BaseModel):
    id: int
    company_id: int
    company_name: str = ""
    stock_code: str = ""
    industry: str = ""
    year: int
    data_source_type: str
    source_file_name: str | None = None
    total_sentences: int
    env_sentences: int
    substantive_count: int
    descriptive_count: int
    non_env_count: int
    tone_score: float | None = None
    industry_median_tone: float | None = None
    gw_index: float | None = None
    risk_level: str = "正常"
    fleiss_kappa: float | None = None
    dispute_count: int = 0
    analysis_status: str = "completed"
    analyzed_at: str | None = None

    class Config:
        from_attributes = True


# ---- 语句 ----
class SentenceResponse(BaseModel):
    id: int
    sentence_text: str
    sentence_order: int | None = None
    deepseek_result: str | None = None
    qwen_result: str | None = None
    glm_result: str | None = None
    final_category: str | None = None
    vote_type: str | None = None
    confidence: float | None = None
    sentiment_score: float | None = None
    needs_review: bool = False

    class Config:
        from_attributes = True


# ---- 仪表盘 ----
class DashboardMetrics(BaseModel):
    fleiss_kappa: float = 0.84
    human_agreement: float = 94.22
    total_sentences: int = 0
    total_companies: int = 0
    warn_threshold: float = 0.0


class RiskThresholdInfo(BaseModel):
    threshold: float
    total_companies: int
    warn_count: int
    normal_count: int


# ---- 关注列表 ----
class WatchlistItemResponse(BaseModel):
    company_id: int
    stock_code: str
    company_name: str
    industry: str
    latest_gw_index: float | None = None
    latest_risk_level: str | None = None
    added_at: str | None = None


# ---- 通用 ----
class SearchQuery(BaseModel):
    q: str


class AnalysisQuery(BaseModel):
    stock_code: str | None = None
    company_name: str | None = None
    force_refresh: bool = False


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int = 1
    page_size: int = 20