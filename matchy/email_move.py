from __future__ import annotations

import logging

LOGGER = logging.getLogger(__name__)


class EmailMoveMixin:
    #R060: Optionally move selected emails into the Mailcart `matchy` folder after successful selection.
    #R060: This is gated by both write-enabled mode and MATCHY_EMAIL_MOVE_ENABLED.
    def _maybe_move_selected_messages(self, selected_message_ids: list[str], transaction_id: str, source: str) -> None:
        settings = getattr(self, "_settings", None)
        move_enabled = bool(getattr(settings, "write_enabled", True)) and bool(getattr(settings, "email_move_enabled", False))
        mover = getattr(getattr(self, "_mailcart_client", None), "move_to_matchy", None)
        if move_enabled and callable(mover):
            for message_id in dict.fromkeys(str(item) for item in selected_message_ids if str(item)):
                try:
                    moved = bool(mover(message_id))
                    if not moved:
                        LOGGER.warning(
                            "mailcart move_to_matchy returned false transaction_id=%s source=%s message_id=%s",
                            transaction_id, source, message_id,
                        )
                except Exception as exc:
                    LOGGER.warning(
                        "mailcart move_to_matchy failed transaction_id=%s source=%s message_id=%s error=%s",
                        transaction_id, source, message_id, exc,
                    )
