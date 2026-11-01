from pathlib import Path
from unittest.mock import patch
import tempfile
import unittest

from orchestrator.engine import Orchestrator


class AgentExecutionSaveFailureTest(unittest.TestCase):
    def test_save_failure_can_be_recovered_without_recreating_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_dir = Path(temp_dir) / "runs"
            project_root = Path(temp_dir) / "project"
            runs_dir.mkdir()

            artifact = project_root / "specs" / "001" / "spec.md"
            artifact.parent.mkdir(parents=True)
            original_content = "# Existing valid draft\n"
            artifact.write_text(original_content, encoding="utf-8")

            with patch("orchestrator.engine.RUNS_DIR", runs_dir), \
                 patch("orchestrator.engine.PROJECT_ROOT", project_root):
                app = Orchestrator()
                run = app.start_workflow("Build a sample web application")

                with patch.object(
                    app,
                    "_save",
                    side_effect=OSError("simulated disk failure"),
                ):
                    with self.assertRaisesRegex(
                        OSError, "simulated disk failure"
                    ):
                        app.record_agent_execution(
                            run_id=run["run_id"],
                            agent_name="requirements-analyst",
                            artifact_path="specs/001/spec.md",
                            execution_status="draft_created",
                            message="Test artifact.",
                        )

                persisted = app.get_workflow(run["run_id"])
                self.assertFalse(any(
                    event.get("type") == "agent_execution_completed"
                    for event in persisted["events"]
                ))
                self.assertEqual(persisted["gate_states"]["G1"], "pending")

                # Retry recording the existing artifact; do not regenerate it.
                recovered = app.record_agent_execution(
                    run_id=run["run_id"],
                    agent_name="requirements-analyst",
                    artifact_path="specs/001/spec.md",
                    execution_status="draft_created",
                    message="Recovered registration of existing artifact.",
                )

                persisted = app.get_workflow(run["run_id"])
                events = [
                    event for event in persisted["events"]
                    if event.get("type") == "agent_execution_completed"
                ]

                self.assertEqual(len(events), 1)
                self.assertEqual(
                    events[0]["artifact_path"], "specs/001/spec.md"
                )
                self.assertEqual(persisted["gate_states"]["G1"], "pending")
                self.assertEqual(recovered["gate_states"]["G1"], "pending")
                self.assertEqual(
                    artifact.read_text(encoding="utf-8"),
                    original_content,
                )


    def test_duplicate_registration_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runs_dir = Path(temp_dir) / "runs"
            project_root = Path(temp_dir) / "project"
            runs_dir.mkdir()
            artifact = project_root / "specs" / "001" / "spec.md"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("# Draft\\n", encoding="utf-8")

            with patch("orchestrator.engine.RUNS_DIR", runs_dir), \
                 patch("orchestrator.engine.PROJECT_ROOT", project_root):
                app = Orchestrator()
                run = app.start_workflow("Build a sample web application")

                kwargs = {
                    "run_id": run["run_id"],
                    "agent_name": "requirements-analyst",
                    "artifact_path": "specs/001/spec.md",
                    "execution_status": "draft_created",
                    "message": "Register existing draft.",
                }
                app.record_agent_execution(**kwargs)

                with self.assertRaisesRegex(ValueError, "already registered"):
                    app.record_agent_execution(**kwargs)

                persisted = app.get_workflow(run["run_id"])
                events = [
                    event for event in persisted["events"]
                    if event.get("type") == "agent_execution_completed"
                ]
                self.assertEqual(len(events), 1)
                self.assertEqual(persisted["gate_states"]["G1"], "pending")


if __name__ == "__main__":
    unittest.main()
