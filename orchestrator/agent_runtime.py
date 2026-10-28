"""Controlled, provider-independent agent execution runtime."""

from dataclasses import dataclass
from pathlib import Path

from orchestrator.agent_registry import AgentRegistry, AgentDefinition


@dataclass(frozen=True)
class AgentRunResult:
    agent_name: str
    status: str
    artifact_path: str
    message: str


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
    """Execute registered handlers under explicit file-write constraints.

    Agent Markdown is treated as configuration, never as executable code.
    No shell commands, tools, network requests, or LLM calls are performed.
    """

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
            }
        else:
            self.handlers = dict(handlers)

    def run(self, agent_name: str, user_request: str, output_path: str) -> AgentRunResult:
        if not isinstance(user_request, str) or not user_request.strip():
            raise ValueError("The user request cannot be empty.")

        definition = self.registry.get(agent_name)
        handler = self.handlers.get(agent_name)
        if handler is None:
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

        content = handler(definition, user_request.strip())
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Agent handler returned an empty or invalid artifact.")

        target.parent.mkdir(parents=True, exist_ok=True)

        # Exclusive creation prevents accidental overwrite.
        with target.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)

        return AgentRunResult(
            agent_name=agent_name,
            status="draft_created",
            artifact_path=relative,
            message=(
                "Deterministic smoke-test artifact created. "
                "No LLM or external action was executed."
            ),
        )