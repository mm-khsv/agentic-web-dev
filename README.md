# Agentic Web Development

A model-independent, Python-based agent orchestration system for controlled workflow execution, agent registration, artifact validation, and human approval.

## Current Capabilities

- Eight-stage workflow model.
- Six defined human approval gates (G1-G6).
- Persistent workflow state and saved run artifacts.
- Agent registry with role definitions and write permissions.
- Controlled agent execution with artifact path validation.
- CLI commands for workflow management and agent execution.
- Automated tests using pytest.

## Current Limitations

- The initial orchestration workflow does not require an LLM provider.
- The Requirements Analyst is not yet a complete LLM-powered agent.
- Not every approval gate necessarily has complete end-to-end behavior implemented.

## Requirements

- Python 3.11 or newer.
- Git.
- pytest to run the test suite.

The core application currently uses Python's standard library.

## Setup

Clone the repository:

    git clone https://github.com/mm-khsv/agentic-web-dev.git
    cd agentic-web-dev

Create and activate a virtual environment.

Windows PowerShell:

    py -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt

Git Bash:

    python -m venv .venv
    source .venv/Scripts/activate
    python -m pip install -r requirements.txt

## Run the CLI

Display available commands:

    python run.py --help

Create a workflow run:

    python run.py workflow-start "My first workflow"

Use the run ID printed by that command to inspect the workflow:

    python run.py workflow-show RUN_ID

Replace RUN_ID with the actual ID returned by the previous command.

## Run Tests

    python -m pytest -q

## Project Layout

- `.agents/` — agent definitions, skills, and policies
- `llm/` — LLM client boundary
- `orchestrator/` — workflow engine, registry, and runtime
- `specs/` — project specifications and artifacts
- `tests/` — automated tests and fixtures
- `run.py` — command-line entry point

## Development Status

This repository is evolving. The current milestone focuses on the orchestration foundation, controlled execution, artifact validation, and automated tests. Full LLM integration and broader end-to-end workflow behavior remain future work.