import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from orchestrator.agent_registry import AgentRegistry
from orchestrator.agent_runtime import AgentRuntime


PROJECT_ROOT = Path(__file__).resolve().parents[1]

UX_SPEC = """# UX Design Specification
## Purpose and Source Requirements
FR-01: Compose a respectful message about unpleasant odor.
## UX Goals and Design Principles
Respectful, clear, and non-judgmental interactions.
## Information Architecture
Composer, preview, and saved drafts.
## Screen Inventory
Composer and saved-drafts views.
## User Flows
Compose, preview, copy, save, and view drafts.
## Interaction Specifications
Tone selection and preview update.
## Validation and Error States
Invalid input, clipboard failure, and persistence failure.
## Accessibility
Semantic controls and visible focus indicators.
## Requirements Traceability
FR-01 maps to the message composer.
## Assumptions and Open Questions
Unresolved technical questions remain open.
"""

CSS = """:root { --color-text: #222; --space-1: 4px; }
body { color: var(--color-text); }
"""

HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prototype</title>
<style>
body { font-family: system-ui, sans-serif; max-width: 48rem; margin: auto; padding: 1rem; }
[hidden] { display: none !important; }
:focus-visible { outline: 3px solid #2457c5; outline-offset: 2px; }
</style>
</head>
<body>
<p><strong>Prototype-only:</strong> drafts are stored in this browser for demonstration.</p>
<button type="button" data-action="switch-design" data-target="a">Design A</button>
<button type="button" data-action="switch-design" data-target="b">Design B</button>
<section data-design-variant="a"><h1>Considerate message</h1></section>
<section data-design-variant="b" hidden><h1>A calmer approach</h1></section>
<form id="composer">
<label for="tone">Tone</label>
<select id="tone" name="tone">
<option value="friendly">Friendly</option>
<option value="formal">Formal</option>
</select>
<label for="message">Message</label>
<textarea id="message"></textarea>
<button type="button" id="preview-button">Preview</button>
<div id="preview"></div>
<button type="button" data-action="copy">Copy</button>
<button type="button" data-action="save-draft">Save draft</button>
<button type="button" data-action="view-drafts">View drafts</button>
</form>
<p id="status" role="status" aria-live="polite"></p>
<ul id="draft-list"></ul>
<script>
const messageInput = document.querySelector("#message");
const preview = document.querySelector("#preview");
const status = document.querySelector("#status");
const draftList = document.querySelector("#draft-list");

document.querySelectorAll('[data-action="switch-design"]').forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-design-variant]").forEach((section) => {
      section.hidden = section.dataset.designVariant !== button.dataset.target;
    });
  });
});

document.querySelector("#preview-button").addEventListener("click", () => {
  preview.textContent = messageInput.value;
});

document.querySelector('[data-action="copy"]').addEventListener("click", async () => {
  try {
    await navigator.clipboard.writeText(messageInput.value);
    status.textContent = "Copied to clipboard.";
  } catch (error) {
    status.textContent = "Copy failed. Select and copy the text manually.";
  }
});

document.querySelector('[data-action="save-draft"]').addEventListener("click", () => {
  try {
    const drafts = JSON.parse(localStorage.getItem("prototype-drafts") || "[]");
    drafts.push({
      message: messageInput.value,
      tone: document.querySelector('[name="tone"]').value
    });
    localStorage.setItem("prototype-drafts", JSON.stringify(drafts));
    status.textContent = "Draft saved in this browser (prototype only).";
  } catch (error) {
    status.textContent = "Could not save the draft in this browser.";
  }
});

document.querySelector('[data-action="view-drafts"]').addEventListener("click", () => {
  try {
    const drafts = JSON.parse(localStorage.getItem("prototype-drafts") || "[]");
    draftList.replaceChildren();
    drafts.forEach((draft) => {
      const item = document.createElement("li");
      item.textContent = draft.message + " (" + draft.tone + ")";
      draftList.appendChild(item);
    });
    status.textContent = drafts.length ? "Saved drafts loaded." : "No saved drafts yet.";
  } catch (error) {
    status.textContent = "Could not load saved drafts.";
  }
});
</script>
</body>
</html>"""

OTHER_ARTIFACTS = {
    "docs/ux/user-flows.md": "# User Flows\nCompose, preview, copy, save, and view.\n",
    "docs/ux/screen-state-inventory.md": "# Screen State Inventory\nComposer and saved drafts.\n",
    "docs/ux/ui-copy.md": "# UI Copy\nRespectful labels and feedback.\n",
    "docs/ux/accessibility-review.md": (
        "# Accessibility Review\nAll checks are NOT TESTED.\n"
    ),
}


def fake_model_output(request):
    marker = "## Required artifact path\n"
    if marker not in request:
        raise AssertionError("Artifact path was not included in model request.")
    path = request.split(marker, 1)[1].splitlines()[0]

    if path == "docs/ux/ux-specification.md":
        return UX_SPEC
    if path == "docs/ux/design-tokens.css":
        return CSS
    if path == "docs/ux/prototypes/smelly-cat-v1.html":
        return HTML
    return OTHER_ARTIFACTS[path]


class UXBundleGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = AgentRuntime(
            registry=AgentRegistry(PROJECT_ROOT),
            project_root=self.root,
        )
        self.generator = Mock(side_effect=lambda *args: fake_model_output(args[-1]))
        self.runtime._cloudflare_generate = self.generator

    def tearDown(self):
        self.temp.cleanup()

    def test_generates_all_seven_artifacts_without_calling_a_real_model(self):
        result = self.runtime.run_bundle(
            agent_name="ui-ux-designer",
            user_request="Design the approved Smelly Cat v1 application.",
            provider="cloudflare",
        )

        expected = {
            "docs/ux/ux-specification.md",
            "docs/ux/user-flows.md",
            "docs/ux/screen-state-inventory.md",
            "docs/ux/ui-copy.md",
            "docs/ux/design-tokens.css",
            "docs/ux/prototypes/smelly-cat-v1.html",
            "docs/ux/accessibility-review.md",
        }

        self.assertEqual(result.status, "draft_created")
        self.assertEqual(set(result.artifact_paths), expected)
        self.assertEqual(self.generator.call_count, 7)
        for relative in expected:
            target = self.root / relative
            self.assertTrue(target.is_file(), relative)
            self.assertTrue(target.read_text(encoding="utf-8").strip())

        self.assertIn("G2 remains mandatory", result.message)

    def test_valid_model_prototype_is_preserved_without_fallback(self):
        self.runtime.run_bundle(
            agent_name="ui-ux-designer",
            user_request="Design the approved Smelly Cat v1 application.",
            provider="cloudflare",
        )

        prototype = (
            self.root
            / "docs/ux/prototypes/smelly-cat-v1.html"
        )

        generated_html = prototype.read_text(encoding="utf-8")

        self.assertEqual(generated_html.rstrip(), HTML.rstrip())
        self.assertNotIn("smelly-cat-required-behaviors", generated_html)
        self.assertNotIn("????", generated_html)

    def test_incomplete_prototype_writes_nothing(self):
        def incomplete_output(*args):
            request = args[-1]
            if "docs/ux/prototypes/smelly-cat-v1.html" in request:
                return (
                    "<!doctype html><html><body><form><textarea></textarea>"
                    "<button>Copy</button><script>"
                    "const clipboard = navigator.clipboard;"
                    "const storage = localStorage;"
                    "</script></form></body></html>"
                )
            return fake_model_output(request)

        self.generator.side_effect = incomplete_output

        with self.assertRaisesRegex(ValueError, "static validation"):
            self.runtime.run_bundle(
                "ui-ux-designer",
                "Test incomplete prototype rejection.",
                provider="cloudflare",
            )

        self.assertFalse((self.root / "docs/ux").exists())

    def test_invalid_ux_spec_writes_nothing(self):
        self.generator.side_effect = lambda *args: (
            "# Incomplete UX\n"
            if "ux-specification.md" in args[-1]
            else fake_model_output(args[-1])
        )

        with self.assertRaisesRegex(ValueError, "failed validation"):
            self.runtime.run_bundle(
                "ui-ux-designer",
                "Test invalid UX output.",
                provider="cloudflare",
            )

        self.assertFalse((self.root / "docs/ux").exists())

    def test_existing_target_is_rejected_before_any_model_call(self):
        existing = self.root / "docs/ux/ui-copy.md"
        existing.parent.mkdir(parents=True)
        existing.write_text("preserve this file", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            self.runtime.run_bundle(
                "ui-ux-designer",
                "Test overwrite protection.",
                provider="cloudflare",
            )

        self.generator.assert_not_called()
        self.assertEqual(
            existing.read_text(encoding="utf-8"),
            "preserve this file",
        )

    def test_wrong_agent_and_provider_are_rejected_before_model_call(self):
        with self.assertRaises(ValueError):
            self.runtime.run_bundle(
                "requirements-analyst",
                "Test wrong agent.",
                provider="cloudflare",
            )

        with self.assertRaises(ValueError):
            self.runtime.run_bundle(
                "ui-ux-designer",
                "Test wrong provider.",
                provider="dry-run",
            )

        self.generator.assert_not_called()
        self.assertFalse((self.root / "docs/ux").exists())

    def test_empty_model_output_writes_nothing(self):
        self.generator.side_effect = lambda *args: (
            "" if "ui-copy.md" in args[-1] else fake_model_output(args[-1])
        )

        with self.assertRaisesRegex(ValueError, "Empty model output"):
            self.runtime.run_bundle(
                "ui-ux-designer",
                "Test empty model response.",
                provider="cloudflare",
            )

        self.assertFalse((self.root / "docs/ux").exists())


if __name__ == "__main__":
    unittest.main()
