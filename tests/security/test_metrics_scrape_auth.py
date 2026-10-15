from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
from fastapi import FastAPI

from adapters.web import auth, routes


async def test_scrape_token_chi_cap_quyen_metrics(monkeypatch: Any) -> None:
    settings = SimpleNamespace(
        METRICS_SCRAPE_TOKEN="s" * 32,
        WEB_AUTH_MODE="trusted_header",
        WEB_AUTH_ISSUER="issuer",
        WEB_AUTH_HEADER_SECRET="h" * 32,
        DAILY_BUDGET_USD=1,
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "get_settings", lambda: settings)
    monkeypatch.setattr(routes, "prometheus_text", AsyncMock(return_value="cp_queue_depth 0\n"))
    app = FastAPI()
    app.include_router(routes.router)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://localhost",
    ) as client:
        headers = {"authorization": f"Bearer {'s' * 32}"}
        assert (await client.get("/api/metrics", headers=headers)).status_code == 200
        assert (await client.get("/api/metrics")).status_code == 401
        assert (
            await client.get("/api/metrics", headers={"authorization": "Bearer bad"})
        ).status_code == 401
        assert (await client.get("/api/threads", headers=headers)).status_code == 401
        assert (
            await client.get("/api/metrics", headers={b"authorization": b"Bearer \xff"})
        ).status_code == 401
