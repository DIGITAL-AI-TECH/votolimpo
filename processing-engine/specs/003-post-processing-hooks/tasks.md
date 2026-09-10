# Tasks: 003 — Post-Processing Hooks

**Branch**: `feature/003-post-processing-hooks` | **Plan**: `plan.md` | **Spec**: `spec.md`

## Phase 1: Foundation (PostProcessor Protocol + PipelineConfig)

### T1. PostProcessor Protocol + Registry [P]
**File**: `app/plugins/post_processors/__init__.py` (CREATE)
**Acceptance**: A1, A2, A3, A4, A5
- Define `PostProcessor` Protocol with `process(output, item_metadata, pool, config) -> dict`
- Create `POST_PROCESSORS` registry dict
- Create `get_post_processor(pp_type: str)` factory function
- Create helper functions: `_normalize_for_search()`, `_normalize_entity_name()`, `_generate_slug()` (move from sinks)
- Export all helpers needed by concrete post-processors

### T2. Update PipelineConfig for post_processors + crons [P]
**File**: `app/core/pipeline_config.py` (MODIFY)
**Acceptance**: A3
**blockedBy**: none
- Add `PostProcessorEntry(BaseModel)`: `type: str`, `config: dict`
- Add `CronEntry(BaseModel)`: `type: str`, `schedule: str`, `config: dict`, `enabled: bool = True`
- Add to `PipelineConfig`: `post_processors: list[PostProcessorEntry]`, `crons: list[CronEntry]`
- Ensure backward compat (default empty lists)

## Phase 2: Extract Post-Processors from Sink

### T3. entity_resolver post-processor
**File**: `app/plugins/post_processors/entity_resolver.py` (CREATE)
**Acceptance**: A6, A7, A8
**blockedBy**: T1
- Extract `_resolve_politician()` and `_resolve_politicians()` from sink
- Extract `_upsert_entities()` (entity part only, not relationships)
- `process()`: resolve politicians → add `resolved_politician_ids` to output
- Resolve entities → add `resolved_entity_ids` to output
- Register in `POST_PROCESSORS`

### T4. score_calculator post-processor
**File**: `app/plugins/post_processors/score_calculator.py` (CREATE)
**Acceptance**: A9, A10
**blockedBy**: T1
- Extract `_update_veracity()` logic from sink
- `process()`: read veracity_signals + source_reputation → calculate weighted score
- Add `veracity_score` and `score_components` to output
- Does NOT write to DB (score persisted by sink with article)
- Register in `POST_PROCESSORS`

### T5. relationship_builder post-processor
**File**: `app/plugins/post_processors/relationship_builder.py` (CREATE)
**Acceptance**: A11, A12
**blockedBy**: T1, T3
- Extract relationship upsert logic from `_upsert_entities()` in sink
- `process()`: uses `resolved_entity_ids` from entity_resolver output
- UPSERT relationships with weight+1, INSERT evidence
- Add `persisted_relationship_ids` to output
- Register in `POST_PROCESSORS`

### T6. milestone_detector post-processor
**File**: `app/plugins/post_processors/milestone_detector.py` (CREATE)
**Acceptance**: A13, A14
**blockedBy**: T1, T3
- Extract `_detect_milestones()` from sink
- `process()`: uses `resolved_politician_ids` from entity_resolver
- Confidence threshold from config (default 0.70)
- Dedup window from config (default 7 days)
- Add `persisted_milestone_ids` to output
- Register in `POST_PROCESSORS`

### T7. article_matcher post-processor
**File**: `app/plugins/post_processors/article_matcher.py` (CREATE)
**Acceptance**: A15, A16
**blockedBy**: T1, T3
- Extract `_match_article()` + `_calculate_similarity()` from sink
- `process()`: needs article_id (from sink persist or from output)
- Uses resolved_politician_ids + keywords from output
- Configurable thresholds and weights
- Add `matched_article_ids` to output
- Register in `POST_PROCESSORS`

### T8. cluster_updater post-processor
**File**: `app/plugins/post_processors/cluster_updater.py` (CREATE)
**Acceptance**: A17, A18
**blockedBy**: T1, T7
- Extract `_update_clusters()` from sink
- `process()`: uses `matched_article_ids` from article_matcher
- Also updates cluster_politicians
- Add `cluster_id` to output
- Register in `POST_PROCESSORS`

## Phase 3: Evolve Sink + Orchestrator

### T9. Configurable Sink with column_mapping [P]
**File**: `app/plugins/sinks/__init__.py` (MODIFY — MAJOR refactor)
**Acceptance**: A19, A20, A21
**blockedBy**: T3, T4, T5, T6, T7, T8
- Remove extracted methods (_resolve_politicians, _upsert_entities, _update_veracity,
  _detect_milestones, _match_article, _update_clusters, _insert_milestones)
- Keep _upsert_article (renamed/simplified) only for legacy `mappings` mode
- Add column_mapping persist logic:
  - `column_mapping`: output_field → db_column
  - `static_columns`: fixed values per row
  - `item_field_mapping`: item metadata → db_column
  - `jsonb_fallback`: output completo como JSONB coluna
  - `conflict_column`: ON CONFLICT target
- Keep backward compat: mappings mode still works
- Keep helper functions that remain in use
- Target: sink goes from ~536 lines to ~200 lines

### T10. Update Orchestrator for post-processing step
**File**: `app/core/orchestrator.py` (MODIFY)
**Acceptance**: A2, A4, A5
**blockedBy**: T1, T2, T9
- Import `get_post_processor` from post_processors
- In `_process_job_items()`: instantiate post-processors from pipeline config
- In `_process_single_item()`: after validate, before sink:
  ```python
  # Step 5.5: Post-process
  item_metadata = {"source_url": item["source_url"], ...}
  for pp_type, processor, pp_config in post_processors:
      output = await processor.process(output, item_metadata, pool, pp_config)
  ```
- Post-processor exception = same as validator failure (abort item, not job)
- Log post-processing step

## Phase 4: Crons

### T11. Cron system + registry
**File**: `app/crons/__init__.py` (CREATE)
**Acceptance**: A23
**blockedBy**: T2
- Define `CronJob` Protocol: `async def run(pool, config) -> dict`
- `CRON_REGISTRY` dict mapping type → class
- `start_crons(pipeline_configs, pool)` — starts asyncio tasks
- Schedule parser (cron expression → next run calculation)
- Graceful shutdown support

### T12. Implement 5 concrete crons [P]
**Files**: `app/crons/score_recalculator.py`, `mv_refresher.py`, `source_reputation.py`,
         `content_generator.py`, `cluster_cleanup.py` (CREATE)
**Acceptance**: A23, A24
**blockedBy**: T11
- Each cron implements `CronJob` Protocol
- score_recalculator: sigmoid normalization of politician scores
- mv_refresher: REFRESH MATERIALIZED VIEW CONCURRENTLY
- source_reputation: recalc based on article accuracy
- content_generator: GPT-4.1-mini for bio + summary (cost-controlled)
- cluster_cleanup: deactivate clusters without articles in 30+ days

### T13. Register crons in main.py
**File**: `app/main.py` (MODIFY)
**Acceptance**: A23
**blockedBy**: T11, T12
- On startup (after pipeline load): start_crons() if engine_role in ("worker", "both")
- On shutdown: cancel cron tasks gracefully

## Phase 5: Tests

### T14. Unit tests for post-processors
**File**: `tests/test_post_processors.py` (CREATE)
**Acceptance**: A1-A18
**blockedBy**: T3-T8
- Test PostProcessor Protocol compliance for all 6
- Test entity_resolver: exact, fuzzy, fuzzy+party, create
- Test score_calculator: weighted calc, components
- Test relationship_builder: weight increment, evidence
- Test milestone_detector: confidence filter, dedup window
- Test article_matcher: 3-signal similarity
- Test cluster_updater: create cluster, merge, politicians
- Test chain: output flows between processors

### T15. Tests for configurable sink
**File**: `tests/test_configurable_sink.py` (CREATE)
**Acceptance**: A19, A20, A21
**blockedBy**: T9
- Test column_mapping mode: maps output fields to columns
- Test static_columns: fixed values
- Test item_field_mapping: item metadata to columns
- Test jsonb_fallback: full output as JSONB
- Test backward compat: legacy mappings still work
- Test conflict handling (ON CONFLICT)

### T16. Tests for crons
**File**: `tests/test_crons.py` (CREATE)
**Acceptance**: A23, A24
**blockedBy**: T12
- Test score_recalculator: sigmoid produces 0-100 range
- Test cluster_cleanup: marks stale clusters
- Test mv_refresher: executes without error
- Test cron scheduling: next_run calculation

## Execution Order

```
Phase 1: T1 + T2 (parallel — no dependencies)
Phase 2: T3 → T4, T5, T6 (T4-T6 parallel after T3) → T7 → T8
Phase 3: T9, T10 (sequential — T9 first, then T10)
Phase 4: T11 → T12 → T13
Phase 5: T14 + T15 + T16 (parallel)
```

Total: 16 tasks, ~10 files create, ~4 files modify.
