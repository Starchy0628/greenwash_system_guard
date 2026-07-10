"""
数据清洗与标准化模块
对提取的年报文本进行清洗、去噪、标准化处理
"""
import re
import hashlib
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from app.services.text_utils import clean_text, split_sentences, filter_env_sentences


@dataclass
class CleaningStats:
    """清洗统计"""
    original_sentences: int = 0
    after_cleaning: int = 0
    duplicates_removed: int = 0
    too_short_removed: int = 0
    noise_removed: int = 0
    env_sentences: int = 0


class DataCleaner:
    """数据清洗器 — 去噪、去重、标准化"""

    def __init__(self, min_sentence_length: int = 8, max_sentence_length: int = 500):
        self.min_sentence_length = min_sentence_length
        self.max_sentence_length = max_sentence_length
        self.noise_patterns = [
            re.compile(r"^[第\d\s章节部分篇]+[:：]?\s*$"),
            re.compile(r"^\d+[\.、]?\s*$"),
            re.compile(r"^[一二三四五六七八九十]+[、\.]{0,2}\s*$"),
            re.compile(r"^[-_\s=*•·]+$"),
            re.compile(r"^[图表]\s*\d+"),
            re.compile(r"^(?:单位|金额|币种|人民币|元)$"),
            re.compile(r"^[\d\s,.%]+$"),
            re.compile(r"^(?:续表|接上页|下转第|上接第).*$"),
        ]
        self.stats = CleaningStats()

    def clean_sentences(self, sentences: List[str]) -> Tuple[List[str], CleaningStats]:
        """清洗语句列表"""
        self.stats = CleaningStats(original_sentences=len(sentences))
        cleaned = []
        seen_hashes = set()

        for sent in sentences:
            if not self._pass_length_check(sent):
                self.stats.too_short_removed += 1
                continue

            if self._is_noise(sent):
                self.stats.noise_removed += 1
                continue

            cleaned_sent = self._normalize_text(sent)
            sent_hash = hashlib.md5(cleaned_sent.encode("utf-8")).hexdigest()
            if sent_hash in seen_hashes:
                self.stats.duplicates_removed += 1
                continue
            seen_hashes.add(sent_hash)

            cleaned.append(cleaned_sent)

        self.stats.after_cleaning = len(cleaned)
        return cleaned, self.stats

    def clean_full_text(self, text: str) -> Tuple[str, CleaningStats]:
        """清洗完整文本"""
        cleaned_text = clean_text(text)
        sentences = split_sentences(cleaned_text)
        cleaned_sentences, stats = self.clean_sentences(sentences)
        return "\n".join(cleaned_sentences), stats

    def _pass_length_check(self, sentence: str) -> bool:
        length = len(sentence.strip())
        return self.min_sentence_length <= length <= self.max_sentence_length

    def _is_noise(self, sentence: str) -> bool:
        sent = sentence.strip()
        for pattern in self.noise_patterns:
            if pattern.match(sent):
                return True
        return False

    def _normalize_text(self, text: str) -> str:
        text = clean_text(text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()


class DataStandardizer:
    """数据标准化器 — 数值单位转换、企业名称标准化"""

    def __init__(self):
        self.unit_mapping = {
            "万元": 10000, "亿元": 100000000, "万": 10000, "亿": 100000000,
            "元": 1, "吨": 1, "万吨": 10000, "千克": 0.001, "克": 0.000001,
            "千瓦时": 1, "万kWh": 10000, "MWh": 1000, "GWh": 1000000,
        }

    def standardize_numeric(self, value_str: str, target_unit: str = None) -> Optional[float]:
        """标准化数值（含单位转换）"""
        try:
            value_str = value_str.strip().replace(",", "").replace("，", "")
            number_match = re.search(r"[\d.]+", value_str)
            if not number_match:
                return None
            number = float(number_match.group())
            for unit_str, multiplier in self.unit_mapping.items():
                if unit_str in value_str:
                    number *= multiplier
                    break
            return number
        except (ValueError, TypeError):
            return None

    def standardize_company_name(self, name: str) -> str:
        """标准化企业名称（去除后缀）"""
        if not name:
            return ""
        name = name.strip()
        suffixes = [
            "股份有限公司", "有限责任公司", "有限公司",
            "集团有限公司", "集团公司", "集团",
            "股份公司", "股份",
        ]
        for suffix in suffixes:
            if name.endswith(suffix):
                name = name[: -len(suffix)]
                break
        return name.strip()

    def standardize_stock_code(self, code: str) -> str:
        """标准化股票代码（6位数字）"""
        if not code:
            return ""
        code = re.sub(r"[^\d]", "", code)
        if len(code) == 6:
            return code
        return code[:6] if len(code) > 6 else code.zfill(6)