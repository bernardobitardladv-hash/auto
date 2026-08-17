from datetime import datetime, timezone

from app.engine import next_step


def test_bdr_contact_has_six_touches_then_recovery() -> None:
    started = datetime(2026, 8, 17, 10, tzinfo=timezone.utc)
    first = next_step("BDR_CONTATO", 0, started)
    last = next_step("BDR_CONTATO", 5, started)
    exhausted = next_step("BDR_CONTATO", 6, started)

    assert first["task"]["channel"] == "ligacao"
    assert last["task"]["channel"] == "whatsapp"
    assert exhausted == {
        "kind": "exhausted",
        "destination": {"category_id": 23, "stage_id": "C23:PREPARATION"},
    }
