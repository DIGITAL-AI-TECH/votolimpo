"""Pipeline configuration endpoints."""

from fastapi import APIRouter, HTTPException

from ...core.pipeline_config import get_pipeline, _registry

router = APIRouter()


@router.get("/pipelines")
async def list_pipelines():
    """List all registered pipelines."""
    return {
        "pipelines": [
            {
                "id": p.id,
                "name": p.name,
                "version": p.version,
                "ingestor": p.ingestor.type,
                "llm_provider": p.llm.provider,
                "llm_model": p.llm.model,
                "validators": [v.type for v in p.validators],
                "sink": p.sink.type,
            }
            for p in _registry.values()
        ]
    }


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline_detail(pipeline_id: str):
    """Get full pipeline configuration."""
    pipeline = get_pipeline(pipeline_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    return {
        "id": pipeline.id,
        "name": pipeline.name,
        "version": pipeline.version,
        "ingestor": {"type": pipeline.ingestor.type, "config": pipeline.ingestor.config},
        "dedup": {"strategy": pipeline.dedup.strategy, "config": pipeline.dedup.config},
        "llm": {
            "provider": pipeline.llm.provider,
            "model": pipeline.llm.model,
            "temperature": pipeline.llm.temperature,
            "max_tokens": pipeline.llm.max_tokens,
            "system_prompt_file": pipeline.llm.system_prompt_file,
            "output_schema_file": pipeline.llm.output_schema_file,
            "max_retries": pipeline.llm.max_retries,
        },
        "validators": [{"type": v.type, "config": v.config} for v in pipeline.validators],
        "sink": {"type": pipeline.sink.type, "config": pipeline.sink.config},
        "cache": {"enabled": pipeline.cache.enabled, "ttl_hours": pipeline.cache.ttl_hours},
    }
