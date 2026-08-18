"""Motor puro das réguas: decide o próximo toque, sem escrever no Bitrix."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import os
from typing import Any

from .cadences import CADENCES, EXHAUSTION_STAGE


def business_timezone() -> timezone:
    return timezone(timedelta(hours=int(os.getenv("BUSINESS_UTC_OFFSET", "-3"))))


def as_datetime(value: datetime | str | None, *, bitrix_wall_clock: bool = False) -> datetime | None:
    if value is None:
        return None
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if bitrix_wall_clock:
        # O CRM devolve o horário digitado com offset de sinal invertido (+03
        # para São Paulo). Para tarefas, a intenção é o relógio local exibido.
        return parsed.replace(tzinfo=business_timezone())
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=business_timezone())
    return parsed


def next_step(cadence_name: str, position: int, started_at: datetime | str, anchor_at: datetime | str | None = None, result: str | None = None) -> dict[str, Any]:
    """Retorna o próximo toque ou o destino de esgotamento da régua."""
    touches = CADENCES[cadence_name]
    while position < len(touches) and touches[position].conditional_result and touches[position].conditional_result != str(result):
        position += 1
    if position >= len(touches):
        return {"kind": "exhausted", "destination": EXHAUSTION_STAGE[cadence_name]}

    touch = touches[position]
    base_at = (as_datetime(anchor_at, bitrix_wall_clock=True) if touch.anchored else as_datetime(started_at))
    if base_at is None and touch.anchored:
        base_at = as_datetime(started_at)
    if base_at is None:
        raise ValueError("data inicial da cadência ausente")
    due_at = base_at + timedelta(days=touch.day, hours=touch.offset_hours)
    if touch.hour is not None:
        due_at = due_at.astimezone(business_timezone()).replace(hour=touch.hour, minute=touch.minute, second=0, microsecond=0)
    return {
        "kind": "task",
        "position": position,
        "due_at": due_at.isoformat(),
        "task": asdict(touch),
    }

