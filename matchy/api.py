from __future__ import annotations

from collections import deque
import logging
import os
import secrets
from threading import Lock
from time import perf_counter
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

from .cldr_cache import CldrCurrenciesCache
from .service import MatchService
from .settings import Settings

NonEmptyId = Annotated[str, Field(min_length=1)]
TransactionId = Annotated[str, Field(min_length=1, pattern=r"^txn_[A-Za-z0-9_-]+$")]
SafeOptionalNote = Annotated[str, Field(pattern=r"^[^\x00]*$")]
LOGGER = logging.getLogger(__name__)


 #R480: Emit startup timing logs only when MATCHY_STARTUP_LOG is enabled and include optional phase details.
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
    #R045: Confirm endpoint ids are required, transaction ids use teller's txn_ prefix, and note excludes null bytes.
    transaction_id: TransactionId
    email_message_id: NonEmptyId
    note: SafeOptionalNote | None = None


def create_app() -> FastAPI:
    startup_started_at = perf_counter()
    _startup_log(startup_started_at, "create-app-enter")
    docs_enabled = os.environ.get("MATCHY_ENABLE_API_DOCS", "false").strip().lower() == "true"
    app = FastAPI(
        title="matchy",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
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
    rate_limit_lock = Lock()
    rate_limit_buckets: dict[tuple[str, str], deque[float]] = {}
    try:
        rate_limit_window_seconds = float(os.environ.get("MATCHY_MUTATION_RATE_LIMIT_WINDOW_SECONDS", "60"))
    except ValueError:
        rate_limit_window_seconds = 60.0
    try:
        rate_limit_max_requests = int(os.environ.get("MATCHY_MUTATION_RATE_LIMIT_MAX_REQUESTS", "30"))
    except ValueError:
        rate_limit_max_requests = 30
    if rate_limit_window_seconds <= 0:
        rate_limit_window_seconds = 60.0
    if rate_limit_max_requests < 1:
        rate_limit_max_requests = 30

    #R485: Lazily initialize MatchService once and map constructor failures to HTTP 503 for API callers.
    def _service() -> MatchService:
        nonlocal service
        if service is None:
            try:
                service = MatchService(settings)
            except Exception as exc:
                LOGGER.exception("Failed to initialize MatchService.")
                raise HTTPException(
                    status_code=503,
                    detail="Match service is unavailable.",
                ) from exc
        return service

    #R055: Require Bearer auth for mutating run/confirm endpoints so only trusted callers can trigger writes.
    def _require_api_auth(
        authorization: str | None = Header(default=None),
        matchy_write_token: str | None = Header(default=None, alias="X-Matchy-Write-Token"),
        teller_write_token: str | None = Header(default=None, alias="X-Teller-Write-Token"),
    ) -> None:
        configured_token = settings.matchy_api_auth_token
        provided_token = ""
        if authorization:
            if authorization.startswith("Bearer "):
                provided_token = authorization[len("Bearer ") :].strip()
            else:
                provided_token = authorization.strip()
        if not provided_token:
            provided_token = (matchy_write_token or teller_write_token or "").strip()
        if not configured_token:
            raise HTTPException(status_code=503, detail="Matchy API auth token is not configured.")
        token_matches = False
        if provided_token:
            try:
                token_matches = secrets.compare_digest(
                    provided_token.encode("utf-8"),
                    configured_token.encode("utf-8"),
                )
            except UnicodeEncodeError:
                token_matches = False
        if not token_matches:
            raise HTTPException(status_code=401, detail="Unauthorized", headers={"WWW-Authenticate": "Bearer"})

    #R055: Enforce MATCHY_WRITE_ENABLED at API boundary before mutating operations.
    def _require_write_enabled() -> None:
        if not settings.write_enabled:
            raise HTTPException(status_code=503, detail="Matchy writes are disabled (MATCHY_WRITE_ENABLED=false).")

    #R055: Apply per-endpoint caller throttling for mutating routes to reduce abuse impact.
    def _enforce_mutating_rate_limit(request: Request) -> None:
        now = perf_counter()
        client_host = "unknown"
        if request.client and request.client.host:
            client_host = request.client.host
        bucket_key = (request.url.path, client_host)
        with rate_limit_lock:
            bucket = rate_limit_buckets.setdefault(bucket_key, deque())
            while bucket and (now - bucket[0]) > rate_limit_window_seconds:
                bucket.popleft()
            if len(bucket) >= rate_limit_max_requests:
                raise HTTPException(status_code=429, detail="Rate limit exceeded for this endpoint.")
            bucket.append(now)

    #R001: Publish a health endpoint that always returns an ok status payload.
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    #R490: Dispatch validated run requests to batch or per-id matching and map ValueError to HTTP 404.
    #R005: Translate unknown transactions from service ValueError into HTTP 404 responses.
    @app.post("/v1/matchy/runs", response_model=MatchRunResponse,
              responses={401: {"description": "Unauthorized."}, 404: {"description": "No transaction matched the supplied transaction_id."},
                         429: {"description": "Rate limit exceeded."}, 503: {"description": "API auth token is not configured."}})
    def run_matches(
        request: MatchRunRequest,
        _auth: None = Depends(_require_api_auth),
        _write_enabled: None = Depends(_require_write_enabled),
        _rate_limit: None = Depends(_enforce_mutating_rate_limit),
    ) -> MatchRunResponse:
        #R490: Run endpoint dispatches through atomic-batch matcher when available, else per-id fallback.
        service = _service()
        batch_matcher = getattr(service, "match_transactions_atomic", None)
        if callable(batch_matcher):
            try:
                rows = batch_matcher(
                    transaction_ids=request.transaction_ids,
                    trigger_source=request.trigger_source,
                    force_rematch=request.force_rematch,
                )
            except ValueError as exc:
                raise HTTPException(status_code=404, detail="No transaction matched the supplied transaction_id.") from exc
            return MatchRunResponse(results=rows)
        rows: list[dict] = []
        for transaction_id in request.transaction_ids:
            try:
                rows.append(service.match_transaction(transaction_id=transaction_id, trigger_source=request.trigger_source, force_rematch=request.force_rematch))
            except ValueError as exc:
                raise HTTPException(status_code=404, detail="No transaction matched the supplied transaction_id.") from exc
        return MatchRunResponse(results=rows)

    #R495: Execute validated pending-run batch requests through MatchService and return delegated rows.
    #R010: Publish a pending-transaction batch endpoint for driver-triggered matching runs.
    @app.post("/v1/matchy/runs/pending", response_model=MatchRunResponse,
              responses={401: {"description": "Unauthorized."}, 429: {"description": "Rate limit exceeded."},
                         500: {"description": "Internal server error."}, 503: {"description": "API auth token is not configured."}})
    def run_pending_matches(
        request: PendingMatchRunRequest,
        _auth: None = Depends(_require_api_auth),
        _write_enabled: None = Depends(_require_write_enabled),
        _rate_limit: None = Depends(_enforce_mutating_rate_limit),
    ) -> MatchRunResponse:
        #R495: Pending endpoint forwards validated batch arguments directly to MatchService.
        rows = _service().match_pending_transactions(
            limit=request.limit,
            lookback_days=request.lookback_days,
            trigger_source=request.trigger_source,
            force_rematch=request.force_rematch,
        )
        return MatchRunResponse(results=rows)

    #R500: Delegate confirm requests with validated payloads and map service ValueError failures to HTTP 404.
    #R045: Expose a human-confirm endpoint with strict input validation and ValueError-to-404 mapping.
    @app.post("/v1/matchy/confirm", response_model=dict,
              responses={401: {"description": "Unauthorized."}, 404: {"description": "Unknown transaction or email message for confirmation."},
                         429: {"description": "Rate limit exceeded."}, 503: {"description": "API auth token is not configured."}})
    def confirm_match(
        request: ConfirmRequest,
        _auth: None = Depends(_require_api_auth),
        _write_enabled: None = Depends(_require_write_enabled),
        _rate_limit: None = Depends(_enforce_mutating_rate_limit),
    ) -> dict:
        #R500: Confirm endpoint delegates validated payloads and maps domain ValueError to HTTP 404.
        try:
            result = _service().confirm_match(
                transaction_id=request.transaction_id,
                email_message_id=request.email_message_id,
                note=request.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Unknown transaction or email message for confirmation.") from exc
        return result

    _startup_log(startup_started_at, "create-app-complete")
    return app
