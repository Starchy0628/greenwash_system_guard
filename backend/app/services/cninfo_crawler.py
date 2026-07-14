"""
巨潮资讯爬虫 — 从 cninfo.com.cn 抓取上市公司年报

功能:
1. 根据股票代码搜索公告列表
2. 下载 PDF 文件
3. 支持年报下载
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


def _get_column(stock_code: str) -> str:
    """根据股票代码判断板块：6开头沪市，0/3开头深市"""
    if stock_code.startswith("6"):
        return "sse"
    else:
        return "szse"


def search_announcements(
    stock_code: str,
    stock_name: str = None,
    year: int = None,
    announcement_type: str = "annual",
    page_size: int = 30,
) -> List[AnnouncementInfo]:
    """
    搜索巨潮资讯公告

    Args:
        stock_code: 股票代码（如 600519）
        stock_name: 股票名称（用于辅助搜索，可选）
        year: 年份（可选）
        announcement_type: annual=年报
        page_size: 每页数量

    Returns:
        公告列表
    """
    column = _get_column(stock_code)

    # 根据公告类型确定搜索策略（仅年报）
    category = "category_ndbg_szsh"
    search_key = stock_code

    params = {
        "pageNum": 1,
        "pageSize": page_size,
        "column": column,
        "tabName": "fulltext",
        "plate": "szsh",
        "stock": "",
        "searchkey": search_key,
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

        announcements = data.get("announcements", []) or []
        results = []

        for ann in announcements:
            title = ann.get("announcementTitle", "").replace("<em>", "").replace("</em>", "")
            adj_url = ann.get("adjunctUrl", "")
            sec_code = ann.get("secCode", "")
            sec_name = ann.get("secName", "").replace("<em>", "").replace("</em>", "")
            ann_time = str(ann.get("announcementTime", ""))

            # 精确匹配股票代码（防止关键词搜索返回其他公司）
            if sec_code != stock_code:
                continue

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

        # 排序：优先中文版（排除英文版），然后按时间倒序
        def _sort_key(ann):
            is_english = "英文" in ann.title or "English" in ann.title or "EN" in ann.title
            return (1 if is_english else 0, -int(ann.announcement_time) if ann.announcement_time.isdigit() else 0)

        results.sort(key=_sort_key)

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
    stock_name: str = None,
    year: int = None,
) -> Tuple[Optional[bytes], Optional[str], Optional[AnnouncementInfo]]:
    """
    获取最新年报 PDF

    Returns:
        (pdf_bytes, error, announcement_info)
    """
    anns = search_announcements(stock_code, stock_name=stock_name, year=year, announcement_type="annual")

    if not anns:
        return None, f"未找到 {stock_code} 的年度报告", None

    ann = anns[0]
    pdf_bytes, error = download_pdf(ann)

    if error:
        return None, error, None

    return pdf_bytes, None, ann


def fetch_report_with_fallback(
    stock_code: str,
    stock_name: str = None,
    year: int = None,
) -> Tuple[Optional[bytes], Optional[str], Optional[AnnouncementInfo]]:
    """
    获取企业最新年报 PDF

    Returns:
        (pdf_bytes, error, announcement_info)
    """
    return fetch_latest_annual_report(stock_code, stock_name=stock_name, year=year)
