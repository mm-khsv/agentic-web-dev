import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.engine import Orchestrator


class OrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.run_dir = Path(self.temp_dir.name) / "runs"
        self.patch_runs = patch(
            "orchestrator.engine.RUNS_DIR", self.run_dir
        )
        self.patch_runs.start()
        self.addCleanup(self.patch_runs.stop)
        self.addCleanup(self.temp_dir.cleanup)
        self.orchestrator = Orchestrator()

    def test_empty_request_is_rejected(self):
        with self.assertRaises(ValueError):
            self.orchestrator.start("   ")

    def test_run_is_saved_and_waits_for_review(self):
        run = self.orchestrator.start("Create a requirements document")
        self.assertEqual(run["status"], "awaiting_human_review")
        saved = self.run_dir / f"{run['run_id']}.json"
        self.assertTrue(saved.is_file())
        loaded = json.loads(saved.read_text(encoding="utf-8"))
        self.assertEqual(loaded["run_id"], run["run_id"])

    def test_approval_is_persisted(self):
        run = self.orchestrator.start("Test approval")
        decided = self.orchestrator.decide(
            run["run_id"], "approved", "Requirements reviewed"
        )
        self.assertEqual(decided["status"], "approved")
        self.assertEqual(
            decided["decision"]["reason"], "Requirements reviewed"
        )
        self.assertEqual(
            decided["events"][-1]["type"], "human_decision"
        )
        self.assertEqual(
            self.orchestrator.get_run(run["run_id"])["status"],
            "approved",
        )

    def test_rejection_requires_a_reason(self):
        run = self.orchestrator.start("Test rejection")
        with self.assertRaises(ValueError):
            self.orchestrator.decide(run["run_id"], "rejected")

    def test_cannot_decide_twice(self):
        run = self.orchestrator.start("Test repeated decision")
        self.orchestrator.decide(run["run_id"], "approved")
        with self.assertRaises(ValueError):
            self.orchestrator.decide(run["run_id"], "rejected", "Too late")

    def test_unknown_run_is_rejected(self):
        with self.assertRaises(FileNotFoundError):
            self.orchestrator.get_run(
                "11111111-1111-4111-8111-111111111111"
            )

    def test_invalid_run_id_is_rejected(self):
        with self.assertRaises(ValueError):
            self.orchestrator.get_run("../../outside")


if __name__ == "__main__":
    unittest.main()