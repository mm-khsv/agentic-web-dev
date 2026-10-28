# Specification 000: Initial Agentic System

Status: Draft

This specification will define the requirements for the orchestration system
itself. It must be reviewed before implementation decisions are treated as final.

Initial scope:
- Local Python orchestration
- Separate agent and skill definitions
- Persistent workflow state
- Human approval gates
- Replaceable LLM provider
- Sequential execution initially

Out of scope for the first milestone:
- Autonomous deployment
- Real external messaging
- Unrestricted shell or filesystem access
- Parallel agent execution
