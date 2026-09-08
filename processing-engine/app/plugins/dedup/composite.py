from __future__ import annotations

from typing import Any

from app.plugins.protocols import DedupResult, DedupStrategy


class CompositeDedupStrategy:
    """Estratégia composta que encadeia múltiplas estratégias de deduplicação.

    Executa cada estratégia em ordem e retorna o primeiro resultado positivo
    encontrado. Se nenhuma estratégia detectar duplicata, retorna
    DedupResult(is_duplicate=False, strategy="composite").

    Parâmetros
    ----------
    strategies:
        Lista de instâncias que implementam o protocolo DedupStrategy.
        São executadas na ordem fornecida.
    """

    def __init__(self, strategies: list[DedupStrategy]) -> None:
        self.strategies = strategies

    async def check(
        self,
        content: str,
        url: str | None,
        pipeline_id: str,
        conn: Any,
        current_item_id: str | None = None,
    ) -> DedupResult:
        for strategy in self.strategies:
            result = await strategy.check(content, url, pipeline_id, conn, current_item_id)
            if result.is_duplicate:
                return result

        return DedupResult(
            is_duplicate=False,
            strategy="composite",
        )
