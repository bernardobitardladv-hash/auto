"""Motor puro das réguas: decide o próximo toque, sem escrever no Bitrix."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Any

from .cadences import CADENCES, EXHAUSTION_STAGE


def next_step(cadence_name: str, position: int, started_at: datetime) -> dict[str, Any]:
    """Retorna o próximo toque ou o destino de esgotamento da régua."""
    touches = CADENCES[cadence_name]
    if position >= len(touches):
        return {"kind": "exhausted", "destination": EXHAUSTION_STAGE[cadence_name]}

    touch = touches[position]
    due_at = (started_at + timedelta(days=touch.day)).replace(
        hour=touch.hour, minute=touch.minute, second=0, microsecond=0
    )
    return {
        "kind": "task",
        "position": position,
        "due_at": due_at.isoformat(),
        "task": asdict(touch),
    }
