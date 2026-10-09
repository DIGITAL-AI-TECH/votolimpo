"""Pre-processor: HelpCoreComputedFields

Calculates deterministic fields from article content BEFORE sending to LLM.
These values are injected into item_metadata so the sink can map them to DB columns
via item_field_mapping.

This runs in the orchestrator's pre-processing phase, before LLM invocation.
"""

import hashlib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def compute_article_fields(content: str, title: str | None = None) -> dict[str, Any]:
    """Compute all deterministic fields from article content."""
    if not content:
        content = ""

    words = content.split()
    word_count = len(words)
    sentences = [s for s in re.split(r'[.!?]+', content) if s.strip()]
    sentence_count = max(len(sentences), 1)
    paragraphs = [p for p in content.split('\n\n') if p.strip()]

    return {
        "computed_char_count": len(content),
        "computed_word_count": word_count,
        "computed_sentence_count": len(sentences),
        "computed_paragraph_count": len(paragraphs),
        "computed_line_count": len(content.splitlines()),
        "computed_avg_sentence_length": round(word_count / sentence_count, 2),
        "computed_reading_time_seconds": int(word_count / 200 * 60),
        "computed_has_numbered_steps": bool(re.search(r'^\d+[.)]\s', content, re.MULTILINE)),
        "computed_has_bullet_points": bool(re.search(r'^[\-\*\•]\s', content, re.MULTILINE)),
        "computed_has_headers": bool(re.search(r'^#+\s', content, re.MULTILINE)),
        "computed_has_tables": bool(re.search(r'\|.*\|.*\|', content) or '<table' in content.lower()),
        "computed_has_images": bool(re.search(r'<img|!\[', content)),
        "computed_uppercase_ratio": round(
            sum(1 for c in content if c.isupper()) / max(len(content), 1), 4
        ),
        "computed_content_hash": hashlib.sha256(content.encode('utf-8')).hexdigest(),
        "computed_link_count": len(re.findall(r'https?://', content)),
        "computed_title_word_count": len(title.split()) if title else 0,
    }
