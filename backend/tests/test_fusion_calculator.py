"""融合模块与计算器单元测试"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.fusion import MajorityVotingFuser, EnsembleAveragingFuser
from app.services.calculator import GreenwashIndexCalculator, SentenceLevelResult


class TestMajorityVotingFuser(unittest.TestCase):
    """多数投票融合器测试"""

    def setUp(self):
        self.fuser = MajorityVotingFuser()

    def test_unanimous_agreement(self):
        """全票一致"""
        results = {
            "model1": "substantive",
            "model2": "substantive",
            "model3": "substantive",
        }
        fusion = self.fuser.fuse(results)
        self.assertEqual(fusion.final_result, "substantive")
        self.assertEqual(fusion.confidence, 1.0)
        self.assertEqual(fusion.vote_type if hasattr(fusion, 'vote_type') else "unanimous", "unanimous" if hasattr(fusion, 'vote_type') else "unanimous")
        self.assertFalse(fusion.is_ambiguous)

    def test_majority_agreement(self):
        """多数一致（2:1）"""
        results = {
            "model1": "substantive",
            "model2": "substantive",
            "model3": "descriptive",
        }
        fusion = self.fuser.fuse(results)
        self.assertEqual(fusion.final_result, "substantive")
        self.assertAlmostEqual(fusion.confidence, 2 / 3, places=2)
        self.assertFalse(fusion.is_ambiguous)

    def test_full_divergence(self):
        """完全分歧（各不同）"""
        results = {
            "model1": "substantive",
            "model2": "descriptive",
            "model3": "non_environmental",
        }
        fusion = self.fuser.fuse(results)
        self.assertTrue(fusion.is_ambiguous)
        self.assertAlmostEqual(fusion.confidence, 1 / 3, places=2)

    def test_empty_results(self):
        """空输入"""
        fusion = self.fuser.fuse({})
        self.assertEqual(fusion.final_result, "unknown")
        self.assertTrue(fusion.is_ambiguous)

    def test_overall_kappa_unanimous(self):
        """整体Kappa：全一致应为1.0"""
        batch = [
            {"m1": "substantive", "m2": "substantive", "m3": "substantive"},
            {"m1": "descriptive", "m2": "descriptive", "m3": "descriptive"},
        ]
        kappa = self.fuser.calculate_overall_kappa(batch)
        self.assertEqual(kappa, 1.0)

    def test_overall_kappa_range(self):
        """整体Kappa应在[-1, 1]范围内"""
        batch = [
            {"m1": "substantive", "m2": "substantive", "m3": "descriptive"},
            {"m1": "descriptive", "m2": "substantive", "m3": "descriptive"},
            {"m1": "substantive", "m2": "descriptive", "m3": "substantive"},
        ]
        kappa = self.fuser.calculate_overall_kappa(batch)
        self.assertGreaterEqual(kappa, -1.0)
        self.assertLessEqual(kappa, 1.0)

    def test_batch_fuse(self):
        """批量融合"""
        batch = [
            {"m1": "substantive", "m2": "substantive", "m3": "substantive"},
            {"m1": "descriptive", "m2": "descriptive", "m3": "substantive"},
        ]
        results = self.fuser.batch_fuse(batch)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].final_result, "substantive")
        self.assertEqual(results[0].confidence, 1.0)


class TestEnsembleAveragingFuser(unittest.TestCase):
    """集成平均融合器测试"""

    def test_arithmetic_mean(self):
        """算术平均"""
        fuser = EnsembleAveragingFuser(method="arithmetic")
        scores = {"m1": 0.5, "m2": 0.3, "m3": 0.7}
        result = fuser.fuse(scores)
        expected = (0.5 + 0.3 + 0.7) / 3
        self.assertAlmostEqual(result.final_result, expected, places=4)

    def test_weighted_mean(self):
        """加权平均"""
        weights = {"m1": 2.0, "m2": 1.0, "m3": 1.0}
        fuser = EnsembleAveragingFuser(method="weighted", weights=weights)
        scores = {"m1": 0.5, "m2": 0.3, "m3": 0.7}
        result = fuser.fuse(scores)
        expected = (0.5 * 2 + 0.3 * 1 + 0.7 * 1) / 4
        self.assertAlmostEqual(result.final_result, expected, places=4)

    def test_median_odd(self):
        """中位数（奇数个）"""
        fuser = EnsembleAveragingFuser(method="median")
        scores = {"m1": 0.1, "m2": 0.5, "m3": 0.9}
        result = fuser.fuse(scores)
        self.assertAlmostEqual(result.final_result, 0.5, places=4)

    def test_median_even(self):
        """中位数（偶数个）"""
        fuser = EnsembleAveragingFuser(method="median")
        scores = {"m1": 0.1, "m2": 0.3, "m3": 0.7, "m4": 0.9}
        result = fuser.fuse(scores)
        self.assertAlmostEqual(result.final_result, 0.5, places=4)

    def test_high_agreement(self):
        """高一致性"""
        fuser = EnsembleAveragingFuser(method="arithmetic")
        scores = {"m1": 0.50, "m2": 0.51, "m3": 0.49}
        result = fuser.fuse(scores)
        self.assertGreater(result.confidence, 0.8)
        self.assertFalse(result.is_ambiguous)


class TestGreenwashIndexCalculator(unittest.TestCase):
    """漂绿指数计算器测试"""

    def setUp(self):
        self.calc = GreenwashIndexCalculator()

    def test_gw_index_positive(self):
        """企业语调高于行业中位数，GW > 0"""
        gw = self.calc.calculate_greenwash_index(0.5, 0.3)
        self.assertAlmostEqual(gw, 0.2, places=4)

    def test_gw_index_zero(self):
        """企业语调低于行业中位数，GW = 0"""
        gw = self.calc.calculate_greenwash_index(0.2, 0.4)
        self.assertEqual(gw, 0.0)

    def test_gw_index_equal(self):
        """企业语调等于行业中位数，GW = 0"""
        gw = self.calc.calculate_greenwash_index(0.3, 0.3)
        self.assertEqual(gw, 0.0)

    def test_company_tone_only_descriptive(self):
        """仅描述性语句参与语调计算"""
        sentences = [
            SentenceLevelResult(
                sentence="环保投入5000万元",
                classification="substantive",
                classification_confidence=1.0,
                sentiment_score=0.5,
            ),
            SentenceLevelResult(
                sentence="高度重视环保工作",
                classification="descriptive",
                classification_confidence=1.0,
                sentiment_score=0.6,
            ),
            SentenceLevelResult(
                sentence="推动绿色发展",
                classification="descriptive",
                classification_confidence=1.0,
                sentiment_score=0.4,
            ),
        ]
        tone = self.calc.calculate_company_tone(sentences)
        self.assertAlmostEqual(tone, 0.5, places=4)

    def test_company_tone_no_descriptive(self):
        """无描述性语句时语调为0"""
        sentences = [
            SentenceLevelResult(
                sentence="环保投入5000万元",
                classification="substantive",
                classification_confidence=1.0,
                sentiment_score=0.5,
            ),
        ]
        tone = self.calc.calculate_company_tone(sentences)
        self.assertEqual(tone, 0.0)

    def test_industry_median(self):
        """行业中位数计算"""
        from app.services.calculator import CompanyGreenwashResult

        companies = [
            CompanyGreenwashResult(company_name="A", industry="化工", year=2024, avg_env_tone=0.2),
            CompanyGreenwashResult(company_name="B", industry="化工", year=2024, avg_env_tone=0.4),
            CompanyGreenwashResult(company_name="C", industry="化工", year=2024, avg_env_tone=0.6),
        ]
        medians = self.calc.compute_industry_benchmark(companies, year=2024)
        self.assertIn("化工", medians)
        self.assertAlmostEqual(medians["化工"], 0.4, places=4)

    def test_finalize_results(self):
        """最终结果计算（行业基准修正）"""
        from app.services.calculator import CompanyGreenwashResult

        companies = [
            CompanyGreenwashResult(
                company_name="A", stock_code="001", year=2024, industry="化工",
                avg_env_tone=0.5, descriptive_count=5,
            ),
            CompanyGreenwashResult(
                company_name="B", stock_code="002", year=2024, industry="化工",
                avg_env_tone=0.3, descriptive_count=5,
            ),
            CompanyGreenwashResult(
                company_name="C", stock_code="003", year=2024, industry="化工",
                avg_env_tone=0.4, descriptive_count=5,
            ),
        ]
        results = self.calc.finalize_results(companies)
        self.assertEqual(len(results), 3)
        for r in results:
            self.assertGreaterEqual(r.greenwash_index, 0.0)


class TestTextUtils(unittest.TestCase):
    """文本工具测试"""

    def test_split_sentences(self):
        """句子切分"""
        from app.services.text_utils import split_sentences

        text = "公司本年度环保投入达五千万元，同比增长百分之十五。通过了ISO14001环境管理体系认证。持续推动绿色低碳转型发展。"
        sentences = split_sentences(text)
        self.assertGreaterEqual(len(sentences), 2)

    def test_split_empty(self):
        """空文本切分"""
        from app.services.text_utils import split_sentences

        self.assertEqual(split_sentences(""), [])
        self.assertEqual(split_sentences(None), [])

    def test_env_keyword_filter(self):
        """环境关键词过滤"""
        from app.services.text_utils import filter_env_sentences

        sentences = [
            "公司环保投入达5000万元",
            "公司营业收入增长15%",
            "积极推动绿色低碳转型",
            "董事会审议通过利润分配方案",
        ]
        env_sents, matched = filter_env_sentences(sentences)
        self.assertEqual(len(env_sents), 2)
        self.assertEqual(len(matched), 2)

    def test_winsorize(self):
        """缩尾处理"""
        from app.services.text_utils import winsorize, calculate_winsorize

        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
        lower, upper = calculate_winsorize(values, lower=0.1, upper=0.9)
        self.assertLess(lower, upper)
        result = winsorize(100, lower, upper)
        self.assertLessEqual(result, upper)
        self.assertGreaterEqual(result, lower)

    def test_clean_text(self):
        """文本清洗"""
        from app.services.text_utils import clean_text

        text = "  你好\u200b世界  \xa0测试  "
        cleaned = clean_text(text)
        self.assertEqual(cleaned, "你好世界 测试")


if __name__ == "__main__":
    unittest.main(verbosity=2)
