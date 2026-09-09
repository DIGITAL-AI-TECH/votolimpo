"""Sink plugins — persist processed output to target systems."""

import hashlib
import json
import logging
import re
import unicodedata
from math import exp, log2
from datetime import datetime, timezone
from typing import Any, Protocol

import asyncpg

logger = logging.getLogger(__name__)


class Sink(Protocol):
    """Protocol for sink plugins."""

    async def persist(self, output: dict, item_metadata: dict, config: dict, conn: asyncpg.Connection) -> dict:
        """Persist processed output. Returns persistence details."""
        ...


class PostgreSQLSink:
    """Persist to PostgreSQL — handles votolimpo schema with entity resolution, scoring, etc."""

    async def persist(self, output: dict, item_metadata: dict, config: dict, conn: asyncpg.Connection) -> dict:
        """Persist extraction output transactionally to votolimpo.* tables.

        C4: If config has 'database_url_env', open a separate connection to the
        target database. Otherwise, use the provided conn (same DB instance).
        """
        import os
        mappings = config.get("mappings", [])
        result = {"tables_written": [], "article_id": None}

        # C4 fix: allow separate target DB
        db_env = config.get("database_url_env")
        own_conn = None
        if db_env:
            target_url = os.environ.get(db_env)
            if target_url:
                own_conn = await asyncpg.connect(target_url)
                conn = own_conn

        try:
            await self._do_persist(conn, output, item_metadata, mappings, result)
        finally:
            if own_conn:
                await own_conn.close()

        return result

    async def _do_persist(self, conn, output, item_metadata, mappings, result):
        """Inner persist logic — extracted for connection flexibility."""
        async with conn.transaction():
            for mapping in mappings:
                source_path = mapping.get("source_path", "")
                target_table = mapping.get("target_table", "")
                strategy = mapping.get("strategy", "insert")

                if target_table == "articles" and strategy == "upsert":
                    article_id = await self._upsert_article(conn, output, item_metadata)
                    result["article_id"] = article_id
                    result["tables_written"].append("articles")

                elif target_table == "politicians" and strategy == "resolve":
                    if result["article_id"]:
                        await self._resolve_politicians(conn, output, result["article_id"])
                        result["tables_written"].append("politicians")

                elif target_table == "milestones" and strategy == "dedup_insert":
                    if result["article_id"]:
                        await self._insert_milestones(conn, output, result["article_id"])
                        result["tables_written"].append("milestones")

            # Post-persist: entities, relationships, veracity, matching, clustering
            if result["article_id"]:
                await self._upsert_entities(conn, output, result["article_id"])
                await self._update_veracity(conn, output, result["article_id"], item_metadata)
                await self._detect_milestones(conn, output, result["article_id"])
                await self._match_article(conn, result["article_id"])
                await self._update_clusters(conn, result["article_id"])

        return result

    async def _upsert_article(self, conn: asyncpg.Connection, output: dict, metadata: dict) -> int:
        """Upsert article into votolimpo.articles."""
        url = metadata.get("source_url", "")
        url_hash = hashlib.sha256(url.encode()).hexdigest()

        # Upsert source
        source_name = metadata.get("source_name")
        source_id = None
        if source_name:
            row = await conn.fetchrow("""
                INSERT INTO votolimpo.sources (name, domain)
                VALUES ($1, $2)
                ON CONFLICT (name) DO UPDATE SET
                    article_count = votolimpo.sources.article_count + 1,
                    updated_at = NOW()
                RETURNING id
            """, source_name, metadata.get("source_domain"))
            if row:
                source_id = row["id"]

        article = output.get("article", output)
        keywords = output.get("keywords", article.get("keywords", []))
        if isinstance(keywords, list):
            keywords = keywords
        else:
            keywords = []

        row = await conn.fetchrow("""
            INSERT INTO votolimpo.articles
                (title, url, url_hash, source_id, published_at,
                 severity, summary, keywords, processing_status,
                 nc_article_id, raw_extraction, processed_at)
            VALUES ($1, $2, $3, $4, $5,
                    $6::votolimpo.severity_level, $7, $8,
                    'completed'::votolimpo.processing_status,
                    $9, $10, NOW())
            ON CONFLICT (url_hash) DO UPDATE SET
                processing_status = 'completed'::votolimpo.processing_status,
                severity = EXCLUDED.severity,
                summary = EXCLUDED.summary,
                keywords = EXCLUDED.keywords,
                raw_extraction = EXCLUDED.raw_extraction,
                processed_at = NOW(),
                updated_at = NOW()
            RETURNING id
        """,
            metadata.get("title", article.get("title", "")),
            url,
            url_hash,
            source_id,
            metadata.get("published_at"),
            output.get("severity", "low"),
            output.get("summary", ""),
            keywords,
            metadata.get("nc_article_id"),
            json.dumps(output),
        )
        return row["id"]

    async def _resolve_politicians(self, conn: asyncpg.Connection, output: dict, article_id: int):
        """Resolve and link politicians to article (H6: safe .get access)."""
        for pol in output.get("politicians", []):
            name = pol.get("name")
            if not name:
                continue
            politician_id = await self._resolve_politician(
                conn, name, pol.get("party"), pol.get("state")
            )

            # Update metadata
            if pol.get("role"):
                await conn.execute("""
                    UPDATE votolimpo.politicians
                    SET role = COALESCE($1, role), updated_at = NOW()
                    WHERE id = $2 AND role IS NULL
                """, pol.get("role"), politician_id)

            # Link to article
            await conn.execute("""
                INSERT INTO votolimpo.politician_articles
                    (politician_id, article_id, role, relevance_score)
                VALUES ($1, $2, $3::votolimpo.article_role, $4)
                ON CONFLICT (politician_id, article_id) DO NOTHING
            """,
                politician_id, article_id,
                pol.get("article_role", "mentioned"),
                pol.get("relevance_score"),
            )

    async def _resolve_politician(
        self, conn: asyncpg.Connection, name: str,
        party: str | None = None, state: str | None = None,
    ) -> int:
        """Resolve politician: exact → fuzzy 0.80 → fuzzy+party 0.70 → create."""
        normalized = _normalize_for_search(name)

        # Exact
        row = await conn.fetchrow(
            "SELECT id FROM votolimpo.politicians WHERE lower(name) = lower($1)",
            name.strip(),
        )
        if row:
            return row["id"]

        # Fuzzy 0.80
        row = await conn.fetchrow("""
            SELECT id, similarity(lower(name), $1) as sim
            FROM votolimpo.politicians
            WHERE similarity(lower(name), $1) > 0.80
            ORDER BY sim DESC LIMIT 1
        """, normalized)
        if row:
            return row["id"]

        # Fuzzy + party 0.70
        if party:
            row = await conn.fetchrow("""
                SELECT id FROM votolimpo.politicians
                WHERE similarity(lower(name), $1) > 0.70
                  AND lower(party) = lower($2)
                ORDER BY similarity(lower(name), $1) DESC LIMIT 1
            """, normalized, party)
            if row:
                return row["id"]

        # Create
        slug = _generate_slug(name)
        row = await conn.fetchrow("""
            INSERT INTO votolimpo.politicians (name, slug, party, state)
            VALUES ($1, $2, $3, $4)
            RETURNING id
        """, name.strip(), slug, party, state)
        return row["id"]

    async def _upsert_entities(self, conn: asyncpg.Connection, output: dict, article_id: int):
        """Upsert entities and relationships."""
        entity_id_map: dict[str, int] = {}

        for ent in output.get("entities", []):
            name = ent.get("name")
            ent_type = ent.get("type")
            if not name or not ent_type:
                continue
            norm = _normalize_for_search(name)

            # Exact
            row = await conn.fetchrow("""
                SELECT id FROM votolimpo.entities
                WHERE normalized_name = $1 AND type = $2::votolimpo.entity_type
            """, norm, ent_type)

            if row:
                ent_id = row["id"]
                await conn.execute("""
                    UPDATE votolimpo.entities
                    SET last_seen_at = NOW(), article_count = article_count + 1
                    WHERE id = $1
                """, ent_id)
            else:
                # Fuzzy 0.85
                row = await conn.fetchrow("""
                    SELECT id FROM votolimpo.entities
                    WHERE similarity(normalized_name, $1) > 0.85
                      AND type = $2::votolimpo.entity_type
                    ORDER BY similarity(normalized_name, $1) DESC LIMIT 1
                """, norm, ent_type)

                if row:
                    ent_id = row["id"]
                    await conn.execute("""
                        UPDATE votolimpo.entities
                        SET last_seen_at = NOW(), article_count = article_count + 1
                        WHERE id = $1
                    """, ent_id)
                else:
                    row = await conn.fetchrow("""
                        INSERT INTO votolimpo.entities (name, normalized_name, type, article_count)
                        VALUES ($1, $2, $3::votolimpo.entity_type, 1)
                        RETURNING id
                    """, _normalize_entity_name(name), norm, ent_type)
                    ent_id = row["id"]

            entity_id_map[name] = ent_id

        # Relationships
        for rel in output.get("relationships", []):
            src_id = entity_id_map.get(rel["source"])
            tgt_id = entity_id_map.get(rel["target"])
            if src_id and tgt_id:
                row = await conn.fetchrow("""
                    INSERT INTO votolimpo.relationships
                        (source_id, target_id, source_type, target_type, type, weight)
                    VALUES ($1, $2, 'entity', 'entity', $3::votolimpo.relationship_type, 1)
                    ON CONFLICT (source_id, target_id, source_type, target_type, type)
                    DO UPDATE SET weight = votolimpo.relationships.weight + 1,
                                  last_seen_at = NOW(), updated_at = NOW()
                    RETURNING id
                """, src_id, tgt_id, rel["type"])

                if row and rel.get("evidence"):
                    await conn.execute("""
                        INSERT INTO votolimpo.relationship_evidence
                            (relationship_id, article_id, excerpt)
                        VALUES ($1, $2, $3)
                    """, row["id"], article_id, rel["evidence"])

    async def _update_veracity(
        self, conn: asyncpg.Connection, output: dict, article_id: int, metadata: dict,
    ):
        """Calculate and persist veracity scores."""
        signals = output.get("veracity_signals", {})

        # Get source reputation
        source_name = metadata.get("source_name")
        sr = 0.50
        if source_name:
            row = await conn.fetchrow(
                "SELECT reputation_score FROM votolimpo.sources WHERE name = $1",
                source_name,
            )
            if row:
                sr = float(row["reputation_score"])

        ms = _normalize_multi_source(signals.get("multi_source", 0))
        nc = max(0.0, min(1.0, signals.get("narrative_consistency", 0.5)))
        de = max(0.0, min(1.0, signals.get("documental_evidence", 0.5)))
        ts = max(0.0, min(1.0, signals.get("temporality", 0.5)))
        el = max(0.0, min(1.0, signals.get("emotional_language", 0.5)))

        veracity = sr * 0.30 + ms * 0.25 + nc * 0.15 + de * 0.10 + ts * 0.10 + el * 0.10

        await conn.execute("""
            UPDATE votolimpo.articles SET
                source_reputation = $1, multi_source_score = $2,
                narrative_consistency = $3, documental_evidence = $4,
                temporality_score = $5, emotional_language = $6,
                veracity_score = $7, updated_at = NOW()
            WHERE id = $8
        """, round(sr, 2), round(ms, 2), round(nc, 2), round(de, 2),
            round(ts, 2), round(el, 2), round(veracity, 2), article_id)

    async def _detect_milestones(self, conn: asyncpg.Connection, output: dict, article_id: int):
        """Detect milestones from extraction — confidence >= 0.70, dedup ±7 days."""
        for m in output.get("milestones", []):
            if m.get("confidence", 0) < 0.70:
                continue
            politician_name = m.get("politician_name")
            if not politician_name:
                continue

            politician_id = await self._resolve_politician(conn, politician_name)

            # Dedup
            row = await conn.fetchrow("""
                SELECT id FROM votolimpo.milestones
                WHERE politician_id = $1 AND type = $2::votolimpo.milestone_type
                  AND ABS(date - $3::date) <= 7
            """, politician_id, m["type"], m["date"])
            if row:
                continue

            await conn.execute("""
                INSERT INTO votolimpo.milestones
                    (politician_id, article_id, type, title, description, date, confidence)
                VALUES ($1, $2, $3::votolimpo.milestone_type, $4, $5, $6, $7)
            """, politician_id, article_id, m["type"], m["title"],
                m.get("description"), m["date"], m["confidence"])

    # Alias for mapping compatibility
    async def _insert_milestones(self, conn: asyncpg.Connection, output: dict, article_id: int):
        await self._detect_milestones(conn, output, article_id)

    async def _match_article(self, conn: asyncpg.Connection, article_id: int):
        """Match article against recent articles (30-day, shared politicians)."""
        row = await conn.fetchrow("""
            SELECT a.keywords, a.published_at,
                   array_agg(pa.politician_id) as politician_ids
            FROM votolimpo.articles a
            LEFT JOIN votolimpo.politician_articles pa ON pa.article_id = a.id
            WHERE a.id = $1
            GROUP BY a.id
        """, article_id)
        if not row:
            return

        keywords = row["keywords"] or []
        published = row["published_at"]
        pids = [x for x in (row["politician_ids"] or []) if x is not None]
        if not pids:
            return

        candidates = await conn.fetch("""
            SELECT a.id, a.keywords, a.published_at,
                   array_agg(pa.politician_id) as politician_ids
            FROM votolimpo.articles a
            JOIN votolimpo.politician_articles pa ON pa.article_id = a.id
            WHERE a.id != $1 AND a.published_at >= NOW() - INTERVAL '30 days'
              AND pa.politician_id = ANY($2)
            GROUP BY a.id
        """, article_id, pids)

        for cand in candidates:
            sim = _calculate_similarity(
                {"keywords": keywords, "published_at": published, "politician_ids": pids},
                {"keywords": cand["keywords"] or [], "published_at": cand["published_at"],
                 "politician_ids": [x for x in (cand["politician_ids"] or []) if x]},
            )
            if sim["similarity"] >= 0.30:
                a_id = min(article_id, cand["id"])
                b_id = max(article_id, cand["id"])
                await conn.execute("""
                    INSERT INTO votolimpo.article_matches
                        (article_a_id, article_b_id, similarity,
                         entity_overlap, keyword_overlap, temporal_prox)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (article_a_id, article_b_id) DO UPDATE
                    SET similarity = EXCLUDED.similarity,
                        entity_overlap = EXCLUDED.entity_overlap,
                        keyword_overlap = EXCLUDED.keyword_overlap,
                        temporal_prox = EXCLUDED.temporal_prox
                """, a_id, b_id, sim["similarity"],
                    sim["entity_overlap"], sim["keyword_overlap"], sim["temporal_prox"])

    async def _update_clusters(self, conn: asyncpg.Connection, article_id: int):
        """Update clusters after article matching."""
        matches = await conn.fetch("""
            SELECT article_a_id, article_b_id
            FROM votolimpo.article_matches
            WHERE (article_a_id = $1 OR article_b_id = $1) AND similarity >= 0.50
        """, article_id)
        if not matches:
            return

        related_ids = set()
        for m in matches:
            related_ids.add(m["article_a_id"])
            related_ids.add(m["article_b_id"])

        row = await conn.fetchrow("""
            SELECT cluster_id FROM votolimpo.cluster_articles
            WHERE article_id = ANY($1) LIMIT 1
        """, list(related_ids))

        if row:
            cluster_id = row["cluster_id"]
        else:
            row = await conn.fetchrow("""
                INSERT INTO votolimpo.news_clusters (title, article_count)
                VALUES ('Auto-generated cluster', 0) RETURNING id
            """)
            cluster_id = row["id"]

        await conn.execute("""
            INSERT INTO votolimpo.cluster_articles (cluster_id, article_id)
            VALUES ($1, $2) ON CONFLICT DO NOTHING
        """, cluster_id, article_id)

        await conn.execute("""
            UPDATE votolimpo.news_clusters SET
                article_count = (SELECT COUNT(*) FROM votolimpo.cluster_articles WHERE cluster_id = $1),
                first_article = (SELECT MIN(a.published_at) FROM votolimpo.articles a
                    JOIN votolimpo.cluster_articles ca ON ca.article_id = a.id WHERE ca.cluster_id = $1),
                last_article = (SELECT MAX(a.published_at) FROM votolimpo.articles a
                    JOIN votolimpo.cluster_articles ca ON ca.article_id = a.id WHERE ca.cluster_id = $1),
                updated_at = NOW()
            WHERE id = $1
        """, cluster_id)

        # Update cluster_politicians
        pols = await conn.fetch("""
            SELECT pa.politician_id, COUNT(*) as cnt
            FROM votolimpo.politician_articles pa
            JOIN votolimpo.cluster_articles ca ON ca.article_id = pa.article_id
            WHERE ca.cluster_id = $1 GROUP BY pa.politician_id
        """, cluster_id)
        for p in pols:
            await conn.execute("""
                INSERT INTO votolimpo.cluster_politicians (cluster_id, politician_id, article_count)
                VALUES ($1, $2, $3)
                ON CONFLICT (cluster_id, politician_id) DO UPDATE SET article_count = EXCLUDED.article_count
            """, cluster_id, p["politician_id"], p["cnt"])


# ─── Helper functions ───

def _normalize_for_search(name: str) -> str:
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_only = nfkd.encode("ASCII", "ignore").decode("ASCII")
    return re.sub(r"\s+", " ", ascii_only.lower().strip())

def _normalize_entity_name(name: str) -> str:
    name = name.strip()
    prefixes = ["ex-", "ex ", "deputado ", "deputada ", "senador ", "senadora ",
                "ministro ", "ministra ", "governador ", "governadora ",
                "prefeito ", "prefeita ", "vereador ", "vereadora "]
    lower = name.lower()
    for p in prefixes:
        if lower.startswith(p):
            name = name[len(p):]
            break
    return name.strip()

def _generate_slug(name: str) -> str:
    normalized = _normalize_for_search(name)
    return re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")

def _normalize_multi_source(raw: float) -> float:
    if raw <= 0:
        return 0.0
    elif raw <= 0.5:
        return 0.5
    return 1.0

def _calculate_similarity(a: dict, b: dict) -> dict:
    pols_a = set(a.get("politician_ids", []))
    pols_b = set(b.get("politician_ids", []))
    entity_overlap = len(pols_a & pols_b) / len(pols_a | pols_b) if pols_a | pols_b else 0.0

    kw_a = set(a.get("keywords", []) or [])
    kw_b = set(b.get("keywords", []) or [])
    keyword_overlap = len(kw_a & kw_b) / len(kw_a | kw_b) if kw_a | kw_b else 0.0

    pub_a, pub_b = a.get("published_at"), b.get("published_at")
    temporal_prox = 0.0
    if pub_a and pub_b:
        days = abs((pub_a - pub_b).days)
        temporal_prox = 1.0 if days <= 1 else 0.7 if days <= 7 else 0.3 if days <= 30 else 0.0

    similarity = entity_overlap * 0.40 + keyword_overlap * 0.35 + temporal_prox * 0.25
    return {
        "similarity": round(similarity, 2),
        "entity_overlap": round(entity_overlap, 2),
        "keyword_overlap": round(keyword_overlap, 2),
        "temporal_prox": round(temporal_prox, 2),
    }


# Registry
SINKS: dict[str, type] = {
    "postgresql": PostgreSQLSink,
}

def get_sink(sink_type: str) -> Sink:
    cls = SINKS.get(sink_type, PostgreSQLSink)
    return cls()
