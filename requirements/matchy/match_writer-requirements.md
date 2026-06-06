# Matchy Match Writer Requirements

## Scope

Applies to `matchy/match_writer.py`. Provides `MatchWriterMixin`, the match-persistence query family
extracted from the repository module: candidate inserts, AI-result persistence, active-match conflict
handling, and human-confirmed inserts. Mixed into `MatchRepository` so its public method surface is
unchanged.

R030  Statement: Persist Mailcart message metadata on candidate insert for downstream UI rendering.
Design: When inserting `transaction_email_candidate` rows, copy subject, sender, and preview into `cached_subject`, `cached_sender`, and `cached_snippet` so UIs (Teller's Match & Classify candidates pane) can render candidate rows without another per-message Mailcart fetch. Matchy already pulls this metadata from Mailcart (search response + body enrichment) so persisting it is free at insert time.
Tests:
- R030-T01: Verify candidate insert SQL includes cached subject/sender/snippet columns populated from Mailcart search metadata.

## Changelog

- 2026-06-05: Extracted R030 (cached candidate metadata on insert) plus the AI-result/human-confirm write methods from `repository.py` into `match_writer.py`/`MatchWriterMixin`.
