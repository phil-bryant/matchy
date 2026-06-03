from __future__ import annotations

import os
from time import perf_counter
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .cldr_cache import CldrCurrenciesCache
from .service import MatchService
from .settings import Settings

NonEmptyId = Annotated[str, Field(min_length=1)]
SafeOptionalNote = Annotated[str, Field(pattern=r"^[^\x00]*$")]


def _startup_log(start_time_seconds: float, phase: str, details: str = "") -> None:
    enabled = os.environ.get("MATCHY_STARTUP_LOG", "false").strip().lower() == "true"
    if enabled:
        elapsed_seconds = perf_counter() - start_time_seconds
        suffix = f" | {details}" if details else ""
        print(f"[matchy-startup +{elapsed_seconds:7.3f}s] {phase}{suffix}", flush=True)


class MatchRunRequest(BaseModel):
    transaction_ids: list[NonEmptyId] = Field(min_length=1, max_length=200)
    trigger_source: Literal["auto", "manual", "retry"] = "manual"
    force_rematch: bool = False


class MatchRunResponse(BaseModel):
    results: list[dict]

class PendingMatchRunRequest(BaseModel):
    limit: int = Field(default=100, ge=1, le=500)
    lookback_days: int = Field(default=14, ge=1, le=365)
    trigger_source: Literal["auto", "manual", "retry"] = "auto"
    force_rematch: bool = False


class ConfirmRequest(BaseModel):
    #R045: Confirm endpoint ids are required and note excludes null bytes that Postgres rejects in jsonb payloads.
    transaction_id: NonEmptyId
    email_message_id: NonEmptyId
    note: SafeOptionalNote | None = None


def create_app() -> FastAPI:
    startup_started_at = perf_counter()
    _startup_log(startup_started_at, "create-app-enter")
    app = FastAPI(title="matchy")
    _startup_log(startup_started_at, "fastapi-instance-created")
    settings_started_at = perf_counter()
    settings = Settings()
    _startup_log(startup_started_at, "settings-created", f"phase_elapsed={perf_counter() - settings_started_at:7.3f}s")
    #R015: Refresh the CLDR currencies cache during API startup when the feature flag is enabled.
    if settings.cldr_currencies_refresh_enabled:
        cache_started_at = perf_counter()
        cache_status = CldrCurrenciesCache(settings).refresh()
        detail = f"updated={cache_status.get('updated')} phase_elapsed={perf_counter() - cache_started_at:7.3f}s"
        _startup_log(startup_started_at, "cldr-currencies-cache-refreshed", detail)
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
    @app.post("/v1/matchy/runs", response_model=MatchRunResponse,
              responses={404: {"description": "No transaction matched the supplied transaction_id."}})
    def run_matches(request: MatchRunRequest) -> MatchRunResponse:
        rows: list[dict] = []
        for transaction_id in request.transaction_ids:
            try:
                rows.append(_service().match_transaction(transaction_id=transaction_id, trigger_source=request.trigger_source, force_rematch=request.force_rematch))
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
            force_rematch=request.force_rematch,
        )
        return MatchRunResponse(results=rows)

    #R045: Expose a human-confirm endpoint with strict input validation and ValueError-to-404 mapping.
    @app.post("/v1/matchy/confirm", response_model=dict,
              responses={404: {"description": "Unknown transaction or email message for confirmation."}})
    def confirm_match(request: ConfirmRequest) -> dict:
        try:
            result = _service().confirm_match(
                transaction_id=request.transaction_id,
                email_message_id=request.email_message_id,
                note=request.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return result

    _startup_log(startup_started_at, "create-app-complete")
    return app
