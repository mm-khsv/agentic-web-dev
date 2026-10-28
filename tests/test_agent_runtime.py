import tempfile
import unittest
from pathlib import Path

from orchestrator.agent_registry import AgentRegistry
from orchestrator.agent_runtime import AgentRuntime


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AgentRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.registry = AgentRegistry(PROJECT_ROOT)
        self.runtime = AgentRuntime(
            registry=self.registry,
            project_root=self.root,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_creates_draft_without_calling_an_llm(self):
        result = self.runtime.run(
            "requirements-analyst",
            "Build a small task management web app",
            "specs/001/spec.md",
        )
        artifact = self.root / "specs" / "001" / "spec.md"

        self.assertTrue(artifact.is_file())
        self.assertEqual(result.status, "draft_created")
        self.assertEqual(result.artifact_path, "specs/001/spec.md")
        self.assertIn("without an LLM", artifact.read_text(encoding="utf-8"))
        self.assertIn("Build a small task management web app",
                      artifact.read_text(encoding="utf-8"))

    def test_refuses_to_overwrite_existing_artifact(self):
        target = self.root / "specs" / "001" / "spec.md"
        target.parent.mkdir(parents=True)
        target.write_text("keep this", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            self.runtime.run(
                "requirements-analyst",
                "Test request",
                "specs/001/spec.md",
            )

        self.assertEqual(target.read_text(encoding="utf-8"), "keep this")

    def test_refuses_path_outside_project(self):
        outside = self.root.parent / "outside-spec.md"
        try:
            with self.assertRaisesRegex(ValueError, "inside the project root"):
                self.runtime.run(
                    "requirements-analyst",
                    "Test request",
                    str(outside),
                )
        finally:
            if outside.exists():
                outside.unlink()

    def test_refuses_path_outside_agent_ownership(self):
        with self.assertRaises(PermissionError):
            self.runtime.run(
                "requirements-analyst",
                "Test request",
                "app/unapproved.py",
            )

    def test_rejects_empty_request(self):
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            self.runtime.run(
                "requirements-analyst",
                "   ",
                "specs/001/spec.md",
            )

    def test_rejects_unregistered_handler(self):
        runtime = AgentRuntime(
            registry=self.registry,
            project_root=self.root,
            handlers={},
        )
        with self.assertRaisesRegex(ValueError, "No executable handler"):
            runtime.run(
                "requirements-analyst",
                "Test request",
                "specs/001/spec.md",
            )


if __name__ == "__main__":
    unittest.main()