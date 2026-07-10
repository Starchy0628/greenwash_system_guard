"""Mock 模式服务 — 模拟三模型分析流程，无需 API Key"""
import random
from typing import Dict, List, Tuple

from app.services.text_utils import ALL_ENV_KEYWORDS, split_sentences


# 模拟语句分类结果（用于生成演示数据）
MOCK_CATEGORIES = {
    "substantive": [
        "公司本年度环保投入达{金额}万元，同比增长{百分比}%。",
        "通过ISO14001环境管理体系认证，{指标}排放量减少{百分比}%。",
        "单位产值能耗同比下降{百分比}%，完成节能减排目标。",
        "报告期内投入{金额}万元用于污染防治设施建设。",
        "清洁能源使用比例提升至{百分比}%，碳排放强度降低{百分比}%。",
    ],
    "descriptive": [
        "公司高度重视环境保护工作，积极履行企业社会责任。",
        "我们持续推动绿色低碳转型，实现可持续发展。",
        "公司致力于打造绿色工厂，践行生态文明理念。",
        "积极推进环境治理工作，提升绿色发展水平。",
        "坚持绿色发展理念，为美丽中国贡献力量。",
    ],
    "non_env": [
        "公司全年实现营业收入稳步增长，净利润同比增长。",
        "董事会审议通过了年度利润分配方案。",
        "公司持续加大研发投入，提升核心竞争力。",
        "报告期内公司完成了定向增发融资事项。",
        "公司治理结构持续优化，内部控制体系不断完善。",
    ],
}


def mock_classify_sentence(sentence: str) -> Tuple[str, str, str, dict]:
    """模拟三模型对一条语句的分类"""
    is_env = any(kw in sentence for kw in ALL_ENV_KEYWORDS[:20])
    if not is_env:
        results = {"deepseek": "non_env", "qwen": "non_env", "pangu": "non_env"}
        return "non_env", "unanimous", 1.0, results

    vote = random.choice(["substantive", "descriptive"])
    confusion = random.random()

    if confusion < 0.85:  # 85%全票通过
        results = {"deepseek": vote, "qwen": vote, "pangu": vote}
        return vote, "unanimous", 1.0, results
    elif confusion < 0.97:  # 12%多数通过
        alt = "descriptive" if vote == "substantive" else "substantive"
        results = {"deepseek": vote, "qwen": vote, "pangu": alt}
        return vote, "majority", 0.67, results
    else:  # 3%完全分歧
        results = {
            "deepseek": "substantive",
            "qwen": "descriptive",
            "pangu": "non_env",
        }
        return "dispute", "full_divergence", 0.33, results


def mock_sentiment_score(sentence: str) -> Tuple[float, float]:
    """模拟情感打分"""
    positive_words = ["成效", "显著", "积极", "推动", "提升", "绿色", "发展", "贡献", "引领", "先进"]
    neutral_words = ["改进", "持续", "优化", "管理", "治理", "履行"]
    negative_words = ["不足", "挑战", "有待", "仍需", "困难", "问题"]

    base = 0.5
    for w in positive_words:
        if w in sentence:
            base += 0.15
    for w in neutral_words:
        if w in sentence:
            base += 0.05
    for w in negative_words:
        if w in sentence:
            base -= 0.2

    score = max(-1.0, min(1.0, base + random.uniform(-0.15, 0.15)))
    std = round(random.uniform(0.01, 0.08), 4)
    return round(score, 4), std


def run_mock_analysis(text: str, industry: str = "白酒") -> dict:
    """
    执行完整的 Mock 分析流程
    流程：句子切分 → 关键词过滤 → 三模型分类(模拟) → 情感打分 → 行业基准修正 → GW指数
    """
    # 1. 句子切分
    raw_sentences = split_sentences(text)
    if not raw_sentences:
        raw_sentences = [text]

    # 2. 环境关键词过滤
    env_sentences = []
    for s in raw_sentences:
        if any(kw in s for kw in ALL_ENV_KEYWORDS):
            env_sentences.append(s)
    if not env_sentences:
        env_sentences = raw_sentences

    # 3. 三模型分类（模拟）
    sentence_results = []
    substantive_count = 0
    descriptive_count = 0
    dispute_count = 0
    unanimous_count = 0
    majority_count = 0
    divergence_count = 0

    for i, sent in enumerate(env_sentences):
        category, vote_type, confidence, model_results = mock_classify_sentence(sent)
        sentiment = 0.0
        sentiment_std = 0.0
        if category == "descriptive":
            sentiment, sentiment_std = mock_sentiment_score(sent)

        if category == "substantive":
            substantive_count += 1
        elif category == "descriptive":
            descriptive_count += 1
        elif category == "dispute":
            dispute_count += 1

        if vote_type == "unanimous":
            unanimous_count += 1
        elif vote_type == "majority":
            majority_count += 1
        else:
            divergence_count += 1

        sentence_results.append({
            "sentence_text": sent,
            "sentence_order": i + 1,
            "deepseek_result": model_results["deepseek"],
            "qwen_result": model_results["qwen"],
            "pangu_result": model_results["pangu"],
            "final_category": category,
            "vote_type": vote_type,
            "confidence": confidence,
            "sentiment_score": sentiment,
            "sentiment_std": sentiment_std,
            "needs_review": vote_type == "full_divergence",
        })

    # 4. 计算环境语调（仅描述性语句）
    descriptive_scores = [
        s["sentiment_score"] for s in sentence_results
        if s["final_category"] == "descriptive" and s["sentiment_score"] is not None
    ]
    tone_score = round(sum(descriptive_scores) / len(descriptive_scores), 6) if descriptive_scores else 0.0

    # 5. 行业基准（模拟）
    industry_median = _get_mock_industry_median(industry)
    gw_index = round(tone_score - industry_median, 6)

    # 6. Fleiss' Kappa（模拟）
    total = unanimous_count + majority_count + divergence_count
    if total > 0:
        kappa = round(0.84 + random.uniform(-0.03, 0.03), 4)
    else:
        kappa = 0.84

    return {
        "total_sentences": len(raw_sentences),
        "env_sentences": len(env_sentences),
        "substantive_count": substantive_count,
        "descriptive_count": descriptive_count,
        "non_env_count": len(raw_sentences) - len(env_sentences),
        "tone_score": tone_score,
        "industry_median_tone": industry_median,
        "gw_index": gw_index,
        "risk_level": "正常",  # 稍后由行业基准服务动态计算
        "fleiss_kappa": kappa,
        "dispute_count": dispute_count,
        "unanimous_count": unanimous_count,
        "majority_count": majority_count,
        "divergence_count": divergence_count,
        "sentence_results": sentence_results,
    }


def _get_mock_industry_median(industry: str) -> float:
    """获取模拟的行业语调中位数"""
    medians = {
        "白酒": 0.65, "食品饮料": 0.55, "电池": 0.50,
        "新能源汽车": 0.48, "房地产": 0.42, "能源化工": 0.35,
        "银行": 0.30, "光伏": 0.52, "化工": 0.40, "电子": 0.45,
    }
    base = medians.get(industry, 0.45)
    return round(base + random.uniform(-0.03, 0.03), 6)