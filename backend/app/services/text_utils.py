"""
文本处理工具函数
句子切分、环境关键词过滤、文本清洗、缩尾处理等
"""
import re
from typing import List, Tuple

# ============================================================
#  环境关键词（与论文一致的分类体系）
# ============================================================
ENVIRONMENT_KEYWORDS = {
    "pollution_prevention": [
        "污染防治", "污染治理", "污染物减排", "废气治理", "废水治理", "固废处理",
        "危废处理", "噪声控制", "脱硫脱硝", "除尘", "污水处理", "垃圾处理",
        "节能减排", "清洁生产", "循环经济", "资源综合利用", "环保设施",
        "污染排放", "达标排放", "超低排放", "零排放", "减排目标",
    ],
    "resource_utilization": [
        "资源利用", "资源节约", "节约用水", "节能", "能效提升", "能源效率",
        "清洁能源", "可再生能源", "太阳能", "风能", "水能", "生物质能",
        "地热能", "新能源", "绿色能源", "水资源", "土地资源", "矿产资源",
        "节约资源", "资源回收", "资源再生", "原材料节约",
    ],
    "green_certification": [
        "绿色认证", "环境管理体系", "ISO14001", "ISO 14001", "环境标志",
        "绿色产品", "低碳产品", "节能产品", "环保产品", "生态设计",
        "绿色工厂", "绿色供应链", "绿色制造", "清洁生产审核", "环保认证",
        "碳足迹", "碳中和认证", "绿色建筑", "LEED认证", "BREEAM认证",
    ],
    "carbon_management": [
        "碳排放", "碳减排", "碳中和", "碳达峰", "碳交易", "碳市场",
        "碳核算", "碳足迹", "碳汇", "碳捕集", "CCUS", "碳封存",
        "碳强度", "碳关税", "低碳转型", "绿色低碳", "双碳目标",
        "温室气体", "GHG", "二氧化碳", "甲烷", "氧化亚氮",
    ],
    "esg_sustainability": [
        "ESG", "环境社会治理", "可持续发展", "社会责任", "企业社会责任",
        "CSR", "绿色发展", "生态保护", "生态文明", "绿色转型",
        "环境保护", "环保投入", "环保投资", "环境责任", "生态修复",
        "生物多样性", "自然保护", "绿色金融", "绿色债券", "绿色信贷",
    ],
}

ALL_ENV_KEYWORDS = [kw for kws in ENVIRONMENT_KEYWORDS.values() for kw in kws]

SENTENCE_SPLIT_PATTERN = r"(?<=[。！？；;!?])\s*"

MD_A_HEADINGS = [
    "管理层讨论与分析",
    "管理层讨论及分析",
    "经营情况讨论与分析",
    "董事会报告",
    "管理当局讨论与分析",
]


def split_sentences(text: str) -> List[str]:
    """按句末标点切分语句"""
    if not text or not text.strip():
        return []
    text = text.strip()
    sentences = re.split(SENTENCE_SPLIT_PATTERN, text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
    return sentences


def contains_env_keywords(sentence: str) -> Tuple[bool, List[str]]:
    """检查语句是否包含环境关键词"""
    found_keywords = []
    for kw in ALL_ENV_KEYWORDS:
        if kw.lower() in sentence.lower():
            found_keywords.append(kw)
    return len(found_keywords) > 0, found_keywords


def filter_env_sentences(sentences: List[str]) -> Tuple[List[str], List[List[str]]]:
    """过滤出包含环境关键词的语句"""
    env_sentences = []
    matched_keywords = []
    for sent in sentences:
        has_kw, kws = contains_env_keywords(sent)
        if has_kw:
            env_sentences.append(sent)
            matched_keywords.append(kws)
    return env_sentences, matched_keywords


def clean_text(text: str) -> str:
    """清洗文本：合并空白、去除零宽字符"""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\u3000", " ")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[\u200b-\u200f\ufeff]", "", text)
    text = text.strip()
    return text


def calculate_winsorize(values: List[float], lower: float = 0.01, upper: float = 0.99) -> Tuple[float, float]:
    """计算缩尾处理的上下界"""
    if not values:
        return 0.0, 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    lower_idx = int(n * lower)
    upper_idx = int(n * upper)
    lower_bound = sorted_vals[max(0, lower_idx)]
    upper_bound = sorted_vals[min(n - 1, upper_idx)]
    return lower_bound, upper_bound


def winsorize(value: float, lower_bound: float, upper_bound: float) -> float:
    """缩尾处理"""
    if value < lower_bound:
        return lower_bound
    elif value > upper_bound:
        return upper_bound
    return value