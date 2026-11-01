import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orchestrator.agent_registry import AgentRegistry
from orchestrator.agent_runtime import AgentRuntime
from orchestrator.engine import Orchestrator
from orchestrator import workflow as wf


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class ArtifactBundleRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = AgentRuntime(
            registry=AgentRegistry(PROJECT_ROOT),
            project_root=self.root,
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_writes_multiple_owned_artifacts(self):
        result = self.runtime.write_artifact_bundle(
            "ui-ux-designer",
            {
                "docs/ux/bundle-test-spec.md": "# UX draft\n",
                "docs/ux/bundle-test-flow.md": "# User flow\n",
            },
        )

        self.assertEqual(result.status, "draft_created")
        self.assertEqual(len(result.artifact_paths), 2)
        self.assertEqual(
            result.artifact_path,
            "docs/ux/bundle-test-spec.md",
        )
        for relative in result.artifact_paths:
            self.assertTrue((self.root / relative).is_file())

    def test_rejects_bundle_before_writing_if_a_target_exists(self):
        existing = self.root / "docs/ux/existing.md"
        existing.parent.mkdir(parents=True)
        existing.write_text("preserve me", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            self.runtime.write_artifact_bundle(
                "ui-ux-designer",
                {
                    "docs/ux/new.md": "# New\n",
                    "docs/ux/existing.md": "# Replacement\n",
                },
            )

        self.assertFalse((self.root / "docs/ux/new.md").exists())
        self.assertEqual(
            existing.read_text(encoding="utf-8"),
            "preserve me",
        )

    def test_rejects_unauthorized_path_without_writing(self):
        with self.assertRaises(PermissionError):
            self.runtime.write_artifact_bundle(
                "ui-ux-designer",
                {
                    "docs/ux/allowed.md": "# Draft\n",
                    "app/forbidden.py": "print('no')\n",
                },
            )

        self.assertFalse((self.root / "docs/ux/allowed.md").exists())
        self.assertFalse((self.root / "app/forbidden.py").exists())

    def test_rejects_parent_traversal(self):
        with self.assertRaises(ValueError):
            self.runtime.write_artifact_bundle(
                "ui-ux-designer",
                {"docs/ux/../outside.md": "# Invalid\n"},
            )


class ArtifactBundleEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runs_path = Path(self.temp.name) / "runs"
        self.patch_runs = patch(
            "orchestrator.engine.RUNS_DIR",
            self.runs_path,
        )
        self.patch_runs.start()
        self.addCleanup(self.patch_runs.stop)
        self.addCleanup(self.temp.cleanup)
        self.app = Orchestrator()

    def prepare_ux_run(self):
        run = self.app.start_workflow("Build a sample web application")
        role_config = wf.WorkflowConfig()
        roles = wf.allowed_approver_roles("G1", config=role_config)
        self.assertTrue(roles)

        self.app.decide_gate(
            run_id=run["run_id"],
            gate_id="G1",
            outcome="approved",
            approver="test-reviewer",
            approver_role=roles[0],
            reason="Test-only approval of G1",
        )
        self.app.transition(run["run_id"], "ux_design")
        return run["run_id"]

    def test_registers_bundle_as_one_event_without_approving_g2(self):
        run_id = self.prepare_ux_run()

        with tempfile.TemporaryDirectory() as project_dir:
            root = Path(project_dir).resolve()
            paths = [
                "docs/ux/ux-spec.md",
                "docs/ux/user-flows.md",
            ]
            for relative in paths:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("# Draft\n", encoding="utf-8")

            with patch("orchestrator.engine.PROJECT_ROOT", root):
                updated = self.app.record_agent_execution_bundle(
                    run_id=run_id,
                    agent_name="ui-ux-designer",
                    artifact_paths=paths,
                    execution_status="draft_created",
                    message="Registered a test artifact bundle.",
                )

        persisted = self.app.get_workflow(run_id)
        events = [
            event for event in persisted["events"]
            if event.get("type") == "agent_execution_completed"
        ]

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["artifact_path"], paths[0])
        self.assertEqual(events[0]["artifact_paths"], paths)
        self.assertEqual(updated["current_stage"], "ux_design")
        self.assertEqual(persisted["gate_states"]["G2"], "pending")
        self.assertEqual(persisted["status"], "in_progress")

    def test_missing_artifact_does_not_register_event(self):
        run_id = self.prepare_ux_run()

        with tempfile.TemporaryDirectory() as project_dir:
            root = Path(project_dir).resolve()
            existing = root / "docs/ux/existing.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("# Existing\n", encoding="utf-8")

            with patch("orchestrator.engine.PROJECT_ROOT", root):
                with self.assertRaises(FileNotFoundError):
                    self.app.record_agent_execution_bundle(
                        run_id=run_id,
                        agent_name="ui-ux-designer",
                        artifact_paths=[
                            "docs/ux/existing.md",
                            "docs/ux/missing.md",
                        ],
                        execution_status="draft_created",
                        message="This bundle must fail validation.",
                    )

        persisted = self.app.get_workflow(run_id)
        self.assertFalse(any(
            event.get("type") == "agent_execution_completed"
            and event.get("agent_name") == "ui-ux-designer"
            for event in persisted["events"]
        ))
        self.assertEqual(persisted["gate_states"]["G2"], "pending")

    def test_duplicate_paths_are_rejected(self):
        run_id = self.prepare_ux_run()

        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.app.record_agent_execution_bundle(
                run_id=run_id,
                agent_name="ui-ux-designer",
                artifact_paths=[
                    "docs/ux/same.md",
                    "docs/ux/same.md",
                ],
                execution_status="draft_created",
                message="Duplicate path test.",
            )

        persisted = self.app.get_workflow(run_id)
        self.assertFalse(any(
            event.get("type") == "agent_execution_completed"
            and event.get("agent_name") == "ui-ux-designer"
            for event in persisted["events"]
        ))


if __name__ == "__main__":
    unittest.main()
