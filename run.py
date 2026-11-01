import argparse
import json
import sys
from pathlib import Path

from orchestrator.engine import Orchestrator
from orchestrator.agent_registry import AgentRegistry
from orchestrator.agent_runtime import AgentRuntime

COMMANDS = {
    "start", "list", "show", "approve", "reject",
    "workflow-start", "workflow-show", "transition", "gate-decide",
    "agent-run", "agent-register-existing", "agent-register-bundle",
}


def print_result(data):
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


def build_parser():
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="Agentic workflow orchestrator",
    )
    sub = parser.add_subparsers(dest="command")

    start = sub.add_parser("start", help="Create a legacy review run")
    start.add_argument("request", nargs="+")

    sub.add_parser("list", help="List saved runs")

    show = sub.add_parser("show", help="Show a saved run")
    show.add_argument("run_id")

    approve = sub.add_parser("approve", help="Approve a legacy run")
    approve.add_argument("run_id")
    approve.add_argument("--reason", default="")

    reject = sub.add_parser("reject", help="Reject a legacy run")
    reject.add_argument("run_id")
    reject.add_argument("--reason", required=True)

    ws = sub.add_parser(
        "workflow-start",
        help="Create a new eight-stage workflow run",
    )
    ws.add_argument("request", nargs="+")
    ws.add_argument(
        "--g2-role",
        action="append",
        default=[],
        help="Explicit G2 approver role; may be repeated",
    )
    ws.add_argument(
        "--conditional-approval-satisfies-gate",
        choices=["true", "false"],
        default=None,
        help="Explicitly decide how conditional approval is treated",
    )

    wshow = sub.add_parser("workflow-show", help="Show a workflow run")
    wshow.add_argument("run_id")

    trans = sub.add_parser("transition", help="Move a workflow to a stage")
    trans.add_argument("run_id")
    trans.add_argument("to_stage")

    gd = sub.add_parser("gate-decide", help="Record a human gate decision")
    gd.add_argument("run_id")
    gd.add_argument("gate_id", choices=["G1", "G2", "G3", "G4", "G5", "G6"])
    gd.add_argument(
        "outcome",
        choices=["approved", "rejected", "approved_with_conditions"],
    )
    gd.add_argument("--approver", required=True)
    gd.add_argument("--role", required=True)
    gd.add_argument("--reason", default="")
    gd.add_argument("--condition", action="append", default=[])

    ar = sub.add_parser(
        "agent-run",
        help="Run a registered agent handler for the current supported stage",
    )
    ar.add_argument("run_id")
    ar.add_argument("--agent", default="requirements-analyst")
    ar.add_argument("--output", default="specs/001/spec.md")
    ar.add_argument(
        "--provider",
        choices=["dry-run", "cloudflare", "pollinations"],
        default="dry-run",
        help="Choose dry-run, Cloudflare Workers AI, or Pollinations",
    )
    ar.add_argument(
        "--bundle",
        action="store_true",
        help="Generate the multi-artifact UX/UI bundle (ui-ux-designer only)",
    )

    register = sub.add_parser(
        "agent-register-existing",
        help="Register an existing artifact after a previous registration failure",
    )
    register.add_argument("run_id")
    register.add_argument("--agent", default="requirements-analyst")
    register.add_argument(
        "--artifact",
        required=True,
        help="Existing project-relative artifact path under specs/",
    )
    register.add_argument(
        "--message",
        default="Recovered registration of existing artifact.",
    )

    bundle = sub.add_parser(
        "agent-register-bundle",
        help="Register multiple existing artifacts as one agent execution",
    )
    bundle.add_argument("run_id")
    bundle.add_argument("--agent", default="ui-ux-designer")
    bundle.add_argument(
        "--artifact",
        action="append",
        required=True,
        help="Existing project-relative artifact path; repeat for each file",
    )
    bundle.add_argument(
        "--message",
        default="Registered an existing artifact bundle.",
    )

    return parser


def main():
    argv = sys.argv[1:]
    if argv and argv[0].lower() == "help":
        argv = ["--help"]

    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    try:
        app = Orchestrator()

        if args.command == "start":
            result = app.start(" ".join(args.request))
        elif args.command == "list":
            result = app.list_runs()
        elif args.command == "show":
            result = app.get_run(args.run_id)
        elif args.command == "approve":
            result = app.decide(args.run_id, "approved", args.reason)
        elif args.command == "reject":
            result = app.decide(args.run_id, "rejected", args.reason)
        elif args.command == "workflow-start":
            conditional = (
                None
                if args.conditional_approval_satisfies_gate is None
                else args.conditional_approval_satisfies_gate == "true"
            )
            result = app.start_workflow(
                " ".join(args.request),
                g2_roles=args.g2_role,
                conditional_approval_satisfies_gate=conditional,
            )
        elif args.command == "workflow-show":
            result = app.get_workflow(args.run_id)
        elif args.command == "transition":
            result = app.transition(args.run_id, args.to_stage)
        elif args.command == "gate-decide":
            result = app.decide_gate(
                args.run_id,
                args.gate_id,
                args.outcome,
                args.approver,
                args.role,
                reason=args.reason,
                conditions=args.condition,
            )
        elif args.command == "agent-run":
            run = app.get_workflow(args.run_id)

            if run["status"] != "in_progress":
                raise ValueError(
                    f"Workflow cannot run an agent while status is '{run['status']}'."
                )

            policies = {
                "requirements-analyst": ("requirements", "G1"),
                "ui-ux-designer": ("ux_design", "G2"),
            }
            stage, gate_id = policies.get(
                args.agent, ("requirements", "G1")
            )
            if run["current_stage"] != stage:
                if args.agent == "requirements-analyst":
                    raise ValueError(
                        "This runtime version only supports the requirements stage."
                    )
                raise ValueError(
                    f"Agent '{args.agent}' can only run in stage '{stage}'."
                )
            if run["gate_states"].get(gate_id) != "pending":
                raise ValueError(
                    f"Agent execution is only allowed while {gate_id} is pending."
                )

            agent_request = run["user_request"]
            if args.agent == "ui-ux-designer":
                source_events = [
                    event for event in run.get("events", [])
                    if event.get("type") == "agent_execution_completed"
                    and event.get("agent_name") == "requirements-analyst"
                    and event.get("stage_id") == "requirements"
                    and event.get("artifact_path")
                ]
                if not source_events:
                    raise ValueError(
                        "UX execution requires a registered requirements artifact."
                    )
                source_event = source_events[-1]
                source_rel = source_event["artifact_path"]
                if (
                    not isinstance(source_rel, str)
                    or not source_rel.startswith("specs/")
                    or "\\" in source_rel
                    or ".." in Path(source_rel).parts
                ):
                    raise ValueError(
                        "Registered requirements artifact path is invalid."
                    )
                source_path = (Path.cwd() / source_rel).resolve()
                project_root = Path.cwd().resolve()
                try:
                    source_path.relative_to(project_root)
                except ValueError as exc:
                    raise ValueError(
                        "Requirements artifact must remain inside the project."
                    ) from exc
                if not source_path.is_file():
                    raise FileNotFoundError(
                        "Registered requirements artifact is missing."
                    )
                source_text = source_path.read_text(encoding="utf-8-sig")
                if not source_text.strip():
                    raise ValueError("Registered requirements artifact is empty.")
                agent_request = (
                    run["user_request"]
                    + "\n\n## Approved Requirements Artifact\n"
                    + source_text
                )

            registry = AgentRegistry()
            runtime = AgentRuntime(registry=registry)
            if args.bundle:
                if args.agent != "ui-ux-designer":
                    raise ValueError("--bundle is only supported for ui-ux-designer.")
                if args.provider not in ("cloudflare", "pollinations"):
                    raise ValueError(
                        "--bundle requires --provider cloudflare or pollinations."
                    )

                execution = runtime.run_bundle(
                    agent_name=args.agent,
                    user_request=agent_request,
                    provider=args.provider,
                )
                updated = app.record_agent_execution_bundle(
                    run_id=args.run_id,
                    agent_name=execution.agent_name,
                    artifact_paths=execution.artifact_paths,
                    execution_status=execution.status,
                    message=execution.message,
                )
            else:
                execution = runtime.run(
                    agent_name=args.agent,
                    user_request=agent_request,
                    output_path=args.output,
                    provider=args.provider,
                )
                updated = app.record_agent_execution(
                    run_id=args.run_id,
                    agent_name=execution.agent_name,
                    artifact_path=execution.artifact_path,
                    execution_status=execution.status,
                    message=execution.message,
                )
            result = {
                "run_id": args.run_id,
                "execution": {
                    "agent_name": execution.agent_name,
                    "status": execution.status,
                    "artifact_path": execution.artifact_path,
                    "artifact_paths": list(execution.artifact_paths),
                    "message": execution.message,
                },
                "workflow_status": updated["status"],
                "current_stage": updated["current_stage"],
                "G1": updated["gate_states"]["G1"],
                "G2": updated["gate_states"]["G2"],
            }
        elif args.command == "agent-register-bundle":
            if len(args.artifact) < 2:
                raise ValueError(
                    "An artifact bundle requires at least two --artifact paths."
                )

            updated = app.record_agent_execution_bundle(
                run_id=args.run_id,
                agent_name=args.agent,
                artifact_paths=args.artifact,
                execution_status="draft_created",
                message=args.message,
            )
            result = {
                "run_id": args.run_id,
                "execution": {
                    "agent_name": args.agent,
                    "status": "draft_created",
                    "artifact_path": args.artifact[0],
                    "artifact_paths": args.artifact,
                    "message": args.message,
                    "reused_existing_artifacts": True,
                },
                "workflow_status": updated["status"],
                "current_stage": updated["current_stage"],
                "G1": updated["gate_states"]["G1"],
                "G2": updated["gate_states"]["G2"],
            }
        elif args.command == "agent-register-existing":
            updated = app.record_agent_execution(
                run_id=args.run_id,
                agent_name=args.agent,
                artifact_path=args.artifact,
                execution_status="draft_created",
                message=args.message,
            )
            result = {
                "run_id": args.run_id,
                "execution": {
                    "agent_name": args.agent,
                    "status": "draft_created",
                    "artifact_path": args.artifact,
                    "message": args.message,
                    "reused_existing_artifact": True,
                },
                "workflow_status": updated["status"],
                "current_stage": updated["current_stage"],
                "G1": updated["gate_states"]["G1"],
                "G2": updated["gate_states"]["G2"],
            }
        else:
            parser.print_help()
            return 0

        print_result(result)
        return 0

    except (ValueError, FileNotFoundError, PermissionError, FileExistsError, OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
