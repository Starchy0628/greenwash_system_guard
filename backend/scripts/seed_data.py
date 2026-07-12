"""
种子数据脚本 — 生成示例企业和分析数据

包含:
- 12 家完整示例企业（有语句数据，可用于完整功能演示）
- ~200 家行业基准企业（只有年度汇总数据，用于行业基准计算）
- 2012-2025 共 14 年历史趋势

剔除规则（与论文一致）:
1. 金融类上市公司（银行、非银金融）
2. ST、*ST、PT 公司
3. 数据缺失企业
"""
import sys
import random
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR.parent))

from app.core.database import SessionLocal, init_db
from app.models.company import Company
from app.models.analysis import AnalysisRecord
from app.models.sentence import Sentence
from app.models.industry import IndustryBenchmark

# 金融类行业（需剔除）
FINANCIAL_INDUSTRIES = ["银行", "非银金融"]

# ============================================================
#  12 家完整示例企业（有语句数据，is_seed=False，主展示用）
#  注意：已剔除金融类（招商银行被替换为美的集团）
# ============================================================
FULL_DEMO_COMPANIES = [
    {"code": "600519", "name": "贵州茅台", "industry": "食品饮料", "base_gw": 0.0013},
    {"code": "000858", "name": "五粮液", "industry": "食品饮料", "base_gw": 0.018},
    {"code": "000333", "name": "美的集团", "industry": "家用电器", "base_gw": 0.0521},
    {"code": "002594", "name": "比亚迪", "industry": "汽车", "base_gw": 0.1461},
    {"code": "300750", "name": "宁德时代", "industry": "电力设备", "base_gw": 0.037},
    {"code": "600048", "name": "保利发展", "industry": "房地产", "base_gw": 0.0746},
    {"code": "600028", "name": "中国石化", "industry": "石油石化", "base_gw": 0.0},
    {"code": "601857", "name": "中国石油", "industry": "石油石化", "base_gw": 0.0},
    {"code": "000002", "name": "万科A", "industry": "房地产", "base_gw": 0.0},
    {"code": "600309", "name": "万华化学", "industry": "基础化工", "base_gw": 0.0},
    {"code": "000725", "name": "京东方A", "industry": "电子", "base_gw": 0.0},
    {"code": "601012", "name": "隆基绿能", "industry": "电力设备", "base_gw": 0.0},
]

# ============================================================
#  ~200 家行业基准企业（只有汇总数据，is_seed=True，用于行业基准计算）
#  覆盖 26 个申万一级行业（剔除银行、非银金融）
# ============================================================
SEED_COMPANIES = {
    "食品饮料": ["泸州老窖", "山西汾酒", "洋河股份", "海天味业", "伊利股份", "青岛啤酒", "重庆啤酒", "张裕A", "双汇发展", "安琪酵母"],
    "房地产": ["碧桂园", "华润置地", "招商蛇口", "金地集团", "新城控股", "华夏幸福", "荣盛发展", "金科股份", "中南建设", "阳光城"],
    "汽车": ["上汽集团", "广汽集团", "长安汽车", "长城汽车", "吉利汽车", "蔚来", "理想汽车", "小鹏汽车", "一汽解放", "东风汽车"],
    "电力设备": ["通威股份", "阳光电源", "特变电工", "国电南瑞", "金风科技", "明阳智能", "汇川技术", "亿纬锂能", "赣锋锂业", "天齐锂业"],
    "石油石化": ["中国海油", "中国神华", "中煤能源", "陕西煤业", "恒力石化", "荣盛石化", "东方盛虹", "卫星化学", "宝丰能源", "广汇能源"],
    "基础化工": ["扬农化工", "新安股份", "合盛硅业", "龙佰集团", "华鲁恒升", "鲁西化工", "沧州大化", "巨化股份", "三友化工", "中泰化学"],
    "电子": ["立讯精密", "歌尔股份", "闻泰科技", "韦尔股份", "兆易创新", "北方华创", "中微公司", "海康威视", "大华股份", "紫光国微"],
    "医药生物": ["恒瑞医药", "药明康德", "迈瑞医疗", "爱尔眼科", "片仔癀", "云南白药", "智飞生物", "长春高新", "复星医药", "人福医药"],
    "计算机": ["用友网络", "金山办公", "科大讯飞", "三六零", "深信服", "启明星辰", "浪潮信息", "中科曙光", "紫光股份", "中国软件"],
    "传媒": ["分众传媒", "芒果超媒", "光线传媒", "华策影视", "完美世界", "三七互娱", "吉比特", "巨人网络", "昆仑万维", "东方明珠"],
    "通信": ["中兴通讯", "中国联通", "中国移动", "中国电信", "烽火通信", "亨通光电", "中天科技", "中际旭创", "新易盛", "光迅科技"],
    "机械设备": ["三一重工", "徐工机械", "中联重科", "中国中车", "潍柴动力", "先导智能", "晶盛机电", "迈为股份", "捷佳伟创", "大族激光"],
    "国防军工": ["中航沈飞", "中航西飞", "航发动力", "中国卫星", "中国船舶", "中航光电", "振华科技", "高德红外", "大立科技", "鸿远电子"],
    "有色金属": ["紫金矿业", "江西铜业", "铜陵有色", "云南铜业", "中国铝业", "南山铝业", "云铝股份", "中国稀土", "北方稀土", "厦门钨业"],
    "钢铁": ["宝钢股份", "鞍钢股份", "首钢股份", "武钢股份", "包钢股份", "太钢不锈", "马钢股份", "华菱钢铁", "新钢股份", "南钢股份"],
    "煤炭": ["兖州煤业", "潞安环能", "山西焦煤", "淮北矿业", "平煤股份", "冀中能源", "盘江股份", "昊华能源", "露天煤业", "晋控煤业"],
    "建筑材料": ["海螺水泥", "中国建材", "北新建材", "东方雨虹", "伟星新材", "海螺新材", "旗滨集团", "福莱特", "南玻A", "金晶科技"],
    "建筑装饰": ["中国建筑", "中国中铁", "中国铁建", "中国交建", "中国电建", "中国能建", "中国中冶", "中国化学", "中国核建", "中国一重"],
    "轻工制造": ["顾家家居", "欧派家居", "索菲亚", "尚品宅配", "志邦家居", "我乐家居", "金牌橱柜", "皮阿诺", "顶固集创", "好莱客"],
    "家用电器": ["格力电器", "海尔智家", "老板电器", "苏泊尔", "九阳股份", "海信家电", "TCL家电", "小熊电器", "新宝股份", "飞科电器"],
    "纺织服装": ["海澜之家", "雅戈尔", "杉杉股份", "安踏体育", "李宁", "特步国际", "361度", "波司登", "报喜鸟", "七匹狼"],
    "农林牧渔": ["牧原股份", "温氏股份", "新希望", "正邦科技", "海大集团", "大北农", "隆平高科", "登海种业", "圣农发展", "仙坛股份"],
    "商贸零售": ["永辉超市", "苏宁易购", "国美零售", "王府井", "天虹股份", "百联股份", "重庆百货", "大商股份", "鄂武武A", "合肥百货"],
    "社会服务": ["中国中免", "宋城演艺", "锦江酒店", "首旅酒店", "华住集团", "海底捞", "九毛九", "颐海国际", "广州酒家", "全聚德"],
    "交通运输": ["顺丰控股", "中通快递", "韵达股份", "圆通速递", "申通快递", "中国国航", "南方航空", "东方航空", "大秦铁路", "京沪高铁"],
    "公用事业": ["长江电力", "华能国际", "华电国际", "国电电力", "大唐发电", "中广核", "中国核电", "川投能源", "国投电力", "粤电力A"],
}


def _generate_trend(base_gw: float, seed_val: int = 0) -> list[dict]:
    """生成 2012-2025 共 14 年历史趋势数据"""
    random.seed(hash(seed_val) % 100000)
    years = list(range(2012, 2026))
    trend = []
    for i, year in enumerate(years):
        if year == 2025:
            gw = max(0.0, base_gw)
            tone = 0.55 + base_gw / 2
        else:
            progress = i / 13.0
            variation = random.uniform(-0.03, 0.03)
            # 早期 GW 更高，逐渐下降（越来越环保是大趋势）
            gw_factor = 0.3 + progress * 0.7
            gw = max(0.0, round(base_gw * gw_factor + variation, 4))
            tone = 0.5 + gw / 2 + random.uniform(-0.02, 0.02)
        trend.append({"year": year, "gw": gw, "tone": tone})
    return trend


def _seed_full_demo_companies(db):
    """生成 12 家完整演示企业（带语句数据）"""
    print("  → 生成 12 家完整演示企业...")

    for idx, comp in enumerate(FULL_DEMO_COMPANIES):
        # 创建企业
        company = Company(
            stock_code=comp["code"],
            company_name=comp["name"],
            industry=comp["industry"],
            short_name=comp["name"],
            is_a_share=True,
            is_seed=False,
            is_st=False,
            is_active=True,
        )
        db.add(company)
        db.flush()

        # 生成 14 年历史趋势
        trend = _generate_trend(comp["base_gw"], seed_val=idx)

        for year_idx, y in enumerate(trend):
            is_latest = (y["year"] == 2025)
            data_source = "ESG" if y["year"] >= 2023 else "MD&A"

            # 简单的风险等级（后 20% 为预警，这里先根据 GW 粗略估计）
            risk_level = "预警" if y["gw"] > 0.15 else "正常"

            record = AnalysisRecord(
                company_id=company.id,
                year=y["year"],
                data_source_type=data_source,
                total_sentences=100 + idx * 10,
                env_sentences=30 + idx * 3,
                substantive_count=10 + idx,
                descriptive_count=15 + idx * 2,
                non_env_count=5,
                tone_score=round(y["tone"], 6),
                industry_median_tone=0.58,
                gw_index=round(y["gw"], 6),
                risk_level=risk_level,
                fleiss_kappa=0.84,
                dispute_count=2,
                analysis_status="completed",
                is_latest=is_latest,
                analyzed_at=None,
            )
            db.add(record)
            db.flush()

            # 只有最新一年生成语句数据（避免数据库太大）
            if is_latest:
                sentences = _generate_demo_sentences(comp["name"], comp["base_gw"])
                for s_idx, s in enumerate(sentences):
                    sentence = Sentence(
                        analysis_record_id=record.id,
                        sentence_text=s["text"],
                        sentence_order=s_idx,
                        deepseek_result=s["deepseek"],
                        qwen_result=s["qwen"],
                        glm_result=s["glm"],
                        final_category=s["final"],
                        vote_type=s["vote_type"],
                        confidence=s["confidence"],
                        sentiment_score=s["sentiment"],
                        sentiment_std=0.05,
                        needs_review=s["needs_review"],
                    )
                    db.add(sentence)

    db.commit()


def _generate_demo_sentences(company_name: str, gw: float) -> list[dict]:
    """生成演示语句数据"""
    sentences = [
        {
            "text": f"{company_name}高度重视环境保护工作，积极践行绿色发展理念。",
            "deepseek": "descriptive", "qwen": "descriptive", "glm": "descriptive",
            "final": "descriptive", "vote_type": "unanimous",
            "confidence": 0.95, "sentiment": 0.7, "needs_review": False,
        },
        {
            "text": "报告期内公司环保投入达到5000万元，同比增长15%。",
            "deepseek": "substantive", "qwen": "substantive", "glm": "substantive",
            "final": "substantive", "vote_type": "unanimous",
            "confidence": 0.9, "sentiment": 0.65, "needs_review": False,
        },
        {
            "text": "公司通过ISO14001环境管理体系认证。",
            "deepseek": "substantive", "qwen": "substantive", "glm": "descriptive",
            "final": "substantive", "vote_type": "majority",
            "confidence": 0.7, "sentiment": 0.6, "needs_review": False,
        },
        {
            "text": "二氧化硫排放量减少15%，达到行业领先水平。",
            "deepseek": "substantive", "qwen": "substantive", "glm": "substantive",
            "final": "substantive", "vote_type": "unanimous",
            "confidence": 0.92, "sentiment": 0.75, "needs_review": False,
        },
        {
            "text": "我们持续推动绿色低碳转型，实现可持续发展。",
            "deepseek": "descriptive", "qwen": "descriptive", "glm": "descriptive",
            "final": "descriptive", "vote_type": "unanimous",
            "confidence": 0.98, "sentiment": 0.8, "needs_review": False,
        },
        {
            "text": "报告期内单位产值能耗同比下降4.2%。",
            "deepseek": "substantive", "qwen": "substantive", "glm": "substantive",
            "final": "substantive", "vote_type": "unanimous",
            "confidence": 0.93, "sentiment": 0.7, "needs_review": False,
        },
        {
            "text": "公司致力于打造绿色工厂，践行生态文明理念。",
            "deepseek": "descriptive", "qwen": "descriptive", "glm": "substantive",
            "final": "descriptive", "vote_type": "majority",
            "confidence": 0.65, "sentiment": 0.68, "needs_review": False,
        },
        {
            "text": "清洁能源使用比例提升至12%，碳排放强度降低8.5%。",
            "deepseek": "substantive", "qwen": "substantive", "glm": "substantive",
            "final": "substantive", "vote_type": "unanimous",
            "confidence": 0.91, "sentiment": 0.72, "needs_review": False,
        },
        {
            "text": "公司全年实现营业收入稳步增长，净利润同比增长。",
            "deepseek": "non_environmental", "qwen": "non_environmental", "glm": "non_environmental",
            "final": "non_environmental", "vote_type": "unanimous",
            "confidence": 0.99, "sentiment": 0.5, "needs_review": False,
        },
        {
            "text": "董事会审议通过了年度利润分配方案。",
            "deepseek": "non_environmental", "qwen": "non_environmental", "glm": "descriptive",
            "final": "non_environmental", "vote_type": "majority",
            "confidence": 0.6, "sentiment": 0.5, "needs_review": True,
        },
    ]
    return sentences


def _seed_benchmark_companies(db):
    """生成 ~200 家行业基准企业（is_seed=True，只有汇总数据）"""
    print("  → 生成 ~200 家行业基准企业（用于行业基准计算）...")

    company_count = 0
    for industry, names in SEED_COMPANIES.items():
        for idx, name in enumerate(names):
            # 生成一个假的股票代码（6位数字）
            seed_val = hash(name) % 1000000
            stock_code = f"{600000 + seed_val % 100000:06d}"

            # 检查是否和完整演示企业重复
            existing = db.query(Company).filter(
                (Company.stock_code == stock_code) |
                (Company.company_name == name)
            ).first()
            if existing:
                continue

            # 每个行业的基础 GW 不同（已剔除金融类）
            high_pollution = ["石油石化", "钢铁", "煤炭", "基础化工", "有色金属", "建筑材料"]
            medium_pollution = ["电力设备", "汽车", "机械设备", "轻工制造", "纺织服装"]
            low_pollution = ["计算机", "传媒", "通信", "医药生物",
                            "食品饮料", "家用电器", "社会服务", "商贸零售", "农林牧渔",
                            "公用事业", "交通运输", "建筑装饰", "国防军工", "电子", "房地产"]

            random.seed(hash(name + industry) % 100000)

            if industry in high_pollution:
                base_gw = round(random.uniform(0.0, 0.35), 4)
            elif industry in medium_pollution:
                base_gw = round(random.uniform(0.0, 0.2), 4)
            else:
                base_gw = round(random.uniform(0.0, 0.25), 4)

            company = Company(
                stock_code=stock_code,
                company_name=name,
                industry=industry,
                short_name=name,
                is_a_share=True,
                is_seed=True,
                is_st=False,
                is_active=True,
            )
            db.add(company)
            db.flush()

            # 生成 14 年趋势
            trend = _generate_trend(base_gw, seed_val=hash(name) % 100000)

            for y in trend:
                is_latest = (y["year"] == 2025)
                data_source = "ESG" if y["year"] >= 2023 else "MD&A"
                risk_level = "预警" if y["gw"] > 0.15 else "正常"

                record = AnalysisRecord(
                    company_id=company.id,
                    year=y["year"],
                    data_source_type=data_source,
                    total_sentences=80,
                    env_sentences=25,
                    substantive_count=8,
                    descriptive_count=12,
                    non_env_count=5,
                    tone_score=round(y["tone"], 6),
                    industry_median_tone=0.58,
                    gw_index=round(y["gw"], 6),
                    risk_level=risk_level,
                    fleiss_kappa=0.82,
                    dispute_count=1,
                    analysis_status="completed",
                    is_latest=is_latest,
                    analyzed_at=None,
                )
                db.add(record)

            company_count += 1

    db.flush()
    print(f"  → 共生成 {company_count} 家基准企业")


def seed_all():
    """生成全部种子数据"""
    print("初始化数据库...")
    init_db()

    db = SessionLocal()
    try:
        # 检查是否已有数据
        existing = db.query(Company).count()
        if existing > 0:
            print(f"数据库已有 {existing} 家企业，跳过种子数据生成")
            return

        print("开始生成种子数据...")
        _seed_full_demo_companies(db)
        _seed_benchmark_companies(db)
        db.commit()

        # 重新计算行业基准
        from app.services.industry_service import compute_industry_benchmarks, update_risk_levels
        print("  → 重新计算行业基准和风险等级...")
        for year in range(2012, 2026):
            compute_industry_benchmarks(db, year)
            update_risk_levels(db, year)
        db.commit()

        total_companies = db.query(Company).count()
        total_records = db.query(AnalysisRecord).count()
        print(f"\n✅ 种子数据生成完成！")
        print(f"   企业总数: {total_companies}")
        print(f"   分析记录数: {total_records}")

    except Exception as e:
        db.rollback()
        print(f"❌ 生成种子数据失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
