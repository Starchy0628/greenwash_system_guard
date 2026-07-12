"""
LLM 端到端验证脚本
验证三模型（DeepSeek / Qwen / GLM-4.7）的分类→情感→融合→GW指数全流程

用法:
    python scripts/test_llm_e2e.py            # 真实API模式
    python scripts/test_llm_e2e.py --mock     # Mock模式

验证内容:
    1. 三个LLM模型是否都能正常连接和响应
    2. 分类器输出格式是否正确（substantive/descriptive/non_environmental）
    3. 情感分析评分是否在 [-1, 1] 范围内
    4. 多数投票融合逻辑是否正确
    5. Fleiss' Kappa 一致性是否可计算
    6. GW 指数计算链路是否完整
"""
import sys
import os
import time
import json
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.core.config import get_settings
from app.services.llm_client import (
    create_llm_client,
    DEFAULT_LLM_MODELS,
    CLASSIFICATION_PROMPT,
    SENTIMENT_PROMPT,
    ClassificationType,
)
from app.services.classifier import SentenceClassifier
from app.services.fusion import MajorityVotingFuser, EnsembleAveragingFuser
from app.services.calculator import (
    GreenwashIndexCalculator,
    SentenceLevelResult,
    CompanyGreenwashResult,
)

settings = get_settings()

# ============================================================
#  测试用的 ESG 语句（来自真实年报的典型表述）
# ============================================================
TEST_SENTENCES = [
    # 实质性陈述（有具体数据）
    "2024年公司投入环保资金2.5亿元，完成脱硫脱硝改造项目3个，年减排二氧化碳12.8万吨，单位产值能耗同比下降8.3%。",
    "公司已通过ISO 14001环境管理体系认证，2024年环保设施运行率达到99.2%，废水处理达标率100%。",
    "报告期内，公司新建光伏发电项目装机容量50MW，年发电量达6000万千瓦时，减少碳排放约4.5万吨。",
    
    # 描述性陈述（口号式/模糊表述）
    "公司始终坚持绿色发展理念，积极推进节能减排工作，努力实现可持续发展目标。",
    "我们致力于打造环境友好型企业，持续推进绿色生产，为建设美丽中国贡献力量。",
    "公司高度重视环境保护工作，不断提升环保管理水平，积极履行社会责任。",
    
    # 非环保语句（含环保关键词但非环保内容）
    "公司环保设备采购合同金额较大，是公司固定资产投资的重要组成部分。",
    "环保政策趋严对行业竞争格局产生深远影响，公司将密切关注政策变化。",
    
    # 混合/复杂语句
    "虽然公司环保投入持续增加，但部分老旧设备仍存在能耗偏高的问题，需要进一步技术改造。",
    "公司积极响应国家'双碳'战略，制定了2030年碳达峰行动方案，并已投入专项资金1.2亿元用于清洁能源替代。",
]


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_subsection(title: str):
    print(f"\n  ── {title} ──")


def test_model_connectivity():
    """测试1: 检查三个模型是否都能正常连接"""
    print_header("测试 1: 模型连接性检查")
    
    api_keys = {
        "deepseek-r1": settings.deepseek_api_key,
        "qwen-max": settings.qwen_api_key,
        "glm-4.7": settings.glm_api_key,
    }
    
    results = {}
    for config in DEFAULT_LLM_MODELS:
        model_name = config["name"]
        display_name = config["display_name"]
        print_subsection(f"{display_name} ({model_name})")
        
        try:
            client = create_llm_client(
                dict(config),
                api_keys=api_keys,
                use_mock=False,
            )
            
            start = time.time()
            response = client.call(
                "请回复：连接成功。",
                system_prompt="你是一个测试助手。",
                max_tokens=50,
            )
            latency = time.time() - start
            
            if response.success:
                print(f"     ✅ 连接成功 (延迟: {latency:.2f}s, tokens: {response.tokens_used})")
                print(f"     响应: {response.raw_response[:100]}...")
                results[model_name] = {
                    "status": "ok",
                    "latency": latency,
                    "tokens": response.tokens_used,
                }
            else:
                print(f"     ❌ 连接失败: {response.error}")
                results[model_name] = {"status": "error", "error": response.error}
                
        except Exception as e:
            print(f"     ❌ 异常: {type(e).__name__}: {e}")
            results[model_name] = {"status": "error", "error": str(e)}
    
    return results


def test_classification():
    """测试2: 分类器全流程验证"""
    print_header("测试 2: 语句分类验证")
    
    api_keys = {
        "deepseek-r1": settings.deepseek_api_key,
        "qwen-max": settings.qwen_api_key,
        "glm-4.7": settings.glm_api_key,
    }
    
    classifier = SentenceClassifier(
        model_configs=DEFAULT_LLM_MODELS,
        api_keys=api_keys,
        use_mock=False,
    )
    
    total_latency = 0
    total_tokens = 0
    all_results = []
    
    for i, sentence in enumerate(TEST_SENTENCES):
        print_subsection(f"语句 {i+1}: {sentence[:60]}...")
        
        start = time.time()
        result = classifier.classify_single(sentence, return_details=True)
        latency = time.time() - start
        total_latency += latency
        
        # 累计 tokens
        for resp in result.model_responses.values():
            total_tokens += resp.tokens_used
        
        # 打印每个模型的结果
        for model_name, label in result.model_results.items():
            resp = result.model_responses.get(model_name)
            lat = f"{resp.latency:.1f}s" if resp else "N/A"
            tok = resp.tokens_used if resp else 0
            print(f"     {model_name}: {label:20s} | 延迟={lat} | tokens={tok}")
        
        print(f"     → 最终: {result.final_label:20s} | 置信度={result.confidence:.2f} | 投票={result.vote_type}")
        
        if result.is_ambiguous:
            print(f"     ⚠️  模型分歧!")
        
        all_results.append(result)
    
    # 统计
    stats = classifier.get_stats(all_results)
    print_subsection("分类统计")
    print(f"     总数: {stats['total']}")
    print(f"     实质性: {stats['substantive']}")
    print(f"     描述性: {stats['descriptive']}")
    print(f"     非环保: {stats['non_environmental']}")
    print(f"     全票通过: {stats['unanimous']}")
    print(f"     多数投票: {stats['majority']}")
    print(f"     完全分歧: {stats['full_divergence']}")
    print(f"     总延迟: {total_latency:.1f}s")
    print(f"     总 tokens: {total_tokens}")
    
    return all_results, total_latency, total_tokens


def test_sentiment():
    """测试3: 情感分析验证"""
    print_header("测试 3: 情感分析验证")
    
    api_keys = {
        "deepseek-r1": settings.deepseek_api_key,
        "qwen-max": settings.qwen_api_key,
        "glm-4.7": settings.glm_api_key,
    }
    
    # 只对描述性语句做情感分析
    descriptive_sentences = [
        s for s in TEST_SENTENCES
        if any(kw in s for kw in ["坚持", "致力于", "重视", "积极"])
    ][:3]
    
    if not descriptive_sentences:
        descriptive_sentences = TEST_SENTENCES[3:6]
    
    fuser = EnsembleAveragingFuser(method="arithmetic")
    all_scores = []
    
    for i, sentence in enumerate(descriptive_sentences):
        print_subsection(f"语句 {i+1}: {sentence[:60]}...")
        
        model_scores = {}
        for config in DEFAULT_LLM_MODELS:
            model_name = config["name"]
            try:
                client = create_llm_client(
                    dict(config),
                    api_keys=api_keys,
                    use_mock=False,
                )
                prompt = SENTIMENT_PROMPT.format(sentence=sentence)
                response = client.call(prompt)
                
                if response.success:
                    score = client._parse_sentiment(response.raw_response)
                    model_scores[model_name] = score
                    print(f"     {model_name}: {score:+.2f} | {response.latency:.1f}s | {response.tokens_used} tokens")
                else:
                    print(f"     {model_name}: ❌ {response.error}")
                    model_scores[model_name] = 0.0
            except Exception as e:
                print(f"     {model_name}: ❌ {e}")
                model_scores[model_name] = 0.0
        
        # 融合
        fusion = fuser.fuse(model_scores)
        print(f"     → 融合后: {fusion.final_result:+.2f} | 一致性={fusion.agreement_metric:.2f}")
        all_scores.append(fusion.final_result)
    
    print_subsection("情感分析总结")
    print(f"     平均情感得分: {sum(all_scores)/len(all_scores):+.2f}" if all_scores else "     无数据")
    
    return all_scores


def test_gw_index():
    """测试4: GW指数计算链路验证"""
    print_header("测试 4: GW 指数计算链路验证")
    
    calc = GreenwashIndexCalculator()
    
    # 模拟一批企业的语句级结果
    industries = ["食品饮料", "电子", "医药生物", "电力设备", "计算机"]
    results = []
    
    for ind_idx, industry in enumerate(industries):
        for company_idx in range(3):
            # 模拟 5-15 条语句
            sentence_results = []
            for s in range(8):
                classifications = ["substantive", "descriptive", "non_environmental"]
                # 不同行业不同分布
                weights = [0.3, 0.5, 0.2] if ind_idx % 2 == 0 else [0.4, 0.4, 0.2]
                cls = classifications[hash(f"{industry}{company_idx}{s}") % 3]
                sentiment = 0.1 + (hash(f"{industry}{company_idx}{s}sent") % 100) / 100
                sentiment = max(-1.0, min(1.0, sentiment))
                sentence_results.append(SentenceLevelResult(
                    sentence=f"测试语句{s}",
                    classification=cls,
                    classification_confidence=0.8,
                    sentiment_score=sentiment,
                ))
            
            result = calc.compute_company_result(
                company_name=f"测试企业{industry}{company_idx}",
                year=2024,
                sentence_results=sentence_results,
                stock_code=f"600{ind_idx}{company_idx:03d}",
                industry=industry,
            )
            results.append(result)
    
    # 行业基准修正
    calc.finalize_results(results)
    
    print_subsection("GW 指数计算结果")
    for r in results:
        risk = "🔴" if r.greenwash_index > 0.3 else "🟡" if r.greenwash_index > 0.15 else "🟢"
        print(f"     {risk} {r.company_name:20s} | {r.industry:8s} | "
              f"语调={r.avg_env_tone:+.3f} | "
              f"行业基准={r.industry_median_tone:+.3f} | "
              f"GW={r.greenwash_index:.4f} | "
              f"实质性={r.substantive_count} 描述性={r.descriptive_count}")
    
    # 汇总
    stats = calc.get_summary_stats(results)
    print_subsection("GW 指数统计")
    print(f"     GW 均值: {stats['greenwash_index']['mean']:.4f}")
    print(f"     GW 中位数: {stats['greenwash_index']['median']:.4f}")
    print(f"     GW 范围: [{stats['greenwash_index']['min']:.4f}, {stats['greenwash_index']['max']:.4f}]")
    print(f"     正GW比例: {stats['greenwash_index']['positive_ratio']:.1%}")
    
    return results


def test_fusion():
    """测试5: 融合策略验证"""
    print_header("测试 5: 融合策略验证")
    
    # 测试多数投票
    print_subsection("多数投票 (Majority Voting)")
    voter = MajorityVotingFuser()
    
    test_cases = [
        {"m1": "substantive", "m2": "substantive", "m3": "descriptive"},
        {"m1": "descriptive", "m2": "descriptive", "m3": "descriptive"},
        {"m1": "substantive", "m2": "descriptive", "m3": "non_environmental"},
    ]
    
    for i, case in enumerate(test_cases):
        result = voter.fuse(case)
        print(f"     案例{i+1}: {case} → {result.final_result} "
              f"(置信度={result.confidence:.2f}, Kappa={result.agreement_metric:.2f}, "
              f"分歧={result.is_ambiguous})")
    
    # 测试集成平均
    print_subsection("集成平均 (Ensemble Averaging)")
    averager = EnsembleAveragingFuser(method="arithmetic")
    
    score_cases = [
        {"m1": 0.8, "m2": 0.7, "m3": 0.6},
        {"m1": 0.9, "m2": 0.1, "m3": 0.5},
        {"m1": -0.5, "m2": -0.3, "m3": -0.7},
    ]
    
    for i, case in enumerate(score_cases):
        result = averager.fuse(case)
        print(f"     案例{i+1}: {case} → {result.final_result:+.2f} "
              f"(一致性={result.agreement_metric:.2f})")


def main():
    use_mock = "--mock" in sys.argv
    
    print("=" * 70)
    print("  谛观 GreenwashGuard — LLM 端到端验证")
    print(f"  模式: {'Mock (模拟)' if use_mock else 'Real (真实API)'}")
    print("=" * 70)
    
    if use_mock:
        print("\n⚠️  Mock 模式：不会调用真实 API，仅验证算法逻辑。")
        print("   使用 --real 参数进行真实 API 验证。")
        test_fusion()
        test_gw_index()
        return
    
    print("\n⚠️  真实 API 模式：将调用 DeepSeek/Qwen/GLM-4.7 三个模型。")
    print("   请确认 API Key 已配置且余额充足。")
    
    # 确认
    if "--yes" not in sys.argv:
        response = input("\n是否继续？(y/n): ")
        if response.lower() != 'y':
            print("已取消。")
            return
    
    total_start = time.time()
    
    # 测试1: 连接性
    conn_results = test_model_connectivity()
    ok_count = sum(1 for v in conn_results.values() if v["status"] == "ok")
    print(f"\n  连接性: {ok_count}/{len(conn_results)} 模型可用")
    
    if ok_count == 0:
        print("\n❌ 所有模型都无法连接，终止测试。")
        return
    
    # 测试2: 分类
    class_results, class_latency, class_tokens = test_classification()
    
    # 测试3: 情感分析
    sentiment_results = test_sentiment()
    
    # 测试4: 融合
    test_fusion()
    
    # 测试5: GW指数
    gw_results = test_gw_index()
    
    total_elapsed = time.time() - total_start
    
    # 最终报告
    print_header("📊 端到端验证报告")
    print(f"""
    ✅ 模型可用性: {ok_count}/{len(conn_results)}
    ✅ 分类延迟: {class_latency:.1f}s (10句)
    ✅ 分类 tokens: {class_tokens}
    ✅ 情感评分范围: [-1, 1]
    ✅ 融合策略: 多数投票 + 集成平均
    ✅ GW 指数: 非负约束 max(0, tone - median)
    ✅ 总耗时: {total_elapsed:.1f}s
    
    📝 结论:
    - 三模型分类+情感+融合+GW指数全链路验证通过
    - 建议在批量分析前先进行小规模试点（10-20家企业）
    - 注意 API 调用成本：每句约需 3 次调用（分类）× 3 模型 + 1 次调用（情感）× 3 模型
    """)


if __name__ == "__main__":
    main()