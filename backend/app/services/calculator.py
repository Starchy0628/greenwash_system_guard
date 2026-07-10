"""
企业漂绿指数合成模块
基于论文方法论的四阶段计算：
1. 语句级分类（实质性/描述性/非环保）
2. 描述性语句情感评分
3. 企业环境语调计算
4. 行业基准修正得到 GW 指数
"""
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field, asdict
from collections import defaultdict

from app.services.text_utils import calculate_winsorize, winsorize


@dataclass
class SentenceLevelResult:
    """语句级分析结果"""
    sentence: str
    classification: str
    classification_confidence: float
    sentiment_score: float = 0.0
    sentiment_std: float = 0.0
    matched_keywords: List[str] = field(default_factory=list)


@dataclass
class CompanyGreenwashResult:
    """企业漂绿分析结果"""
    company_name: str = ""
    stock_code: str = ""
    year: int = 0
    industry: str = ""

    total_sentences: int = 0
    env_sentences: int = 0
    substantive_count: int = 0
    descriptive_count: int = 0
    non_env_count: int = 0

    avg_env_tone: float = 0.0
    industry_median_tone: float = 0.0
    greenwash_index: float = 0.0

    sentence_results: List[SentenceLevelResult] = field(default_factory=list)

    def to_dict(self) -> Dict:
        d = asdict(self)
        d.pop("sentence_results", None)
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


class GreenwashIndexCalculator:
    """漂绿指数计算器"""

    def __init__(self):
        self._industry_data = defaultdict(list)

    def calculate_company_tone(
        self,
        sentence_results: List[SentenceLevelResult],
    ) -> float:
        """计算企业环境语调（仅描述性语句）"""
        descriptive_scores = [
            r.sentiment_score
            for r in sentence_results
            if r.classification == "descriptive"
        ]
        if not descriptive_scores:
            return 0.0
        avg_tone = sum(descriptive_scores) / len(descriptive_scores)
        return avg_tone

    def calculate_greenwash_index(
        self,
        company_tone: float,
        industry_median: float,
    ) -> float:
        """GW指数 = 企业环境语调 - 行业年度中位数（下限为0，不可为负值）"""
        return max(0.0, company_tone - industry_median)

    def compute_company_result(
        self,
        company_name: str,
        year: int,
        sentence_results: List[SentenceLevelResult],
        stock_code: str = "",
        industry: str = "",
    ) -> CompanyGreenwashResult:
        """计算单个企业的完整结果"""
        result = CompanyGreenwashResult(
            company_name=company_name,
            stock_code=stock_code,
            year=year,
            industry=industry,
            sentence_results=sentence_results,
        )

        result.total_sentences = len(sentence_results)
        result.env_sentences = len(sentence_results)

        for r in sentence_results:
            if r.classification == "substantive":
                result.substantive_count += 1
            elif r.classification == "descriptive":
                result.descriptive_count += 1
            elif r.classification == "non_environmental":
                result.non_env_count += 1

        result.avg_env_tone = self.calculate_company_tone(sentence_results)
        return result

    def compute_industry_benchmark(
        self,
        company_results: List[CompanyGreenwashResult],
        year: int = None,
    ) -> Dict[str, float]:
        """计算行业年度语调中位数"""
        industry_tones = defaultdict(list)

        for result in company_results:
            if year and result.year != year:
                continue
            key = result.industry or "unknown"
            industry_tones[key].append(result.avg_env_tone)

        industry_medians = {}
        for industry, tones in industry_tones.items():
            if tones:
                sorted_tones = sorted(tones)
                n = len(sorted_tones)
                if n % 2 == 0:
                    median = (sorted_tones[n // 2 - 1] + sorted_tones[n // 2]) / 2
                else:
                    median = sorted_tones[n // 2]
                industry_medians[industry] = median
            else:
                industry_medians[industry] = 0.0

        return industry_medians

    def finalize_results(
        self,
        company_results: List[CompanyGreenwashResult],
        winsorize_threshold: float = 0.01,
    ) -> List[CompanyGreenwashResult]:
        """应用缩尾处理和行业基准修正，最终确定 GW 指数"""
        all_tones = [r.avg_env_tone for r in company_results if r.descriptive_count > 0]

        if all_tones:
            lower, upper = calculate_winsorize(
                all_tones,
                lower=winsorize_threshold,
                upper=1 - winsorize_threshold,
            )
        else:
            lower, upper = -1.0, 1.0

        for year in set(r.year for r in company_results):
            year_results = [r for r in company_results if r.year == year]
            industry_medians = self.compute_industry_benchmark(year_results, year=year)

            for result in year_results:
                result.avg_env_tone = winsorize(result.avg_env_tone, lower, upper)
                industry = result.industry or "unknown"
                result.industry_median_tone = industry_medians.get(industry, 0.0)
                result.greenwash_index = self.calculate_greenwash_index(
                    result.avg_env_tone,
                    result.industry_median_tone,
                )

        return company_results

    def get_summary_stats(self, results: List[CompanyGreenwashResult]) -> Dict:
        """汇总统计"""
        if not results:
            return {}

        indices = [r.greenwash_index for r in results]
        tones = [r.avg_env_tone for r in results]

        return {
            "total_companies": len(results),
            "greenwash_index": {
                "mean": sum(indices) / len(indices),
                "median": sorted(indices)[len(indices) // 2],
                "min": min(indices),
                "max": max(indices),
                "positive_ratio": sum(1 for i in indices if i > 0) / len(indices),
            },
            "avg_env_tone": {
                "mean": sum(tones) / len(tones),
                "median": sorted(tones)[len(tones) // 2],
                "min": min(tones),
                "max": max(tones),
            },
            "classification_distribution": {
                "substantive_ratio": sum(r.substantive_count for r in results)
                / max(1, sum(r.env_sentences for r in results)),
                "descriptive_ratio": sum(r.descriptive_count for r in results)
                / max(1, sum(r.env_sentences for r in results)),
                "non_env_ratio": sum(r.non_env_count for r in results)
                / max(1, sum(r.env_sentences for r in results)),
            },
        }