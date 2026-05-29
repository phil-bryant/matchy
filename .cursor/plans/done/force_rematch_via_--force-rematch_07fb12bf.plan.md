---
name: Force rematch via --force-rematch
overview: Extend the pending-run path (and single-run path for completeness) with a force_rematch boolean. When true, _maybe_cached_response returns None so a fresh AI evaluation occurs under PROMPT_VERSION v3.
todos:
  - id: api-models
    content: "In matchy/api.py, add force_rematch: bool = False to both MatchRunRequest and PendingMatchRunRequest. Pass it through to MatchService methods."
    status: completed
  - id: service-layer
    content: "Update MatchService.match_transaction and match_pending_transactions to accept force_rematch: bool = False and forward it to _maybe_cached_response. Modify _maybe_cached_response to return None immediately when force_rematch is True."
    status: completed
  - id: driver-entrypoint
    content: "In 09_run_matchy_driver.py, add argparse argument --force-rematch (store_true). Include force_rematch in the JSON payload sent to POST /v1/matchy/runs/pending. Usage example: ./09_run_matchy_driver.py --once --force-rematch"
    status: completed
  - id: traceability
    content: Add minimal R-tags / comments noting the force-rematch bypass of the v2/v3 cache. No new test files required.
    status: completed
isProject: false
---

Add --force-rematch CLI flag to the driver so that the next run bypasses the prompt-version cache and exercises the v3 prompt change.