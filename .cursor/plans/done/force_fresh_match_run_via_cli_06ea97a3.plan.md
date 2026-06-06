---
name: Force fresh match run via CLI
overview: Provide a --force flag on the existing driver (Option 1) and optionally a dedicated force-match command (Option 2). Both surface a force boolean through the API and service layers to skip _maybe_cached_response.
todos:
  - id: option-1-driver-flag
    content: "Add optional force: bool = False to MatchRunRequest and PendingMatchRunRequest in matchy/api.py; thread through MatchService.match_transaction and match_pending_transactions; short-circuit cache in _maybe_cached_response when force=True. Extend 09_run_matchy_driver.py with --force arg and include it in the pending-run payload. Usage: ./09_run_matchy_driver.py --once --force"
    status: completed
  - id: option-2-standalone-command
    content: Create a new 10_force_match.py entrypoint (modeled on 08/09) that accepts one or more --transaction-id values, always sends force=true to POST /v1/matchy/runs, and prints results. Minimal argparse surface for targeted re-evaluation.
    status: completed
  - id: docs-and-tests
    content: Update the two request models and service signatures; add minimal traceability comments. No new unit tests required beyond the existing stub style unless the user requests full coverage.
    status: completed
isProject: false
---

Add CLI support to force fresh AI evaluations (bypassing the prompt-version cache) so the v3 prompt change is actually exercised.