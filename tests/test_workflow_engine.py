import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator import workflow as wf
from orchestrator.engine import Orchestrator


class WorkflowEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.runs_path = Path(self.temp_dir.name)
        self.patch_runs = patch("orchestrator.engine.RUNS_DIR", self.runs_path)
        self.patch_runs.start()
        self.addCleanup(self.patch_runs.stop)
        self.addCleanup(self.temp_dir.cleanup)
        self.app = Orchestrator()

    def start(self):
        return self.app.start_workflow("Build a sample web application")

    def approve_g1(self, run_id):
        role_config = wf.WorkflowConfig()
        roles = wf.allowed_approver_roles("G1", config=role_config)
        self.assertTrue(roles, "G1 must have at least one documented role")
        return self.app.decide_gate(
            run_id=run_id,
            gate_id="G1",
            outcome="approved",
            approver="test-reviewer",
            approver_role=roles[0],
            reason="Test approval",
        )

    def test_new_workflow_stores_string_gate_ids(self):
        run = self.start()
        self.assertEqual(run["schema_version"], 1)
        self.assertEqual(run["current_stage"], "requirements")
        self.assertEqual(
            set(run["gate_states"]),
            {gate.id for gate in wf.GATES},
        )
        self.assertTrue(all(
            isinstance(key, str) for key in run["gate_states"]
        ))

    def test_cannot_skip_g1(self):
        run = self.start()
        with self.assertRaisesRegex(ValueError, "Transition blocked"):
            self.app.transition(run["run_id"], "ux_design")

        unchanged = self.app.get_workflow(run["run_id"])
        self.assertEqual(unchanged["current_stage"], "requirements")

    def test_g1_approval_allows_next_stage(self):
        run = self.start()
        self.approve_g1(run["run_id"])
        moved = self.app.transition(run["run_id"], "ux_design")
        self.assertEqual(moved["current_stage"], "ux_design")
        self.assertEqual(moved["gate_states"]["G1"], "approved")

    def test_g2_decision_requires_explicit_role_configuration(self):
        run = self.start()
        with self.assertRaises(wf.UnresolvedDecisionError):
            self.app.decide_gate(
                run_id=run["run_id"],
                gate_id="G2",
                outcome="approved",
                approver="test-reviewer",
                approver_role="product_owner",
                reason="Test",
            )

        unchanged = self.app.get_workflow(run["run_id"])
        self.assertEqual(unchanged["gate_states"]["G2"], "pending")
        self.assertNotIn("G2", unchanged["gate_decisions"])

    def test_legacy_run_cannot_use_workflow_gate_api(self):
        legacy = self.app.start("Legacy test request")
        with self.assertRaisesRegex(ValueError, "version-1 workflow"):
            self.app.get_workflow(legacy["run_id"])
        with self.assertRaisesRegex(ValueError, "not a version-1 workflow run"):
            self.app.decide_gate(
                run_id=legacy["run_id"],
                gate_id="G1",
                outcome="approved",
                approver="test-reviewer",
                approver_role="product_owner",
            )

    def test_agent_execution_is_persisted_without_approving_g1(self):
        run = self.start()

        with tempfile.TemporaryDirectory() as project_dir:
            project_root = Path(project_dir).resolve()
            artifact = project_root / "specs" / "001" / "test-spec.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("# Test specification\\n", encoding="utf-8")

            with patch("orchestrator.engine.PROJECT_ROOT", project_root):
                updated = self.app.record_agent_execution(
                    run_id=run["run_id"],
                    agent_name="requirements-analyst",
                    artifact_path="specs/001/test-spec.md",
                    execution_status="draft_created",
                    message="Test execution; no LLM called.",
                )

        persisted = self.app.get_workflow(run["run_id"])
        self.assertEqual(updated["gate_states"]["G1"], "pending")
        self.assertEqual(persisted["gate_states"]["G1"], "pending")
        self.assertEqual(persisted["current_stage"], "requirements")
        self.assertEqual(persisted["status"], "in_progress")

        events = [
            event for event in persisted["events"]
            if event.get("type") == "agent_execution_completed"
        ]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["agent_name"], "requirements-analyst")
        self.assertEqual(events[0]["execution_status"], "draft_created")
        self.assertEqual(events[0]["artifact_path"], "specs/001/test-spec.md")

    def test_agent_execution_rejects_missing_artifact_without_mutation(self):
        run = self.start()

        with tempfile.TemporaryDirectory() as project_dir:
            project_root = Path(project_dir).resolve()
            (project_root / "specs" / "001").mkdir(parents=True)

            with patch("orchestrator.engine.PROJECT_ROOT", project_root):
                with self.assertRaises(FileNotFoundError):
                    self.app.record_agent_execution(
                        run_id=run["run_id"],
                        agent_name="requirements-analyst",
                        artifact_path="specs/001/not-created.md",
                        execution_status="draft_created",
                        message="This artifact does not exist.",
                    )

        persisted = self.app.get_workflow(run["run_id"])
        self.assertFalse(any(
            event.get("type") == "agent_execution_completed"
            for event in persisted["events"]
        ))

    def test_agent_execution_rejects_directory_as_artifact(self):
        run = self.start()

        with tempfile.TemporaryDirectory() as project_dir:
            project_root = Path(project_dir).resolve()
            directory = project_root / "specs" / "001" / "not-a-file.md"
            directory.mkdir(parents=True)

            with patch("orchestrator.engine.PROJECT_ROOT", project_root):
                with self.assertRaises(FileNotFoundError):
                    self.app.record_agent_execution(
                        run_id=run["run_id"],
                        agent_name="requirements-analyst",
                        artifact_path="specs/001/not-a-file.md",
                        execution_status="draft_created",
                        message="A directory is not an artifact file.",
                    )

        persisted = self.app.get_workflow(run["run_id"])
        self.assertFalse(any(
            event.get("type") == "agent_execution_completed"
            for event in persisted["events"]
        ))

    def test_agent_execution_rejects_unsupported_agent_without_mutation(self):
        run = self.start()

        with self.assertRaisesRegex(ValueError, "only supports requirements-analyst"):
            self.app.record_agent_execution(
                run_id=run["run_id"],
                agent_name="unknown-agent",
                artifact_path="specs/001/test-spec.md",
                execution_status="draft_created",
                message="Should not be recorded.",
            )

        persisted = self.app.get_workflow(run["run_id"])
        self.assertEqual(persisted["gate_states"]["G1"], "pending")
        self.assertFalse(any(
            event.get("type") == "agent_execution_completed"
            for event in persisted["events"]
        ))

    def test_agent_execution_rejects_wrong_stage_without_mutation(self):
        run = self.start()
        self.approve_g1(run["run_id"])
        self.app.transition(run["run_id"], "ux_design")

        with self.assertRaisesRegex(ValueError, "only supports the requirements stage"):
            self.app.record_agent_execution(
                run_id=run["run_id"],
                agent_name="requirements-analyst",
                artifact_path="specs/001/test-spec.md",
                execution_status="draft_created",
                message="Should not be recorded.",
            )

        persisted = self.app.get_workflow(run["run_id"])
        self.assertEqual(persisted["current_stage"], "ux_design")
        self.assertFalse(any(
            event.get("type") == "agent_execution_completed"
            for event in persisted["events"]
        ))


    def test_agent_execution_rejects_unsafe_artifact_paths(self):
        run = self.start()
        invalid_paths = [
            "",
            "   ",
            "/tmp/outside.md",
            "../outside.md",
            "specs/../../outside.md",
            "specs/./draft.md",
            "specs//draft.md",
            "specs\\001\\draft.md",
            "C:\\temp\\draft.md",
            "C:relative\\draft.md",
            "specs",
            "other/draft.md",
            " specs/001/draft.md",
            "specs/001/draft.md ",
        ]

        for path in invalid_paths:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    self.app.record_agent_execution(
                        run_id=run["run_id"],
                        agent_name="requirements-analyst",
                        artifact_path=path,
                        execution_status="draft_created",
                        message="Test execution.",
                    )

        persisted = self.app.get_workflow(run["run_id"])
        self.assertFalse(any(
            event.get("type") == "agent_execution_completed"
            for event in persisted["events"]
        ))

    def test_agent_execution_rejects_unsupported_status(self):
        run = self.start()

        for status in ("completed", "failed", "", None, 123):
            with self.subTest(status=status):
                with self.assertRaises(ValueError):
                    self.app.record_agent_execution(
                        run_id=run["run_id"],
                        agent_name="requirements-analyst",
                        artifact_path="specs/001/test-spec.md",
                        execution_status=status,
                        message="Test execution.",
                    )

        persisted = self.app.get_workflow(run["run_id"])
        self.assertFalse(any(
            event.get("type") == "agent_execution_completed"
            for event in persisted["events"]
        ))

    def test_agent_execution_rejects_empty_or_non_string_message(self):
        run = self.start()

        for message in ("", "   ", None, 123):
            with self.subTest(message=message):
                with self.assertRaises(ValueError):
                    self.app.record_agent_execution(
                        run_id=run["run_id"],
                        agent_name="requirements-analyst",
                        artifact_path="specs/001/test-spec.md",
                        execution_status="draft_created",
                        message=message,
                    )

        persisted = self.app.get_workflow(run["run_id"])
        self.assertFalse(any(
            event.get("type") == "agent_execution_completed"
            for event in persisted["events"]
        ))


if __name__ == "__main__":
    unittest.main()
