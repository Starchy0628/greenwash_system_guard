"""Mock 模式服务 — 模拟三模型分析流程，无需 API Key"""
import random
import hashlib
from typing import Dict, List, Tuple

from app.services.text_utils import ALL_ENV_KEYWORDS, split_sentences


def _stable_seed(text: str) -> int:
    """生成稳定的种子值（不依赖Python内置hash的随机化）"""
    return int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % (2**32)


# 模拟语句分类结果（用于生成演示数据）
MOCK_CATEGORIES = {
    "substantive": [
        "公司本年度环保投入达{金额}万元，同比增长{百分比}%。",
        "通过ISO14001环境管理体系认证，{指标}排放量减少{百分比}%，达到行业领先水平。",
        "单位产值能耗同比下降{百分比}%，完成节能减排目标。",
        "报告期内投入{金额}万元用于污染防治设施建设。",
        "清洁能源使用比例提升至{百分比}%，碳排放强度降低{百分比}%。",
        "投入{金额}万元用于脱硫脱硝技术改造，废气排放浓度下降{百分比}%。",
        "新建污水处理厂一期工程已投入使用，日处理能力达{金额}万吨。",
        "本年度资源综合利用率提升至{百分比}%，工业固废处置率达100%。",
        "完成{金额}万元碳配额交易，碳排放权履约率达到100%。",
        "绿色债券发行规模达{金额}亿元，专项用于新能源项目建设。",
        "生态修复项目投入{金额}万元，植被恢复面积达{金额}公顷。",
    ],
    "descriptive": [
        "公司高度重视环境保护工作，积极履行企业社会责任。",
        "我们持续推动绿色低碳转型，实现可持续发展。",
        "公司致力于打造绿色工厂，践行生态文明理念。",
        "积极推进环境治理工作，提升绿色发展水平。",
        "坚持绿色发展理念，为美丽中国贡献力量。",
        "公司不断完善环境管理制度，强化环境风险防控体系建设。",
        "持续加大环保领域投入，践行负责任的环境管理理念。",
        "秉持绿水青山就是金山银山的发展理念，推动企业与环境和谐共生。",
        "公司积极响应国家双碳目标号召，全面推进绿色低碳发展战略。",
        "将ESG理念融入企业治理各环节，构建可持续发展长效机制。",
    ],
    "non_env": [
        "公司全年实现营业收入稳步增长，净利润同比增长。",
        "董事会审议通过了年度利润分配方案。",
        "公司持续加大研发投入，提升核心竞争力。",
        "报告期内公司完成了定向增发融资事项。",
        "公司治理结构持续优化，内部控制体系不断完善。",
        "全年实现营业收入{金额}亿元，同比增长{百分比}%。",
        "公司完成非公开发行股票募集资金{金额}亿元。",
        "研发费用增长{百分比}%，新增专利授权{金额}件。",
        "公司被评为国家级高新技术企业，享受税收优惠政策。",
        "新增员工持股计划覆盖{金额}人，占总人数的{百分比}%。",
        "报告期内公司完成重大资产重组，新增并表子公司3家。",
    ],
}


def mock_classify_sentence(sentence: str) -> Tuple[str, str, str, dict]:
    """模拟三模型对一条语句的分类

    分类标准（严格依据论文）：
    - 实质性陈述 (substantive)：包含可验证的定量数据 或 具体认证成果
    - 描述性陈述 (descriptive)：定性口号 或 模糊承诺（无具体数据支撑）
    - 非环保语句 (non_env)：虽含关键词但无实际环境含义
    """
    is_env = any(kw in sentence for kw in ALL_ENV_KEYWORDS)
    if not is_env:
        results = {"deepseek": "non_env", "qwen": "non_env", "glm": "non_env"}
        return "non_env", "unanimous", 1.0, results

    # 判定实质性的特征：数字+单位、百分比、认证名称、具体金额/面积/产能等
    substantive_patterns = [
        r"\d+\.?\d*[%％]",
        r"\d+\.?\d*万元",
        r"\d+\.?\d*亿元",
        r"\d+\.?\d*吨",
        r"\d+\.?\d*万吨",
        r"\d+\.?\d*公顷",
        r"\d+\.?\d*平方千米",
        r"\d+\.?\d*万千瓦",
        r"\d+\.?\d*兆瓦",
        r"\d+\.?\d*万吨标准煤",
        r"通过.*认证",
        r"获得.*认证",
        r"取得.*认证",
        r"ISO\s*14001",
        r"ISO\s*14064",
        r"ISO\s*50001",
        r"环境管理体系认证",
        r"能源管理体系认证",
        r"碳管理体系认证",
        r"绿色产品认证",
        r"碳中和认证",
        r"碳配额交易",
        r"完成.*碳交易",
        r"发行绿色债券",
        r"绿色债券发行",
        r"100%",
        r"零排放",
        r"近零排放",
        r"污水处理厂.*投入使用",
        r"脱硫脱硝.*改造",
        r"达标排放",
        r"完成.*目标",
        r"投入使用",
        r"日处理能力",
    ]

    import re
    is_substantive = any(re.search(pat, sentence) for pat in substantive_patterns)
    base_category = "substantive" if is_substantive else "descriptive"

    seed = _stable_seed(sentence)
    rng = random.Random(seed)

    # 实质性句子有明确数据支撑，分歧率更低（约5%）；描述性句子分歧率约10%
    if is_substantive:
        unanimous_rate = 0.90
        majority_rate = 0.07
    else:
        unanimous_rate = 0.80
        majority_rate = 0.10

    confusion = rng.random()

    if confusion < unanimous_rate:
        results = {"deepseek": base_category, "qwen": base_category, "glm": base_category}
        return base_category, "unanimous", 1.0, results
    elif confusion < unanimous_rate + majority_rate:
        alt = "descriptive" if base_category == "substantive" else "substantive"
        results = {"deepseek": base_category, "qwen": base_category, "glm": alt}
        return base_category, "majority", 0.67, results
    else:
        results = {
            "deepseek": "substantive",
            "qwen": "descriptive",
            "glm": "non_env",
        }
        return "dispute", "full_divergence", 0.33, results


def mock_sentiment_score(sentence: str) -> Tuple[float, float]:
    """模拟情感打分（依据论文：句内语义依存 + 修辞强度级差）

    评分逻辑：
    - 基于句内修辞强度分级（强/中/弱积极词、否定词、转折连词）
    - 标准化在[-1, 1]区间
    - 负值=风险揭示/问题承认，正值=积极修辞/成就宣扬
    - 仅对描述性语句打分（实质性语句不参与语调计算）
    """
    import re

    # 强积极修辞（成就宣扬、高度承诺）
    strong_positive = [
        "行业领先", "国际先进", "国内领先", "显著成效", "重大突破",
        "全面推进", "深入贯彻", "坚决落实", "全力以赴", "坚定不移",
        "卓有成效", "硕果累累", "成绩斐然", "大幅提升", "跨越式发展",
        "引领", "典范", "标杆", "楷模", "先锋",
        "高度重视", "积极履行", "主动承担", "率先垂范",
    ]
    # 中等积极修辞
    medium_positive = [
        "积极推动", "持续提升", "不断优化", "稳步推进", "有效改善",
        "逐步", "进一步", "持续", "不断", "稳步",
        "提升", "改善", "优化", "推进", "加强",
        "绿色发展", "可持续发展", "高质量发展",
        "贡献", "践行", "秉持", "响应", "融入",
    ]
    # 弱积极/中性
    weak_positive = [
        "开展", "进行", "实施", "完善", "建立",
        "管理", "治理", "建设", "工作", "制度",
        "理念", "战略", "目标", "规划", "体系",
    ]
    # 负面/风险揭示
    negative_words = [
        "不足", "挑战", "有待", "仍需", "困难", "问题",
        "差距", "压力", "风险", "严峻", "艰巨",
        "虽然", "尽管", "但是", "然而", "不过",
    ]
    # 否定词（反转语义）
    negation_words = ["不", "未能", "没有", "无", "未"]

    base_score = 0.0
    score = base_score

    # 强积极：每词 +0.25
    for w in strong_positive:
        if w in sentence:
            score += 0.25
    # 中等积极：每词 +0.12
    for w in medium_positive:
        if w in sentence:
            score += 0.12
    # 弱积极：每词 +0.04
    for w in weak_positive:
        if w in sentence:
            score += 0.04
    # 负面：每词 -0.2
    for w in negative_words:
        if w in sentence:
            score -= 0.2

    # 转折结构检测（虽然...但是...）：但后面的语义权重更高
    if re.search(r"虽然.*但是", sentence) or re.search(r"尽管.*但是", sentence):
        score *= 1.1  # 转折句修辞强度提升

    # 否定词检测：简单反转（简化处理）
    negation_count = sum(1 for w in negation_words if w in sentence)
    if negation_count % 2 == 1:
        score = -score * 0.7  # 否定后强度略减

    seed = _stable_seed(sentence)
    rng = random.Random(seed)

    score += rng.uniform(-0.08, 0.08)

    final_score = max(-1.0, min(1.0, round(score, 4)))
    std = round(rng.uniform(0.02, 0.10), 4)
    return final_score, std


def run_mock_analysis(text: str, industry: str = "白酒") -> dict:
    """
    执行完整的 Mock 分析流程
    流程：句子切分 → 关键词过滤 → 三模型分类(模拟) → 情感打分 → 行业基准修正 → GW指数
    """
    # 1. 句子切分
    raw_sentences = split_sentences(text)
    if not raw_sentences:
        raw_sentences = [text]

    # 2. 环境关键词过滤（使用强弱关键词策略，同时过滤表格数据）
    from app.services.text_utils import contains_env_keywords, is_valid_sentence
    env_sentences = []
    for s in raw_sentences:
        if not is_valid_sentence(s):
            continue
        is_env, _ = contains_env_keywords(s)
        if is_env:
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
            "glm_result": model_results["glm"],
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
    gw_index = round(max(0.0, tone_score - industry_median), 6)

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
    """获取模拟的行业语调中位数
    
    中位数设置在 0.25-0.40 之间，确保描述性语句情感分（约 0.2-0.6）
    与中位数的差值能产生合理的 GW 指数分布。
    """
    medians = {
        "白酒": 0.35, "食品饮料": 0.30, "电池": 0.28,
        "新能源汽车": 0.26, "房地产": 0.25, "能源化工": 0.22,
        "银行": 0.20, "光伏": 0.30, "化工": 0.24, "电子": 0.28,
    }
    base = medians.get(industry, 0.25)
    return round(base + random.uniform(-0.02, 0.02), 6)


def generate_mock_company_text(company_name: str, industry: str = "白酒", seed: int = 0, target_gw: float = None) -> str:
    """生成企业特定的模拟 MD&A 文本
    
    与种子数据生成逻辑保持一致，确保拉取前后数据一致性。
    实质性语句约占环境语句的 60%，描述性约 30%，分歧约 10%。
    
    Args:
        company_name: 企业名称
        industry: 行业
        seed: 随机种子
        target_gw: 目标 GW 指数（用于调整描述性语句的漂绿程度）
    """
    random.seed(seed if seed else hash(company_name + industry) % 100000)

    # 实质性语句模板（有具体数据/认证）
    substantive_templates = [
        f"{company_name}本年度环保投入达{random.randint(3000, 8000)}万元，同比增长{random.uniform(5, 20):.1f}%。",
        f"通过ISO14001环境管理体系认证，{random.choice(['二氧化硫', '氮氧化物', 'COD', '氨氮'])}排放量减少{random.uniform(8, 20):.1f}%，达到行业领先水平。",
        f"报告期内单位产值能耗同比下降{random.uniform(3, 8):.1f}%，完成年度节能减排目标。",
        f"报告期内投入{random.randint(2000, 6000)}万元用于污染防治设施建设。",
        f"清洁能源使用比例提升至{random.uniform(8, 25):.1f}%，碳排放强度降低{random.uniform(5, 12):.1f}%。",
        f"投入{random.randint(1500, 5000)}万元用于脱硫脱硝技术改造，废气排放浓度下降{random.uniform(10, 25):.1f}%。",
        f"本年度资源综合利用率提升至{random.uniform(70, 95):.1f}%，工业固废处置率达100%。",
        f"完成{random.randint(500, 2000)}万元碳配额交易，碳排放权履约率达到100%。",
        f"新建污水处理厂一期工程已投入使用，日处理能力达{random.randint(2, 10)}万吨。",
        f"生态修复项目投入{random.randint(1000, 4000)}万元，植被恢复面积达{random.randint(50, 200)}公顷。",
    ]

    # 高漂绿描述性模板（强积极修辞，口号式承诺）
    high_greenwash_templates = [
        f"{company_name}高度重视环境保护工作，积极履行企业社会责任，全力打造行业绿色发展标杆。",
        f"{company_name}持续推动绿色低碳转型，实现可持续发展，引领行业生态文明建设。",
        f"公司致力于打造世界级绿色工厂，践行生态文明理念，树立行业环保典范。",
        f"全面推进环境治理工作，大幅提升绿色发展水平，取得举世瞩目的显著成效。",
        f"始终坚持绿色发展理念，为生态环境保护做出卓越贡献，全力守护绿水青山。",
        f"公司不断完善环境管理体系，强化环境风险防控，全面提升环境治理能力。",
        f"持续加大环保领域投入，深入践行负责任的环境管理理念，争创行业先锋。",
        f"秉持绿水青山就是金山银山的发展理念，推动企业与环境和谐共生，实现跨越式发展。",
        f"公司积极响应国家双碳目标号召，全面推进绿色低碳发展战略，争当行业领跑者。",
        f"将ESG理念深度融入企业治理各环节，构建可持续发展长效机制，打造卓越企业。",
    ]

    # 低漂绿描述性模板（平实表述，较少修辞）
    low_greenwash_templates = [
        f"{company_name}开展环境保护工作，履行企业社会责任。",
        f"公司推进绿色低碳转型，关注可持续发展。",
        f"逐步完善环境管理相关制度。",
        f"进行环境治理工作，提升绿色发展水平。",
        f"贯彻绿色发展理念，参与生态环境保护。",
        f"公司完善环境管理制度，加强环境风险防控。",
        f"增加环保投入，践行环境管理理念。",
        f"落实绿色发展要求，推动企业绿色转型。",
        f"响应双碳目标，推进绿色发展相关工作。",
        f"探索ESG理念在企业中的应用。",
    ]

    # 非环境语句模板
    non_env_templates = [
        f"{company_name}全年实现营业收入稳步增长，净利润同比增长。",
        "董事会审议通过了年度利润分配方案。",
        "公司持续加大研发投入，提升核心竞争力。",
        "报告期内公司完成了定向增发融资事项。",
        "公司治理结构持续优化，内部控制体系不断完善。",
    ]

    sentences = []

    # 实质性语句：6-7条（保持多数，符合论文要求）
    num_substantive = random.randint(6, 7)
    selected_substantive = random.sample(substantive_templates, num_substantive)
    sentences.extend(selected_substantive)

    # 描述性语句：3-4条（通过调整情感强度来控制GW，而不是数量）
    num_descriptive = random.randint(3, 4)
    if target_gw is not None and target_gw > 0.1:
        # 高漂绿：使用高漂绿模板（强积极修辞）
        descriptive_pool = high_greenwash_templates
    elif target_gw is not None and target_gw > 0.05:
        # 中漂绿：混合模板
        descriptive_pool = high_greenwash_templates[:5] + low_greenwash_templates[:5]
    else:
        # 低漂绿：使用平实模板
        descriptive_pool = low_greenwash_templates

    selected_descriptive = random.sample(descriptive_pool, num_descriptive)
    sentences.extend(selected_descriptive)

    # 非环境语句：2-3条
    num_non_env = random.randint(2, 3)
    selected_non_env = random.sample(non_env_templates, num_non_env)
    sentences.extend(selected_non_env)

    # 打乱顺序
    random.shuffle(sentences)

    return "".join(sentences)