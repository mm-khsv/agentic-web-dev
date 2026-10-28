import tempfile
import unittest
from pathlib import Path

from orchestrator.agent_registry import AgentRegistry, _parse_front_matter


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class AgentRegistryTests(unittest.TestCase):
    def test_loads_requirements_analyst(self):
        registry = AgentRegistry(PROJECT_ROOT)
        agent = registry.get("requirements-analyst")

        self.assertEqual(agent.name, "requirements-analyst")
        self.assertIn("specs/**", agent.writable_paths)
        self.assertIn("write-requirements", agent.skills)

    def test_lists_existing_agent_definitions(self):
        agents = AgentRegistry(PROJECT_ROOT).list_agents()
        names = {agent.name for agent in agents}

        self.assertIn("orchestrator", names)
        self.assertIn("requirements-analyst", names)

    def test_rejects_unknown_agent(self):
        with self.assertRaisesRegex(ValueError, "Unknown agent"):
            AgentRegistry(PROJECT_ROOT).get("not-a-real-agent")

    def test_parses_multiline_description_and_lists(self):
        data = _parse_front_matter(
            "---\n"
            "name: example\n"
            "description: First line,\n"
            "  continued line.\n"
            "tools: []\n"
            "writable_paths:\n"
            "  - specs/**\n"
            "---\n"
        )
        self.assertEqual(data["description"], "First line, continued line.")
        self.assertEqual(data["writable_paths"], ["specs/**"])

    def test_rejects_invalid_front_matter(self):
        with self.assertRaises(ValueError):
            _parse_front_matter("# No front matter")


if __name__ == "__main__":
    unittest.main()