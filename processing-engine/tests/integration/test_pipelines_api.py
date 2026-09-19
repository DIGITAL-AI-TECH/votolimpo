from __future__ import annotations

import pytest

HEADERS = {"X-Api-Key": "test-key"}


# ---------------------------------------------------------------------------
# GET /v1/pipelines  (read-only — pipelines are loaded from YAML, not API)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_pipelines_returns_dict_with_array(client) -> None:
    """GET /v1/pipelines returns {"pipelines": [...]}."""
    response = await client.get("/v1/pipelines", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert "pipelines" in data
    assert isinstance(data["pipelines"], list)


# ---------------------------------------------------------------------------
# GET /v1/pipelines/{pipeline_id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_nonexistent_pipeline(client) -> None:
    """GET de UUID inexistente deve retornar 404."""
    fake_id = "00000000-0000-0000-0000-000000000001"
    response = await client.get(f"/v1/pipelines/{fake_id}", headers=HEADERS)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST / PUT não existem — API é read-only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_pipelines_not_allowed(client) -> None:
    """POST /v1/pipelines deve retornar 405 (read-only API)."""
    response = await client.post("/v1/pipelines", json={"name": "x"}, headers=HEADERS)
    assert response.status_code == 405


@pytest.mark.asyncio
async def test_put_pipeline_not_allowed(client) -> None:
    """PUT /v1/pipelines/{id} deve retornar 405 (read-only API)."""
    fake_id = "00000000-0000-0000-0000-000000000002"
    response = await client.put(
        f"/v1/pipelines/{fake_id}", json={"name": "x"}, headers=HEADERS
    )
    assert response.status_code == 405


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
