"""Persistent legacy runs and model-independent workflow runs."""

from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import UUID, uuid4
import json
import os

from orchestrator import workflow as wf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = PROJECT_ROOT / "workflow" / "runs"

AGENT_REGISTRY = {
    "requirements-analyst": ".agents/agents/requirements-analyst.md",
}

PENDING = "awaiting_human_review"
APPROVED = "approved"
REJECTED = "rejected"


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def validate_run_id(run_id: str) -> str:
    try:
        return str(UUID(run_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid run ID.") from exc


class Orchestrator:
    """Persist legacy runs and explicitly versioned workflow runs."""

    def __init__(self):
        RUNS_DIR.mkdir(parents=True, exist_ok=True)

    def _path_for(self, run_id: str) -> Path:
        return RUNS_DIR / f"{validate_run_id(run_id)}.json"

    def _read(self, run_id: str) -> dict:
        path = self._path_for(run_id)
        if not path.is_file():
            raise FileNotFoundError(f"Run not found: {run_id}")
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict):
            raise ValueError("Run record must be a JSON object.")
        return data

    def _save(self, run: dict) -> None:
        path = self._path_for(run["run_id"])
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(run, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, path)

    # Legacy API: intentionally preserved.
    def start(self, user_request: str) -> dict:
        request = user_request.strip()
        if not request:
            raise ValueError("The user request cannot be empty.")

        agent = "requirements-analyst"
        definition = PROJECT_ROOT / AGENT_REGISTRY[agent]
        if not definition.is_file():
            raise FileNotFoundError(f"Agent definition not found: {definition}")

        now = utc_now()
        run = {
            "run_id": str(uuid4()),
            "user_request": request,
            "status": PENDING,
            "current_stage": "intake",
            "assigned_agent": agent,
            "created_at": now,
            "updated_at": now,
            "decision": None,
            "events": [
                {
                    "type": "run_created",
                    "timestamp": now,
                    "message": "Request received and validated.",
                },
                {
                    "type": "agent_assigned",
                    "timestamp": now,
                    "agent": agent,
                    "message": (
                        "Assigned for planning only. "
                        "No LLM or external action was executed."
                    ),
                },
                {
                    "type": "human_gate",
                    "timestamp": now,
                    "message": "Human review is required before proceeding.",
                },
            ],
        }
        self._save(run)
        return run

    def decide(self, run_id: str, decision: str, reason: str = "") -> dict:
        run = self._read(run_id)
        if "schema_version" in run:
            raise ValueError(
                "This is a workflow run. Use the gate-decide command instead."
            )
        if decision not in (APPROVED, REJECTED):
            raise ValueError("Decision must be 'approved' or 'rejected'.")
        if run["status"] != PENDING:
            raise ValueError(
                f"Cannot decide this run: current status is '{run['status']}'."
            )

        reason = reason.strip()
        if decision == REJECTED and not reason:
            raise ValueError("A reason is required when rejecting a run.")

        now = utc_now()
        run["status"] = decision
        run["updated_at"] = now
        run["decision"] = {
            "outcome": decision,
            "reason": reason,
            "timestamp": now,
        }
        run["events"].append({
            "type": "human_decision",
            "timestamp": now,
            "outcome": decision,
            "reason": reason,
        })
        self._save(run)
        return run

    def _workflow_config(self, run: dict) -> wf.WorkflowConfig:
        raw = run["workflow_config"]
        return wf.WorkflowConfig(
            approver_roles=raw.get("approver_roles", {}),
            conditional_approval_satisfies_gate=raw.get(
                "conditional_approval_satisfies_gate"
            ),
        )

    def _require_workflow(self, run_id: str) -> dict:
        run = self._read(run_id)
        if run.get("schema_version") != 1 or "gate_states" not in run:
            raise ValueError(
                "This is not a version-1 workflow run. "
                "Legacy runs cannot be used as workflow runs."
            )
        return run

    def start_workflow(
        self,
        user_request: str,
        g2_roles=None,
        conditional_approval_satisfies_gate=None,
    ) -> dict:
        request = user_request.strip()
        if not request:
            raise ValueError("The user request cannot be empty.")

        if conditional_approval_satisfies_gate not in (None, True, False):
            raise ValueError(
                "Conditional approval setting must be true, false, or undecided."
            )

        roles = list(g2_roles or [])
        role_config = {"G2": roles} if roles else {}
        config = wf.WorkflowConfig(
            approver_roles=role_config,
            conditional_approval_satisfies_gate=(
                conditional_approval_satisfies_gate
            ),
        )

        start_check = wf.check_stage_start(
            "requirements",
            gate_states={gate.id: "pending" for gate in wf.GATES},
            lane="feature",
            config=config,
        )
        if not start_check.allowed:
            raise ValueError(
                "Cannot start requirements stage: "
                + "; ".join(start_check.reasons)
            )

        now = utc_now()
        run_id = str(uuid4())
        run = {
            "schema_version": 1,
            "run_id": run_id,
            "user_request": request,
            "workflow_lane": "feature",
            "status": "in_progress",
            "current_stage": "requirements",
            "created_at": now,
            "updated_at": now,
            "workflow_config": {
                "approver_roles": role_config,
                "conditional_approval_satisfies_gate": (
                    conditional_approval_satisfies_gate
                ),
            },
            "gate_states": {
                gate.id: "pending" for gate in wf.GATES
            },
            "gate_decisions": {},
            "events": [
                {
                    "type": "workflow_created",
                    "timestamp": now,
                    "message": "Version-1 workflow created; no agent was executed.",
                },
                {
                    "type": "stage_entered",
                    "timestamp": now,
                    "stage_id": "requirements",
                },
                {
                    "type": "human_gate_required",
                    "timestamp": now,
                    "gate_id": "G1",
                },
            ],
        }
        self._save(run)
        return run

    def get_workflow(self, run_id: str) -> dict:
        return self._require_workflow(run_id)

    def transition(self, run_id: str, to_stage_id: str) -> dict:
        run = self._require_workflow(run_id)
        if run["status"] != "in_progress":
            raise ValueError(
                f"Workflow cannot transition while status is '{run['status']}'."
            )

        config = self._workflow_config(run)
        result = wf.check_transition(
            from_stage_id=run["current_stage"],
            to_stage_id=to_stage_id,
            gate_states=run["gate_states"],
            lane=run["workflow_lane"],
            config=config,
        )
        if not result.allowed:
            reasons = list(result.reasons) + [
                f"Missing gates: {', '.join(result.missing_gate_ids)}"
            ]
            raise ValueError("Transition blocked: " + "; ".join(reasons))

        now = utc_now()
        run["current_stage"] = to_stage_id
        run["updated_at"] = now
        run["events"].append({
            "type": "stage_transition",
            "timestamp": now,
            "from_stage": result.from_stage_id,
            "to_stage": to_stage_id,
        })

        # Announce gates associated with the stage being entered.
        stage = wf.get_stage(to_stage_id)
        gate_id = getattr(stage, "gate_id", None)
        if gate_id and gate_id in run["gate_states"]:
            run["events"].append({
                "type": "human_gate_required",
                "timestamp": now,
                "gate_id": gate_id,
            })

        self._save(run)
        return run

    def decide_gate(
        self,
        run_id: str,
        gate_id: str,
        outcome: str,
        approver: str,
        approver_role: str,
        reason: str = "",
        conditions=None,
    ) -> dict:
        run = self._require_workflow(run_id)
        if run["status"] != "in_progress":
            raise ValueError(
                f"Workflow cannot accept a gate decision while status is "
                f"'{run['status']}'."
            )
        if gate_id not in {gate.id for gate in wf.GATES}:
            raise ValueError(f"Unknown gate: {gate_id}")
        if gate_id in run["gate_decisions"]:
            raise ValueError(f"Gate {gate_id} already has a recorded decision.")

        config = self._workflow_config(run)
        now = utc_now()
        record = {
            "gate_id": gate_id,
            "outcome": outcome,
            "approver": approver,
            "approver_role": approver_role,
            "reason": reason,
            "conditions": list(conditions or []),
            "decided_at": now,
        }

        validated = wf.validate_decision_record(record, config=config)
        permission = wf.check_gate_decision_allowed(
            gate_id=gate_id,
            outcome=validated.outcome,
            gate_states=run["gate_states"],
            lane=run["workflow_lane"],
            config=config,
        )
        if not permission.allowed:
            raise ValueError(
                "Gate decision blocked: "
                + "; ".join(permission.reasons)
                + (
                    "; Missing gates: "
                    + ", ".join(permission.missing_gate_ids)
                    if permission.missing_gate_ids else ""
                )
            )

        run["gate_decisions"][gate_id] = {
            "gate_id": validated.gate_id,
            "outcome": validated.outcome,
            "approver": validated.approver,
            "approver_role": validated.approver_role,
            "reason": validated.reason,
            "conditions": list(validated.conditions),
            "decided_at": validated.decided_at,
        }
        run["gate_states"][gate_id] = validated.outcome
        run["updated_at"] = now
        run["events"].append({
            "type": "gate_decision",
            "timestamp": now,
            "gate_id": gate_id,
            "outcome": validated.outcome,
            "approver": validated.approver,
            "approver_role": validated.approver_role,
        })

        if validated.outcome == "rejected":
            run["status"] = "blocked_by_gate_rejection"
        self._save(run)
        return run

    def record_agent_execution(
        self,
        run_id: str,
        agent_name: str,
        artifact_path: str,
        execution_status: str,
        message: str,
    ) -> dict:
        """Record a validated agent execution without approving human gates."""
        run = self._require_workflow(run_id)

        if run["status"] != "in_progress":
            raise ValueError(
                f"Workflow cannot run an agent while status is '{run['status']}'."
            )
        if run["current_stage"] != "requirements":
            raise ValueError(
                "This runtime version only supports the requirements stage."
            )
        if run["gate_states"].get("G1") != "pending":
            raise ValueError(
                "Requirements execution is only allowed while G1 is pending."
            )
        if agent_name != "requirements-analyst":
            raise ValueError(
                "This runtime version only supports requirements-analyst."
            )

        if execution_status != "draft_created":
            raise ValueError(
                "Unsupported execution status; expected 'draft_created'."
            )

        if not isinstance(message, str) or not message.strip():
            raise ValueError("Execution message must be a non-empty string.")

        if (
            not isinstance(artifact_path, str)
            or not artifact_path
            or artifact_path != artifact_path.strip()
            or "\\" in artifact_path
            or "\x00" in artifact_path
        ):
            raise ValueError(
                "Artifact path must be a normalized relative path inside specs/."
            )

        posix_path = PurePosixPath(artifact_path)
        windows_path = PureWindowsPath(artifact_path)
        path_parts = artifact_path.split("/")

        if (
            posix_path.is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.drive)
            or len(path_parts) < 2
            or path_parts[0] != "specs"
            or any(part in ("", ".", "..") for part in path_parts)
            or posix_path.as_posix() != artifact_path
        ):
            raise ValueError(
                "Artifact path must be a normalized relative path inside specs/."
            )

        project_root = PROJECT_ROOT.resolve()
        target = (project_root / posix_path).resolve()

        try:
            resolved_relative = target.relative_to(project_root).as_posix()
        except ValueError as exc:
            raise ValueError(
                "Artifact must resolve inside the project root."
            ) from exc

        resolved_parts = PurePosixPath(resolved_relative).parts
        if (
            len(resolved_parts) < 2
            or resolved_parts[0] != "specs"
            or not target.is_file()
        ):
            raise FileNotFoundError(
                "Artifact must be an existing file inside the specs/ directory."
            )

        now = utc_now()
        run["updated_at"] = now
        run["events"].append({
            "type": "agent_execution_completed",
            "timestamp": now,
            "stage_id": run["current_stage"],
            "agent_name": agent_name,
            "execution_status": execution_status,
            "artifact_path": artifact_path,
            "message": message.strip(),
        })
        self._save(run)
        return run

    def get_run(self, run_id: str) -> dict:
        return self._read(run_id)

    def list_runs(self) -> list:
        records = []
        for path in sorted(RUNS_DIR.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8-sig"))
                if isinstance(record, dict):
                    records.append(record)
            except (OSError, json.JSONDecodeError):
                continue
        return records