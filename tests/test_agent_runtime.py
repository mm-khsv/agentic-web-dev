import tempfile
import unittest
from pathlib import Path

from orchestrator.agent_registry import AgentRegistry
from orchestrator.agent_runtime import AgentRuntime


PROJECT_ROOT = Path(__file__).resolve().parent.parent


VALID_SRS_FIXTURE = """# Software Requirements Specification

## 1. Problem and Scope
The system provides an online store.

## 2. User Stories
- **US-01:** As a customer, I want to browse products.

## 3. Functional Requirements
- **FR-01:** The system shall display the product catalogue.

## 4. Non-Functional Requirements
- **NFR-01:** The system shall return catalogue responses within two seconds
  under the agreed test load.

## 5. Acceptance Criteria
- **AC-01:** Given an available product, when a customer opens its page,
  then the product details are displayed.

## 6. Assumptions
The payment provider is not yet selected.

## 7. Open Questions
Which payment provider will be used?

## 8. Privacy, Security & Abuse
The system shall protect account credentials.
"""


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


    def _prepare_cloudflare_fixture(self, include_skill=True):
        (self.root / "AGENTS.md").write_text(
            "# Test Governance\nGLOBAL_RULE_SENTINEL\n",
            encoding="utf-8",
        )

        agent_dir = self.root / ".agents" / "agents"
        agent_dir.mkdir(parents=True, exist_ok=True)
        (agent_dir / "requirements-analyst.md").write_text(
            "---\n"
            "name: requirements-analyst\n"
            "skills:\n"
            "  - write-requirements\n"
            "---\n"
            "# Test Agent\nAGENT_RULE_SENTINEL\n",
            encoding="utf-8",
        )

        if include_skill:
            skill_dir = self.root / ".agents" / "skills" / "write-requirements"
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(
                "# Test Skill\nSKILL_RULE_SENTINEL\n",
                encoding="utf-8",
            )

    def test_cloudflare_prompt_includes_project_and_skill_instructions(self):
        from unittest.mock import patch

        self._prepare_cloudflare_fixture()

        with patch.dict(
            "os.environ",
            {
                "CLOUDFLARE_ACCOUNT_ID": "test-account-id",
                "CLOUDFLARE_API_TOKEN": "test-api-token",
            },
        ), patch(
            "llm.client.LLMClient.generate",
            return_value=VALID_SRS_FIXTURE,
        ) as mocked_generate:
            result = self.runtime.run(
                "requirements-analyst",
                "?? ??????? ???????? ????",
                "specs/001/cloudflare-test.md",
                provider="cloudflare",
            )

        self.assertEqual(result.status, "draft_created")
        self.assertTrue(
            (self.root / "specs" / "001" / "cloudflare-test.md").is_file()
        )
        mocked_generate.assert_called_once()

        prompt = mocked_generate.call_args.args[0]
        self.assertIn("GLOBAL_RULE_SENTINEL", prompt)
        self.assertIn("AGENT_RULE_SENTINEL", prompt)
        self.assertIn("SKILL_RULE_SENTINEL", prompt)
        self.assertIn("Write technical artifacts in English", prompt)
        self.assertIn("Human review at gate G1 is mandatory", prompt)
        self.assertIn("?? ??????? ???????? ????", mocked_generate.call_args.args[1])


    def test_cloudflare_rejects_structurally_invalid_srs_before_saving(self):
        from unittest.mock import patch

        self._prepare_cloudflare_fixture()

        invalid_draft = """# Draft
## Functional Requirements
This is not a complete SRS.
"""
        with patch.dict(
            "os.environ",
            {
                "CLOUDFLARE_ACCOUNT_ID": "test-account-id",
                "CLOUDFLARE_API_TOKEN": "test-api-token",
            },
        ), patch(
            "llm.client.LLMClient.generate",
            return_value=invalid_draft,
        ):
            with self.assertRaisesRegex(
                ValueError, "SRS validation failed; artifact was not saved"
            ):
                self.runtime.run(
                    "requirements-analyst",
                    "Test request",
                    "specs/001/invalid-draft.md",
                    provider="cloudflare",
                )

        self.assertFalse(
            (self.root / "specs" / "001" / "invalid-draft.md").exists()
        )

    def test_srs_validator_rejects_placeholders_and_non_english_text(self):
        from orchestrator.agent_runtime import validate_srs_draft

        # Build a non-English sample from Unicode code points so that
        # PowerShell or console encoding cannot replace it with question marks.
        non_english_text = chr(0x0645) + chr(0x062A)
        invalid = VALID_SRS_FIXTURE.replace(
            "The system provides an online store.",
            non_english_text + " [TODO]",
        )
        errors = validate_srs_draft(invalid)

        self.assertTrue(
            any("written in English" in error for error in errors),
            msg=f"Expected non-English text to be rejected; got: {errors}",
        )
        self.assertTrue(
            any("placeholder" in error.lower() for error in errors),
            msg=f"Expected placeholder to be rejected; got: {errors}",
        )

    def test_srs_validator_accepts_structurally_complete_english_draft(self):
        from orchestrator.agent_runtime import validate_srs_draft

        self.assertEqual(validate_srs_draft(VALID_SRS_FIXTURE), [])

    def test_cloudflare_runtime_fails_closed_when_skill_is_missing(self):
        from unittest.mock import patch

        self._prepare_cloudflare_fixture(include_skill=False)

        with patch("llm.client.LLMClient.generate") as mocked_generate:
            with self.assertRaisesRegex(FileNotFoundError, "references missing Skill"):
                self.runtime.run(
                    "requirements-analyst",
                    "Test request",
                    "specs/001/missing-skill.md",
                    provider="cloudflare",
                )

        mocked_generate.assert_not_called()
        self.assertFalse(
            (self.root / "specs" / "001" / "missing-skill.md").exists()
        )


if __name__ == "__main__":
    unittest.main()