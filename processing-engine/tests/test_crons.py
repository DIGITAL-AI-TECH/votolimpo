"""Tests for cron job functions."""

import math
from datetime import UTC, datetime, timedelta

from app.cron import ROLE_WEIGHT, SEVERITY_WEIGHT, _calculate_politician_score


class TestCalculatePoliticianScore:
    """Test the score calculation function used by the recalculate_scores cron."""

    def test_empty_articles_returns_zero(self):
        result = _calculate_politician_score([])
        assert result["score"] == 0.0
        assert result["components"] == {}

    def test_single_article_returns_positive(self):
        articles = [
            {
                "severity": "medium",
                "role": "protagonist",
                "veracity_score": 0.8,
                "published_at": datetime.now(UTC),
            }
        ]
        result = _calculate_politician_score(articles)
        assert result["score"] > 0.0
        assert result["components"]["article_count"] == 1

    def test_more_articles_increase_score(self):
        now = datetime.now(UTC)
        base_article = {
            "severity": "medium",
            "role": "protagonist",
            "veracity_score": 0.6,
            "published_at": now,
        }
        low = _calculate_politician_score([base_article])
        high = _calculate_politician_score([base_article] * 10)
        assert high["score"] > low["score"]

    def test_higher_severity_increases_score(self):
        now = datetime.now(UTC)
        low = _calculate_politician_score(
            [
                {
                    "severity": "low",
                    "role": "mentioned",
                    "veracity_score": 0.5,
                    "published_at": now,
                }
            ]
        )
        high = _calculate_politician_score(
            [
                {
                    "severity": "critical",
                    "role": "mentioned",
                    "veracity_score": 0.5,
                    "published_at": now,
                }
            ]
        )
        assert high["score"] > low["score"]

    def test_recency_decay_older_articles_lower(self):
        now = datetime.now(UTC)
        recent = _calculate_politician_score(
            [
                {
                    "severity": "medium",
                    "role": "protagonist",
                    "veracity_score": 0.7,
                    "published_at": now,
                }
            ]
        )
        old = _calculate_politician_score(
            [
                {
                    "severity": "medium",
                    "role": "protagonist",
                    "veracity_score": 0.7,
                    "published_at": now - timedelta(days=180),
                }
            ]
        )
        assert recent["score"] > old["score"]

    def test_score_bounded_0_100(self):
        now = datetime.now(UTC)
        articles = [
            {
                "severity": "critical",
                "role": "protagonist",
                "veracity_score": 1.0,
                "published_at": now,
            }
        ] * 200
        result = _calculate_politician_score(articles)
        assert 0.0 <= result["score"] <= 100.0

    def test_score_returns_float(self):
        result = _calculate_politician_score(
            [{"severity": "low", "published_at": datetime.now(UTC)}]
        )
        assert isinstance(result["score"], float)
        assert not math.isnan(result["score"])
        assert not math.isinf(result["score"])

    def test_severity_weights_defined(self):
        assert "low" in SEVERITY_WEIGHT
        assert "critical" in SEVERITY_WEIGHT
        assert SEVERITY_WEIGHT["critical"] > SEVERITY_WEIGHT["low"]

    def test_role_weights_defined(self):
        assert "protagonist" in ROLE_WEIGHT
        assert "mentioned" in ROLE_WEIGHT
        assert ROLE_WEIGHT["protagonist"] > ROLE_WEIGHT["mentioned"]
