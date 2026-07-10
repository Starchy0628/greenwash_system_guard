"""
PDF 解析服务 — 提取年报/ESG报告的文本内容

支持:
- 直接文本提取（PyPDF2 / pdfplumber）
- 降级处理：无法解析时返回错误提示
"""
import io
import re
from typing import Tuple, Optional


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