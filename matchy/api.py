from __future__ import annotations

from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .service import MatchService
from .settings import Settings


class MatchRunRequest(BaseModel):
    transaction_ids: list[str] = Field(min_length=1, max_length=200)
    trigger_source: Literal["auto", "manual", "retry"] = "manual"


class MatchRunResponse(BaseModel):
    results: list[dict]


def create_app() -> FastAPI:
    app = FastAPI(title="matchy")
    settings = Settings()
    service: MatchService | None = None

    def _service() -> MatchService:
        nonlocal service
        if service is None:
            try:
                service = MatchService(settings)
            except Exception as exc:
                raise HTTPException(
                    status_code=503,
                    detail=f"Match service not configured: {exc}",
                ) from exc
        return service

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/matchy/runs", response_model=MatchRunResponse)
    def run_matches(request: MatchRunRequest) -> MatchRunResponse:
        rows: list[dict] = []
        for transaction_id in request.transaction_ids:
            try:
                rows.append(_service().match_transaction(transaction_id=transaction_id, trigger_source=request.trigger_source))
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        return MatchRunResponse(results=rows)

    return app
