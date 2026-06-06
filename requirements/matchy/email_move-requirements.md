# Matchy Email Move Requirements

## Scope

Applies to `matchy/email_move.py`. Provides `EmailMoveMixin`, the optional post-selection Mailcart
folder-move concern extracted from the service orchestration module. Mixed into `MatchService` and
invoked after a successful AI selection and after a human confirm.

R060  Statement: Optionally move AI-selected emails into Mailcart's `matchy` folder after successful selection.
Design: After a persisted AI selection (and after a human confirm), `_maybe_move_selected_messages` calls `MailcartClient.move_to_matchy(message_id)` only when `MATCHY_WRITE_ENABLED=true` and `MATCHY_EMAIL_MOVE_ENABLED=true`. Duplicate ids are moved once; move failures are logged and do not fail the run.
Tests:
- R060-T01: Verify successful AI-selected ids are moved when email-move mode is enabled.

## Changelog

- 2026-06-05: Extracted R060 (optional post-selection Mailcart move) from `service.py` into `email_move.py`/`EmailMoveMixin`.
