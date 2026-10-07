"""Post-processor: MarkdownGenerator

Generates a Markdown (.md) representation of each processed article from the
helpcore-analysis pipeline. Adds a `markdown_content` key to the output dict.
Does NOT write files to disk — the sink persists the content via column_mapping.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)


class MarkdownGenerator:
    """Generate a clean Markdown document with YAML frontmatter from LLM output.

    Expects the output to contain `inventory` and `quality` blocks as produced
    by the helpcore-analysis pipeline. All field accesses use .get() with safe
    defaults so the processor never raises on partial/missing data.
    """

    async def process(
        self,
        output: dict,
        item_metadata: dict,
        pool: asyncpg.Pool,
        config: dict[str, Any],
    ) -> dict:
        try:
            markdown_content = self._generate_markdown(output)
            output["markdown_content"] = markdown_content
        except Exception:
            logger.exception("MarkdownGenerator failed — skipping markdown_content")
            output.setdefault("markdown_content", None)
        return output

    # ─── Private helpers ──────────────────────────────────────────────────────

    def _generate_markdown(self, output: dict) -> str:
        inventory = output.get("inventory") or {}
        quality = output.get("quality") or {}
        # Conflicts now live in quality block (migrated from dedup_analysis)

        processed_at = datetime.now(timezone.utc).isoformat()

        frontmatter = self._build_frontmatter(inventory, quality, processed_at)
        body = self._build_body(inventory, quality)

        return f"{frontmatter}\n{body}"

    def _build_frontmatter(
        self, inventory: dict, quality: dict, processed_at: str
    ) -> str:
        doc_type = inventory.get("doc_type", "")
        category = inventory.get("category", "")
        subcategory = inventory.get("subcategory", "")
        area_operacional = inventory.get("area_operacional", "")
        complexity_level = inventory.get("complexity_level", "")
        target_audience = inventory.get("target_audience", "")
        requires_update = inventory.get("requires_update", False)
        escalation_present = inventory.get("escalation_present", False)
        confidence = inventory.get("confidence", 0.0)

        overall_score = quality.get("overall_score", 0)
        priority_level = quality.get("priority_level", "")

        mentions_systems = inventory.get("mentions_systems") or []
        key_topics = inventory.get("key_topics") or []

        mentions_yaml = self._list_to_yaml(mentions_systems)
        topics_yaml = self._list_to_yaml(key_topics)

        lines = [
            "---",
            f"doc_type: {doc_type}",
            f"category: {category}",
            f"subcategory: {subcategory}",
            f"area_operacional: {area_operacional}",
            f"complexity_level: {complexity_level}",
            f"target_audience: {target_audience}",
            f"quality_score: {overall_score}",
            f"priority_level: {priority_level}",
            f"requires_update: {str(requires_update).lower()}",
            f"escalation_present: {str(escalation_present).lower()}",
            f"confidence: {confidence}",
            f"mentions_systems:{mentions_yaml}",
            f"key_topics:{topics_yaml}",
            f"processed_at: {processed_at}",
            "---",
        ]
        return "\n".join(lines)

    def _build_body(
        self, inventory: dict, quality: dict
    ) -> str:
        summary = inventory.get("summary", "")
        doc_type = inventory.get("doc_type", "")
        category = inventory.get("category", "")
        subcategory = inventory.get("subcategory", "")
        area_operacional = inventory.get("area_operacional", "")
        complexity_level = inventory.get("complexity_level", "")
        target_audience = inventory.get("target_audience", "")

        overall_score = quality.get("overall_score", 0)
        priority_level = quality.get("priority_level", "")
        clarity = quality.get("clarity", 0)
        structure = quality.get("structure", 0)
        completeness = quality.get("completeness", 0)
        accuracy_signals = quality.get("accuracy_signals", 0)
        readability = quality.get("readability", 0)
        estimated_effort = quality.get("estimated_effort", "")
        improvement_suggestions = quality.get("improvement_suggestions") or []

        steps = inventory.get("steps") or []
        mentions_systems = inventory.get("mentions_systems") or []

        conflicting_info = quality.get("has_internal_conflicts", False)
        conflict_details = quality.get("internal_conflict_details")

        sections: list[str] = []

        # Title
        sections.append(f"# {summary}\n")

        # Classificação
        sections.append("## Classificação\n")
        sections.append("| Campo | Valor |")
        sections.append("|-------|-------|")
        sections.append(f"| Tipo | {doc_type} |")
        sections.append(f"| Categoria | {category} |")
        sections.append(f"| Subcategoria | {subcategory} |")
        sections.append(f"| Área | {area_operacional} |")
        sections.append(f"| Complexidade | {complexity_level} |")
        sections.append(f"| Público-alvo | {target_audience} |")
        sections.append("")

        # Qualidade
        sections.append("## Qualidade\n")
        sections.append(
            f"**Score geral**: {overall_score}/100 — Prioridade: {priority_level}\n"
        )
        sections.append("| Dimensão | Score |")
        sections.append("|----------|-------|")
        sections.append(f"| Clareza | {clarity}/100 |")
        sections.append(f"| Estrutura | {structure}/100 |")
        sections.append(f"| Completude | {completeness}/100 |")
        sections.append(f"| Precisão | {accuracy_signals}/100 |")
        sections.append(f"| Legibilidade | {readability}/100 |")
        sections.append("")
        sections.append(f"**Esforço estimado**: {estimated_effort}\n")

        sections.append("### Sugestões de melhoria\n")
        if improvement_suggestions:
            for i, suggestion in enumerate(improvement_suggestions, start=1):
                sections.append(f"{i}. {suggestion}")
        else:
            sections.append("Nenhuma sugestão registrada.")
        sections.append("")

        # Passos do procedimento
        sections.append("## Passos do procedimento\n")
        if steps:
            for i, step in enumerate(steps, start=1):
                sections.append(f"{i}. {step}")
        else:
            sections.append("Artigo não descreve procedimento sequencial.")
        sections.append("")

        # Sistemas mencionados
        sections.append("## Sistemas mencionados\n")
        if mentions_systems:
            for system in mentions_systems:
                sections.append(f"- {system}")
        else:
            sections.append("Nenhum sistema interno citado.")
        sections.append("")

        # Conflitos internos
        sections.append("## Conflitos internos\n")
        if conflicting_info and conflict_details:
            sections.append(conflict_details)
        else:
            sections.append("Nenhum conflito interno detectado.")
        sections.append("")

        return "\n".join(sections)

    @staticmethod
    def _list_to_yaml(items: list) -> str:
        """Convert a Python list to an inline YAML list string for frontmatter.

        Returns an empty string (no value) when the list is empty, or a
        multi-line YAML list representation when items are present.

        Example output for ["a", "b"]:
            \n  - a\n  - b
        """
        if not items:
            return " []"
        lines = [""]
        for item in items:
            lines.append(f"  - {item}")
        return "\n".join(lines)
