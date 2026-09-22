import io
import json
import unittest

from _load import load

engine = load()


def call(args, stdin_text=""):
    """Run the engine as the panel does: argv in, one JSON document out."""
    out = io.StringIO()
    code = engine.main(args, environ={"HOME": "/nonexistent"}, run=None,
                       stdin=io.StringIO(stdin_text), stdout=out)
    return code, json.loads(out.getvalue())


class EngineTest(unittest.TestCase):
    def test_version_reports_the_manifest_version(self):
        code, payload = call(["version"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["name"], "hypr-rules-studio")
        self.assertRegex(payload["version"], r"^\d+\.\d+\.\d+$")

    def test_an_unknown_command_is_an_error(self):
        code, payload = call(["nope"])
        self.assertEqual(code, 1)
        self.assertIn("Unknown command", payload["error"])

    def test_no_command_prints_the_usage(self):
        code, payload = call([])
        self.assertEqual(code, 1)
        self.assertIn("Usage", payload["error"])

    def test_engine_version_matches_the_manifest(self):
        import os
        here = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(os.path.dirname(here), "manifest.json")) as handle:
            manifest = json.load(handle)
        self.assertEqual(manifest["version"], engine.VERSION)


if __name__ == "__main__":
    unittest.main()
