from __future__ import annotations

import pytest

HEADERS = {"X-Api-Key": "test-key"}

VALID_PAYLOAD: dict = {
    "name": "test-pipeline-integration",
    "system_prompt": "Extract structured data from the given text.",
    "output_schema": {
        "type": "object",
        "required": ["title"],
        "properties": {"title": {"type": "string"}},
    },
    "ingestor_type": "html",
    "dedup_strategy": "hash",
    "llm_provider": "openai",
    "llm_model": "gpt-4.1-mini",
    "llm_temperature": 0,
    "validators": ["schema"],
    "sink_type": "postgresql",
    "sink_config": {"table": "test.output"},
    "max_concurrent": 3,
    "rate_limit_rpm": 30,
    "max_retries": 2,
    "cache_ttl_hours": 24,
    "budget_period": "month",
}


# ---------------------------------------------------------------------------
# POST /v1/pipelines
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_pipeline(client) -> None:
    """POST com payload válido deve retornar 201 com id e version=1."""
    payload = {**VALID_PAYLOAD, "name": "create-test-pipeline"}
    response = await client.post("/v1/pipelines", json=payload, headers=HEADERS)

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["version"] == 1
    assert data["name"] == "create-test-pipeline"
    assert data["is_active"] is True
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_missing_required_field(client) -> None:
    """POST sem system_prompt deve retornar 422."""
    payload = {
        "name": "missing-system-prompt",
        "output_schema": {"type": "object"},
    }
    response = await client.post("/v1/pipelines", json=payload, headers=HEADERS)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_duplicate_name(client) -> None:
    """POST com nome duplicado deve retornar 409."""
    payload = {**VALID_PAYLOAD, "name": "duplicate-name-pipeline"}
    # Primeira criação
    r1 = await client.post("/v1/pipelines", json=payload, headers=HEADERS)
    assert r1.status_code == 201

    # Segunda criação com mesmo nome
    r2 = await client.post("/v1/pipelines", json=payload, headers=HEADERS)
    assert r2.status_code == 409


# ---------------------------------------------------------------------------
# GET /v1/pipelines
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_pipelines(client) -> None:
    """GET deve retornar lista contendo o pipeline criado."""
    payload = {**VALID_PAYLOAD, "name": "list-test-pipeline"}
    create_resp = await client.post("/v1/pipelines", json=payload, headers=HEADERS)
    assert create_resp.status_code == 201

    list_resp = await client.get("/v1/pipelines", headers=HEADERS)
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert isinstance(items, list)
    names = [p["name"] for p in items]
    assert "list-test-pipeline" in names


@pytest.mark.asyncio
async def test_list_pipelines_returns_array(client) -> None:
    """GET /v1/pipelines sempre retorna array (mesmo vazio)."""
    response = await client.get("/v1/pipelines", headers=HEADERS)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# ---------------------------------------------------------------------------
# GET /v1/pipelines/{pipeline_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_pipeline(client) -> None:
    """GET por id deve retornar 200 com dados corretos."""
    payload = {**VALID_PAYLOAD, "name": "get-by-id-pipeline"}
    create_resp = await client.post("/v1/pipelines", json=payload, headers=HEADERS)
    assert create_resp.status_code == 201
    pipeline_id = create_resp.json()["id"]

    get_resp = await client.get(f"/v1/pipelines/{pipeline_id}", headers=HEADERS)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == pipeline_id
    assert data["name"] == "get-by-id-pipeline"


@pytest.mark.asyncio
async def test_get_nonexistent_pipeline(client) -> None:
    """GET de UUID inexistente deve retornar 404."""
    fake_id = "00000000-0000-0000-0000-000000000001"
    response = await client.get(f"/v1/pipelines/{fake_id}", headers=HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PUT /v1/pipelines/{pipeline_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_pipeline_bumps_version(client) -> None:
    """PUT deve incrementar version para 2."""
    payload = {**VALID_PAYLOAD, "name": "update-version-pipeline"}
    create_resp = await client.post("/v1/pipelines", json=payload, headers=HEADERS)
    assert create_resp.status_code == 201
    pipeline_id = create_resp.json()["id"]
    assert create_resp.json()["version"] == 1

    updated_payload = {**payload, "description": "Updated description"}
    update_resp = await client.put(
        f"/v1/pipelines/{pipeline_id}", json=updated_payload, headers=HEADERS
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["version"] == 2
    assert data["description"] == "Updated description"


@pytest.mark.asyncio
async def test_update_nonexistent_pipeline(client) -> None:
    """PUT em UUID inexistente deve retornar 404."""
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = await client.put(
        f"/v1/pipelines/{fake_id}", json=VALID_PAYLOAD, headers=HEADERS
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_requires_api_key(client) -> None:
    """Endpoints de pipelines devem exigir X-Api-Key."""
    response = await client.get("/v1/pipelines")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_invalid_api_key_rejected(client) -> None:
    """Chave inválida deve retornar 401."""
    response = await client.get("/v1/pipelines", headers={"X-Api-Key": "wrong-key"})
    assert response.status_code == 401
