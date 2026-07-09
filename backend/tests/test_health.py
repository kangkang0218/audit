import asyncio

import httpx

from app.main import app


async def get(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def test_liveness() -> None:
    response = asyncio.run(get("/api/v1/health/live"))

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["checks"] == {"process": "ok"}
    assert response.headers["X-Request-ID"]


def test_readiness_without_dependency_probes() -> None:
    response = asyncio.run(get("/api/v1/health/ready"))

    assert response.status_code == 200
    assert response.json()["checks"]["configuration"] == "ok"
