import contextlib
import io
import sys
import unittest
from unittest.mock import patch

import run


class UnknownCommandTests(unittest.TestCase):
    def test_unknown_command_is_rejected_without_creating_a_run(self):
        stderr = io.StringIO()

        with patch.object(sys, "argv", ["run.py", "status", "sample-run"]):
            with contextlib.redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as raised:
                    run.main()

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("invalid choice", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
