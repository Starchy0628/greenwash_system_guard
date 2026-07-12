"""
PDF 解析服务 — 提取年报/ESG报告的文本内容

支持:
- 直接文本提取（PyPDF2 / pdfplumber）
- 表格提取并转自然语言描述（方案 A）
- MD&A / ESG 章节定位
- 关键环境指标提取（方案 D）
- 降级处理：无法解析时返回错误提示
"""
import io
import re
from typing import Tuple, Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class ParsedReport:
    """解析后的报告内容"""
    full_text: str = ""
    mda_text: str = ""  # 管理层讨论与分析章节
    esg_text: str = ""  # ESG / 环境相关章节
    table_sentences: List[str] = field(default_factory=list)  # 表格转自然语言的句子
    key_indicators: List[Dict[str, Any]] = field(default_factory=list)  # 关键环境指标
    report_type: str = "年报"  # 年报 / ESG
    company_name: str = ""


def extract_text_from_pdf(file_bytes: bytes, filename: str = "") -> Tuple[str, Optional[str]]:
    """
    从 PDF 字节流中提取文本
    
    Returns:
        (text, error_message) — 成功时 error_message 为 None
    """
    text = ""
    errors = []

    # 方法 1: PyPDF2
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                pages.append(page_text)
        if pages:
            text = "\n\n".join(pages)
            if len(text.strip()) > 200:
                return text, None
    except Exception as e:
        errors.append(f"PyPDF2: {e}")

    # 方法 2: pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    pages.append(page_text)
            if pages:
                text = "\n\n".join(pages)
                if len(text.strip()) > 200:
                    return text, None
    except Exception as e:
        errors.append(f"pdfplumber: {e}")

    # 方法 3: 尝试从原始字节中提取（用于简单文本PDF）
    try:
        raw = file_bytes.decode('utf-8', errors='ignore')
        # 提取流中的文本
        matches = re.findall(r'\(([^)]+)\)', raw)
        if matches:
            text = " ".join(m for m in matches if len(m) > 5)
            if len(text.strip()) > 200:
                return text, None
    except Exception as e:
        errors.append(f"raw: {e}")

    # 所有方法都失败
    if text.strip():
        return text, None  # 即使短也返回

    error_detail = "; ".join(errors) if errors else "无法解析PDF文件内容"
    return "", f"PDF解析失败：{error_detail}。请确认文件是否为文本型PDF（非扫描图片），或尝试使用其他格式。"


def infer_report_type(text: str, filename: str = "") -> str:
    """推断报告类型"""
    text_lower = text.lower()
    name_lower = filename.lower()

    # ESG 报告
    esg_keywords = ["esg", "环境、社会及管治", "环境、社会及治理", "可持续发展报告", "社会责任报告"]
    for kw in esg_keywords:
        if kw in text_lower[:500] or kw in name_lower:
            return "ESG"

    # 年报
    annual_keywords = ["年度报告", "年报", "annual report", "董事会报告", "管理层讨论与分析", "md&a"]
    for kw in annual_keywords:
        if kw in text_lower[:500] or kw in name_lower:
            return "年报"

    return "年报"  # 默认


def infer_company_from_text(text: str, filename: str = "") -> Optional[str]:
    """尝试从文本中推断企业名称"""
    # 常见模式：XXX股份有限公司 / XXX有限公司
    patterns = [
        r"([\u4e00-\u9fff]{2,8}(?:股份有限公司|有限责任公司|有限公司|集团))",
        r"公司名称[：:]\s*([\u4e00-\u9fff]{2,20}(?:股份有限公司|有限责任公司|有限公司|集团))",
    ]
    for pattern in patterns:
        match = re.search(pattern, text[:2000])
        if match:
            return match.group(1)
    return None


# ============================================================
#  表格提取与转换（方案 A：表格转自然语言句子）
# ============================================================

def extract_tables_from_pdf(file_bytes: bytes) -> List[List[List[str]]]:
    """
    使用 pdfplumber 提取 PDF 中的所有表格

    Returns:
        List[表格]，每个表格是 List[行]，每行是 List[单元格]
    """
    tables = []
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    for t in page_tables:
                        # 过滤过小的表格（至少2行2列）
                        if len(t) >= 2 and len(t[0]) >= 2:
                            tables.append(t)
    except Exception:
        pass
    return tables


def tables_to_sentences(tables: List[List[List[str]]]) -> List[str]:
    """
    将表格转换为自然语言句子（方案 A）

    转换规则:
    - 第一行视为表头
    - 每一行数据生成一句："<行标题>：<列1名称>为<值>，<列2名称>为<值>，..."
    - 过滤明显无关的表格（不含环境/能源/排放等关键词）
    """
    sentences = []
    env_keywords = [
        "环保", "环境", "排放", "碳", "能耗", "能源", "节能", "污染",
        "废水", "废气", "固废", "减排", "绿色", "生态", "可持续",
        "ESG", "社会责任", "投入", "治理", "修复",
    ]

    for table in tables:
        if len(table) < 2:
            continue

        headers = [str(h).strip() if h else "" for h in table[0]]
        # 判断表格是否与环境相关
        header_text = "".join(headers)
        first_col_text = "".join([str(row[0]).strip() if row and row[0] else "" for row in table[1:6]])
        table_preview = header_text + first_col_text

        is_env_related = any(kw in table_preview for kw in env_keywords)
        if not is_env_related:
            continue

        # 逐行转句子
        for row in table[1:]:
            if not row or len(row) < 2:
                continue

            row_label = str(row[0]).strip() if row[0] else ""
            if not row_label or len(row_label) > 30:
                continue

            parts = []
            for i in range(1, min(len(row), len(headers))):
                value = str(row[i]).strip() if row[i] else ""
                if not value or value in ["-", "/", "—", ""]:
                    continue
                col_name = headers[i] if i < len(headers) else f"指标{i}"
                if col_name:
                    parts.append(f"{col_name}为{value}")
                else:
                    parts.append(f"为{value}")

            if parts:
                sentence = f"{row_label}：{''.join(parts)}。"
                if 10 < len(sentence) < 300:
                    sentences.append(sentence)

    return sentences


# ============================================================
#  章节定位
# ============================================================

def extract_mda_section(text: str) -> str:
    """
    从年报全文中提取管理层讨论与分析（MD&A）章节

    常见标题模式：
    - 管理层讨论与分析
    - 经营情况讨论与分析
    - 第四节 经营情况讨论与分析
    - 第三节 管理层讨论与分析
    """
    # 起始标题模式
    start_patterns = [
        r"(?:第[一二三四五六七八九十]+节\s*)?管理层讨论与分析",
        r"(?:第[一二三四五六七八九十]+节\s*)?经营情况讨论与分析",
        r"Management's Discussion and Analysis",
        r"MD&A",
    ]

    # 结束标题模式（下一大节）
    end_patterns = [
        r"(?:第[一二三四五六七八九十]+节\s*)?公司治理",
        r"(?:第[一二三四五六七八九十]+节\s*)?环境和社会",
        r"(?:第[一二三四五六七八九十]+节\s*)?社会责任",
        r"(?:第[一二三四五六七八九十]+节\s*)?重要事项",
        r"(?:第[一二三四五六七八九十]+节\s*)?股份变动",
        r"(?:第[一二三四五六七八九十]+节\s*)?财务报告",
        r"(?:第[一二三四五六七八九十]+节\s*)?审计报告",
    ]

    # 找起始位置
    start_pos = -1
    for pat in start_patterns:
        m = re.search(pat, text[:50000])
        if m:
            start_pos = m.start()
            break

    if start_pos < 0:
        return ""

    # 在起始位置后找结束位置
    search_end = min(start_pos + 100000, len(text))
    end_pos = len(text)
    for pat in end_patterns:
        m = re.search(pat, text[start_pos:search_end])
        if m:
            pos = start_pos + m.start()
            if pos < end_pos and pos > start_pos + 500:
                end_pos = pos

    section = text[start_pos:end_pos].strip()
    return section if len(section) > 200 else ""


def extract_esg_section(text: str) -> str:
    """
    从报告中提取 ESG / 环境 / 社会责任相关章节
    """
    start_patterns = [
        r"(?:第[一二三四五六七八九十]+节\s*)?环境、社会及管治",
        r"(?:第[一二三四五六七八九十]+节\s*)?环境、社会及治理",
        r"(?:第[一二三四五六七八九十]+节\s*)?ESG",
        r"(?:第[一二三四五六七八九十]+节\s*)?社会责任",
        r"(?:第[一二三四五六七八九十]+节\s*)?环境与社会",
        r"(?:第[一二三四五六七八九十]+节\s*)?可持续发展",
        r"(?:第[一二三四五六七八九十]+节\s*)?环境保护",
    ]

    end_patterns = [
        r"(?:第[一二三四五六七八九十]+节\s*)?公司治理",
        r"(?:第[一二三四五六七八九十]+节\s*)?重要事项",
        r"(?:第[一二三四五六七八九十]+节\s*)?财务报告",
        r"(?:第[一二三四五六七八九十]+节\s*)?审计报告",
        r"(?:第[一二三四五六七八九十]+节\s*)?股份变动",
    ]

    start_pos = -1
    for pat in start_patterns:
        m = re.search(pat, text[:80000])
        if m:
            start_pos = m.start()
            break

    if start_pos < 0:
        return ""

    search_end = min(start_pos + 150000, len(text))
    end_pos = len(text)
    for pat in end_patterns:
        m = re.search(pat, text[start_pos:search_end])
        if m:
            pos = start_pos + m.start()
            if pos < end_pos and pos > start_pos + 500:
                end_pos = pos

    section = text[start_pos:end_pos].strip()
    return section if len(section) > 200 else ""


# ============================================================
#  关键环境指标提取（方案 D）
# ============================================================

def extract_key_env_indicators(text: str, table_sentences: List[str] = None) -> List[Dict[str, Any]]:
    """
    从文本和表格句子中提取关键环境指标（方案 D）

    返回结构化的指标列表：
    [
        {"name": "碳排放强度", "value": "0.52", "unit": "吨/万元", "year": "2024", "change": "-8.3%"},
        ...
    ]
    """
    indicators = []
    all_text = text
    if table_sentences:
        all_text += "\n" + "\n".join(table_sentences)

    # 定义要提取的关键指标及其匹配模式
    indicator_patterns = [
        # 碳排放类
        (r"碳排放强度[：:为是]?\s*([\d.]+)\s*(吨[/／]万元|t[/／]万元|吨 CO2[/／]万元|%)?", "碳排放强度"),
        (r"二氧化碳排放量[：:为是]?\s*([\d.]+)\s*(万吨|吨|吨 CO2)?", "二氧化碳排放量"),
        (r"碳排放量[：:为是]?\s*([\d.]+)\s*(万吨|吨)?", "碳排放量"),
        (r"温室气体排放总量[：:为是]?\s*([\d.]+)\s*(万吨|吨)?", "温室气体排放总量"),

        # 能耗类
        (r"综合能耗[：:为是]?\s*([\d.]+)\s*(万吨标准煤|吨标准煤|万 kWh|kWh|万千瓦时)?", "综合能耗"),
        (r"单位产值能耗[：:为是]?\s*([\d.]+)\s*(吨标准煤[/／]万元|千瓦时[/／]万元)?", "单位产值能耗"),
        (r"能源消耗总量[：:为是]?\s*([\d.]+)\s*(万吨标准煤|吨标准煤)?", "能源消耗总量"),
        (r"清洁能源占比[：:为是]?\s*([\d.]+)\s*%?", "清洁能源使用比例"),
        (r"可再生能源占比[：:为是]?\s*([\d.]+)\s*%?", "可再生能源比例"),

        # 排放物类
        (r"二氧化硫排放量[：:为是]?\s*([\d.]+)\s*(万吨|吨)?", "二氧化硫排放量"),
        (r"氮氧化物排放量[：:为是]?\s*([\d.]+)\s*(万吨|吨)?", "氮氧化物排放量"),
        (r"废水排放量[：:为是]?\s*([\d.]+)\s*(万吨|吨)?", "废水排放量"),
        (r"化学需氧量[：:为是]?\s*([\d.]+)\s*(万吨|吨)?", "化学需氧量(COD)"),

        # 环保投入类
        (r"环保投入[：:为是]?\s*([\d.]+)\s*(万元|亿元|万)?", "环保投入"),
        (r"环保投资[：:为是]?\s*([\d.]+)\s*(万元|亿元|万)?", "环保投资"),
        (r"环境治理投入[：:为是]?\s*([\d.]+)\s*(万元|亿元|万)?", "环境治理投入"),

        # 其他
        (r"绿色专利数量[：:为是]?\s*(\d+)\s*(项|个)?", "绿色专利数量"),
        (r"绿色工厂[：:为是]?\s*(\d+)\s*(家|个|座)?", "绿色工厂数量"),
    ]

    seen = set()
    for pattern, name in indicator_patterns:
        match = re.search(pattern, all_text)
        if match and name not in seen:
            value = match.group(1)
            unit = match.group(2) if match.lastindex and match.lastindex >= 2 else ""
            indicators.append({
                "name": name,
                "value": value,
                "unit": unit or "",
            })
            seen.add(name)

    return indicators


# ============================================================
#  完整解析入口
# ============================================================

def parse_report_full(file_bytes: bytes, filename: str = "") -> ParsedReport:
    """
    完整解析 PDF 报告

    Returns:
        ParsedReport 对象，包含全文、MD&A、ESG章节、表格句子、关键指标
    """
    result = ParsedReport()

    # 1. 提取全文
    text, error = extract_text_from_pdf(file_bytes, filename)
    if error or not text:
        return result

    result.full_text = text

    # 2. 判断报告类型
    result.report_type = infer_report_type(text, filename)

    # 3. 推断企业名称
    result.company_name = infer_company_from_text(text, filename) or ""

    # 4. 提取 MD&A 章节
    result.mda_text = extract_mda_section(text)

    # 5. 提取 ESG 章节
    result.esg_text = extract_esg_section(text)

    # 6. 提取表格并转句子
    try:
        tables = extract_tables_from_pdf(file_bytes)
        result.table_sentences = tables_to_sentences(tables)
    except Exception:
        result.table_sentences = []

    # 7. 提取关键环境指标
    try:
        result.key_indicators = extract_key_env_indicators(text, result.table_sentences)
    except Exception:
        result.key_indicators = []

    return result


def get_analysis_text(parsed: ParsedReport) -> str:
    """
    获取用于分析的文本（MD&A + ESG章节 + 表格句子）

    优先顺序：
    1. ESG报告的环境章节（如有）
    2. 年报的 MD&A 章节（如有）
    3. 全文
    再加上表格转成的自然语言句子
    """
    parts = []

    if parsed.esg_text and len(parsed.esg_text) > 500:
        parts.append(parsed.esg_text)

    if parsed.mda_text and len(parsed.mda_text) > 500:
        parts.append(parsed.mda_text)

    if not parts:
        parts.append(parsed.full_text)

    # 加上表格句子
    if parsed.table_sentences:
        parts.append("\n".join(parsed.table_sentences))

    return "\n\n".join(parts)