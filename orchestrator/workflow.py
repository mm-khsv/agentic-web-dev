"""Pure workflow model for agentic-web-dev (Milestone M1).

This module describes the eight workflow stages and six human approval gates
(G1-G6) of ``Agentic-Web-Development.pdf`` and offers pure functions that
answer questions about them.

Guarantees
----------
* Side-effect free: no file, network or process access. The module never
  reads or writes ``workflow/runs/``. Callers pass plain data in and get
  immutable results back.
* Nothing here is wired into ``engine.py`` or ``run.py`` (that is M2).
* No LLM, no sub-agents, no parallel execution.

How the PDF is represented
--------------------------
Page references (``pdf_pages``) are PDF page numbers ("Page N of 156").

* Facts the PDF states directly are stored as data on ``Stage`` / ``Gate``.
* Rules that this module *derives* from the documented gate positions are
  labelled as derived (see ``Stage.explicit_required_gate_ids`` and
  ``DESIGN_DECISIONS``). They are implementation choices awaiting approval.
* Places where the PDF is ambiguous or inconsistent are NOT resolved here.
  They are listed in ``UNRESOLVED_QUESTIONS``. Where behaviour would depend
  on an answer, the function either refuses (``UnresolvedDecisionError``)
  until a ``WorkflowConfig`` states the decision explicitly, or it returns
  the relevant ambiguity IDs in ``unresolved_refs`` so the caller can see
  them.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

# --------------------------------------------------------------------------
# Errors. All subclass ValueError so the existing CLI error handling
# (``except ValueError``) would treat them uniformly in a later milestone.
# --------------------------------------------------------------------------


class WorkflowError(ValueError):
    """Base class for all workflow-model errors."""


class UnknownStageError(WorkflowError):
    """A stage ID is not one of the eight documented stages."""


class UnknownGateError(WorkflowError):
    """A gate ID is not one of G1-G6."""


class UnsupportedLaneError(WorkflowError):
    """A lane is unknown or not supported by this milestone."""


class InvalidGateStateError(WorkflowError):
    """A gate-state mapping contains an unknown gate or invalid value."""


class InvalidDecisionError(WorkflowError):
    """A human decision record is malformed."""


class ApproverRoleError(InvalidDecisionError):
    """The approver's role is not permitted to decide the gate."""


class UnresolvedDecisionError(WorkflowError):
    """Behaviour depends on a PDF ambiguity that has not been decided.

    Supply the decision explicitly through ``WorkflowConfig``.
    """


class InvalidRunRecordError(WorkflowError):
    """A run record cannot be classified (not a JSON object, bad version)."""


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

LANE_FEATURE = "feature"

OUTCOME_APPROVED = "approved"
OUTCOME_APPROVED_WITH_CONDITIONS = "approved_with_conditions"
OUTCOME_REJECTED = "rejected"
# The PDF names exactly these three choices (Lab 4, Page 26).
DECISION_OUTCOMES = (
    OUTCOME_APPROVED,
    OUTCOME_APPROVED_WITH_CONDITIONS,
    OUTCOME_REJECTED,
)
_APPROVAL_OUTCOMES = (OUTCOME_APPROVED, OUTCOME_APPROVED_WITH_CONDITIONS)

GATE_STATE_PENDING = "pending"
GATE_STATE_VALUES = DECISION_OUTCOMES + (GATE_STATE_PENDING,)

# Human approver roles named in the gate table (Page 23-24) and Page 7.
ROLE_PRODUCT_OWNER = "product-owner"
ROLE_TECH_LEAD = "tech-lead"
ROLE_SECURITY_OWNER = "security-owner"
ROLE_DESIGN_LEAD = "design-lead"  # appears only on Page 7 (see A3)

# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Stage:
    """One of the eight workflow stages (Pages 4-5)."""

    id: str
    number: int
    name: str
    # Agent file names follow Appendix A.5 (Pages 147-148).
    lead_roles: tuple
    # Output paths the PDF names explicitly. ``NNN`` is the PDF's literal
    # placeholder for the spec number; it is not resolved here.
    output_paths: tuple
    # Outputs the PDF describes without giving a path (or whose
    # ownership/timing is ambiguous).
    other_outputs: tuple
    # Gates the PDF's table places on this stage (Pages 4-5, 23-24).
    gate_ids: tuple
    pdf_pages: tuple
    # Subset of the start prerequisites the PDF states explicitly. All other
    # start prerequisites are derived from gate positions (decision D2).
    explicit_required_gate_ids: tuple
    explicit_rule_pdf_pages: tuple
    # IDs in UNRESOLVED_QUESTIONS that touch this stage.
    unresolved_refs: tuple


@dataclass(frozen=True)
class ApproverReading:
    """One place where the PDF states who approves a gate."""

    source: str
    roles: tuple
    pdf_pages: tuple


@dataclass(frozen=True)
class Gate:
    """One of the six human approval gates (Pages 23-24)."""

    id: str
    number: int
    name: str
    after_stage_ids: tuple
    # Roles from the gate table (Page 23-24).
    documented_approver_roles: tuple
    # "documented": the PDF is consistent. "disputed": it contradicts itself.
    approver_roles_status: str
    # Other readings found elsewhere in the PDF (only filled when disputed).
    alternate_approver_readings: tuple
    # Prerequisite gates the PDF states explicitly for approving this gate.
    explicit_required_gate_ids: tuple
    explicit_rule_pdf_pages: tuple
    pdf_pages: tuple
    unresolved_refs: tuple


@dataclass(frozen=True)
class Lane:
    """A work lane from Page 9."""

    id: str
    name: str
    stages_run: str  # text from the PDF, not machine-interpreted
    human_involvement: str  # text from the PDF
    supported: bool
    pdf_pages: tuple
    unsupported_reason: str


@dataclass(frozen=True)
class UnresolvedQuestion:
    """A PDF ambiguity/inconsistency preserved as metadata, not resolved."""

    id: str
    title: str
    description: str
    pdf_pages: tuple
    affects_stage_ids: tuple
    affects_gate_ids: tuple
    modeled_as: str  # how M1 treats it
    status: str = "unresolved"


@dataclass(frozen=True)
class DesignDecision:
    """An implementation choice made in M1 that needs human approval."""

    id: str
    title: str
    description: str
    status: str = "awaiting_approval"


@dataclass(frozen=True)
class WorkflowConfig:
    """Explicit human decisions on otherwise-unresolved questions.

    Every field defaults to "not decided". Nothing is assumed.

    approver_roles
        Per-gate override of the roles allowed to decide that gate. Required
        for G2 (A3) before any G2 decision record can be validated.
    conditional_approval_satisfies_gate
        Whether ``approved_with_conditions`` counts as approved for the
        purpose of starting later stages / deciding later gates (A4).
        ``None`` means undecided.
    """

    approver_roles: Mapping[str, Sequence[str]] = field(default_factory=dict)
    conditional_approval_satisfies_gate: Optional[bool] = None


DEFAULT_CONFIG = WorkflowConfig()


@dataclass(frozen=True)
class StageStartCheck:
    stage_id: str
    allowed: bool
    required_gate_ids: tuple
    explicit_required_gate_ids: tuple
    missing_gate_ids: tuple
    unresolved_refs: tuple
    reasons: tuple


@dataclass(frozen=True)
class TransitionCheck:
    from_stage_id: Optional[str]
    to_stage_id: str
    allowed: bool
    missing_gate_ids: tuple
    unresolved_refs: tuple
    reasons: tuple


@dataclass(frozen=True)
class GateDecisionCheck:
    gate_id: str
    outcome: str
    allowed: bool
    required_gate_ids: tuple
    explicit_required_gate_ids: tuple
    missing_gate_ids: tuple
    unresolved_refs: tuple
    reasons: tuple
    notes: tuple


@dataclass(frozen=True)
class DecisionRecord:
    """A validated human decision on one gate."""

    gate_id: str
    outcome: str
    approver: str
    approver_role: str
    reason: str
    conditions: tuple
    decided_at: Optional[str]


@dataclass(frozen=True)
class RunRecordClassification:
    """Result of classifying a run record. Never grants a gate approval."""

    kind: str  # "legacy" or "versioned"
    schema_version: Optional[int]
    legacy_status: Optional[str]
    legacy_current_stage: Optional[str]
    # "legacy_intake_review", "legacy_unmapped" or None (versioned).
    workflow_position: Optional[str]
    mapped_stage_id: Optional[str]  # always None in M1
    gate_approvals: tuple  # always empty in M1
    counts_as_g1_approval: bool  # always False in M1
    interpretation: str
    warnings: tuple


# --------------------------------------------------------------------------
# Stage and gate definitions (PDF order)
# --------------------------------------------------------------------------

STAGES = (
    Stage(
        id="requirements",
        number=1,
        name="Requirements",
        lead_roles=("requirements-analyst",),
        output_paths=("specs/NNN/spec.md",),
        other_outputs=(),
        gate_ids=("G1",),
        pdf_pages=(4, 5, 7, 27, 30),
        explicit_required_gate_ids=(),
        explicit_rule_pdf_pages=(),
        unresolved_refs=("A1", "A10"),
    ),
    Stage(
        id="ux_design",
        number=2,
        name="UX design",
        lead_roles=("ux-designer",),
        output_paths=("docs/ux/", "prototypes/"),
        other_outputs=(
            "design tokens (the PDF's example file is tailwind.config.ts, "
            "Page 7; stack-specific, see A10)",
        ),
        gate_ids=("G2",),
        pdf_pages=(5, 7, 34, 36),
        explicit_required_gate_ids=(),
        explicit_rule_pdf_pages=(),
        unresolved_refs=("A1", "A2", "A3", "A9", "A10"),
    ),
    Stage(
        id="architecture",
        number=3,
        name="Architecture",
        lead_roles=("web-architect",),
        output_paths=(
            "specs/NNN/design.md",
            "api/openapi.yaml",
            "docs/adr/",
        ),
        other_outputs=(
            "docs/security/threat-model.md (listed after stage 3 on Page 7 "
            "but produced by the Security agent on Page 110; ownership "
            "unresolved, see A7)",
        ),
        gate_ids=("G2",),
        pdf_pages=(5, 7, 39, 41),
        explicit_required_gate_ids=(),
        explicit_rule_pdf_pages=(),
        unresolved_refs=("A1", "A2", "A3", "A7", "A10"),
    ),
    Stage(
        id="planning",
        number=4,
        name="Planning",
        lead_roles=("planner",),
        output_paths=("specs/NNN/tasks.md",),
        other_outputs=("cost and time estimate (Page 45)",),
        gate_ids=("G3",),
        pdf_pages=(5, 7, 45, 47),
        explicit_required_gate_ids=(),
        explicit_rule_pdf_pages=(),
        unresolved_refs=("A1",),
    ),
    Stage(
        id="build",
        number=5,
        name="Build",
        lead_roles=(
            "frontend-engineer",
            "api-engineer",
            "database",
            "auth-engineer",
            "integrations",
        ),
        output_paths=(),
        other_outputs=("code and tests in pull requests (Pages 5, 7)",),
        gate_ids=(),  # the PDF lists "PR reviews", not a G-gate (Page 5)
        pdf_pages=(5, 7, 13, 26),
        # "Plan must be approved first" (Page 13); CI refuses code before
        # G3 (Page 26).
        explicit_required_gate_ids=("G3",),
        explicit_rule_pdf_pages=(13, 26),
        unresolved_refs=(),
    ),
    Stage(
        id="verify",
        number=6,
        name="Verify",
        lead_roles=(
            "test-engineer",
            "code-reviewer",
            "security",
            "frontend-performance",
            "styling-a11y",
        ),
        output_paths=("tests/e2e/", "reports/traceability.md"),
        other_outputs=(
            "test and scan reports (Pages 5, 7)",
            "docs/security/threat-model.md updates (Page 110; "
            "ownership unresolved, see A7)",
        ),
        gate_ids=("G4", "G5"),
        pdf_pages=(5, 7, 100, 102, 110, 113),
        explicit_required_gate_ids=(),
        explicit_rule_pdf_pages=(),
        unresolved_refs=("A1", "A7", "A8", "A9"),
    ),
    Stage(
        id="release",
        number=7,
        name="Release",
        lead_roles=("devops",),
        output_paths=("CHANGELOG.md",),
        other_outputs=(
            "pipeline run (Page 5)",
            "release notes (Pages 5, 7)",
            "feature flag config (Page 7)",
        ),
        gate_ids=("G6",),
        pdf_pages=(5, 7, 117, 119, 121, 154),
        explicit_required_gate_ids=(),
        explicit_rule_pdf_pages=(),
        unresolved_refs=("A1", "A6"),
    ),
    Stage(
        id="operate",
        number=8,
        name="Operate",
        lead_roles=("sre", "docs-writer"),
        output_paths=("docs/runbooks/",),
        other_outputs=(
            "dashboards and alert rules (Pages 5, 7)",
            "documentation: README, API reference, help pages "
            "(Page 128; timing unresolved, see A6)",
        ),
        gate_ids=(),  # the PDF lists "Incident reviews", not a G-gate
        pdf_pages=(5, 7, 123, 128),
        explicit_required_gate_ids=(),
        explicit_rule_pdf_pages=(),
        unresolved_refs=("A6", "A9", "A11"),
    ),
)

GATES = (
    Gate(
        id="G1",
        number=1,
        name="Requirements",
        after_stage_ids=("requirements",),
        documented_approver_roles=(ROLE_PRODUCT_OWNER,),
        approver_roles_status="documented",
        alternate_approver_readings=(),
        explicit_required_gate_ids=(),
        explicit_rule_pdf_pages=(),
        pdf_pages=(5, 23, 30),
        unresolved_refs=("A4",),
    ),
    Gate(
        id="G2",
        number=2,
        name="Design",
        after_stage_ids=("ux_design", "architecture"),
        documented_approver_roles=(ROLE_PRODUCT_OWNER, ROLE_TECH_LEAD),
        approver_roles_status="disputed",
        alternate_approver_readings=(
            ApproverReading(
                "Gate table (Page 23): product owner + tech lead",
                (ROLE_PRODUCT_OWNER, ROLE_TECH_LEAD),
                (23,),
            ),
            ApproverReading(
                "'What exists after each stage', stage 2 (Page 7): "
                "product owner, design lead",
                (ROLE_PRODUCT_OWNER, ROLE_DESIGN_LEAD),
                (7,),
            ),
            ApproverReading(
                "'What exists after each stage', stage 3 (Page 7): "
                "tech lead, security owner",
                (ROLE_TECH_LEAD, ROLE_SECURITY_OWNER),
                (7,),
            ),
            ApproverReading(
                "Worked examples (Pages 25, 134): G2 approved by the "
                "tech lead alone",
                (ROLE_TECH_LEAD,),
                (25, 134),
            ),
        ),
        explicit_required_gate_ids=(),
        explicit_rule_pdf_pages=(),
        pdf_pages=(5, 23, 25, 36, 41),
        unresolved_refs=("A1", "A2", "A3", "A4"),
    ),
    Gate(
        id="G3",
        number=3,
        name="Plan",
        after_stage_ids=("planning",),
        documented_approver_roles=(ROLE_TECH_LEAD,),
        approver_roles_status="documented",
        alternate_approver_readings=(),
        explicit_required_gate_ids=(),
        explicit_rule_pdf_pages=(),
        pdf_pages=(5, 13, 23, 26, 47),
        unresolved_refs=("A4",),
    ),
    Gate(
        id="G4",
        number=4,
        name="Feature acceptance",
        after_stage_ids=("verify",),
        documented_approver_roles=(ROLE_PRODUCT_OWNER,),
        approver_roles_status="documented",
        alternate_approver_readings=(),
        explicit_required_gate_ids=(),
        explicit_rule_pdf_pages=(),
        pdf_pages=(5, 23, 102),
        unresolved_refs=("A4", "A8"),
    ),
    Gate(
        id="G5",
        number=5,
        name="Security",
        after_stage_ids=("verify",),
        documented_approver_roles=(ROLE_SECURITY_OWNER,),
        approver_roles_status="documented",
        alternate_approver_readings=(),
        explicit_required_gate_ids=(),
        explicit_rule_pdf_pages=(),
        pdf_pages=(5, 23, 113),
        unresolved_refs=("A4", "A8"),
    ),
    Gate(
        id="G6",
        number=6,
        name="Release",
        after_stage_ids=("release",),
        documented_approver_roles=(ROLE_TECH_LEAD,),
        approver_roles_status="documented",
        alternate_approver_readings=(),
        # "Checklist: before release (G6): G4 and G5 approved" (Page 154).
        explicit_required_gate_ids=("G4", "G5"),
        explicit_rule_pdf_pages=(154,),
        pdf_pages=(5, 24, 119, 121, 154),
        unresolved_refs=("A4", "A6"),
    ),
)

STAGE_IDS = tuple(stage.id for stage in STAGES)
GATE_IDS = tuple(gate.id for gate in GATES)

_STAGE_BY_ID = {stage.id: stage for stage in STAGES}
_GATE_BY_ID = {gate.id: gate for gate in GATES}

# --------------------------------------------------------------------------
# Lanes (Page 9). Only the Feature lane is modelled; the others are listed
# so they can be rejected with a precise reason.
# --------------------------------------------------------------------------

LANES = (
    Lane(
        id="express",
        name="Express",
        stages_run="Build, Verify, Release",
        human_involvement="Auto-merge if all checks pass",
        supported=False,
        pdf_pages=(9, 21),
        unsupported_reason=(
            "Unresolved A5: the PDF does not say whether G4-G6 apply to "
            "lanes that run Verify and Release."
        ),
    ),
    Lane(
        id="standard",
        name="Standard",
        stages_run="Short spec in the issue, Build, Verify, Release",
        human_involvement="One PR approval",
        supported=False,
        pdf_pages=(9,),
        unsupported_reason=(
            "Unresolved A5: the PDF does not say whether G4-G6 apply to "
            "lanes that run Verify and Release."
        ),
    ),
    Lane(
        id=LANE_FEATURE,
        name="Feature",
        stages_run="All eight",
        human_involvement="Gates G1 to G6",
        supported=True,
        pdf_pages=(9,),
        unsupported_reason="",
    ),
    Lane(
        id="critical",
        name="Critical",
        stages_run="All eight, extra review",
        human_involvement="All gates + security owner on every PR",
        supported=False,
        pdf_pages=(9,),
        unsupported_reason=(
            "Unresolved A5: the PDF does not define the 'extra review' "
            "or how the security-owner PR review interacts with gates."
        ),
    ),
)

_LANE_BY_ID = {lane.id: lane for lane in LANES}
LANE_IDS = tuple(lane.id for lane in LANES)

# --------------------------------------------------------------------------
# Unresolved PDF questions, preserved as metadata (IDs match the Phase 1
# audit). Nothing below is decided by this module.
# --------------------------------------------------------------------------

UNRESOLVED_QUESTIONS = (
    UnresolvedQuestion(
        id="A1",
        title="Gate labels vs gate count",
        description=(
            "'Six of the stages also end with a human gate' (Page 4) "
            "matches six gate-labelled stages (1,2,3,4,6,7), but the six "
            "gates are not one-to-one with them: G2 spans stages 2-3 and "
            "G4/G5 share stage 6."
        ),
        pdf_pages=(4, 5, 23),
        affects_stage_ids=(
            "requirements", "ux_design", "architecture", "planning",
            "verify", "release",
        ),
        affects_gate_ids=("G2", "G4", "G5"),
        modeled_as="Informational only; no behaviour depends on it.",
        status="informational",
    ),
    UnresolvedQuestion(
        id="A2",
        title="G2 timing and stage 2/3 ordering",
        description=(
            "'Planning stages run in order' (Page 4) but the example flow "
            "shows UX design and architecture happening together (Page 6, "
            "step 4). G2 is 'after stage 2 and 3' (Page 23) and 'with "
            "stage 3' (Page 5). Whether stage 3 may run concurrently with, "
            "or must wait for, stage 2 is not stated."
        ),
        pdf_pages=(4, 5, 6, 23),
        affects_stage_ids=("ux_design", "architecture"),
        affects_gate_ids=("G2",),
        modeled_as=(
            "check_transition permits ux_design -> architecture as an "
            "adjacent step with no gate in between (D10) and always "
            "reports A2. Concurrent execution is not modelled."
        ),
    ),
    UnresolvedQuestion(
        id="A3",
        title="G2 approvers",
        description=(
            "Page 23 says product owner + tech lead; Page 7 says product "
            "owner/design lead (stage 2) and tech lead/security owner "
            "(stage 3); the worked examples (Pages 25, 134) show the tech "
            "lead alone approving G2. Whether both roles are required, and "
            "who they are, is undecided."
        ),
        pdf_pages=(7, 23, 25, 134),
        affects_stage_ids=("ux_design", "architecture"),
        affects_gate_ids=("G2",),
        modeled_as=(
            "Decision records for G2 are refused (UnresolvedDecisionError) "
            "until WorkflowConfig.approver_roles['G2'] is supplied. "
            "Aggregating several approvers into one gate state is not "
            "modelled."
        ),
    ),
    UnresolvedQuestion(
        id="A4",
        title="Rejection and conditional-approval semantics",
        description=(
            "Lab 4 names 'approve, approve with conditions, reject' "
            "(Page 26) and a sample gates.yaml has a 'conditions' field "
            "(Page 25), but the PDF never says where rejected work goes, "
            "how often it may be retried, how conditions are tracked or "
            "closed, or whether conditional approval unblocks later work."
        ),
        pdf_pages=(25, 26),
        affects_stage_ids=(),
        affects_gate_ids=("G1", "G2", "G3", "G4", "G5", "G6"),
        modeled_as=(
            "All three outcomes are accepted in decision records. A "
            "rejected or pending gate never counts as approved. "
            "approved_with_conditions cannot satisfy a gate until "
            "WorkflowConfig.conditional_approval_satisfies_gate is set. "
            "Rejection routing and retry limits are not modelled; "
            "backward transitions are reported as not allowed."
        ),
    ),
    UnresolvedQuestion(
        id="A5",
        title="Lane behaviour",
        description=(
            "Express and Standard lanes still run Release (Page 9), but "
            "their 'human involvement' is auto-merge / one PR approval; "
            "whether G4-G6 are waived is not stated. Critical's 'extra "
            "review' is undefined."
        ),
        pdf_pages=(9, 10, 21),
        affects_stage_ids=("build", "verify", "release"),
        affects_gate_ids=("G4", "G5", "G6"),
        modeled_as=(
            "Only the Feature lane is supported; every other lane raises "
            "UnsupportedLaneError."
        ),
    ),
    UnresolvedQuestion(
        id="A6",
        title="Documentation timing",
        description=(
            "Documentation is a stage-8 agent (Pages 5-6) yet help pages "
            "are read 'before release' (Page 129) and the G6 checklist "
            "requires 'help page and changelog ready' (Page 154). "
            "CHANGELOG.md is listed under stage 7 (Page 7)."
        ),
        pdf_pages=(5, 6, 7, 129, 154),
        affects_stage_ids=("release", "operate"),
        affects_gate_ids=("G6",),
        modeled_as=(
            "Flagged on the release and operate stages. CHANGELOG.md is "
            "listed as a release output because Page 7 does so; no rule "
            "about when documentation must exist is encoded."
        ),
    ),
    UnresolvedQuestion(
        id="A7",
        title="Threat-model ownership",
        description=(
            "docs/security/threat-model.md is listed as a stage-3 output "
            "(Page 7) but the Security agent produces it during Verify "
            "(Page 110)."
        ),
        pdf_pages=(7, 110),
        affects_stage_ids=("architecture", "verify"),
        affects_gate_ids=("G2", "G5"),
        modeled_as=(
            "Listed under other_outputs of both stages with a note; not a "
            "required artifact of either."
        ),
    ),
    UnresolvedQuestion(
        id="A8",
        title="G4/G5 ordering",
        description=(
            "G4 and G5 both follow stage 6 (Page 23); G4 then G5 is "
            "listed in the example (Page 6) but no order is required. "
            "Both must be approved before G6 (Page 154)."
        ),
        pdf_pages=(6, 23, 154),
        affects_stage_ids=("verify", "release"),
        affects_gate_ids=("G4", "G5", "G6"),
        modeled_as=(
            "Neither gate is a prerequisite of the other; both are "
            "required for G6 and for starting Release."
        ),
    ),
    UnresolvedQuestion(
        id="A9",
        title="Per-stage automated checks",
        description=(
            "Page 4 says each stage ends with an automated check. Checks "
            "are named for stages 1, 3, 4, 5 and 6 (Pages 30, 32, 44, 48, "
            "21, 102) but none was located for stages 2 and 8 in the "
            "pages reviewed."
        ),
        pdf_pages=(4, 30, 32, 44, 48, 102),
        affects_stage_ids=("ux_design", "operate"),
        affects_gate_ids=(),
        modeled_as="Not modelled; validators are a later milestone.",
    ),
    UnresolvedQuestion(
        id="A10",
        title="Stack-specific example paths",
        description=(
            "The PDF is TypeScript/Next.js teaching sketches, 'not "
            "drop-in production code' (Page 156); this repository is "
            "Python. Output paths come from the PDF's examples."
        ),
        pdf_pages=(3, 156),
        affects_stage_ids=("requirements", "ux_design", "architecture"),
        affects_gate_ids=(),
        modeled_as=(
            "output_paths are descriptive. M1 never checks that they "
            "exist on disk. 'NNN' is kept as a literal placeholder."
        ),
    ),
    UnresolvedQuestion(
        id="A11",
        title="Final stage and re-entry",
        description=(
            "Stage 8 has no gate and the PDF poses, but does not answer, "
            "where a production bug fix re-enters the workflow (Page 8, "
            "exercise 4)."
        ),
        pdf_pages=(8,),
        affects_stage_ids=("operate",),
        affects_gate_ids=(),
        modeled_as=(
            "operate is final; check_transition allows nothing out of it."
        ),
    ),
)

_UNRESOLVED_BY_ID = {q.id: q for q in UNRESOLVED_QUESTIONS}

# --------------------------------------------------------------------------
# M1 implementation choices that need human approval.
# --------------------------------------------------------------------------

DESIGN_DECISIONS = (
    DesignDecision(
        "D1", "Feature lane only",
        "Only the Feature lane (all eight stages, G1-G6, Page 9) is "
        "supported; other lanes raise UnsupportedLaneError (A5).",
    ),
    DesignDecision(
        "D2", "Start prerequisites derived from gate positions",
        "A stage may start when every gate positioned before it is "
        "approved. The PDF states explicitly only: Build needs G3 "
        "(Pages 13, 26) and G6 needs G4 and G5 (Page 154). The rest "
        "(e.g. Planning needs G2) is derived from the gate table "
        "(Pages 23-24) and the rule 'never start a stage whose gate is "
        "not approved' (Page 144), whose wording is itself ambiguous.",
    ),
    DesignDecision(
        "D3", "Strictly sequential, adjacent transitions",
        "Only the immediately following stage is a legal transition. "
        "Skipping, repeating and moving backward are reported as not "
        "allowed because the PDF defines no rework routing (A4, A11).",
    ),
    DesignDecision(
        "D4", "Gate state is one aggregated outcome per gate",
        "Callers supply a single outcome per gate. Combining several "
        "approvers' records (needed if G2 requires two people, A3) is "
        "deferred.",
    ),
    DesignDecision(
        "D5", "Only approval outcomes are blocked by missing prerequisites",
        "check_gate_decision_allowed blocks 'approved' and "
        "'approved_with_conditions' when prerequisite gates are not "
        "approved. Recording a 'rejected' decision is not blocked, "
        "because the PDF is silent.",
    ),
    DesignDecision(
        "D6", "Decision-record shape",
        "Required: gate_id, outcome, approver, approver_role. Optional: "
        "reason, conditions, decided_at. Unknown keys are rejected. "
        "reason is required for 'rejected' (as in the existing engine); "
        "conditions are required for 'approved_with_conditions' and "
        "forbidden otherwise. The PDF does not define this shape.",
    ),
    DesignDecision(
        "D7", "Role identifiers",
        "Agent role IDs follow the file names in Appendix A.5 "
        "(Pages 147-148). Human roles are product-owner, tech-lead, "
        "security-owner (and design-lead, which appears only on Page 7).",
    ),
    DesignDecision(
        "D8", "Legacy classification",
        "A record without 'schema_version' is legacy. Legacy records map "
        "to 'legacy_intake_review' (not to any PDF stage), carry no gate "
        "approvals and never count as G1. Records with 'schema_version' "
        "are reported as versioned but not interpreted, because no "
        "versioned schema exists yet.",
    ),
    DesignDecision(
        "D9", "Artifact paths are descriptive",
        "output_paths use the PDF's example paths with 'NNN' unresolved. "
        "M1 does not check the filesystem (A10).",
    ),
    DesignDecision(
        "D10", "Stage 2 -> 3 has no gate in between",
        "Taken literally from the table (G2 follows both stages). "
        "Always reported together with A2.",
    ),
    DesignDecision(
        "D11", "Conditional approval accepted but inert",
        "approved_with_conditions is a valid record outcome but cannot "
        "satisfy a gate until WorkflowConfig decides (A4).",
    ),
    DesignDecision(
        "D12", "Compatibility",
        "Python 3.10+ standard library only; all errors subclass "
        "ValueError.",
    ),
)

# --------------------------------------------------------------------------
# Lookups
# --------------------------------------------------------------------------


def get_stage(stage_id: str) -> Stage:
    if not isinstance(stage_id, str) or stage_id not in _STAGE_BY_ID:
        raise UnknownStageError(
            f"Unknown stage ID: {stage_id!r}. "
            f"Known stages: {', '.join(STAGE_IDS)}."
        )
    return _STAGE_BY_ID[stage_id]


def get_gate(gate_id: str) -> Gate:
    if not isinstance(gate_id, str) or gate_id not in _GATE_BY_ID:
        raise UnknownGateError(
            f"Unknown gate ID: {gate_id!r}. "
            f"Known gates: {', '.join(GATE_IDS)}."
        )
    return _GATE_BY_ID[gate_id]


def get_unresolved_question(question_id: str) -> UnresolvedQuestion:
    if question_id not in _UNRESOLVED_BY_ID:
        raise KeyError(f"Unknown unresolved-question ID: {question_id!r}")
    return _UNRESOLVED_BY_ID[question_id]


def require_supported_lane(lane: str) -> Lane:
    """Return the lane or raise ``UnsupportedLaneError``."""
    if not isinstance(lane, str) or lane not in _LANE_BY_ID:
        raise UnsupportedLaneError(
            f"Unknown workflow lane: {lane!r}. "
            f"Lanes named in the PDF (Page 9): {', '.join(LANE_IDS)}."
        )
    found = _LANE_BY_ID[lane]
    if not found.supported:
        raise UnsupportedLaneError(
            f"Lane {lane!r} is not supported by this milestone. "
            f"{found.unsupported_reason}"
        )
    return found


def next_stage_id(stage_id: str) -> Optional[str]:
    """The stage after ``stage_id`` in PDF order, or None for the last."""
    stage = get_stage(stage_id)
    if stage.number >= len(STAGES):
        return None
    return STAGES[stage.number].id  # numbers are 1-based


def _gate_last_stage_number(gate: Gate) -> int:
    return max(get_stage(s).number for s in gate.after_stage_ids)


def _gate_first_stage_number(gate: Gate) -> int:
    return min(get_stage(s).number for s in gate.after_stage_ids)


def required_gates_for_stage(stage_id: str) -> tuple:
    """Gates that must be approved before ``stage_id`` may start.

    Derived (D2): every gate whose last documented stage precedes this one.
    """
    stage = get_stage(stage_id)
    return tuple(
        gate.id for gate in GATES
        if _gate_last_stage_number(gate) < stage.number
    )


def required_gates_for_gate_decision(gate_id: str) -> tuple:
    """Gates that must be approved before ``gate_id`` may be approved.

    Derived (D2): every gate whose last documented stage precedes this
    gate's first documented stage. G4 and G5 do not precede each other (A8).
    """
    gate = get_gate(gate_id)
    first = _gate_first_stage_number(gate)
    return tuple(
        other.id for other in GATES
        if other.id != gate.id and _gate_last_stage_number(other) < first
    )


# --------------------------------------------------------------------------
# Configuration and gate-state handling
# --------------------------------------------------------------------------


def _resolve_config(config: Optional[WorkflowConfig]) -> WorkflowConfig:
    if config is None:
        return DEFAULT_CONFIG
    if not isinstance(config, WorkflowConfig):
        raise WorkflowError("config must be a WorkflowConfig or None.")
    if not isinstance(config.approver_roles, Mapping):
        raise WorkflowError("config.approver_roles must be a mapping.")
    for gate_id, roles in config.approver_roles.items():
        get_gate(gate_id)
        if (
            isinstance(roles, (str, bytes))
            or not isinstance(roles, Sequence)
            or not roles
            or not all(isinstance(r, str) and r.strip() for r in roles)
        ):
            raise WorkflowError(
                f"config.approver_roles[{gate_id!r}] must be a non-empty "
                "list of role names."
            )
    flag = config.conditional_approval_satisfies_gate
    if flag is not None and not isinstance(flag, bool):
        raise WorkflowError(
            "config.conditional_approval_satisfies_gate must be True, "
            "False or None."
        )
    return config


def _normalize_gate_states(gate_states: Optional[Mapping[str, Any]]) -> dict:
    if gate_states is None:
        return {}
    if not isinstance(gate_states, Mapping):
        raise InvalidGateStateError("gate_states must be a mapping.")
    states = {}
    for gate_id, value in gate_states.items():
        if not isinstance(gate_id, str) or gate_id not in _GATE_BY_ID:
            raise UnknownGateError(
                f"Unknown gate ID in gate_states: {gate_id!r}. "
                f"Known gates: {', '.join(GATE_IDS)}."
            )
        if value is not None and value not in GATE_STATE_VALUES:
            raise InvalidGateStateError(
                f"Invalid state {value!r} for gate {gate_id}. "
                f"Allowed: {', '.join(GATE_STATE_VALUES)} or None."
            )
        states[gate_id] = value
    return states


def _gate_satisfied(
    gate_id: str, state: Optional[str], config: WorkflowConfig
) -> bool:
    if state == OUTCOME_APPROVED:
        return True
    if state == OUTCOME_APPROVED_WITH_CONDITIONS:
        decided = config.conditional_approval_satisfies_gate
        if decided is None:
            raise UnresolvedDecisionError(
                f"Gate {gate_id} is 'approved_with_conditions' but the PDF "
                "does not say whether that unblocks later work (A4). "
                "Set WorkflowConfig.conditional_approval_satisfies_gate "
                "to True or False."
            )
        return decided
    return False  # None, "pending", "rejected"


def allowed_approver_roles(
    gate_id: str, config: Optional[WorkflowConfig] = None
) -> tuple:
    """Roles allowed to decide ``gate_id``.

    An explicit ``config.approver_roles`` entry always wins. Otherwise the
    PDF's roles are used, except for gates whose approvers the PDF
    contradicts (G2, A3), which raise ``UnresolvedDecisionError``.
    """
    gate = get_gate(gate_id)
    cfg = _resolve_config(config)
    if gate_id in cfg.approver_roles:
        return tuple(cfg.approver_roles[gate_id])
    if gate.approver_roles_status == "disputed":
        raise UnresolvedDecisionError(
            f"The PDF is inconsistent about who approves {gate_id} (A3: "
            "Pages 7, 23, 25, 134). Set "
            f"WorkflowConfig.approver_roles[{gate_id!r}] explicitly."
        )
    return gate.documented_approver_roles


# --------------------------------------------------------------------------
# Stage start, transitions, gate-decision permission
# --------------------------------------------------------------------------


def check_stage_start(
    stage_id: str,
    gate_states: Optional[Mapping[str, Any]] = None,
    lane: str = LANE_FEATURE,
    config: Optional[WorkflowConfig] = None,
) -> StageStartCheck:
    """Report whether ``stage_id`` may start given the gate states."""
    require_supported_lane(lane)
    stage = get_stage(stage_id)
    states = _normalize_gate_states(gate_states)
    cfg = _resolve_config(config)

    required = required_gates_for_stage(stage_id)
    missing = tuple(
        g for g in required if not _gate_satisfied(g, states.get(g), cfg)
    )
    reasons = tuple(
        f"Gate {g} ({get_gate(g).name}) is not approved "
        f"(state: {states.get(g) or GATE_STATE_PENDING})."
        for g in missing
    )
    return StageStartCheck(
        stage_id=stage_id,
        allowed=not missing,
        required_gate_ids=required,
        explicit_required_gate_ids=stage.explicit_required_gate_ids,
        missing_gate_ids=missing,
        unresolved_refs=stage.unresolved_refs,
        reasons=reasons,
    )


def can_start_stage(
    stage_id: str,
    gate_states: Optional[Mapping[str, Any]] = None,
    lane: str = LANE_FEATURE,
    config: Optional[WorkflowConfig] = None,
) -> bool:
    return check_stage_start(stage_id, gate_states, lane, config).allowed


def check_transition(
    from_stage_id: Optional[str],
    to_stage_id: str,
    gate_states: Optional[Mapping[str, Any]] = None,
    lane: str = LANE_FEATURE,
    config: Optional[WorkflowConfig] = None,
) -> TransitionCheck:
    """Report whether a run may move from one stage to another.

    ``from_stage_id=None`` means the run has not entered any stage yet.
    Unknown IDs and unsupported lanes raise; an illegal-but-well-formed
    move returns ``allowed=False`` with reasons.
    """
    require_supported_lane(lane)
    if from_stage_id is not None:
        get_stage(from_stage_id)
    get_stage(to_stage_id)

    refs = set()
    reasons = []

    if from_stage_id is None:
        expected = STAGE_IDS[0]
        if to_stage_id != expected:
            reasons.append(
                f"A run must begin at stage {expected!r}, not "
                f"{to_stage_id!r}."
            )
    else:
        expected = next_stage_id(from_stage_id)
        if expected is None:
            reasons.append(
                f"Stage {from_stage_id!r} is the final stage; the PDF does "
                "not define re-entry (A11)."
            )
            refs.add("A11")
        elif to_stage_id != expected:
            reasons.append(
                f"Only the next stage ({expected!r}) may follow "
                f"{from_stage_id!r}; skipping, repeating or moving backward "
                "is not defined by the PDF (A4, A11)."
            )
            refs.update(("A4", "A11"))

    if (from_stage_id, to_stage_id) == ("ux_design", "architecture"):
        refs.add("A2")

    missing: tuple = ()
    if not reasons:
        start = check_stage_start(to_stage_id, gate_states, lane, config)
        missing = start.missing_gate_ids
        reasons.extend(start.reasons)
        refs.update(start.unresolved_refs)

    return TransitionCheck(
        from_stage_id=from_stage_id,
        to_stage_id=to_stage_id,
        allowed=not reasons,
        missing_gate_ids=missing,
        unresolved_refs=tuple(sorted(refs)),
        reasons=tuple(reasons),
    )


def check_gate_decision_allowed(
    gate_id: str,
    outcome: str,
    gate_states: Optional[Mapping[str, Any]] = None,
    lane: str = LANE_FEATURE,
    config: Optional[WorkflowConfig] = None,
) -> GateDecisionCheck:
    """Report whether ``outcome`` may be recorded on ``gate_id`` now.

    Approval outcomes require the prerequisite gates to be approved, so G6
    cannot be approved until both G4 and G5 are (Page 154). A rejection is
    not blocked (D5).
    """
    require_supported_lane(lane)
    gate = get_gate(gate_id)
    if outcome not in DECISION_OUTCOMES:
        raise InvalidDecisionError(
            f"Invalid outcome {outcome!r}. "
            f"Allowed: {', '.join(DECISION_OUTCOMES)}."
        )
    states = _normalize_gate_states(gate_states)
    cfg = _resolve_config(config)

    required = required_gates_for_gate_decision(gate_id)
    notes: tuple = ()
    if outcome in _APPROVAL_OUTCOMES:
        missing = tuple(
            g for g in required
            if not _gate_satisfied(g, states.get(g), cfg)
        )
    else:
        missing = ()
        notes = (
            "A rejection is recorded regardless of prerequisite gates; "
            "the PDF is silent (D5). Rejection routing is unresolved (A4).",
        )
    reasons = tuple(
        f"Cannot approve {gate_id}: gate {g} ({get_gate(g).name}) is not "
        f"approved (state: {states.get(g) or GATE_STATE_PENDING})."
        for g in missing
    )
    return GateDecisionCheck(
        gate_id=gate_id,
        outcome=outcome,
        allowed=not missing,
        required_gate_ids=required,
        explicit_required_gate_ids=gate.explicit_required_gate_ids,
        missing_gate_ids=missing,
        unresolved_refs=gate.unresolved_refs,
        reasons=reasons,
        notes=notes,
    )


# --------------------------------------------------------------------------
# Decision-record validation
# --------------------------------------------------------------------------

_REQUIRED_DECISION_KEYS = ("gate_id", "outcome", "approver", "approver_role")
_OPTIONAL_DECISION_KEYS = ("reason", "conditions", "decided_at")


def _non_empty_str(record: Mapping, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvalidDecisionError(
            f"Decision field {key!r} must be a non-empty string."
        )
    return value.strip()


def _normalize_conditions(value: Any) -> tuple:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, Sequence) and not isinstance(value, bytes):
        items = list(value)
    else:
        raise InvalidDecisionError(
            "Decision field 'conditions' must be a string or a list of "
            "strings."
        )
    cleaned = []
    for item in items:
        if not isinstance(item, str) or not item.strip():
            raise InvalidDecisionError(
                "Every entry of 'conditions' must be a non-empty string."
            )
        cleaned.append(item.strip())
    return tuple(cleaned)


def validate_decision_record(
    record: Mapping[str, Any],
    config: Optional[WorkflowConfig] = None,
) -> DecisionRecord:
    """Validate a human decision record and return it normalised.

    Structure and approver role only. Whether the decision is allowed *now*
    is ``check_gate_decision_allowed``.
    """
    if not isinstance(record, Mapping):
        raise InvalidDecisionError("A decision record must be a mapping.")

    allowed_keys = _REQUIRED_DECISION_KEYS + _OPTIONAL_DECISION_KEYS
    unknown = sorted(str(k) for k in record if k not in allowed_keys)
    if unknown:
        raise InvalidDecisionError(
            f"Unknown decision field(s): {', '.join(unknown)}. "
            f"Allowed: {', '.join(allowed_keys)}."
        )
    missing = [k for k in _REQUIRED_DECISION_KEYS if k not in record]
    if missing:
        raise InvalidDecisionError(
            f"Missing decision field(s): {', '.join(missing)}."
        )

    gate_id = record["gate_id"]
    get_gate(gate_id)  # raises UnknownGateError

    outcome = record["outcome"]
    if outcome not in DECISION_OUTCOMES:
        raise InvalidDecisionError(
            f"Invalid outcome {outcome!r}. "
            f"Allowed: {', '.join(DECISION_OUTCOMES)}."
        )

    approver = _non_empty_str(record, "approver")
    role = _non_empty_str(record, "approver_role")

    permitted = allowed_approver_roles(gate_id, config)
    if role not in permitted:
        raise ApproverRoleError(
            f"Role {role!r} may not decide gate {gate_id}. "
            f"Permitted: {', '.join(permitted)}."
        )

    reason = record.get("reason", "")
    if reason is None:
        reason = ""
    if not isinstance(reason, str):
        raise InvalidDecisionError("Decision field 'reason' must be a string.")
    reason = reason.strip()
    if outcome == OUTCOME_REJECTED and not reason:
        raise InvalidDecisionError(
            "A reason is required when rejecting a gate."
        )

    raw_conditions = record.get("conditions")
    if outcome == OUTCOME_APPROVED_WITH_CONDITIONS:
        if raw_conditions is None:
            raise InvalidDecisionError(
                "'conditions' is required for approved_with_conditions."
            )
        conditions = _normalize_conditions(raw_conditions)
        if not conditions:
            raise InvalidDecisionError(
                "'conditions' must contain at least one entry."
            )
    else:
        if raw_conditions not in (None, "", [], ()):
            raise InvalidDecisionError(
                "'conditions' is only valid with approved_with_conditions."
            )
        conditions = ()

    decided_at = record.get("decided_at")
    if decided_at is not None:
        if not isinstance(decided_at, str):
            raise InvalidDecisionError(
                "'decided_at' must be an ISO-8601 string."
            )
        try:
            datetime.fromisoformat(decided_at)
        except ValueError as exc:
            raise InvalidDecisionError(
                f"'decided_at' is not a valid ISO-8601 value: "
                f"{decided_at!r}."
            ) from exc

    return DecisionRecord(
        gate_id=gate_id,
        outcome=outcome,
        approver=approver,
        approver_role=role,
        reason=reason,
        conditions=conditions,
        decided_at=decided_at,
    )


# --------------------------------------------------------------------------
# Read-only run-record classification
# --------------------------------------------------------------------------

_LEGACY_INTERPRETATION = (
    "Legacy run record (no 'schema_version'). Its status and decision were "
    "written by the pre-workflow engine at creation time, before any spec "
    "artifact existed, so they are not a gate approval. It is never "
    "treated as G1 approval."
)
_VERSIONED_INTERPRETATION = (
    "Versioned run record. Milestone M1 defines no versioned run schema, "
    "so nothing is interpreted and no gate approval is inferred."
)


def classify_run_record(record: Mapping[str, Any]) -> RunRecordClassification:
    """Classify an already-parsed run record. Pure and read-only."""
    if not isinstance(record, Mapping):
        raise InvalidRunRecordError("A run record must be a JSON object.")

    if "schema_version" in record:
        version = record["schema_version"]
        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version < 1
        ):
            raise InvalidRunRecordError(
                "'schema_version' must be a positive integer, got "
                f"{version!r}."
            )
        return RunRecordClassification(
            kind="versioned",
            schema_version=version,
            legacy_status=None,
            legacy_current_stage=None,
            workflow_position=None,
            mapped_stage_id=None,
            gate_approvals=(),
            counts_as_g1_approval=False,
            interpretation=_VERSIONED_INTERPRETATION,
            warnings=(),
        )

    status = record.get("status")
    current_stage = record.get("current_stage")
    warnings = tuple(
        f"Missing expected legacy field {key!r}."
        for key in ("run_id", "status", "current_stage")
        if key not in record
    )
    position = (
        "legacy_intake_review"
        if current_stage == "intake"
        else "legacy_unmapped"
    )
    return RunRecordClassification(
        kind="legacy",
        schema_version=None,
        legacy_status=status if isinstance(status, str) else None,
        legacy_current_stage=(
            current_stage if isinstance(current_stage, str) else None
        ),
        workflow_position=position,
        mapped_stage_id=None,
        gate_approvals=(),
        counts_as_g1_approval=False,
        interpretation=_LEGACY_INTERPRETATION,
        warnings=warnings,
    )


def classify_run_json(data: "str | bytes") -> RunRecordClassification:
    """Classify run-record JSON given as text or bytes (no file access).

    Bytes are decoded as ``utf-8-sig`` so BOM-prefixed files, which the
    existing engine also tolerates, are accepted.
    """
    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidRunRecordError(
                "Run record is not valid UTF-8."
            ) from exc
    elif isinstance(data, str):
        text = data.lstrip("\ufeff")
    else:
        raise InvalidRunRecordError("Run record data must be str or bytes.")
    try:
        record = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidRunRecordError(
            f"Run record is not valid JSON: {exc}"
        ) from exc
    return classify_run_record(record)
