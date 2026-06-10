# Matchy Threat Model

## Scope

Matchy provides transaction-to-email matching and exposes mutating API endpoints for run, pending-run, and confirm workflows.

## Trust Boundaries

1. **Caller Boundary**: external automation calling Matchy HTTP endpoints.
2. **Database Boundary**: Teller database credentials and write paths.
3. **Service Boundary**: Mailcart and model-provider integrations (Anthropic/OpenAI).
4. **Secret Boundary**: 1Password/`1psa`, environment variables, and local runtime configuration.

## Primary Threats And Controls

### Unauthorized API Triggering

- Threat: untrusted callers trigger matching or confirmation writes.
- Controls: bearer/write-token authentication for mutating endpoints and explicit `MATCHY_WRITE_ENABLED` API gate.

### Information Leakage Through Error Details

- Threat: raw service exceptions expose internal object identifiers/state.
- Controls: standardized 404 detail messages for transaction and confirmation misses.

### Abuse Through High-Rate Mutating Calls

- Threat: request bursts drive expensive AI/database operations and degrade availability.
- Controls: in-process endpoint rate limiting on mutating routes.

### OpenAPI/Docs Surface Exposure

- Threat: accidental disclosure of route contract and mutation paths.
- Controls: docs/openapi endpoints disabled by default (`MATCHY_ENABLE_API_DOCS=false`).

## Data-Flow Notes

- Teller DB is system-of-record for transaction state (`teller.*`) and hosts match artifacts owned by `matchy.*`.
- Mailcart provides message metadata/body data used for candidate ranking.
- Anthropic/OpenAI receive limited scoring context based on configured ranking flow.

## Residual Risks

- Local in-memory rate limiting is per-process (not shared across replicas).
- Caller token rotation remains operationally enforced via environment/secret management.
