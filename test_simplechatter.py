import contextlib
import io
import os
import sys
import unittest
from unittest.mock import patch

import simplechatter


class SimplechatterRichInterfaceTest(unittest.TestCase):
    def test_rich_interface_formats_response_json(self):
        raw_response = '{"choices":[{"message":{"content":"hello"}}],"id":"abc"}'
        stdin = iter(["/interface rich", "hello"])
        stdout = io.StringIO()

        def read_input(prompt=None):
            try:
                return next(stdin)
            except StopIteration:
                raise EOFError

        with patch.object(
            sys,
            "argv",
            [
                "simplechatter.py",
                "--url",
                "https://example.test/chat/completions",
                "--model",
                "test-model",
            ],
        ), patch.dict(os.environ, {"OPENAI_API_KEY": "test-token"}), patch.object(
            simplechatter, "post_json", return_value=(200, raw_response)
        ), patch(
            "builtins.input", side_effect=read_input
        ), contextlib.redirect_stdout(
            stdout
        ):
            self.assertEqual(simplechatter.main(), 0)

        output = stdout.getvalue()
        self.assertIn("Interface set to: rich", output)
        self.assertIn('"choices": [', output)
        self.assertIn('"content": "hello"', output)


if __name__ == "__main__":
    unittest.main()
