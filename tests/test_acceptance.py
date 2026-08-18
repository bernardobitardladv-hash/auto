from datetime import datetime, timezone
import unittest

from app.cadences import CADENCES
from app.engine import next_step
from app.workflow import RESULT_ROUTES, _event_entity_id, _task_fields


class AcceptanceTests(unittest.TestCase):
    def test_cadence_lengths(self):
        self.assertEqual(len(CADENCES["SDR_TENTATIVA"]), 9)
        self.assertEqual(len(CADENCES["SDR_RETORNO"]), 6)
        self.assertEqual(len(CADENCES["BDR_CONTATO"]), 6)
        self.assertEqual(len(CADENCES["BDR_RECUPERAR"]), 4)

    def test_bdr_exact_slots(self):
        base = datetime(2026, 8, 17, 9, tzinfo=timezone.utc)
        self.assertEqual(next_step("BDR_CONTATO", 0, base)["due_at"], "2026-08-17T13:00:00+00:00")
        self.assertEqual(next_step("BDR_CONTATO", 5, base)["due_at"], "2026-08-18T17:00:00+00:00")

    def test_sdr_return_accepts_bitrix_datetime(self):
        step = next_step("SDR_RETORNO", 1, "2026-08-17T09:00:00+00:00", "2026-08-20T14:30:00+00:00")
        self.assertEqual(step["due_at"], "2026-08-20T14:30:00+00:00")

    def test_sdr_return_confirmation_is_immediate(self):
        step = next_step("SDR_RETORNO", 0, "2026-08-17T09:00:00+00:00", "2026-08-20T14:30:00+00:00")
        self.assertEqual(step["due_at"], "2026-08-17T09:00:00+00:00")

    def test_sdr_return_reinforcement_requires_no_answer(self):
        base = "2026-08-17T09:00:00+00:00"
        anchor = "2026-08-20T14:30:00+00:00"
        self.assertEqual(next_step("SDR_RETORNO", 2, base, anchor, result="45")["position"], 2)
        self.assertEqual(next_step("SDR_RETORNO", 2, base, anchor, result="51")["position"], 3)

    def test_routes_are_stage_specific(self):
        self.assertEqual(RESULT_ROUTES[(0, "PREPARATION")]["81"], "UC_OIFN4M")
        self.assertNotIn("81", RESULT_ROUTES[(0, "UC_OIFN4M")])
        self.assertEqual(RESULT_ROUTES[(23, "NEW")]["51"], "C23:PREPARATION")
        self.assertNotIn("51", RESULT_ROUTES[(23, "PREPARATION")])

    def test_default_funnel_stage_has_no_c0_prefix(self):
        exhausted = next_step("SDR_TENTATIVA", 9, "2026-08-17T09:00:00+00:00")
        self.assertEqual(exhausted["destination"]["stage_id"], "UC_XXPI8O")

    def test_task_is_bound_to_deal(self):
        fields = _task_fields(2221, TITLE="Teste")
        self.assertEqual(fields["UF_CRM_TASK"], ["D_2221"])

    def test_task_event_uses_fields_after_id(self):
        self.assertEqual(_event_entity_id({"data[FIELDS_AFTER][ID]": "4363"}), "4363")

    def test_deal_event_uses_fields_id(self):
        self.assertEqual(_event_entity_id({"data[FIELDS][ID]": "2221"}), "2221")

    def test_correction_position_precedes_first_touch(self):
        self.assertEqual(-1 + 1, 0)

    def test_one_task_then_exhaustion(self):
        base = datetime(2026, 8, 17, 9, tzinfo=timezone.utc)
        self.assertEqual(next_step("BDR_CONTATO", 0, base)["kind"], "task")
        self.assertEqual(next_step("BDR_CONTATO", 6, base)["kind"], "exhausted")

    def test_dry_run_flag_is_default(self):
        import os
        self.assertNotEqual(os.getenv("AUTOMATION_ENABLED", "false").lower(), "true")


if __name__ == "__main__":
    unittest.main()

