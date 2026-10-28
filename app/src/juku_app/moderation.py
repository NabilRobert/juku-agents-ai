"""The moderation check before the model sees a message (Phase 2 AG6; scale path gap 3).

If a message suggests self-harm, Shiori gives a fixed, kind reply with
Indonesia's official mental-health line instead of improvising, no model
is called, and Arthur gets an alert with no content in it.

Which checker runs is open (ADR-025, "to check in a spike"): the
provider's moderation endpoint if Sumopod exposes one, otherwise a small
local classifier on the gateway's ONNX setup. Until that spike, the app
runs `PendingModerator`, which flags nothing; the fixed reply, the alert
and the "no model call" path are built and tested with a test double.
This is a launch blocker, listed in the slice plan's open items.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Verdict:
    suggests_self_harm: bool


class Moderator(Protocol):
    async def check(self, message: str) -> Verdict: ...


class PendingModerator:
    """Flags nothing, on purpose and visibly: the real checker is chosen in a spike before launch."""

    async def check(self, message: str) -> Verdict:
        del message
        return Verdict(suggests_self_harm=False)


def distress_reply(crisis_line: str) -> str:
    """The fixed reply. `crisis_line` is set by Arthur after he checks the number (JUKU_CRISIS_LINE)."""
    return (
        "Terima kasih sudah mau bercerita. Shiori bukan konselor, tetapi kamu tidak sendirian. "
        f"Kalau kamu sedang berpikir untuk menyakiti diri sendiri, hubungi layanan kesehatan jiwa: {crisis_line}. "
        "Dalam keadaan darurat, hubungi 112."
    )
