from datetime import datetime, timezone
import unittest

from app.cadences import CADENCES
from app.engine import next_step


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

    def test_one_task_then_exhaustion(self):
        base = datetime(2026, 8, 17, 9, tzinfo=timezone.utc)
        self.assertEqual(next_step("BDR_CONTATO", 0, base)["kind"], "task")
        self.assertEqual(next_step("BDR_CONTATO", 6, base)["kind"], "exhausted")

    def test_dry_run_flag_is_default(self):
        import os
        self.assertNotEqual(os.getenv("AUTOMATION_ENABLED", "false").lower(), "true")


if __name__ == "__main__":
    unittest.main()

