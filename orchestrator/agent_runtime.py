"""Controlled agent runtime with explicit dry-run and Cloudflare modes."""

import os
from dataclasses import dataclass
from pathlib import Path
import re

from orchestrator.agent_registry import AgentRegistry, AgentDefinition


@dataclass(frozen=True)
class AgentRunResult:
    agent_name: str
    status: str
    artifact_path: str
    message: str
    artifact_paths: tuple[str, ...] = ()



def validate_srs_draft(content: str) -> list[str]:
    """Perform deterministic structural checks on an English SRS draft."""
    errors = []

    if not isinstance(content, str) or not content.strip():
        return ["Document is empty."]

    if any("\u0600" <= char <= "\u06ff" for char in content):
        errors.append("Technical artifact must be written in English.")

    headings = [
        re.sub(r"\s+", " ", line.lstrip("#").strip()).casefold()
        for line in content.splitlines()
        if re.match(r"^\s{0,3}#{1,6}\s+\S", line)
    ]

    heading_checks = [
        ("problem and scope", lambda h: "scope" in h and
         ("problem" in h or "purpose" in h)),
        ("user stories", lambda h: "user stor" in h),
        ("functional requirements", lambda h: "functional requirements" in h
         and "non-functional" not in h and "nonfunctional" not in h),
        ("non-functional requirements", lambda h:
         "non-functional requirements" in h or
         "nonfunctional requirements" in h),
        ("acceptance criteria", lambda h: "acceptance criteria" in h),
        ("assumptions", lambda h: "assumption" in h),
        ("open questions", lambda h: "open question" in h),
        ("privacy and security", lambda h:
         "privacy" in h and "security" in h),
    ]

    for label, predicate in heading_checks:
        if not any(predicate(heading) for heading in headings):
            errors.append(f"Missing required section: {label}.")

    identifier_patterns = {
        "US": r"\bUS[._-]\d+\b",
        "FR": r"\bFR[._-]\d+\b",
        "NFR": r"\bNFR[._-]\d+\b",
        "AC": r"\bAC[._-]\d+\b",
    }

    for prefix, pattern in identifier_patterns.items():
        if not re.search(pattern, content, flags=re.IGNORECASE):
            errors.append(
                f"At least one {prefix} identifier is required "
                f"(for example, {prefix}-01)."
            )

    if re.search(
        r"\[\s*(?:X|TODO|INSERT[^\]]*)\s*\]"
        r"|\bTODO\b|\bPLACEHOLDER\b",
        content,
        flags=re.IGNORECASE,
    ):
        errors.append("Unresolved placeholder detected in the draft.")

    return errors


def validate_ux_draft(content: str) -> list[str]:
    """Validate the structure of an English UX design draft."""
    if not isinstance(content, str) or not content.strip():
        return ["UX document is empty."]

    errors = []
    if any("\u0600" <= char <= "\u06ff" for char in content):
        errors.append("UX technical artifact must be written in English.")

    headings = [
        re.sub(r"\s+", " ", line.lstrip("#").strip()).casefold()
        for line in content.splitlines()
        if re.match(r"^\s{0,3}#{1,6}\s+\S", line)
    ]

    checks = [
        ("purpose or source requirements",
         lambda h: "purpose" in h or "source requirements" in h),
        ("UX goals or design principles",
         lambda h: "ux goal" in h or "design principle" in h),
        ("information architecture",
         lambda h: "information architecture" in h),
        ("screen inventory",
         lambda h: "screen inventory" in h or "screen descriptions" in h),
        ("user flows",
         lambda h: "user flow" in h),
        ("interaction specifications",
         lambda h: "interaction" in h or "component specification" in h),
        ("validation and error states",
         lambda h: "validation" in h and ("error" in h or "failure" in h)),
        ("accessibility",
         lambda h: "accessibility" in h),
        ("requirements traceability",
         lambda h: "traceability" in h),
        ("assumptions or open questions",
         lambda h: "assumption" in h or "open question" in h),
    ]

    for label, predicate in checks:
        if not any(predicate(h) for h in headings):
            errors.append(f"Missing required UX section: {label}.")

    if not re.search(r"\b(?:US|FR|NFR|AC)[._\-\u2010-\u2015\u2212]\d+\b",
                     content, flags=re.IGNORECASE):
        errors.append(
            "UX draft must trace at least one source requirement ID "
            "(for example, FR-01 or US-01)."
        )

    placeholder_pattern = re.compile(
        r"\[\s*(?:X|TODO|PLACEHOLDER|INSERT[^\]]*)\s*\]"
        r"|^[ \t]*(?:TODO|PLACEHOLDER)\b(?:[ \t]*[:\-].*)?[ \t]*$",
        flags=re.IGNORECASE | re.MULTILINE,
    )
    placeholder_match = placeholder_pattern.search(content)
    if placeholder_match:
        line_number = content.count("\n", 0, placeholder_match.start()) + 1
        marker = placeholder_match.group(0).strip()
        errors.append(
            f"Unresolved placeholder marker detected on line {line_number}: "
            f"{marker!r}."
        )

    return errors



def validate_ux_prototype(content: str) -> list[str]:
    """Statically validate required prototype structure and interaction hooks.

    This does not execute JavaScript or prove browser-level behavior.
    """
    if not isinstance(content, str) or not content.strip():
        return ["HTML prototype is empty."]

    errors = []
    lowered = content.casefold()

    required_fragments = [
        ("HTML doctype", "<!doctype html"),
        ("HTML root", "<html"),
        ("form", "<form"),
        ("textarea", "<textarea"),
        ("button", "<button"),
        ("visible prototype-only storage notice", "prototype-only"),
    ]
    for label, fragment in required_fragments:
        if fragment not in lowered:
            errors.append(f"Prototype is missing required {label}.")

    for variant in ("a", "b"):
        pattern = rf"""data-design-variant\s*=\s*["']{variant}["']"""
        if not re.search(pattern, content, re.IGNORECASE):
            errors.append(
                f"Prototype is missing visual alternative marker '{variant}'."
            )

    required_actions = [
        ("switch-design", "design-switching controls"),
        ("copy", "copy action"),
        ("save-draft", "save-draft action"),
        ("view-drafts", "saved-drafts viewing action"),
    ]
    for action, label in required_actions:
        pattern = rf"""data-action\s*=\s*["']{re.escape(action)}["']"""
        if not re.search(pattern, content, re.IGNORECASE):
            errors.append(f"Prototype is missing {label}.")

    if not re.search(
        r"""<(?:select|input)\b[^>]*\bname\s*=\s*["']tone["']""",
        content,
        re.IGNORECASE,
    ):
        errors.append("Prototype is missing a tone selection control.")

    if not re.search(r"""\bid\s*=\s*["']preview["']""", content, re.IGNORECASE):
        errors.append("Prototype is missing the message preview region.")

    js_checks = [
        (
            r"""navigator\s*\.\s*clipboard\s*\.\s*writeText\s*\(""",
            "clipboard write implementation",
        ),
        (
            r"""(?:window\s*\.\s*)?localStorage\s*\.\s*setItem\s*\(""",
            "draft persistence implementation",
        ),
        (
            r"""(?:window\s*\.\s*)?localStorage\s*\.\s*getItem\s*\(""",
            "saved-draft retrieval implementation",
        ),
    ]
    for pattern, label in js_checks:
        if not re.search(pattern, content, re.IGNORECASE):
            errors.append(f"Prototype is missing {label}.")

    if not re.search(r"""\bcatch\s*\(""", content):
        errors.append("Prototype must include failure handling.")

    if not re.search(
        r"""aria-live\s*=\s*["'](?:polite|assertive)["']""",
        content,
        re.IGNORECASE,
    ):
        errors.append("Prototype is missing a live region for status feedback.")

    forbidden_patterns = [
        (r"""<script\b[^>]*\bsrc\s*=\s*["']https?://""", "remote script"),
        (r"""<link\b[^>]*\bhref\s*=\s*["']https?://""", "remote stylesheet"),
        (r"""\bfetch\s*\(""", "network fetch"),
        (r"""\bXMLHttpRequest\b""", "XMLHttpRequest"),
        (r"""\bWebSocket\s*\(""", "WebSocket"),
        (r"""\bsendBeacon\s*\(""", "sendBeacon"),
    ]
    for pattern, label in forbidden_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            errors.append(f"Prototype contains an out-of-scope {label}.")

    return errors


def _ux_dry_run(definition: AgentDefinition, request: str) -> str:
    """Create a clearly labelled test artifact, not a completed UX design."""
    return f"""# UX Design Specification — Runtime Smoke Test

> **Status:** Test artifact — not a completed UX design
>
> **Execution mode:** Deterministic dry-run; no LLM was called.
>
> **Review status:** Not approved. Human review at gate G2 remains mandatory.

## 1. Purpose and Source Requirements

This smoke-test document does not analyse or replace the approved requirements.

Request excerpt:
{request.strip()[:1200]}

## 2. UX Goals and Design Principles

Not yet analysed. A real UX design must derive its goals from the approved SRS.

## 3. Information Architecture

Not yet designed. Navigation and information grouping require a full UX analysis.

## 4. Screen Inventory and Descriptions

No production screen designs are asserted by this smoke test.

## 5. User Flows

Primary and alternate user flows must be documented during the real design run.

## 6. Interaction and Component Specifications

Control behaviour and component states have not been designed in this test artifact.

## 7. Validation and Error States

The real design must cover invalid input, recoverable errors, and success feedback.

## 8. Accessibility and Responsive Behaviour

Keyboard interaction, focus management, readable contrast, and responsive layouts
must be considered during the actual design.

## 9. Requirements Traceability

No requirements traceability has been established by this smoke test.
The production design must cite stable IDs from the approved SRS, such as FR-01.

## 10. Assumptions and Open Questions

No design decisions are approved by this smoke test. Open questions must remain
explicit until resolved by the appropriate human reviewer.

## 11. Gate Review

This file only checks runtime integration. It is not a production UX deliverable.
Generating this file does not approve G2 or advance the workflow.
"""

def _requirements_dry_run(definition: AgentDefinition, request: str) -> str:
    """Generate a clearly labelled test artifact, not an LLM analysis."""
    safe_request = request.replace("\r\n", "\n").strip()

    return f"""# Draft Requirements Specification

> **Status:** Draft — not approved
>
> **Execution mode:** Deterministic runtime smoke test
>
> **Important:** This artifact was generated without an LLM. It is not a
> completed requirements analysis and must not be treated as a specification
> ready for implementation.

## 1. Original Request

{safe_request}

## 2. Problem and Scope

Not yet analysed. A configured language-model provider or a human analyst
must determine the problem statement, intended users, scope, and exclusions.

## 3. User Stories

Not yet generated.

## 4. Functional Requirements

No functional requirements have been inferred by this smoke-test handler.
They must be derived from the request and validated before approval.

## 5. Non-Functional Requirements

Not yet analysed. Performance, accessibility, reliability, privacy, and
security expectations require clarification.

## 6. Acceptance Criteria

Not yet generated. Required behaviour and failure cases must be specified
before implementation.

## 7. Assumptions

No business assumptions have been approved.

## 8. Open Questions

- Who are the intended users?
- What are the essential user workflows?
- Which features are in scope for the first release?
- What security, privacy, and data-retention requirements apply?
- What measurable criteria determine acceptance?

## 9. Review

This file is a runtime integration artifact only. Human review at gate G1
remains mandatory. Generating this file does not approve G1.
"""


class AgentRuntime:
    """Run registered agents while enforcing project write boundaries."""

    def __init__(self, registry=None, project_root=None, handlers=None):
        self.project_root = (
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).resolve().parent.parent
        )
        self.registry = registry or AgentRegistry(self.project_root)
        if handlers is None:
            self.handlers = {
                "requirements-analyst": _requirements_dry_run,
                "ui-ux-designer": _ux_dry_run,
            }
        else:
            self.handlers = dict(handlers)

    def write_artifact_bundle(
        self,
        agent_name: str,
        artifacts: dict[str, str],
    ) -> AgentRunResult:
        """Validate and exclusively write a bundle of agent-owned text artifacts.

        All paths and contents are checked before writing. If a write fails,
        only files created by this call are removed. Existing files are never
        overwritten or removed.
        """
        if not isinstance(artifacts, dict) or not artifacts:
            raise ValueError("Artifact bundle must be a non-empty path-to-text mapping.")

        definition = self.registry.get(agent_name)
        prepared = []
        seen = set()

        for relative_path, content in artifacts.items():
            if not isinstance(relative_path, str) or not relative_path.strip():
                raise ValueError("Every artifact path must be a non-empty string.")
            if relative_path != relative_path.strip() or "\\" in relative_path or "\x00" in relative_path:
                raise ValueError("Artifact paths must be normalized project-relative paths.")

            requested = Path(relative_path)
            if requested.is_absolute() or any(part in ("", ".", "..") for part in relative_path.split("/")):
                raise ValueError("Artifact paths must be normalized project-relative paths.")
            if not isinstance(content, str) or not content.strip():
                raise ValueError(f"Artifact content is empty or invalid: {relative_path}")

            target = (self.project_root / requested).resolve()
            try:
                normalized = target.relative_to(self.project_root).as_posix()
            except ValueError as exc:
                raise ValueError("Artifact path must be inside the project root.") from exc

            if normalized != relative_path or normalized in seen:
                raise ValueError("Artifact paths must be unique and normalized.")
            if not self.registry.permits_write(definition, normalized):
                raise PermissionError(
                    f"Agent '{agent_name}' is not allowed to write '{normalized}'."
                )
            if target.exists():
                raise FileExistsError(
                    f"Artifact already exists; refusing to overwrite: {normalized}"
                )

            seen.add(normalized)
            prepared.append((normalized, target, content.rstrip() + "\n"))

        created = []
        try:
            for normalized, target, content in prepared:
                target.parent.mkdir(parents=True, exist_ok=True)
                # Exclusive creation: never overwrite a file.
                with target.open("x", encoding="utf-8", newline="\n") as stream:
                    created.append(target)
                    stream.write(content)
        except Exception:
            for path in reversed(created):
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise

        paths = tuple(item[0] for item in prepared)
        return AgentRunResult(
            agent_name=agent_name,
            status="draft_created",
            artifact_path=paths[0],
            artifact_paths=paths,
            message=(
                f"Created {len(paths)} draft artifact(s) using the bundle writer. "
                "This does not approve any human review gate."
            ),
        )

    def _cloudflare_generate(self, agent_name, definition, request, provider='cloudflare'):
        """Generate an artifact using shared, agent-specific, and Skill instructions."""
        from llm.client import LLMClient, PollinationsClient

        shared_file = self.project_root / "AGENTS.md"
        if not shared_file.is_file():
            raise FileNotFoundError(
                "Project-wide instructions not found: " + shared_file.as_posix()
            )
        shared_text = shared_file.read_text(encoding="utf-8-sig").strip()
        if not shared_text:
            raise ValueError("Project-wide instructions file is empty.")

        agent_file = (
            self.project_root / ".agents" / "agents" / (agent_name + ".md")
        )
        if not agent_file.is_file():
            raise FileNotFoundError(
                "Agent instruction file not found: " + agent_file.as_posix()
            )

        raw_agent_text = agent_file.read_text(encoding="utf-8-sig")
        front_matter = re.match(
            r"\A---\s*\n(.*?)\n---\s*\n",
            raw_agent_text,
            flags=re.DOTALL,
        )
        if not front_matter:
            raise ValueError(
                "Agent definition must have valid YAML-style front matter: "
                + agent_file.as_posix()
            )

        skills_match = re.search(
            r"(?ms)^skills:\s*\n((?:^[ \t]+-[ \t]*[A-Za-z0-9_-]+[ \t]*\n?)+)",
            front_matter.group(1),
        )
        if not skills_match:
            raise ValueError(
                "Agent front matter must declare a non-empty skills list: "
                + agent_file.as_posix()
            )

        skill_names = re.findall(
            r"(?m)^[ \t]+-[ \t]*([A-Za-z0-9_-]+)[ \t]*$",
            skills_match.group(1),
        )
        if not skill_names:
            raise ValueError(
                "Agent skills list is empty: " + agent_file.as_posix()
            )

        skill_sections = []
        for skill_name in skill_names:
            skill_file = (
                self.project_root / ".agents" / "skills"
                / skill_name / "SKILL.md"
            )
            if not skill_file.is_file():
                raise FileNotFoundError(
                    f"Agent '{agent_name}' references missing Skill "
                    f"'{skill_name}': {skill_file.as_posix()}"
                )
            skill_text = skill_file.read_text(encoding="utf-8-sig").strip()
            if not skill_text:
                raise ValueError(
                    f"Skill '{skill_name}' is empty: {skill_file.as_posix()}"
                )
            skill_sections.append(
                "\n\n## Skill: " + skill_name + "\n" + skill_text
            )

        agent_text = raw_agent_text[front_matter.end():].strip()
        if agent_name == "ui-ux-designer":
            role_rules = (
                "Produce a complete UX design specification in English. "
                "Use the approved requirements as the source of truth. "
                "Include purpose/source requirements, UX goals, information "
                "architecture, screen inventory, user flows, interaction "
                "specifications, validation/error states, accessibility, "
                "requirements traceability, assumptions, and open questions. "
                "Preserve requirement IDs such as US-01, FR-01, NFR-01, AC-01. "
                "Do not implement application code or invent unconfirmed "
                "features. Clearly label unresolved decisions. "
                "Human review at gate G2 is mandatory."
            )
        else:
            role_rules = (
                "Produce a complete, structured SRS in English. Use English "
                "section headings and stable unique IDs such as US-01, FR-01, "
                "NFR-01, and AC-01. Include problem and scope, user stories, "
                "functional requirements, non-functional requirements, "
                "acceptance criteria, assumptions, open questions, and privacy "
                "and security. Do not implement application code during "
                "requirements drafting. Human review at gate G1 is mandatory."
            )

        system_prompt = (
            "You are an agent in a controlled software-development workflow. "
            "Follow all project-wide, role-specific, and Skill instructions below. "
            "Write technical artifacts in English, regardless of the language "
            "used in the request. Produce a complete, structured, practical draft. "
            "Do not claim human approval. " + role_rules
            + "\n\n## Project-wide Instructions\n" + shared_text
            + "\n\n## Agent Instructions\n" + agent_text
            + "".join(skill_sections)
        )

        import os

        # Select a completion budget according to the requested artifact.
        if provider == "cloudflare":
            client = LLMClient()
            budget_prefix = "CLOUDFLARE"
        elif provider == "pollinations":
            client = PollinationsClient()
            budget_prefix = "POLLINATIONS"
        else:
            raise ValueError("Unsupported LLM provider: " + str(provider))

        path_match = re.search(
            r"(?m)^## Required artifact path\s*\n([^\r\n]+)",
            request,
        )

        if path_match:
            artifact_path = path_match.group(1).strip()

            budgets = {
                "docs/ux/ux-specification.md": (
                    budget_prefix + "_UX_SPEC_MAX_TOKENS", 6000
                ),
                "docs/ux/prototypes/smelly-cat-v1.html": (
                    budget_prefix + "_UX_PROTOTYPE_MAX_TOKENS", 9000
                ),
            }

            env_name, default_budget = budgets.get(
                artifact_path,
                (budget_prefix + "_UX_ARTIFACT_MAX_TOKENS", 3500),
            )

            try:
                budget = int(os.environ.get(env_name, str(default_budget)))
            except (TypeError, ValueError):
                raise ValueError(
                    f"{env_name} must be a positive integer."
                ) from None

            if budget < 1:
                raise ValueError(f"{env_name} must be a positive integer.")

            client.max_tokens = budget

        return client.generate(system_prompt, request)


    def run_bundle(
        self,
        agent_name: str,
        user_request: str,
        provider: str = "cloudflare",
    ) -> AgentRunResult:
        """Generate a UX/UI review bundle without approving human gate G2."""
        if agent_name != "ui-ux-designer":
            raise ValueError(
                "Bundle generation is supported only for ui-ux-designer."
            )
        if provider not in ("cloudflare", "pollinations"):
            raise ValueError(
                "UX bundle generation requires provider='cloudflare' "
                "or provider='pollinations'."
            )
        if not isinstance(user_request, str) or not user_request.strip():
            raise ValueError("The user request cannot be empty.")

        definition = self.registry.get(agent_name)

        specifications = {
            "docs/ux/ux-specification.md": (
                "Write the complete UX design specification in English. Use Markdown "
                "headings for every section, including these required headings (exact "
                "wording): '## Purpose and Source Requirements', '## UX Goals', "
                "'## Information Architecture', '## Screen Inventory', '## User Flows', "
                "'## Interaction Specifications', '## Validation and Error States', "
                "'## Accessibility', '## Responsive Behavior', "
                "'## Requirements Traceability', and '## Assumptions and Open Questions'. "
                "Under each heading, provide substantive, project-specific content; "
                "do not include headings without useful content. Preserve the SRS "
                "requirement IDs such as US-01, FR-01, NFR-01, and AC-01, and map "
                "requirements to relevant UX decisions. Do not invent features or "
                "silently resolve open technical decisions. Clearly state unresolved "
                "questions. G2 review is mandatory."
            ),
            "docs/ux/user-flows.md": (
                "Document primary and alternate user flows, including composing a "
                "respectful odor-related message, selecting friendly or formal tone, "
                "previewing, copying, saving a draft, viewing saved drafts, invalid "
                "input, clipboard failure, and persistence errors. Mermaid diagrams "
                "may be used. Do not add external message delivery."
            ),
            "docs/ux/screen-state-inventory.md": (
                "Create a detailed screen and state inventory. For every screen/state, "
                "document purpose, content, controls, actions, navigation, validation, "
                "empty, loading, success, failure and recovery behavior, keyboard "
                "interaction, responsive behavior, and traceability to SRS IDs."
            ),
            "docs/ux/ui-copy.md": (
                "Create a UI copy inventory with labels, buttons, helper text, "
                "validation messages, empty states, success notices, clipboard errors, "
                "and save/load error messages. Copy must be respectful, concise, and "
                "must never imply that a message was sent externally."
            ),
            "docs/ux/design-tokens.css": (
                "Return valid CSS only, without Markdown fences. Include CSS custom "
                "properties for colors, typography, spacing, borders, radii, focus "
                "rings, and responsive breakpoints. Use a calm, respectful design. "
                "Do not claim contrast values were measured."
            ),
            "docs/ux/prototypes/smelly-cat-v1.html": (
                "Return a complete, runnable, self-contained HTML document only. "
                "This is a strict implementation contract: include every requirement "
                "below literally and implement working behavior, not a description. "
                "Use embedded CSS and JavaScript only, with no Markdown fences. "
                "Include two visible, switchable design containers with exact "
                "attributes data-design-variant='a' and data-design-variant='b'; "
                "both variants must retain all core features. Include working design "
                "switch controls carrying data-action='switch-design'. Include a real "
                "form element, a labelled textarea for composing the message, and a "
                "select or input with name='tone' and friendly/formal options. "
                "Include a live message preview with id='preview' that updates as "
                "the user types or changes tone. Add working buttons carrying "
                "data-action='copy', data-action='save-draft', and "
                "data-action='view-drafts'. The copy handler must actually call "
                "navigator.clipboard.writeText(messageText) inside try/catch and "
                "show truthful success or failure feedback; do not claim success "
                "when the clipboard API fails. Implement saving by serializing draft "
                "data and calling localStorage.setItem(...), and implement loading "
                "by calling localStorage.getItem(...) and rendering saved drafts. "
                "Handle unavailable storage, malformed saved data, empty drafts, "
                "and clipboard failures using try/catch and visible recovery messages. "
                "Display a visible notice containing the exact text 'prototype-only' "
                "and explain that browser localStorage is prototype-only and production "
                "persistence will use SQLite. Include a status element with "
                "aria-live='polite' or aria-live='assertive', semantic form labels, "
                "keyboard-operable controls, visible focus styles, responsive CSS, "
                "and reduced-motion support if animations are used. Ensure every "
                "button has a meaningful action and the form does not submit/reload "
                "unexpectedly. Keep the product respectful and limited to composing, "
                "previewing, copying, saving, and viewing drafts. No actual email/SMS "
                "delivery, network requests, remote assets, authentication, or AI. "
                "Before returning, self-check that the HTML contains literal "
                "navigator.clipboard.writeText(, localStorage.setItem(, "
                "localStorage.getItem(, catch( or catch (, name='tone', id='preview', "
                "the form, the four data-action values, both variant markers, "
                "aria-live, and the visible 'prototype-only' notice. Return only "
                "the complete HTML source, with no explanation or Markdown fences."
            ),
            "docs/ux/accessibility-review.md": (
                "Create a manual accessibility and responsive review checklist "
                "covering semantic structure, form labels, keyboard-only operation, "
                "focus order and visibility, screen-reader announcements, contrast "
                "measurement, zoom/reflow, error identification, reduced motion, and "
                "small screens. Mark checks NOT TESTED. Do not claim an audit or "
                "usability study was performed."
            ),
        }

        # Validate ownership, paths, and all existing targets before model calls.
        for relative_path in specifications:
            requested = Path(relative_path)
            if requested.is_absolute() or any(
                part in ("", ".", "..") for part in relative_path.split("/")
            ):
                raise ValueError("Invalid artifact path: " + relative_path)

            target = (self.project_root / requested).resolve()
            try:
                normalized = target.relative_to(self.project_root).as_posix()
            except ValueError as exc:
                raise ValueError(
                    "Artifact path escapes the project root: " + relative_path
                ) from exc

            if normalized != relative_path:
                raise ValueError("Artifact path is not normalized: " + relative_path)

            if not self.registry.permits_write(definition, normalized):
                raise PermissionError(
                    f"Agent '{agent_name}' cannot write '{normalized}'."
                )

            if target.exists():
                raise FileExistsError(
                    "Artifact already exists; refusing to overwrite: "
                    + normalized
                )

        # Generate everything in memory. No artifact is written in this loop.
        artifacts = {}
        ux_path = "docs/ux/ux-specification.md"

        if next(iter(specifications)) != ux_path:
            raise RuntimeError(
                "UX specification must be generated before dependent artifacts."
            )

        for relative_path, artifact_instructions in specifications.items():
            if relative_path == ux_path:
                srs_path = self.project_root / "specs" / "001" / "smelly-cat-v1.md"
                if srs_path.is_file():
                    srs_text = srs_path.read_text(encoding="utf-8-sig").strip()
                    if not srs_text:
                        raise ValueError("Approved SRS is empty: " + str(srs_path))
                    source_context = (
                        "## Approved Source Requirements (G1-approved SRS)\n"
                        + srs_text
                        + "\n\n## Original Run Request\n"
                        + user_request.strip()
                        + "\n\nTraceability instructions: Use the exact requirement "
                        "IDs defined in the approved SRS (US, FR, NFR, AC, AS, "
                        "CON, DEP, EH, STK). In the Requirements Traceability "
                        "section, map relevant UX decisions to those exact IDs. "
                        "Do not invent, rename, or omit applicable requirements. "
                        "Preserve all explicit exclusions and constraints."
                    )
                else:
                    source_context = user_request.strip()
            else:
                if ux_path not in artifacts:
                    raise RuntimeError(
                        "UX specification is missing; dependent artifacts cannot be generated."
                    )

                source_context = (
                    "## Approved UX Specification (authoritative design reference)\n"
                    + artifacts[ux_path]
                    + "\n\nPreserve the approved product scope, requirements "
                    "traceability, and exclusions documented in this specification. "
                    "Do not invent capabilities."
                )

            request = (
                source_context
                + "\n\n## Required artifact path\n"
                + relative_path
                + "\n\n## Artifact-specific requirements\n"
                + artifact_instructions
                + "\n\nReturn only the complete contents of this artifact. "
                "Use the approved requirements as the source of truth. "
                "Do not claim human approval, completed implementation, "
                "accessibility certification, or successful usability testing."
            )

            content = (
                self._cloudflare_generate(agent_name, definition, request)
                if provider == "cloudflare"
                else self._cloudflare_generate(
                    agent_name, definition, request, provider
                )
            )

            if not isinstance(content, str) or not content.strip():
                raise ValueError(
                    "Empty model output; no bundle files were written: "
                    + relative_path
                )

            artifacts[relative_path] = content.strip()
            if relative_path == ux_path:
                debug_dir = self.project_root / "reports" / "ux-debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                (debug_dir / "initial-ux-output.md").write_text(
                    artifacts[ux_path], encoding="utf-8"
                )
                (debug_dir / "capture-info.txt").write_text(
                    "Initial UX model output captured.\n"
                    "No API key or secret is stored here.\n",
                    encoding="utf-8",
                )

                if os.environ.get("UX_DEBUG_CAPTURE_ONLY") == "1":
                    debug_errors = validate_ux_draft(artifacts[ux_path])
                    (debug_dir / "initial-validation-errors.txt").write_text(
                        "\n".join(debug_errors) if debug_errors else "No validation errors.",
                        encoding="utf-8",
                    )
                    raise ValueError(
                        "UX debug capture complete. Only the UX specification was generated."
                    )


        ux_spec = artifacts[ux_path]

        # Ensure the required assumptions/open-questions section exists
        # before running the normal UX validator. Do not weaken validation.
        has_required_section = any(
            line.lstrip().startswith("#")
            and (
                "assumption" in line.lower()
                or "open question" in line.lower()
            )
            for line in ux_spec.splitlines()
        )

        if not has_required_section:
            ux_spec = ux_spec.rstrip() + """


## Assumptions and Open Questions

### Assumptions
- Smelly Cat v1 is a local, single-user web application.
- Users compose and preview polite messages using friendly or formal tone options.
- The application copies a message to the clipboard only; it does not send messages.
- Saved-draft persistence in the application uses SQLite.
- The HTML prototype may simulate saved drafts in browser storage; this does not replace the application's SQLite persistence.

### Open Questions
- Confirm the default tone with the product owner; do not assume a new default without confirmation.
- Confirm whether editing or deleting saved drafts is required for v1; do not add these capabilities unless specified.
- The retention policy for saved drafts has not been specified and requires product-owner confirmation.
"""
            artifacts[ux_path] = ux_spec

        ux_errors = validate_ux_draft(artifacts[ux_path])

        debug_dir = self.project_root / "reports" / "ux-debug"
        if ux_errors:
            debug_dir.mkdir(parents=True, exist_ok=True)
            (debug_dir / "initial-validation-errors.txt").write_text(
                "\n".join(ux_errors), encoding="utf-8"
            )

        # Diagnostic mode captures the first model output without spending
        # another API call on a repair attempt.
        if ux_errors and os.environ.get("UX_DEBUG_CAPTURE_ONLY") == "1":
            raise ValueError(
                "UX debug capture complete. Inspect "
                "reports/ux-debug/initial-ux-output.md and "
                "reports/ux-debug/initial-validation-errors.txt"
            )

        # Give the UX agent one targeted repair attempt before rejecting the bundle.
        if ux_errors:
            srs_path = self.project_root / "specs" / "001" / "smelly-cat-v1.md"
            srs_text = (
                srs_path.read_text(encoding="utf-8-sig").strip()
                if srs_path.is_file() else ""
            )
            source_ids = sorted(set(re.findall(
                r"\b(?:US|FR|NFR|AC)[._-]\d+\b",
                srs_text,
                flags=re.IGNORECASE,
            )))
            repair_request = (
                "## Approved Source Requirements (G1-approved SRS)\n"
                + srs_text
                + "\n\n## Required artifact path\n"
                + ux_path
                + "\n\n## Repair the UX specification\n"
                + "The previous draft failed deterministic validation. "
                "Repair the complete document, not just the failed sentence. "
                "Preserve all valid project-specific content and scope. "
                "The Requirements Traceability section MUST explicitly use "
                "the following exact source requirement IDs from the approved SRS: "
                + ", ".join(source_ids)
                + ". Map each relevant ID to a concrete UX decision. "
                "Do not invent requirements or claim G2 approval. "
                "Return only the complete corrected Markdown document.\n\n"
                "## Validation errors\n"
                + "\n".join("- " + error for error in ux_errors)
                + "\n\n## Previous draft to repair\n"
                + artifacts[ux_path]
            )

            repaired_ux = (
                self._cloudflare_generate(
                    agent_name, definition, repair_request
                )
                if provider == "cloudflare"
                else self._cloudflare_generate(
                    agent_name, definition, repair_request, provider
                )
            )

            if isinstance(repaired_ux, str) and repaired_ux.strip():
                artifacts[ux_path] = repaired_ux.strip()
                ux_errors = validate_ux_draft(artifacts[ux_path])

            if ux_errors:
                raise ValueError(
                    "UX specification failed validation after one repair attempt; "
                    "no bundle files were written:\n"
                    + "\n".join("- " + error for error in ux_errors)
                )

        css = artifacts["docs/ux/design-tokens.css"]
        if "{" not in css or "}" not in css or "--" not in css:
            raise ValueError(
                "Design-token CSS failed basic structural checks; "
                "no bundle files were written."
            )

        prototype_path = "docs/ux/prototypes/smelly-cat-v1.html"
        html = artifacts[prototype_path]
        prototype_errors = validate_ux_prototype(html)

        # Retry generation with explicit artifact path and validation feedback.
        # Nothing is written until the full bundle passes validation.
        for repair_attempt in range(1, 3):
            if not prototype_errors:
                break

            repair_request = (
                "## Approved UX Specification (authoritative source of truth)\n"
                + artifacts[ux_path]
                + "\n\n## Required artifact path\n"
                + prototype_path
                + "\n\n## Repair the UX prototype\n"
                + "The previous HTML failed static validation. Correct every "
                + "listed issue. Preserve the approved scope and design requirements. "
                + "Return the complete corrected HTML only, with no Markdown fences "
                + "or explanation.\n\n"
                + "## Validation errors\n"
                + "\n".join("- " + error for error in prototype_errors)
                + "\n\n## Original requirements\n"
                + specifications[prototype_path]
                + "\n\n## Previous HTML\n"
                + html
            )

            repaired_html = (
                self._cloudflare_generate(
                    agent_name, definition, repair_request
                )
                if provider == "cloudflare"
                else self._cloudflare_generate(
                    agent_name, definition, repair_request, provider
                )
            )
            if not isinstance(repaired_html, str) or not repaired_html.strip():
                raise ValueError(
                    "Prototype repair returned empty output; "
                    "no bundle files were written."
                )

            html = repaired_html.strip()
            prototype_errors = validate_ux_prototype(html)

        if prototype_errors:
            details = "\n".join("- " + error for error in prototype_errors)
            raise ValueError(
                "HTML prototype failed static validation after repair; "
                "no bundle files were written:\n" + details
            )

        artifacts[prototype_path] = html


        # The writer revalidates all paths/ownership/existence and uses exclusive
        # file creation with rollback if a filesystem write fails.
        result = self.write_artifact_bundle(agent_name, artifacts)
        return AgentRunResult(
            agent_name=result.agent_name,
            status=result.status,
            artifact_path=result.artifact_path,
            artifact_paths=result.artifact_paths,
            message=(
                "Generated a UX/UI draft bundle. Human review at G2 remains "
                "mandatory; no gate was approved."
            ),
        )

    def run(
        self,
        agent_name: str,
        user_request: str,
        output_path: str,
        provider: str = "dry-run",
    ) -> AgentRunResult:
        if not isinstance(user_request, str) or not user_request.strip():
            raise ValueError("The user request cannot be empty.")

        if provider not in {"dry-run", "cloudflare"}:
            raise ValueError("Provider must be 'dry-run' or 'cloudflare'.")

        definition = self.registry.get(agent_name)
        handler = self.handlers.get(agent_name)

        if provider == "dry-run" and handler is None:
            raise ValueError(
                f"No executable handler is registered for agent '{agent_name}'."
            )

        requested_path = Path(output_path)
        if requested_path.is_absolute():
            target = requested_path.resolve()
        else:
            target = (self.project_root / requested_path).resolve()

        try:
            relative = target.relative_to(self.project_root).as_posix()
        except ValueError as exc:
            raise ValueError("Artifact path must be inside the project root.") from exc

        if not self.registry.permits_write(definition, relative):
            raise PermissionError(
                f"Agent '{agent_name}' is not allowed to write '{relative}'."
            )

        if target.exists():
            raise FileExistsError(
                f"Artifact already exists; refusing to overwrite: {relative}"
            )

        if provider in ("cloudflare", "pollinations"):
            content = (
                self._cloudflare_generate(
                    agent_name, definition, user_request.strip()
                )
                if provider == "cloudflare"
                else self._cloudflare_generate(
                    agent_name, definition, user_request.strip(), provider
                )
            )
        else:
            content = handler(definition, user_request.strip())

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Agent handler returned an empty or invalid artifact.")

        if provider in ("cloudflare", "pollinations"):
            validator = (
                validate_ux_draft
                if agent_name == "ui-ux-designer"
                else validate_srs_draft
            )
            artifact_kind = "UX design" if agent_name == "ui-ux-designer" else "SRS"
            gate_id = "G2" if agent_name == "ui-ux-designer" else "G1"

            validation_errors = validator(content)
            if validation_errors:
                correction_request = (
                    user_request.strip()
                    + "\n\n## Required validation corrections\n"
                    + f"Revise the complete {artifact_kind} draft to fix every issue below. "
                    + "Return only the complete corrected English document, not an "
                    + "explanation. Preserve all required sections and requirement "
                    + "traceability. Do not merely append headings or IDs without "
                    + "writing meaningful, reviewable content.\n"
                    + "\n".join("- " + error for error in validation_errors)
                    + "\n\n## Previous draft to correct\n"
                    + content
                )
                content = (
                    self._cloudflare_generate(
                        agent_name, definition, correction_request
                    )
                    if provider == "cloudflare"
                    else self._cloudflare_generate(
                        agent_name, definition, correction_request, provider
                    )
                )

                if not isinstance(content, str) or not content.strip():
                    raise ValueError(
                        f"Agent returned an empty artifact after the {artifact_kind} correction attempt."
                    )

                validation_errors = validator(content)
                if validation_errors:
                    details = "\n".join("- " + error for error in validation_errors)
                    raise ValueError(
                        f"{artifact_kind} validation failed; artifact was not saved "
                        f"after one correction attempt.\n" + details
                    )

        target.parent.mkdir(parents=True, exist_ok=True)

        # Exclusive creation prevents accidental overwrite.
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content.rstrip() + "\n")

        if provider == "cloudflare":
            gate_id = "G2" if agent_name == "ui-ux-designer" else "G1"
            message = (
                "Draft generated using Cloudflare Workers AI. "
                f"Human review at {gate_id} is still required."
            )
        else:
            message = (
                "Deterministic smoke-test artifact created. "
                "No LLM or external action was executed."
            )

        return AgentRunResult(
            agent_name=agent_name,
            status="draft_created",
            artifact_path=relative,
            message=message,
        )
