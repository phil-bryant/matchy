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

class PendingMatchRunRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)
    lookback_days: int = Field(default=14, ge=1, le=365)
    trigger_source: Literal["auto", "manual", "retry"] = "auto"


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

    #R001: Publish a health endpoint that always returns an ok status payload.
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    #R005: Translate unknown transactions from service ValueError into HTTP 404 responses.
    @app.post("/v1/matchy/runs", response_model=MatchRunResponse)
    def run_matches(request: MatchRunRequest) -> MatchRunResponse:
        rows: list[dict] = []
        for transaction_id in request.transaction_ids:
            try:
                rows.append(_service().match_transaction(transaction_id=transaction_id, trigger_source=request.trigger_source))
            except ValueError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        return MatchRunResponse(results=rows)

    #R010: Publish a pending-transaction batch endpoint for driver-triggered matching runs.
    @app.post("/v1/matchy/runs/pending", response_model=MatchRunResponse)
    def run_pending_matches(request: PendingMatchRunRequest) -> MatchRunResponse:
        rows = _service().match_pending_transactions(
            limit=request.limit,
            lookback_days=request.lookback_days,
            trigger_source=request.trigger_source,
        )
        return MatchRunResponse(results=rows)

    return app
