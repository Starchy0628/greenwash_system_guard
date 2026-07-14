"""Mock 服务单元测试"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.mock_service import (
    mock_classify_sentence,
    mock_sentiment_score,
    run_mock_analysis,
    generate_mock_company_text,
)
from app.services.text_utils import split_sentences


class TestMockClassifySentence(unittest.TestCase):
    """语句分类测试"""

    def test_substantive_with_amount(self):
        """含具体金额的实质性陈述"""
        sentence = "公司本年度环保投入达5000万元，同比增长15.5%。"
        cat, vote_type, conf, _ = mock_classify_sentence(sentence)
        self.assertEqual(cat, "substantive")

    def test_substantive_with_certification(self):
        """含认证的实质性陈述"""
        sentence = "通过ISO14001环境管理体系认证，二氧化硫排放量减少12.3%。"
        cat, vote_type, conf, _ = mock_classify_sentence(sentence)
        self.assertEqual(cat, "substantive")

    def test_substantive_with_energy_data(self):
        """含能耗数据的实质性陈述"""
        sentence = "单位产值能耗同比下降6.7%，完成年度节能减排目标。"
        cat, vote_type, conf, _ = mock_classify_sentence(sentence)
        self.assertEqual(cat, "substantive")

    def test_descriptive_qualitative(self):
        """定性描述性陈述（无定量数据不应为实质性）"""
        sentence = "我们秉持绿色发展理念，推动企业可持续发展。"
        cat, vote_type, conf, _ = mock_classify_sentence(sentence)
        self.assertIn(cat, ["descriptive", "dispute"])
        self.assertNotEqual(cat, "substantive")

    def test_descriptive_green_development(self):
        """绿色发展口号（无定量数据不应为实质性）"""
        sentence = "公司坚持绿色发展理念，关注生态环境保护。"
        cat, vote_type, conf, _ = mock_classify_sentence(sentence)
        self.assertIn(cat, ["descriptive", "dispute"])
        self.assertNotEqual(cat, "substantive")

    def test_deterministic_same_sentence(self):
        """同句同分类（确定性验证）"""
        sentence = "清洁能源使用比例提升至13.5%，碳排放强度降低10.2%。"
        results = []
        for _ in range(10):
            cat, _, _, _ = mock_classify_sentence(sentence)
            results.append(cat)
        self.assertEqual(len(set(results)), 1)

    def test_clean_energy_substantive(self):
        """清洁能源数据应为实质性"""
        sentence = "清洁能源使用比例提升至13.5%，碳排放强度降低10.2%。"
        cat, vote_type, conf, _ = mock_classify_sentence(sentence)
        self.assertEqual(cat, "substantive")
        self.assertNotEqual(vote_type, "full_divergence")


class TestMockSentimentScore(unittest.TestCase):
    """情感打分测试"""

    def test_positive_sentiment(self):
        """积极修辞语句"""
        sentence = "公司高度重视环境保护工作，积极履行企业社会责任。"
        score, _ = mock_sentiment_score(sentence)
        self.assertGreater(score, 0)

    def test_deterministic_same_sentence(self):
        """同句同分数（确定性验证）"""
        sentence = "公司高度重视环境保护工作，积极履行企业社会责任。"
        scores = []
        for _ in range(10):
            score, _ = mock_sentiment_score(sentence)
            scores.append(score)
        self.assertEqual(len(set(scores)), 1)

    def test_score_range(self):
        """分数在[-1, 1]区间内"""
        test_sentences = [
            "公司高度重视环境保护工作。",
            "报告期内环保投入达5000万元。",
            "虽然存在不足，但我们持续改进。",
        ]
        for s in test_sentences:
            score, _ = mock_sentiment_score(s)
            self.assertGreaterEqual(score, -1.0)
            self.assertLessEqual(score, 1.0)


class TestGenerateMockText(unittest.TestCase):
    """模拟文本生成测试"""

    def test_no_duplicate_sentences(self):
        """生成的语句无重复"""
        for i in range(10):
            text = generate_mock_company_text(f"测试企业{i}", "化工", seed=i)
            sents = split_sentences(text)
            unique_sents = set(sents)
            self.assertEqual(len(sents), len(unique_sents),
                             f"企业{i}存在重复语句: {len(sents) - len(unique_sents)}条")

    def test_deterministic_same_seed(self):
        """相同种子生成相同文本"""
        text1 = generate_mock_company_text("测试企业", "化工", seed=42)
        text2 = generate_mock_company_text("测试企业", "化工", seed=42)
        self.assertEqual(text1, text2)

    def test_different_seed_different_text(self):
        """不同种子生成不同文本"""
        text1 = generate_mock_company_text("测试企业", "化工", seed=1)
        text2 = generate_mock_company_text("测试企业", "化工", seed=2)
        self.assertNotEqual(text1, text2)

    def test_substantive_majority(self):
        """实质性语句占环境语句多数"""
        text = generate_mock_company_text("测试企业", "化工", seed=100)
        result = run_mock_analysis(text, "化工")
        self.assertGreater(result["substantive_count"], result["descriptive_count"])


class TestRunMockAnalysis(unittest.TestCase):
    """完整Mock分析流程测试"""

    def test_analysis_basic_structure(self):
        """分析结果包含所有必要字段"""
        text = (
            "公司高度重视环境保护工作，全年环保投入达5000万元，同比增长15%。"
            "通过ISO14001认证，碳排放强度降低20%。"
            "我们持续推动绿色低碳转型，实现可持续发展。"
            "公司全年实现营业收入稳步增长。"
        )
        result = run_mock_analysis(text, "白酒")

        required_fields = [
            "total_sentences", "env_sentences", "substantive_count",
            "descriptive_count", "non_env_count", "tone_score",
            "industry_median_tone", "gw_index", "fleiss_kappa",
            "dispute_count", "sentence_results",
        ]
        for field in required_fields:
            self.assertIn(field, result)

    def test_gw_index_non_negative(self):
        """GW指数非负"""
        text = (
            "公司高度重视环境保护工作，积极履行企业社会责任。"
            "持续推动绿色低碳转型，实现可持续发展。"
            "环保投入达5000万元，同比增长15%。"
        )
        result = run_mock_analysis(text, "白酒")
        self.assertGreaterEqual(result["gw_index"], 0.0)

    def test_sentence_results_consistent(self):
        """语句级结果与汇总数据一致"""
        text = (
            "环保投入达5000万元，同比增长15%。"
            "公司高度重视环境保护工作。"
            "推动绿色低碳转型，实现可持续发展。"
            "通过ISO14001认证，碳排放降低20%。"
            "公司全年营收稳步增长。"
        )
        result = run_mock_analysis(text, "化工")

        sentences = result["sentence_results"]
        sub_count = sum(1 for s in sentences if s["final_category"] == "substantive")
        desc_count = sum(1 for s in sentences if s["final_category"] == "descriptive")

        self.assertEqual(sub_count, result["substantive_count"])
        self.assertEqual(desc_count, result["descriptive_count"])

    def test_fleiss_kappa_range(self):
        """Fleiss' Kappa 在合理范围"""
        text = (
            "环保投入达5000万元，同比增长15%。"
            "公司高度重视环境保护工作。"
            "推动绿色低碳转型。"
        )
        result = run_mock_analysis(text, "化工")
        self.assertGreaterEqual(result["fleiss_kappa"], 0.0)
        self.assertLessEqual(result["fleiss_kappa"], 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
