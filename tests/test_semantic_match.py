import unittest
import numpy as np

from utils.match_engine import match_users
from utils.zhihu_openapi import build_semantic_embedding, generate_profile


def cosine_similarity(v1, v2):
    denom = np.linalg.norm(v1) * np.linalg.norm(v2)
    if denom == 0:
        return 0.0
    return float(np.dot(v1, v2) / denom)


class SemanticMatchTest(unittest.TestCase):
    def test_match_users_vectorized_ranking_and_filters(self):
        candidate_pool = [
            {"input_text": "base", "embedding": np.array([1.0, 0.0])},
            {"input_text": "closest", "embedding": np.array([2.0, 0.0])},
            {"input_text": "different", "embedding": np.array([0.0, 1.0])},
            {"input_text": "empty", "embedding": np.array([0.0, 0.0])},
        ]

        results = match_users(candidate_pool, 0, top_k=2, min_similarity=0.5)

        self.assertEqual([item["input"] for item in results], ["closest"])
        self.assertEqual(results[0]["similarity"], 1.0)

    def test_match_users_rejects_invalid_base_index(self):
        with self.assertRaises(IndexError):
            match_users([{"input_text": "base", "embedding": np.array([1.0])}], 1)

    def test_related_topics_have_high_similarity(self):
        a = build_semantic_embedding("人工智能 伦理 安全 监管 公共利益")
        b = build_semantic_embedding("AI 安全治理 与 伦理 责任")
        self.assertGreater(cosine_similarity(a, b), 0.5)

    def test_unrelated_topics_have_lower_similarity(self):
        a = build_semantic_embedding("人工智能 伦理 安全 监管 公共利益")
        b = build_semantic_embedding("篮球 足球 球员 比赛 训练")
        self.assertLess(cosine_similarity(a, b), 0.5)

    def test_profile_scores_are_in_valid_range(self):
        prof = generate_profile("AI 伦理")
        scores = [score for _, score in prof["viewpoint_scores"]]
        self.assertTrue(all(0 <= score <= 100 for score in scores))


if __name__ == "__main__":
    unittest.main()
