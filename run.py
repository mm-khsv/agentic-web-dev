import argparse
import json
import sys

from orchestrator.engine import Orchestrator
from orchestrator.agent_registry import AgentRegistry
from orchestrator.agent_runtime import AgentRuntime

COMMANDS = {
    "start", "list", "show", "approve", "reject",
    "workflow-start", "workflow-show", "transition", "gate-decide",
    "agent-run",
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

    return parser


def main():
    argv = sys.argv[1:]
    if argv and argv[0].lower() == "help":
        argv = ["--help"]
    elif argv and argv[0] not in COMMANDS and not argv[0].startswith("-"):
        argv = ["start", *argv]

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
            if run["current_stage"] != "requirements":
                raise ValueError(
                    "This runtime version only supports the requirements stage."
                )
            if run["gate_states"].get("G1") != "pending":
                raise ValueError(
                    "Requirements execution is only allowed while G1 is pending."
                )

            registry = AgentRegistry()
            runtime = AgentRuntime(registry=registry)
            execution = runtime.run(
                agent_name=args.agent,
                user_request=run["user_request"],
                output_path=args.output,
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
                    "message": execution.message,
                },
                "workflow_status": updated["status"],
                "current_stage": updated["current_stage"],
                "G1": updated["gate_states"]["G1"],
            }
        else:
            parser.print_help()
            return 0

        print_result(result)
        return 0

    except (ValueError, FileNotFoundError, PermissionError, FileExistsError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())