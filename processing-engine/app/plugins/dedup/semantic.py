from __future__ import annotations

from typing import Any

from app.plugins.protocols import DedupResult, LLMProvider


class SemanticDedupStrategy:
    """Deduplicação semântica via pgvector (similaridade de cosseno).

    Embute o conteúdo usando o LLMProvider fornecido e consulta a tabela
    processing_engine.items em busca de itens no mesmo pipeline cuja
    similaridade de cosseno seja maior ou igual ao threshold configurado.

    Parâmetros
    ----------
    llm:
        Provedor LLM que implementa o método `embed(text) -> list[float]`.
    threshold:
        Limiar de similaridade de cosseno. Valor padrão: 0.92.
    """

    def __init__(self, llm: LLMProvider, threshold: float = 0.92) -> None:
        self.llm = llm
        self.threshold = threshold

    async def check(
        self,
        content: str,
        url: str | None,
        pipeline_id: str,
        conn: Any,
    ) -> DedupResult:
        vector = await self.llm.embed(content)

        # pgvector: operador <=> calcula distância de cosseno (0 = idêntico, 2 = oposto)
        # logo, similaridade = 1 - distância
        row = await conn.fetchrow(
            """
            SELECT id, 1 - (embedding <=> $2::vector) AS similarity
            FROM processing_engine.items
            WHERE pipeline_id = $1
              AND embedding IS NOT NULL
              AND status != 'failed'
              AND 1 - (embedding <=> $2::vector) >= $3
            ORDER BY embedding <=> $2::vector ASC
            LIMIT 1
            """,
            pipeline_id,
            vector,
            self.threshold,
        )

        if row:
            return DedupResult(
                is_duplicate=True,
                matched_item_id=str(row["id"]),
                strategy="semantic",
                similarity=float(row["similarity"]),
            )

        return DedupResult(
            is_duplicate=False,
            strategy="semantic",
        )
