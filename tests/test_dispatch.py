"""I8: dispatch-level coverage for every subcommand through main() - the
level the panel actually talks to. Before this file, tests reached main()
for exactly four commands (rules, windows, save-rule, remove-rule); explain,
mine, purge, preview, doctor and the error paths were only ever exercised
one function below main(), which is exactly how C2 (a crash with empty
stdout) slipped through: a `dispatch`-level test asserting "exactly one JSON
document on stdout, the right exit code" would have caught it."""
import io
import json
import os
import shutil
import tempfile
import unittest

from _load import load
from fakes import CLIENTS, FakeRun
from test_preview import eval_call, toggle_snippet

engine = load()
HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
VERSION_JSON = '{"tag": "v0.56.2", "commit": "abc"}'


def answers(config_errors="[]"):
    return {"hyprctl -j clients": (0, CLIENTS, ""),
            "hyprctl -j configerrors": (0, config_errors, ""),
            "hyprctl -j version": (0, VERSION_JSON, "")}


class DispatchTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.home, ".config"))
        shutil.copytree(os.path.join(FIXTURES, "basic"),
                        os.path.join(self.home, ".config", "hypr"))
        self.environ = {"HOME": self.home, "PATH": os.environ["PATH"]}
        self.run = FakeRun(answers())

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def call(self, args, stdin_text="", run=None):
        """Run the engine exactly as the panel's Process does: argv in, one
        JSON document out, nothing else on stdout."""
        out = io.StringIO()
        code = engine.main(args, environ=self.environ, run=run if run is not None else self.run,
                           stdin=io.StringIO(stdin_text), stdout=out)
        text = out.getvalue()
        self.assertEqual(text.count("\n"), 1, "not exactly one JSON line: %r" % text)
        return code, json.loads(text)

    def hybrid_run(self, argv, **kwargs):
        """`explain` asks for both a real `hyprctl` answer (faked here) and a
        real `lua` run against the fixture config (collect_rules' own job) -
        dispatch hands both calls the one `run` it was given, so the fake has
        to route between them the way a real machine's two programs would."""
        if argv[0] == "hyprctl":
            return self.run(argv, **kwargs)
        return engine.subprocess.run(argv, **kwargs)

    # ---- every subcommand, the happy path

    def test_version(self):
        code, payload = self.call(["version"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["name"], "hypr-rules-studio")

    def test_rules(self):
        code, payload = self.call(["rules"], run=engine.subprocess.run)
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["rules"]), 3)

    def test_windows(self):
        code, payload = self.call(["windows"])
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["windows"]), 2)

    def test_explain(self):
        code, payload = self.call(["explain", "0x1"], run=self.hybrid_run)
        self.assertEqual(code, 0)
        self.assertIn("applied", payload)
        self.assertIn("effective", payload)

    def test_mine_starts_empty(self):
        code, payload = self.call(["mine"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["rules"], [])

    def test_save_rule(self):
        code, payload = self.call(
            ["save-rule"], json.dumps({"match": {"class": "^(kitty)$"}, "props": {"float": True}}))
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["rules"]), 1)

    def test_remove_rule(self):
        self.call(["save-rule"], json.dumps({"match": {"class": "^(kitty)$"}, "props": {"float": True}}))
        rule_id = engine.load_store(self.environ)["rules"][0]["id"]
        code, payload = self.call(["remove-rule", rule_id])
        self.assertEqual(code, 0)
        self.assertEqual(payload["rules"], [])

    def test_purge(self):
        self.call(["save-rule"], json.dumps({"match": {"class": "^(kitty)$"}, "props": {"float": True}}))
        code, payload = self.call(["purge"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["rules"], [])

    def test_preview(self):
        self.run.answers[eval_call(toggle_snippet("floating", "float", True))] = (0, "ok", "")
        code, payload = self.call(["preview", "0x1"], json.dumps({"props": {"float": True}}))
        self.assertEqual(code, 0)
        self.assertIn("float", payload["applied"])

    def test_doctor(self):
        code, payload = self.call(["doctor"])
        self.assertEqual(code, 0)
        self.assertTrue(payload["healthy"])

    # ---- error paths: missing argument, unknown command

    def test_no_command_prints_the_usage(self):
        code, payload = self.call([])
        self.assertEqual(code, 1)
        self.assertIn("Usage", payload["error"])

    def test_unknown_command(self):
        code, payload = self.call(["nope"])
        self.assertEqual(code, 1)
        self.assertIn("Unknown command", payload["error"])

    def test_explain_missing_address_is_an_error(self):
        code, payload = self.call(["explain"])
        self.assertEqual(code, 1)
        self.assertIn("Missing window address", payload["error"])

    def test_explain_unknown_window_is_an_error(self):
        code, payload = self.call(["explain", "0xdead"])
        self.assertEqual(code, 1)
        self.assertIn("gone", payload["error"])

    def test_remove_rule_missing_id_is_an_error(self):
        code, payload = self.call(["remove-rule"])
        self.assertEqual(code, 1)
        self.assertIn("Missing rule id", payload["error"])

    def test_remove_rule_unknown_id_is_an_error(self):
        code, payload = self.call(["remove-rule", "f" * 32])
        self.assertEqual(code, 1)
        self.assertIn("No such rule", payload["error"])

    def test_preview_missing_address_is_an_error(self):
        code, payload = self.call(["preview"])
        self.assertEqual(code, 1)
        self.assertIn("Missing window address", payload["error"])

    def test_save_rule_invalid_is_an_error(self):
        code, payload = self.call(["save-rule"], json.dumps({"match": {}, "props": {}}))
        self.assertEqual(code, 1)
        self.assertIn("error", payload)

    # ---- C2: the crash shapes - stdout must never come back empty

    def test_a_hand_edited_store_missing_version_does_not_crash_mine(self):
        store_dir = os.path.join(self.home, ".config", "hypr-rules-studio")
        os.makedirs(store_dir)
        with open(os.path.join(store_dir, "rules.json"), "w") as handle:
            handle.write('{"rules": []}')
        code, payload = self.call(["mine"])
        self.assertEqual(code, 0)
        self.assertEqual(payload["rules"], [])

    def test_rules_survives_a_decode_error_from_lua(self):
        # collect_rules must report this, not raise it past dispatch/main.
        def boom_run(argv, **kwargs):
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        code, payload = self.call(["rules"], run=boom_run)
        self.assertEqual(code, 0)
        self.assertEqual(payload["rules"], [])
        self.assertIsNotNone(payload["error"])

    def test_an_unexpected_exception_is_reported_not_left_to_a_traceback(self):
        # main()'s catch-all: whatever dispatch() does, stdout gets exactly
        # one JSON document and exit code 1, never a bare Python traceback
        # on stderr with nothing usable on stdout.
        original = engine.dispatch

        def boom(args, environ, run, stdin):
            raise ValueError("boom")

        engine.dispatch = boom
        try:
            code, payload = self.call(["mine"])
        finally:
            engine.dispatch = original
        self.assertEqual(code, 1)
        self.assertIn("Something went wrong", payload["error"])


if __name__ == "__main__":
    unittest.main()
