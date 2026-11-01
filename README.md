# Agentic Web Development

A Python-based agent orchestration framework for managing structured development workflows, executing registered agents, validating artifacts, and enforcing human approval gates.

## Features

- Eight-stage development workflow.
- Six human approval gates (G1-G6).
- Persistent workflow state and saved run artifacts.
- Agent registry with role definitions, skills, and writable-path restrictions.
- Controlled agent execution and artifact validation.
- LLM provider support for Cloudflare Workers AI and Pollinations.
- Dry-run execution mode.
- Requirements specification generation.
- UX/UI design package generation.
- Registration of existing artifacts and multi-artifact bundles.
- Command-line interface and automated tests.

## Registered Agents

### Requirements Analyst

**Agent ID:** `requirements-analyst`

Transforms feature requests into structured requirements specifications.

Expected deliverables:

- Problem statement and scope
- User stories
- Functional requirements
- Non-functional requirements
- Acceptance criteria
- Assumptions and open questions
- Privacy and security considerations

Output directory: `specs/`

The specification requires human review at G1.

### UI/UX Designer

**Agent ID:** `ui-ux-designer`

Transforms approved requirements into a reviewable UX/UI design package.

Expected deliverables:

- UX specification
- User flows
- Screen and state inventory
- UI copy
- Design tokens
- Accessibility review
- Self-contained HTML prototype

Output directory: `docs/ux/`

The design package requires human review at G2.

## Requirements

- Python 3.11 or newer
- Git
- pytest for running tests

The core application uses Python's standard library.

## Installation

Clone the repository:

    git clone https://github.com/mm-khsv/agentic-web-dev.git
    cd agentic-web-dev

Create a virtual environment.

**Windows PowerShell:**

    py -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt

**Git Bash:**

    python -m venv .venv
    source .venv/Scripts/activate
    python -m pip install -r requirements.txt

## Configuration

The project supports the following execution providers:

- `dry-run`
- `cloudflare`
- `pollinations`

For Cloudflare Workers AI or Pollinations, create a `.env` file in the repository root and configure the credentials for the provider you intend to use.

Example configuration:

    CLOUDFLARE_ACCOUNT_ID=your_account_id
    CLOUDFLARE_API_TOKEN=your_api_token
    CLOUDFLARE_MODEL=your_model

    POLLINATIONS_API_KEY=your_api_key

Keep `.env` private. Never commit API keys, tokens, or other credentials.

The `dry-run` provider does not require API credentials.

## CLI Usage

Display available commands:

    python run.py --help

### Create a workflow

    python run.py workflow-start "Build a small web application"

Save the workflow run ID printed by the command.

### Inspect a workflow

    python run.py workflow-show RUN_ID

Replace `RUN_ID` with the actual workflow ID.

### Run the Requirements Analyst

Using Pollinations:

    python run.py agent-run RUN_ID --agent requirements-analyst --provider pollinations

Using Cloudflare Workers AI:

    python run.py agent-run RUN_ID --agent requirements-analyst --provider cloudflare

### Run the UI/UX Designer

    python run.py agent-run RUN_ID --agent ui-ux-designer --provider pollinations --bundle

Replace `pollinations` with `cloudflare` when using Cloudflare Workers AI.

### Record a human approval decision

Example:

    python run.py gate-decide RUN_ID G1 approved --approver "Project Owner" --role product-owner --reason "Requirements reviewed"

Supported outcomes:

- `approved`
- `rejected`
- `approved_with_conditions`

Approval decisions must be made by authorized human reviewers. Agents cannot approve their own work.

### Register an existing artifact

    python run.py agent-register-existing RUN_ID --agent requirements-analyst --artifact specs/001/example.md

### Register multiple existing artifacts

    python run.py agent-register-bundle RUN_ID --agent ui-ux-designer --artifact docs/ux/ux-specification.md --artifact docs/ux/user-flows.md

For command-specific options:

    python run.py COMMAND --help

## Running Tests

Using pytest:

    python -m pytest -q

Alternatively, using unittest:

    python -m unittest discover -s tests -q

## Project Structure

    .agents/
        agents/          # Agent definitions
        skills/          # Reusable agent skills
        ownership.yaml   # Artifact ownership rules

    llm/
        client.py        # LLM provider clients

    orchestrator/
        engine.py        # Workflow and artifact validation
        workflow.py      # Workflow management
        agent_runtime.py # Agent execution runtime

    docs/
        ux/              # UX/UI design artifacts and prototypes

    specs/
        001/             # Example product specifications

    tests/               # Automated tests and fixtures

    run.py               # CLI entry point
    AGENTS.md             # Project-level agent instructions
    requirements.txt     # Python dependencies

## Design Principles

- **Human approval:** Workflow gates require explicit human decisions.
- **Controlled execution:** Agents operate within their assigned writable paths.
- **Artifact traceability:** Generated artifacts are validated and registered.
- **Separation of responsibilities:** The orchestrator coordinates; agents perform assigned tasks.
- **Provider independence:** LLM integrations are separated from orchestration logic.
- **Security:** Credentials and local runtime state are excluded from version control.

## Development Status

This repository is an evolving demonstration of agentic web development.

The current implementation includes workflow orchestration, registered requirements and UX agents, LLM provider integrations, artifact registration, validation, and human approval mechanisms.

The eight-stage workflow and six approval gates define the intended development process. Not every stage or production implementation is necessarily complete.

The included Smelly Cat example contains requirements and UX design artifacts. Its HTML prototype is a design prototype, not a production application.

## License

No license has been specified yet.