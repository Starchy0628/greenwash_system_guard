"""
巨潮资讯爬虫 — 从 cninfo.com.cn 抓取上市公司年报/ESG报告

功能:
1. 根据股票代码搜索公告列表
2. 下载 PDF 文件
3. 支持年报和 ESG 报告两种类型
"""
import re
import time
import requests
from typing import Optional, Tuple, List
from dataclasses import dataclass


CNINFO_SEARCH_URL = "http://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_BASE = "http://www.cninfo.com.cn"


@dataclass
class AnnouncementInfo:
    """公告信息"""
    title: str
    adj_url: str
    sec_code: str
    sec_name: str
    announcement_time: str
    announcement_type: str = "年报"


def search_announcements(
    stock_code: str,
    year: int = None,
    announcement_type: str = "annual",
    page_size: int = 30,
) -> List[AnnouncementInfo]:
    """
    搜索巨潮资讯公告

    Args:
        stock_code: 股票代码（如 600519）
        year: 年份（可选）
        announcement_type: annual=年报, esg=ESG报告
        page_size: 每页数量

    Returns:
        公告列表
    """
    # 确定板块：6开头沪市，0/3开头深市
    if stock_code.startswith("6"):
        column = "sse"
    else:
        column = "szse"

    # 板块分类
    if announcement_type == "annual":
        plate = "szsh"
        category = "category_ndbg_szsh"
    elif announcement_type == "esg":
        plate = "szsh"
        category = "category_shrzg_szsh"
    else:
        plate = "szsh"
        category = "category_ndbg_szsh"

    params = {
        "pageNum": 1,
        "pageSize": page_size,
        "column": column,
        "tabName": "fulltext",
        "plate": plate,
        "stock": f"{stock_code},{column}",
        "searchkey": "",
        "secid": "",
        "category": category,
        "trade": "",
        "seDate": "",
        "sortName": "time",
        "sortType": "desc",
        "isHLtitle": "true",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "http://www.cninfo.com.cn",
    }

    try:
        resp = requests.post(
            CNINFO_SEARCH_URL,
            data=params,
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        announcements = data.get("announcements", [])
        results = []

        for ann in announcements:
            title = ann.get("announcementTitle", "")
            adj_url = ann.get("adjunctUrl", "")
            sec_code = ann.get("secCode", "")
            sec_name = ann.get("secName", "")
            ann_time = str(ann.get("announcementTime", ""))

            # 按年份过滤
            if year:
                if str(year) not in title and str(year) not in ann_time[:4]:
                    continue

            # 过滤摘要版（取全文版）
            if "摘要" in title or "摘要版" in title:
                continue

            results.append(AnnouncementInfo(
                title=title,
                adj_url=adj_url,
                sec_code=sec_code,
                sec_name=sec_name,
                announcement_time=ann_time,
                announcement_type=announcement_type,
            ))

        return results

    except Exception as e:
        print(f"搜索公告失败: {e}")
        return []


def download_pdf(announcement: AnnouncementInfo) -> Tuple[Optional[bytes], Optional[str]]:
    """
    下载公告 PDF

    Returns:
        (pdf_bytes, error_message)
    """
    if not announcement.adj_url:
        return None, "公告地址为空"

    url = f"{CNINFO_BASE}/{announcement.adj_url}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "http://www.cninfo.com.cn/",
        "Accept": "application/pdf, */*",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=60)
        resp.raise_for_status()
        content = resp.content

        if len(content) < 1000:
            return None, "PDF 文件过小，可能下载失败"

        return content, None

    except Exception as e:
        return None, f"下载 PDF 失败: {str(e)}"


def fetch_latest_annual_report(
    stock_code: str,
    year: int = None,
) -> Tuple[Optional[bytes], Optional[str], Optional[AnnouncementInfo]]:
    """
    获取最新年报 PDF

    Returns:
        (pdf_bytes, error, announcement_info)
    """
    # 搜索年报
    anns = search_announcements(stock_code, year=year, announcement_type="annual")

    if not anns:
        return None, f"未找到 {stock_code} 的年度报告", None

    # 取第一条（最新的）
    ann = anns[0]
    pdf_bytes, error = download_pdf(ann)

    if error:
        return None, error, None

    return pdf_bytes, None, ann


def fetch_latest_esg_report(
    stock_code: str,
    year: int = None,
) -> Tuple[Optional[bytes], Optional[str], Optional[AnnouncementInfo]]:
    """
    获取最新 ESG/社会责任报告 PDF

    Returns:
        (pdf_bytes, error, announcement_info)
    """
    # 搜索 ESG 报告（社会责任报告）
    anns = search_announcements(stock_code, year=year, announcement_type="esg")

    if not anns:
        return None, f"未找到 {stock_code} 的 ESG/社会责任报告", None

    # 取第一条（最新的）
    ann = anns[0]
    pdf_bytes, error = download_pdf(ann)

    if error:
        return None, error, None

    return pdf_bytes, None, ann


def fetch_report_with_fallback(
    stock_code: str,
    year: int = None,
) -> Tuple[Optional[bytes], Optional[str], Optional[AnnouncementInfo]]:
    """
    获取企业最新披露文本，ESG 报告优先，无则退回年报

    Returns:
        (pdf_bytes, error, announcement_info)
    """
    # 先尝试 ESG 报告
    pdf_bytes, error, ann = fetch_latest_esg_report(stock_code, year=year)
    if pdf_bytes:
        return pdf_bytes, None, ann

    # ESG 失败，尝试年报
    pdf_bytes2, error2, ann2 = fetch_latest_annual_report(stock_code, year=year)
    if pdf_bytes2:
        return pdf_bytes2, None, ann2

    # 都失败
    combined_error = f"ESG报告: {error}; 年报: {error2}"
    return None, combined_error, None
