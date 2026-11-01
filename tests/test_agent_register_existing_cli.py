import unittest

from run import build_parser


class AgentRegisterExistingCliTests(unittest.TestCase):
    def test_register_existing_requires_artifact_path(self):
        parser = build_parser()
        with self.assertRaises(SystemExit) as raised:
            parser.parse_args(["agent-register-existing", "sample-run"])
        self.assertEqual(raised.exception.code, 2)

    def test_register_existing_parses_explicit_artifact_and_agent(self):
        args = build_parser().parse_args([
            "agent-register-existing",
            "sample-run",
            "--agent", "requirements-analyst",
            "--artifact", "specs/001/spec.md",
            "--message", "Recovered after a save failure.",
        ])
        self.assertEqual(args.command, "agent-register-existing")
        self.assertEqual(args.run_id, "sample-run")
        self.assertEqual(args.agent, "requirements-analyst")
        self.assertEqual(args.artifact, "specs/001/spec.md")
        self.assertEqual(args.message, "Recovered after a save failure.")


if __name__ == "__main__":
    unittest.main()
