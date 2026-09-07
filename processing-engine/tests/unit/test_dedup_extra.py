"""Testes unitários para SemanticDedupStrategy e CompositeDedupStrategy."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.plugins.dedup.composite import CompositeDedupStrategy
from app.plugins.dedup.semantic import SemanticDedupStrategy
from app.plugins.protocols import DedupResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conn(row=None) -> MagicMock:
    """Cria um mock de conexão asyncpg."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row)
    return conn


def _make_llm(vector: list[float] | None = None) -> MagicMock:
    """Cria um mock de LLMProvider com embed configurado."""
    if vector is None:
        vector = [0.1, 0.2, 0.3]
    llm = MagicMock()
    llm.embed = AsyncMock(return_value=vector)
    return llm


def _make_strategy(result: DedupResult) -> MagicMock:
    """Cria um mock de DedupStrategy que retorna o resultado fornecido."""
    strategy = MagicMock()
    strategy.check = AsyncMock(return_value=result)
    return strategy


# ---------------------------------------------------------------------------
# SemanticDedupStrategy
# ---------------------------------------------------------------------------

class TestSemanticDedupStrategy:

    pipeline_id = "pipe-semantic-001"

    async def test_semantic_dedup_no_match(self):
        """embed retorna vetor, conn.fetchrow retorna None → não é duplicata."""
        vector = [0.1, 0.2, 0.3]
        llm = _make_llm(vector)
        conn = _make_conn(row=None)

        strategy = SemanticDedupStrategy(llm=llm, threshold=0.92)
        result = await strategy.check(
            content="conteúdo único",
            url=None,
            pipeline_id=self.pipeline_id,
            conn=conn,
        )

        llm.embed.assert_called_once_with("conteúdo único")
        conn.fetchrow.assert_called_once()
        assert isinstance(result, DedupResult)
        assert result.is_duplicate is False
        assert result.matched_item_id is None
        assert result.strategy == "semantic"
        assert result.similarity is None

    async def test_semantic_dedup_match(self):
        """conn.fetchrow retorna linha com id e similarity → é duplicata com similarity."""
        vector = [0.9, 0.8, 0.7]
        llm = _make_llm(vector)
        fake_row = {"id": "item-abc-123", "similarity": 0.97}
        conn = _make_conn(row=fake_row)

        strategy = SemanticDedupStrategy(llm=llm, threshold=0.92)
        result = await strategy.check(
            content="conteúdo muito parecido",
            url="https://example.com/article",
            pipeline_id=self.pipeline_id,
            conn=conn,
        )

        llm.embed.assert_called_once_with("conteúdo muito parecido")
        assert result.is_duplicate is True
        assert result.matched_item_id == "item-abc-123"
        assert result.strategy == "semantic"
        assert result.similarity == pytest.approx(0.97)

    async def test_semantic_uses_threshold_in_query(self):
        """Threshold customizado deve ser passado como parâmetro para a query."""
        custom_threshold = 0.85
        llm = _make_llm()
        conn = _make_conn(row=None)

        strategy = SemanticDedupStrategy(llm=llm, threshold=custom_threshold)
        await strategy.check("texto", None, self.pipeline_id, conn)

        call_args = conn.fetchrow.call_args[0]
        # Parâmetros posicionais: (query, pipeline_id, vector, threshold)
        assert call_args[3] == custom_threshold

    async def test_semantic_similarity_cast_to_float(self):
        """similarity deve ser float mesmo quando o banco retorna Decimal."""
        llm = _make_llm()
        fake_row = {"id": "item-xyz", "similarity": 0.9500001}
        conn = _make_conn(row=fake_row)

        strategy = SemanticDedupStrategy(llm=llm)
        result = await strategy.check("texto", None, self.pipeline_id, conn)

        assert isinstance(result.similarity, float)


# ---------------------------------------------------------------------------
# CompositeDedupStrategy
# ---------------------------------------------------------------------------

class TestCompositeDedupStrategy:

    pipeline_id = "pipe-composite-001"

    async def test_composite_first_match(self):
        """Primeira estratégia diz que é duplicata → retorna esse resultado."""
        expected = DedupResult(
            is_duplicate=True,
            matched_item_id="first-match-id",
            strategy="hash",
        )
        first = _make_strategy(expected)
        second = _make_strategy(DedupResult(is_duplicate=False, strategy="semantic"))

        composite = CompositeDedupStrategy(strategies=[first, second])
        result = await composite.check("conteúdo", None, self.pipeline_id, _make_conn())

        assert result.is_duplicate is True
        assert result.matched_item_id == "first-match-id"
        assert result.strategy == "hash"
        # Segunda estratégia não deve ser chamada
        second.check.assert_not_called()

    async def test_composite_fallthrough(self):
        """Primeira diz não, segunda diz sim → retorna resultado da segunda."""
        no_match = DedupResult(is_duplicate=False, strategy="hash")
        yes_match = DedupResult(
            is_duplicate=True,
            matched_item_id="second-match-id",
            strategy="semantic",
            similarity=0.95,
        )
        first = _make_strategy(no_match)
        second = _make_strategy(yes_match)

        composite = CompositeDedupStrategy(strategies=[first, second])
        result = await composite.check("conteúdo", None, self.pipeline_id, _make_conn())

        assert result.is_duplicate is True
        assert result.matched_item_id == "second-match-id"
        assert result.strategy == "semantic"
        assert result.similarity == pytest.approx(0.95)
        first.check.assert_called_once()
        second.check.assert_called_once()

    async def test_composite_no_match(self):
        """Todas as estratégias dizem não → retorna DedupResult composite não-duplicata."""
        strategies = [
            _make_strategy(DedupResult(is_duplicate=False, strategy="hash")),
            _make_strategy(DedupResult(is_duplicate=False, strategy="semantic")),
        ]
        composite = CompositeDedupStrategy(strategies=strategies)
        result = await composite.check("conteúdo", None, self.pipeline_id, _make_conn())

        assert result.is_duplicate is False
        assert result.matched_item_id is None
        assert result.strategy == "composite"
        for s in strategies:
            s.check.assert_called_once()

    async def test_composite_empty_strategies(self):
        """Lista vazia de estratégias → retorna não-duplicata composite."""
        composite = CompositeDedupStrategy(strategies=[])
        result = await composite.check("conteúdo", None, self.pipeline_id, _make_conn())

        assert result.is_duplicate is False
        assert result.strategy == "composite"

    async def test_composite_passes_args_to_strategies(self):
        """Argumentos devem ser repassados corretamente para cada estratégia."""
        conn = _make_conn()
        strategy = _make_strategy(DedupResult(is_duplicate=False, strategy="hash"))
        composite = CompositeDedupStrategy(strategies=[strategy])

        await composite.check("meu conteúdo", "https://example.com", self.pipeline_id, conn)

        strategy.check.assert_called_once_with(
            "meu conteúdo",
            "https://example.com",
            self.pipeline_id,
            conn,
        )


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------

class TestDedupRegistryExtra:
    def test_semantic_and_composite_registered(self):
        import app.plugins.dedup  # noqa: F401 — dispara o registro
        from app.plugins.registry import list_available

        available = list_available("dedup")
        assert "semantic" in available
        assert "composite" in available
