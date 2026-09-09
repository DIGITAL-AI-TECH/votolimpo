"""Tests for politician score calculation."""

from datetime import datetime, timezone, timedelta

import pytest

from app.cron import _calculate_politician_score, SEVERITY_WEIGHT, ROLE_WEIGHT


class TestCalculatePoliticianScore:
    def test_empty_articles(self):
        result = _calculate_politician_score([])
        assert result["score"] == 0.0
        assert result["components"] == {}

    def test_single_article_low_severity(self):
        articles = [
            {"severity": "low", "role": "mentioned", "veracity_score": 0.5,
             "published_at": datetime.now(timezone.utc)},
        ]
        result = _calculate_politician_score(articles)
        assert 0 < result["score"] < 100
        assert result["components"]["article_count"] == 1

    def test_high_severity_gives_higher_score(self):
        base = {"role": "protagonist", "veracity_score": 0.8,
                "published_at": datetime.now(timezone.utc)}
        low = _calculate_politician_score([{**base, "severity": "low"}])
        high = _calculate_politician_score([{**base, "severity": "critical"}])
        assert high["score"] > low["score"]

    def test_recency_decay(self):
        base = {"severity": "high", "role": "protagonist", "veracity_score": 0.8}
        recent = _calculate_politician_score([
            {**base, "published_at": datetime.now(timezone.utc)},
        ])
        old = _calculate_politician_score([
            {**base, "published_at": datetime.now(timezone.utc) - timedelta(days=365)},
        ])
        assert recent["score"] > old["score"]

    def test_volume_bonus(self):
        base = {"severity": "medium", "role": "mentioned", "veracity_score": 0.5,
                "published_at": datetime.now(timezone.utc)}
        one = _calculate_politician_score([base])
        many = _calculate_politician_score([base] * 10)
        assert many["components"]["volume_bonus"] > one["components"]["volume_bonus"]

    def test_score_bounded_0_100(self):
        articles = [
            {"severity": "critical", "role": "protagonist", "veracity_score": 1.0,
             "published_at": datetime.now(timezone.utc)}
        ] * 100
        result = _calculate_politician_score(articles)
        assert 0 <= result["score"] <= 100

    def test_missing_veracity_defaults_to_half(self):
        articles = [
            {"severity": "medium", "role": "mentioned", "veracity_score": None,
             "published_at": datetime.now(timezone.utc)},
        ]
        result = _calculate_politician_score(articles)
        assert result["score"] > 0

    def test_naive_datetime_handled(self):
        articles = [
            {"severity": "low", "role": "mentioned", "veracity_score": 0.5,
             "published_at": datetime(2025, 1, 1)},
        ]
        result = _calculate_politician_score(articles)
        assert result["score"] > 0

    def test_no_published_at(self):
        articles = [
            {"severity": "low", "role": "mentioned", "veracity_score": 0.5,
             "published_at": None},
        ]
        result = _calculate_politician_score(articles)
        assert result["score"] > 0


class TestWeights:
    def test_severity_weights_monotonic(self):
        values = [SEVERITY_WEIGHT[k] for k in ["low", "medium", "high", "critical"]]
        assert values == sorted(values)

    def test_role_weights_protagonist_highest(self):
        assert ROLE_WEIGHT["protagonist"] >= max(
            v for k, v in ROLE_WEIGHT.items() if k != "protagonist"
        )
