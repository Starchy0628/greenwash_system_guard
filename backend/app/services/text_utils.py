"""
文本处理工具函数
句子切分、环境关键词过滤、文本清洗、缩尾处理等
"""
import re
from typing import List, Tuple

# ============================================================
#  环境关键词（与论文一致的分类体系）
# ============================================================
# 强关键词：单独出现即可认定环保相关（具体、明确的环保术语）
STRONG_ENV_KEYWORDS = [
    "污染防治", "污染治理", "污染物减排", "废气治理", "废水治理", "固废处理",
    "危废处理", "噪声控制", "脱硫脱硝", "除尘", "污水处理", "垃圾处理",
    "节能减排", "清洁生产", "循环经济", "资源综合利用", "环保设施",
    "污染排放", "达标排放", "超低排放", "零排放", "减排目标",
    "资源利用", "资源节约", "节约用水", "节能", "能效提升", "能源效率",
    "清洁能源", "可再生能源", "太阳能", "风能", "水能", "生物质能",
    "地热能", "新能源", "绿色能源", "水资源", "节约资源", "资源回收",
    "绿色认证", "环境管理体系", "ISO14001", "ISO 14001", "环境标志",
    "绿色产品", "低碳产品", "节能产品", "环保产品", "生态设计",
    "绿色工厂", "绿色供应链", "绿色制造", "清洁生产审核", "环保认证",
    "碳足迹", "碳中和认证", "绿色建筑", "LEED认证", "BREEAM认证",
    "碳排放", "碳减排", "碳中和", "碳达峰", "碳交易", "碳市场",
    "碳核算", "碳汇", "碳捕集", "CCUS", "碳封存",
    "碳强度", "碳关税", "低碳转型", "绿色低碳", "双碳目标",
    "温室气体", "GHG", "二氧化碳", "甲烷", "氧化亚氮",
    "ESG", "环境社会治理", "生态保护", "生态文明",
    "环境保护", "环保投入", "环保投资", "环境责任", "生态修复",
    "生物多样性", "自然保护", "绿色金融", "绿色债券", "绿色信贷",
    "环保", "排污", "能耗", "节水", "节电", "绿化", "植树",
]

# 弱关键词：容易在非环保语境中出现，需配合强关键词或至少两个弱关键词才保留
WEAK_ENV_KEYWORDS = [
    "可持续发展", "社会责任", "企业社会责任", "CSR",
    "绿色发展", "绿色转型", "环境",
]

ALL_ENV_KEYWORDS = STRONG_ENV_KEYWORDS + WEAK_ENV_KEYWORDS

# 向后兼容：保持旧变量名，但内容基于新的关键词体系重新组织
ENVIRONMENT_KEYWORDS = {
    "pollution_prevention": [
        kw for kw in STRONG_ENV_KEYWORDS
        if any(x in kw for x in ["污染", "排放", "节能", "清洁生产", "循环", "固废", "危废", "脱硫", "除尘", "污水", "垃圾"])
    ],
    "resource_utilization": [
        kw for kw in STRONG_ENV_KEYWORDS
        if any(x in kw for x in ["资源", "能源", "能效", "清洁", "可再生", "太阳", "风能", "水能", "生物质", "地热", "新能源", "绿色能源"])
    ],
    "green_certification": [
        kw for kw in STRONG_ENV_KEYWORDS
        if any(x in kw for x in ["认证", "ISO", "标志", "绿色产品", "低碳产品", "节能产品", "环保产品", "生态设计", "绿色工厂", "绿色供应链", "绿色制造", "LEED", "BREEAM"])
    ],
    "carbon_management": [
        kw for kw in STRONG_ENV_KEYWORDS
        if any(x in kw for x in ["碳", "温室", "GHG", "二氧化碳", "甲烷", "氧化亚氮"])
    ],
    "esg_sustainability": [
        kw for kw in STRONG_ENV_KEYWORDS + WEAK_ENV_KEYWORDS
        if any(x in kw for x in ["ESG", "可持续", "社会责任", "CSR", "绿色", "生态", "环保", "环境", "生物", "自然", "绿色金融", "绿色债券", "绿色信贷"])
    ],
}

SENTENCE_SPLIT_PATTERN = r"(?<=[。！？；;!?])\s*"

MD_A_HEADINGS = [
    "管理层讨论与分析",
    "管理层讨论及分析",
    "经营情况讨论与分析",
    "董事会报告",
    "管理当局讨论与分析",
]


def is_valid_sentence(sentence: str) -> bool:
    """判断句子是否是有效的高质量文本（排除表格数据、乱码等）"""
    s = sentence.strip()
    if not s:
        return False

    # 1. 长度检查：过短或过长都排除（表格数据通常非常长）
    if len(s) < 10 or len(s) > 200:
        return False

    # 2. 中文字符比例：必须包含足够的中文
    chinese_chars = sum(1 for c in s if '\u4e00' <= c <= '\u9fff')
    if chinese_chars < 5:
        return False

    # 3. 数字比例检查：表格数据通常数字占比很高
    digit_count = sum(1 for c in s if c.isdigit())
    total = len(s)
    if digit_count / total > 0.4:
        return False

    # 4. 连续数字/逗号/小数点检查：超过15个连续字符认为是表格行
    max_consecutive = 0
    current = 0
    for c in s:
        if c.isdigit() or c in ',.，．':
            current += 1
            max_consecutive = max(max_consecutive, current)
        else:
            current = 0
    if max_consecutive > 15:
        return False

    return True


def split_sentences(text: str) -> List[str]:
    """按句末标点切分语句，并过滤掉表格数据等低质量句子"""
    if not text or not text.strip():
        return []
    text = text.strip()
    sentences = re.split(SENTENCE_SPLIT_PATTERN, text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]
    # 过滤表格数据等低质量句子
    sentences = [s for s in sentences if is_valid_sentence(s)]
    return sentences


def contains_env_keywords(sentence: str) -> Tuple[bool, List[str]]:
    """检查语句是否包含环境关键词

    逻辑：
    - 包含任意强关键词 → 直接认定环保相关
    - 无强关键词，但包含≥2个不同弱关键词 → 认定环保相关
    - 仅包含1个弱关键词 → 不认定（避免"社会责任""可持续发展"等宽泛词误匹配）
    """
    sent_lower = sentence.lower()
    found_strong = []
    found_weak = []

    for kw in STRONG_ENV_KEYWORDS:
        if kw.lower() in sent_lower:
            found_strong.append(kw)

    # 有强关键词直接通过
    if found_strong:
        return True, found_strong

    # 无强关键词时，检查弱关键词数量
    for kw in WEAK_ENV_KEYWORDS:
        if kw.lower() in sent_lower:
            found_weak.append(kw)

    # 至少2个不同弱关键词才通过
    if len(found_weak) >= 2:
        return True, found_weak

    return False, found_strong + found_weak


def filter_env_sentences(sentences: List[str]) -> Tuple[List[str], List[List[str]]]:
    """过滤出包含环境关键词的高质量语句（排除表格数据）"""
    env_sentences = []
    matched_keywords = []
    for sent in sentences:
        if not is_valid_sentence(sent):
            continue
        has_kw, kws = contains_env_keywords(sent)
        if has_kw:
            env_sentences.append(sent)
            matched_keywords.append(kws)
    return env_sentences, matched_keywords


def clean_text(text: str) -> str:
    """清洗文本：合并空白、去除零宽字符、过滤表格数据"""
    if not text:
        return ""
    # 移除制表符分隔的表格行（连续数字/金额的行）
    text = re.sub(r"[\t\|]+", " ", text)
    # 合并空白
    text = re.sub(r"\s+", " ", text)
    text = text.replace("\u3000", " ")
    text = text.replace("\xa0", " ")
    text = re.sub(r"[\u200b-\u200f\ufeff]", "", text)
    # 移除明显的表格数据片段（大量连续数字和逗号）
    text = re.sub(r"(\d{3,}[,.]){5,}", "", text)
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