"""Tests for post-processor plugins."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.plugins.post_processors import (
    PostProcessor,
    normalize_for_search,
    normalize_entity_name,
    generate_slug,
    get_post_processor,
    POST_PROCESSORS,
    _register_all,
)
from app.plugins.post_processors.entity_resolver import EntityResolver
from app.plugins.post_processors.score_calculator import ScoreCalculator, _clamp, _normalize_multi_source
from app.plugins.post_processors.relationship_builder import RelationshipBuilder
from app.plugins.post_processors.milestone_detector import MilestoneDetector
from app.plugins.post_processors.article_matcher import ArticleMatcher, _calculate_similarity
from app.plugins.post_processors.cluster_updater import ClusterUpdater


# ─── Helpers ───


class _AsyncCtx:
    """Proper async context manager for pool.acquire()."""

    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *args):
        return False


def _make_pool(conn=None):
    """Create a mock asyncpg.Pool that yields a mock connection."""
    mock_conn = conn or AsyncMock()
    mock_pool = MagicMock()
    mock_pool.acquire.return_value = _AsyncCtx(mock_conn)
    return mock_pool, mock_conn


# ─── Protocol compliance ───


class TestProtocolCompliance:
    def test_entity_resolver_implements_protocol(self):
        assert isinstance(EntityResolver(), PostProcessor)

    def test_score_calculator_implements_protocol(self):
        assert isinstance(ScoreCalculator(), PostProcessor)

    def test_relationship_builder_implements_protocol(self):
        assert isinstance(RelationshipBuilder(), PostProcessor)

    def test_milestone_detector_implements_protocol(self):
        assert isinstance(MilestoneDetector(), PostProcessor)

    def test_article_matcher_implements_protocol(self):
        assert isinstance(ArticleMatcher(), PostProcessor)

    def test_cluster_updater_implements_protocol(self):
        assert isinstance(ClusterUpdater(), PostProcessor)


# ─── Registry ───


class TestRegistry:
    def test_register_all_populates_registry(self):
        POST_PROCESSORS.clear()
        _register_all()
        assert "entity_resolver" in POST_PROCESSORS
        assert "score_calculator" in POST_PROCESSORS
        assert "relationship_builder" in POST_PROCESSORS
        assert "milestone_detector" in POST_PROCESSORS
        assert "article_matcher" in POST_PROCESSORS
        assert "cluster_updater" in POST_PROCESSORS

    def test_get_post_processor_returns_instance(self):
        pp = get_post_processor("score_calculator")
        assert isinstance(pp, ScoreCalculator)

    def test_get_post_processor_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown post-processor"):
            get_post_processor("nonexistent_processor")


# ─── Helper functions ───


class TestHelperFunctions:
    def test_normalize_for_search_removes_accents(self):
        assert normalize_for_search("José da Silva") == "jose da silva"

    def test_normalize_for_search_collapses_spaces(self):
        assert normalize_for_search("  João   Marcos  ") == "joao marcos"

    def test_normalize_entity_name_removes_title(self):
        assert normalize_entity_name("Deputado João Silva") == "João Silva"

    def test_normalize_entity_name_removes_ex_prefix(self):
        # Only strips one prefix (first match), so "ex-" is removed but "Governador" stays
        assert normalize_entity_name("ex-Governador Carlos") == "Governador Carlos"

    def test_normalize_entity_name_removes_governador(self):
        assert normalize_entity_name("Governador Carlos") == "Carlos"

    def test_normalize_entity_name_case_insensitive(self):
        assert normalize_entity_name("SENADOR Maria Souza") == "Maria Souza"

    def test_normalize_entity_name_no_prefix(self):
        assert normalize_entity_name("Carlos Almeida") == "Carlos Almeida"

    def test_generate_slug(self):
        assert generate_slug("José da Silva") == "jose-da-silva"

    def test_generate_slug_strips_special_chars(self):
        assert generate_slug("João (PL-SP)") == "joao-pl-sp"


# ─── ScoreCalculator ───


class TestScoreCalculator:
    async def test_computes_score_with_default_weights(self):
        pool, conn = _make_pool()
        conn.fetchrow = AsyncMock(return_value=None)

        output = {
            "veracity_signals": {
                "multi_source": 1.0,
                "narrative_consistency": 0.8,
                "documental_evidence": 0.7,
                "temporality": 0.6,
                "emotional_language": 0.3,
            }
        }

        result = await ScoreCalculator().process(output, {}, pool, {})
        assert "veracity_score" in result
        assert "score_components" in result
        assert 0.0 <= result["veracity_score"] <= 1.0

    async def test_uses_source_reputation_from_db(self):
        pool, conn = _make_pool()
        conn.fetchrow = AsyncMock(return_value={"reputation_score": 0.90})

        output = {"veracity_signals": {}}
        metadata = {"source_name": "g1.globo.com"}

        result = await ScoreCalculator().process(output, metadata, pool, {})
        assert result["score_components"]["source_reputation"] == 0.90

    async def test_custom_output_field(self):
        pool, conn = _make_pool()
        conn.fetchrow = AsyncMock(return_value=None)

        result = await ScoreCalculator().process(
            {"veracity_signals": {}}, {}, pool, {"output_field": "custom_score"},
        )
        assert "custom_score" in result

    def test_clamp(self):
        assert _clamp(-0.5) == 0.0
        assert _clamp(1.5) == 1.0
        assert _clamp(0.5) == 0.5

    def test_normalize_multi_source(self):
        assert _normalize_multi_source(0) == 0.0
        assert _normalize_multi_source(-1) == 0.0
        assert _normalize_multi_source(0.3) == 0.5
        assert _normalize_multi_source(0.5) == 0.5
        assert _normalize_multi_source(0.8) == 1.0


# ─── EntityResolver ───


class TestEntityResolver:
    async def test_resolves_politician_exact_match(self):
        pool, conn = _make_pool()
        # Exact match returns id=42
        conn.fetchrow = AsyncMock(return_value={"id": 42})

        output = {"politicians": [{"name": "Lula", "party": "PT"}]}
        result = await EntityResolver().process(output, {}, pool, {})

        assert result["resolved_politician_ids"] == [42]
        assert result["politicians"][0]["resolved_id"] == 42

    async def test_creates_new_politician_when_no_match(self):
        pool, conn = _make_pool()
        # No exact match, no fuzzy match, no party match → create returns id=99
        conn.fetchrow = AsyncMock(side_effect=[None, None, None, {"id": 99}])

        output = {"politicians": [{"name": "Novo Político", "party": "PL", "state": "SP"}]}
        result = await EntityResolver().process(output, {}, pool, {})

        assert result["resolved_politician_ids"] == [99]

    async def test_skips_politicians_without_name(self):
        pool, conn = _make_pool()

        output = {"politicians": [{"party": "PT"}]}
        result = await EntityResolver().process(output, {}, pool, {})

        assert result["resolved_politician_ids"] == []

    async def test_resolves_entities(self):
        pool, conn = _make_pool()
        conn.fetchrow = AsyncMock(return_value={"id": 10})
        conn.execute = AsyncMock()

        output = {"entities": [{"name": "Petrobras", "type": "organization"}]}
        result = await EntityResolver().process(output, {}, pool, {})

        assert result["resolved_entity_ids"] == [10]
        assert result["entities"][0]["resolved_id"] == 10

    async def test_skips_entities_without_type(self):
        pool, conn = _make_pool()

        output = {"entities": [{"name": "Petrobras"}]}
        result = await EntityResolver().process(output, {}, pool, {})

        assert result["resolved_entity_ids"] == []

    async def test_preserves_existing_output_keys(self):
        pool, conn = _make_pool()

        output = {"politicians": [], "entities": [], "existing_key": "untouched"}
        result = await EntityResolver().process(output, {}, pool, {})

        assert result["existing_key"] == "untouched"
        assert "resolved_politician_ids" in result


# ─── RelationshipBuilder ───


class TestRelationshipBuilder:
    async def test_persists_relationships(self):
        pool, conn = _make_pool()
        conn.fetchrow = AsyncMock(return_value={"id": 1})
        conn.execute = AsyncMock()

        output = {
            "article_id": 100,
            "entities": [
                {"name": "Petrobras", "resolved_id": 10},
                {"name": "Lava Jato", "resolved_id": 20},
            ],
            "politicians": [],
            "relationships": [
                {"source": "Petrobras", "target": "Lava Jato", "type": "investigation", "evidence": "texto"},
            ],
        }
        result = await RelationshipBuilder().process(output, {}, pool, {})
        assert result["persisted_relationship_ids"] == [1]

    async def test_skips_relationship_missing_source(self):
        pool, conn = _make_pool()

        output = {
            "entities": [{"name": "A", "resolved_id": 1}],
            "politicians": [],
            "relationships": [{"source": "Unknown", "target": "A", "type": "x"}],
        }
        result = await RelationshipBuilder().process(output, {}, pool, {})
        assert result["persisted_relationship_ids"] == []

    async def test_no_relationships_key_returns_empty(self):
        pool, conn = _make_pool()

        output = {"entities": [], "politicians": []}
        result = await RelationshipBuilder().process(output, {}, pool, {})
        assert result["persisted_relationship_ids"] == []


# ─── MilestoneDetector ───


class TestMilestoneDetector:
    async def test_persists_milestones_above_threshold(self):
        pool, conn = _make_pool()
        # No existing (dedup check), then insert returns id
        conn.fetchrow = AsyncMock(side_effect=[None, {"id": 5}])

        output = {
            "article_id": 100,
            "politicians": [{"name": "Lula", "resolved_id": 42}],
            "milestones": [{
                "politician_name": "Lula",
                "type": "indictment",
                "date": "2026-01-15",
                "title": "Indiciamento",
                "description": "Desc",
                "confidence": 0.90,
            }],
        }
        result = await MilestoneDetector().process(output, {}, pool, {})
        assert result["persisted_milestone_ids"] == [5]

    async def test_skips_below_threshold(self):
        pool, conn = _make_pool()

        output = {
            "article_id": 100,
            "politicians": [{"name": "Lula", "resolved_id": 42}],
            "milestones": [{
                "politician_name": "Lula",
                "type": "indictment",
                "date": "2026-01-15",
                "confidence": 0.50,
            }],
        }
        result = await MilestoneDetector().process(output, {}, pool, {"confidence_threshold": 0.70})
        assert result["persisted_milestone_ids"] == []

    async def test_skips_without_politician_id(self):
        pool, conn = _make_pool()

        output = {
            "article_id": 100,
            "politicians": [{"name": "Lula"}],  # no resolved_id
            "milestones": [{
                "politician_name": "Lula",
                "type": "indictment",
                "date": "2026-01-15",
                "confidence": 0.90,
            }],
        }
        result = await MilestoneDetector().process(output, {}, pool, {})
        assert result["persisted_milestone_ids"] == []

    async def test_dedup_skips_existing(self):
        pool, conn = _make_pool()
        # Dedup check returns existing row → skip
        conn.fetchrow = AsyncMock(return_value={"id": 99})

        output = {
            "article_id": 100,
            "politicians": [{"name": "Lula", "resolved_id": 42}],
            "milestones": [{
                "politician_name": "Lula",
                "type": "indictment",
                "date": "2026-01-15",
                "confidence": 0.90,
            }],
        }
        result = await MilestoneDetector().process(output, {}, pool, {})
        assert result["persisted_milestone_ids"] == []


# ─── ArticleMatcher ───


class TestArticleMatcher:
    def test_calculate_similarity_full_overlap(self):
        a = {"keywords": ["corrupção", "lava jato"], "published_at": None, "politician_ids": [1, 2]}
        b = {"keywords": ["corrupção", "lava jato"], "published_at": None, "politician_ids": [1, 2]}
        weights = {"entity_overlap": 0.40, "keyword_overlap": 0.35, "temporal_proximity": 0.25}
        result = _calculate_similarity(a, b, weights)
        assert result["entity_overlap"] == 1.0
        assert result["keyword_overlap"] == 1.0

    def test_calculate_similarity_no_overlap(self):
        a = {"keywords": ["educação"], "published_at": None, "politician_ids": [1]}
        b = {"keywords": ["saúde"], "published_at": None, "politician_ids": [2]}
        weights = {"entity_overlap": 0.40, "keyword_overlap": 0.35, "temporal_proximity": 0.25}
        result = _calculate_similarity(a, b, weights)
        assert result["entity_overlap"] == 0.0
        assert result["keyword_overlap"] == 0.0

    def test_calculate_similarity_temporal_same_day(self):
        from datetime import datetime, timedelta
        now = datetime.now()
        a = {"keywords": [], "published_at": now, "politician_ids": [1]}
        b = {"keywords": [], "published_at": now, "politician_ids": [1]}
        weights = {"entity_overlap": 0.40, "keyword_overlap": 0.35, "temporal_proximity": 0.25}
        result = _calculate_similarity(a, b, weights)
        assert result["temporal_prox"] == 1.0

    def test_calculate_similarity_temporal_7_days(self):
        from datetime import datetime, timedelta
        now = datetime.now()
        a = {"keywords": [], "published_at": now, "politician_ids": [1]}
        b = {"keywords": [], "published_at": now - timedelta(days=5), "politician_ids": [1]}
        weights = {"entity_overlap": 0.40, "keyword_overlap": 0.35, "temporal_proximity": 0.25}
        result = _calculate_similarity(a, b, weights)
        assert result["temporal_prox"] == 0.7

    async def test_returns_empty_without_article_id(self):
        pool, _ = _make_pool()
        output = {}
        result = await ArticleMatcher().process(output, {}, pool, {})
        assert result is output  # returns unchanged

    async def test_returns_empty_when_no_matches(self):
        pool, conn = _make_pool()
        # fetchrow returns article data, then fetch returns no candidates
        conn.fetchrow = AsyncMock(return_value={
            "keywords": ["test"], "published_at": None, "politician_ids": [None],
        })
        conn.fetch = AsyncMock(return_value=[])

        output = {"article_id": 1}
        result = await ArticleMatcher().process(output, {}, pool, {})
        assert result["matched_article_ids"] == []


# ─── ClusterUpdater ───


class TestClusterUpdater:
    async def test_returns_unchanged_without_article_id(self):
        pool, _ = _make_pool()
        output = {"some_key": "value"}
        result = await ClusterUpdater().process(output, {}, pool, {})
        assert result is output
        assert "cluster_id" not in result

    async def test_returns_unchanged_when_no_matches(self):
        pool, conn = _make_pool()
        conn.fetch = AsyncMock(return_value=[])

        output = {"article_id": 1}
        result = await ClusterUpdater().process(output, {}, pool, {})
        assert result is output
        assert "cluster_id" not in result

    async def test_creates_cluster_when_no_existing(self):
        pool, conn = _make_pool()
        # fetch matches
        conn.fetch = AsyncMock(side_effect=[
            [{"article_a_id": 1, "article_b_id": 2}],  # matches
            [],  # cluster_politicians (empty)
        ])
        # fetchrow: no existing cluster, then create cluster
        conn.fetchrow = AsyncMock(side_effect=[
            None,  # no existing cluster
            {"id": 50},  # new cluster created
        ])
        conn.execute = AsyncMock()

        output = {"article_id": 1}
        result = await ClusterUpdater().process(output, {}, pool, {})
        assert result["cluster_id"] == 50

    async def test_joins_existing_cluster(self):
        pool, conn = _make_pool()
        conn.fetch = AsyncMock(side_effect=[
            [{"article_a_id": 1, "article_b_id": 3}],  # matches
            [],  # cluster_politicians
        ])
        conn.fetchrow = AsyncMock(return_value={"cluster_id": 25})  # existing cluster
        conn.execute = AsyncMock()

        output = {"article_id": 1}
        result = await ClusterUpdater().process(output, {}, pool, {})
        assert result["cluster_id"] == 25


# ─── Output chain immutability ───


class TestOutputChain:
    async def test_post_processor_preserves_existing_keys(self):
        """Every post-processor must ADD keys, never remove existing ones."""
        pool, conn = _make_pool()
        conn.fetchrow = AsyncMock(return_value=None)

        base_output = {
            "summary": "test",
            "severity": "high",
            "keywords": ["test"],
            "custom_field": 123,
        }

        # ScoreCalculator should not remove any keys
        result = await ScoreCalculator().process(
            {**base_output, "veracity_signals": {}}, {}, pool, {},
        )
        for key in base_output:
            assert key in result, f"ScoreCalculator removed key '{key}'"

    async def test_sequential_enrichment(self):
        """Simulate a chain: score → relationship. Each adds but doesn't remove."""
        pool, conn = _make_pool()
        conn.fetchrow = AsyncMock(return_value=None)

        output = {"veracity_signals": {}, "entities": [], "politicians": [], "relationships": []}

        # Step 1: ScoreCalculator adds veracity_score
        output = await ScoreCalculator().process(output, {}, pool, {})
        assert "veracity_score" in output

        # Step 2: RelationshipBuilder adds persisted_relationship_ids
        output = await RelationshipBuilder().process(output, {}, pool, {})
        assert "persisted_relationship_ids" in output
        assert "veracity_score" in output  # still there from step 1
