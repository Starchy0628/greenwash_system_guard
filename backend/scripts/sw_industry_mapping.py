"""
申万2021行业分类代码映射表
来源: 申万研究所 StockClassifyUse_stock.xls + tushare index_classify 文档
"""
import requests
import urllib3
import pandas as pd
import io

urllib3.disable_warnings()

# ============================================================
#  申万2021版 一级行业代码 → 名称 映射表
#  前2位数字对应一级行业
# ============================================================
SW_L1_CODE_MAP = {
    "11": "农林牧渔",
    "21": "煤炭",
    "22": "基础化工",
    "23": "钢铁",
    "24": "有色金属",
    "25": "石油石化",
    "26": "建筑材料",
    "27": "电子",
    "28": "汽车",
    "31": "家用电器",
    "32": "食品饮料",
    "33": "纺织服饰",
    "34": "轻工制造",
    "35": "医药生物",
    "36": "公用事业",
    "37": "交通运输",
    "41": "房地产",
    "42": "商贸零售",
    "43": "社会服务",
    "44": "综合",
    "45": "建筑材料",  # 2021版建筑材料也可能用45
    "46": "建筑装饰",
    "47": "国防军工",
    "48": "计算机",
    "49": "传媒",
    "51": "通信",
    "61": "银行",
    "62": "非银金融",
    "63": "机械设备",
    "64": "电力设备",
    "65": "环保",
    "71": "美容护理",
    "72": "煤炭",       # 2021版煤炭也可能用72
    "73": "综合",       # 2021版综合
    "74": "基础化工",   # 2021版基础化工
    "75": "石油石化",   # 2021版石油石化
    "76": "汽车",       # 2021版汽车
    "77": "传媒",       # 2021版传媒
}


def fetch_sw_industry_map() -> dict:
    """
    从申万研究所下载 StockClassifyUse_stock.xls，
    返回 {stock_code: sw_l1_industry_name} 映射。
    对于每个股票，取最新更新日期的行业分类。
    """
    url = "https://www.swsresearch.com/swindex/pdf/SwClass2021/StockClassifyUse_stock.xls"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        r = requests.get(url, headers=headers, verify=False, timeout=30)
        if r.status_code != 200:
            print(f"  ⚠️  SW Excel 下载失败: HTTP {r.status_code}")
            return {}
    except Exception as e:
        print(f"  ⚠️  SW Excel 下载异常: {e}")
        return {}
    
    df = pd.read_excel(io.BytesIO(r.content))
    
    # 股票代码需要补齐6位
    df["股票代码"] = df["股票代码"].astype(str).str.zfill(6)
    df["行业代码"] = df["行业代码"].astype(str).str.zfill(6)
    
    # 按股票代码分组，取最新更新日期
    df_sorted = df.sort_values("更新日期", ascending=False)
    latest = df_sorted.groupby("股票代码").first().reset_index()
    
    # 提取一级行业代码（前2位）
    latest["l1_code"] = latest["行业代码"].str[:2]
    
    # 映射到行业名称
    result = {}
    no_map = set()
    for _, row in latest.iterrows():
        code = row["股票代码"]
        l1_code = row["l1_code"]
        industry = SW_L1_CODE_MAP.get(l1_code)
        if industry:
            result[code] = industry
        else:
            no_map.add(l1_code)
    
    if no_map:
        print(f"  ⚠️  未映射的行业代码: {sorted(no_map)}")
    
    return result


if __name__ == "__main__":
    mapping = fetch_sw_industry_map()
    print(f"获取到 {len(mapping)} 只股票的申万行业分类")
    
    # 统计行业分布
    from collections import Counter
    dist = Counter(mapping.values())
    for ind, cnt in dist.most_common():
        print(f"  {ind}: {cnt}")