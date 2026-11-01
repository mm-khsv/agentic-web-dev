import shutil
import tempfile
import unittest
from pathlib import Path

from orchestrator.agent_registry import AgentRegistry
from orchestrator.agent_runtime import AgentRuntime, validate_ux_draft


class UXAgentTests(unittest.TestCase):
    def test_validator_rejects_empty_and_incomplete_documents(self):
        self.assertTrue(validate_ux_draft(""))
        errors = validate_ux_draft("# UX Design")
        self.assertTrue(any("information architecture" in e for e in errors))

    def test_validator_rejects_non_english_and_placeholders(self):
        content = """# Purpose
فارسی
## UX Goals
## Information Architecture
## Screen Inventory
## User Flows
## Interaction Specifications
## Validation and Error States
## Accessibility
## Requirements Traceability
FR-01
## Assumptions and Open Questions
TODO
"""
        errors = validate_ux_draft(content)
        self.assertTrue(any("English" in e for e in errors))
        self.assertTrue(any("placeholder" in e.lower() for e in errors))
        self.assertTrue(any("line 13" in e for e in errors), msg=str(errors))

    def test_validator_accepts_complete_ux_outline(self):
        content = """# UX Design Specification
## Purpose and Source Requirements
FR-01
## UX Goals and Design Principles
## Information Architecture
## Screen Inventory
## User Flows
## Interaction Specifications
## Validation and Error States
## Accessibility
## Requirements Traceability
FR-01 maps to the message composer.
## Assumptions and Open Questions
The word PLACEHOLDER is explained here, not used as a marker.
"""
        self.assertEqual(validate_ux_draft(content), [])

    def test_dry_run_creates_only_a_labelled_test_artifact(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".agents" / "agents").mkdir(parents=True)
            (project / ".agents" / "skills" / "design-ux").mkdir(parents=True)
            shutil.copy(
                root / ".agents" / "agents" / "ui-ux-designer.md",
                project / ".agents" / "agents" / "ui-ux-designer.md",
            )
            shutil.copy(
                root / ".agents" / "skills" / "design-ux" / "SKILL.md",
                project / ".agents" / "skills" / "design-ux" / "SKILL.md",
            )
            registry = AgentRegistry(project)
            runtime = AgentRuntime(registry=registry, project_root=project)
            result = runtime.run(
                "ui-ux-designer",
                "Create a UX design for a small local application.",
                "docs/ux/smoke-test.md",
                provider="dry-run",
            )
            artifact = project / result.artifact_path
            self.assertTrue(artifact.is_file())
            text = artifact.read_text(encoding="utf-8")
            self.assertIn("not a completed UX design", text)
            self.assertIn("does not approve G2", text)
            self.assertEqual(result.status, "draft_created")

    def test_ux_agent_cannot_write_application_code(self):
        registry = AgentRegistry()
        definition = registry.get("ui-ux-designer")
        self.assertTrue(
            registry.permits_write(definition, "docs/ux/design.md")
        )
        self.assertFalse(
            registry.permits_write(definition, "app/main.py")
        )


if __name__ == "__main__":
    unittest.main()
