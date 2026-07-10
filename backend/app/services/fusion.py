"""
模型融合策略模块
实现多数投票原则（Majority Voting Rule）和集成平均法（Ensemble Averaging）
支持 Fleiss' Kappa 一致性检验
"""
from typing import List, Dict, Any, Optional
from collections import Counter
from dataclasses import dataclass


@dataclass
class FusionResult:
    """融合结果"""
    final_result: Any
    confidence: float
    vote_distribution: Dict[str, int]
    agreement_metric: float
    fusion_method: str
    is_ambiguous: bool = False
    raw_results: Dict[str, Any] = None


class MajorityVotingFuser:
    """
    多数投票融合器 — 用于分类任务
    支持：全票通过、多数投票、完全分歧
    """

    def __init__(self, threshold_ratio: float = 0.5):
        self.threshold_ratio = threshold_ratio

    def fuse(self, model_results: Dict[str, str]) -> FusionResult:
        """单次投票融合"""
        if not model_results:
            return FusionResult(
                final_result="unknown",
                confidence=0.0,
                vote_distribution={},
                agreement_metric=0.0,
                fusion_method="majority_voting",
                is_ambiguous=True,
            )

        labels = list(model_results.values())
        n_models = len(labels)
        label_counts = Counter(labels)

        max_count = max(label_counts.values())
        majority_labels = [l for l, c in label_counts.items() if c == max_count]

        kappa = self._calculate_fleiss_kappa(model_results)

        if max_count == n_models:
            final = majority_labels[0]
            confidence = 1.0
            ambiguous = False
        elif len(majority_labels) == 1:
            final = majority_labels[0]
            confidence = max_count / n_models
            ambiguous = False
        else:
            final = majority_labels[0]
            confidence = max_count / n_models
            ambiguous = True

        return FusionResult(
            final_result=final,
            confidence=confidence,
            vote_distribution=dict(label_counts),
            agreement_metric=kappa,
            fusion_method="majority_voting",
            is_ambiguous=ambiguous,
            raw_results=model_results,
        )

    def _calculate_fleiss_kappa(self, model_results: Dict[str, str]) -> float:
        """计算 Fleiss' Kappa — 评分者间一致性"""
        if len(model_results) < 2:
            return 1.0

        all_labels = set(model_results.values())
        models = list(model_results.keys())
        n_models = len(models)

        # 观察一致性 P_o
        P_o = 0.0
        pair_count = 0
        for i in range(n_models):
            for j in range(i + 1, n_models):
                if model_results[models[i]] == model_results[models[j]]:
                    P_o += 1
                pair_count += 1
        P_o = P_o / pair_count if pair_count > 0 else 0.0

        # 期望一致性 P_e
        label_props = {}
        for label in all_labels:
            count = sum(1 for v in model_results.values() if v == label)
            label_props[label] = count / n_models
        P_e = sum(p ** 2 for p in label_props.values())

        if P_e == 1.0:
            return 1.0

        kappa = (P_o - P_e) / (1 - P_e) if (1 - P_e) != 0 else 0.0
        return max(-1.0, min(1.0, kappa))

    def batch_fuse(self, batch_results: List[Dict[str, str]]) -> List[FusionResult]:
        """批量投票融合"""
        return [self.fuse(results) for results in batch_results]

    def calculate_overall_kappa(self, batch_results: List[Dict[str, str]]) -> float:
        """计算整体 Fleiss' Kappa"""
        if not batch_results:
            return 0.0

        all_labels = set()
        for results in batch_results:
            all_labels.update(results.values())

        models = list(batch_results[0].keys()) if batch_results else []
        n_models = len(models)
        n_items = len(batch_results)

        if n_models < 2 or n_items == 0:
            return 0.0

        P_i_list = []
        for item_results in batch_results:
            same_pairs = 0
            total_pairs = 0
            for i in range(n_models):
                for j in range(i + 1, n_models):
                    if item_results[models[i]] == item_results[models[j]]:
                        same_pairs += 1
                    total_pairs += 1
            P_i = same_pairs / total_pairs if total_pairs > 0 else 0
            P_i_list.append(P_i)

        P_o = sum(P_i_list) / n_items

        p_j_list = {}
        for label in all_labels:
            total = 0
            for item_results in batch_results:
                total += sum(1 for v in item_results.values() if v == label)
            p_j_list[label] = total / (n_items * n_models)

        P_e = sum(p ** 2 for p in p_j_list.values())

        if P_e >= 1.0:
            return 1.0

        kappa = (P_o - P_e) / (1 - P_e) if (1 - P_e) != 0 else 0.0
        return max(-1.0, min(1.0, kappa))


class EnsembleAveragingFuser:
    """
    集成平均融合器 — 用于连续值评分任务
    支持算术平均、加权平均、中位数等策略
    """

    def __init__(self, method: str = "arithmetic", weights: Dict[str, float] = None):
        self.method = method
        self.weights = weights or {}

    def fuse(self, model_scores: Dict[str, float]) -> FusionResult:
        """单次评分融合"""
        if not model_scores:
            return FusionResult(
                final_result=0.0,
                confidence=0.0,
                vote_distribution={},
                agreement_metric=0.0,
                fusion_method=f"ensemble_average_{self.method}",
                is_ambiguous=True,
            )

        scores = list(model_scores.values())
        n_models = len(scores)

        if self.method == "arithmetic":
            final = sum(scores) / n_models
        elif self.method == "weighted":
            weighted_sum = 0.0
            weight_total = 0.0
            for model_name, score in model_scores.items():
                w = self.weights.get(model_name, 1.0)
                weighted_sum += score * w
                weight_total += w
            final = weighted_sum / weight_total if weight_total > 0 else 0.0
        elif self.method == "median":
            sorted_scores = sorted(scores)
            mid = n_models // 2
            if n_models % 2 == 0:
                final = (sorted_scores[mid - 1] + sorted_scores[mid]) / 2
            else:
                final = sorted_scores[mid]
        elif self.method == "trimmed_mean":
            sorted_scores = sorted(scores)
            trim = max(1, n_models // 4)
            trimmed = sorted_scores[trim:-trim] if len(sorted_scores) > 2 * trim else sorted_scores
            final = sum(trimmed) / len(trimmed) if trimmed else 0.0
        else:
            final = sum(scores) / n_models

        if n_models > 1:
            mean = sum(scores) / n_models
            variance = sum((s - mean) ** 2 for s in scores) / n_models
            std = variance ** 0.5
            agreement = 1.0 - min(std, 1.0)
        else:
            agreement = 1.0

        return FusionResult(
            final_result=final,
            confidence=agreement,
            vote_distribution={k: round(v, 4) for k, v in model_scores.items()},
            agreement_metric=agreement,
            fusion_method=f"ensemble_average_{self.method}",
            is_ambiguous=agreement < 0.5,
            raw_results=model_scores,
        )

    def batch_fuse(self, batch_scores: List[Dict[str, float]]) -> List[FusionResult]:
        """批量评分融合"""
        return [self.fuse(scores) for scores in batch_scores]