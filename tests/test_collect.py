import io
import json
import os
import shutil
import tempfile
import unittest

from _load import load

engine = load()
HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")


class CollectTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.home, ".config"))
        shutil.copytree(os.path.join(FIXTURES, "basic"),
                        os.path.join(self.home, ".config", "hypr"))
        self.environ = {"HOME": self.home, "PATH": os.environ["PATH"]}

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def collect(self):
        return engine.collect_rules(self.environ, engine.subprocess.run)

    def test_every_rule_is_collected_in_config_order(self):
        result = self.collect()
        self.assertIsNone(result["error"])
        self.assertEqual([r["props"].get("tag") or r["props"].get("float")
                          or r["props"].get("opacity") for r in result["rules"]],
                         ["+default-opacity", True, "0.985 0.96"])
        self.assertEqual([r["index"] for r in result["rules"]], [0, 1, 2])

    def test_each_rule_carries_the_file_that_wrote_it_not_the_helper(self):
        rules = self.collect()["rules"]
        self.assertTrue(rules[1]["file"].endswith("apps/term.lua"), rules[1]["file"])
        self.assertEqual(rules[1]["line"], 1)
        self.assertTrue(rules[0]["file"].endswith("hyprland.lua"))

    def test_a_string_match_becomes_a_class_match(self):
        self.assertEqual(self.collect()["rules"][0]["match"], {"class": ".*"})

    def test_nested_values_survive_as_lists(self):
        self.assertEqual(self.collect()["rules"][1]["props"]["size"], [1200, 800])

    def test_rules_from_the_user_config_are_tagged_as_user(self):
        self.assertEqual({r["source"] for r in self.collect()["rules"]}, {"user"})

    def test_a_broken_config_reports_the_error_instead_of_crashing(self):
        with open(os.path.join(self.home, ".config", "hypr", "hyprland.lua"), "a") as handle:
            handle.write("\nthis is not lua\n")
        result = self.collect()
        self.assertEqual(result["rules"], [])
        self.assertIn("hyprland.lua", result["error"])

    def test_a_non_utf8_collector_stdout_is_reported_not_left_to_crash(self):
        # C2: collect_rules' docstring promises it never raises. `run(...,
        # text=True)` decodes stdout as UTF-8, so a collector emitting a raw
        # byte that is not valid UTF-8 raises UnicodeDecodeError - a real
        # exception distinct from OSError/TimeoutExpired, which used to
        # escape uncaught (doctor calls collect_rules first thing, so this
        # used to take the whole Doctor down with a bare traceback).
        script = os.path.join(self.home, "bad-lua")
        with open(script, "w") as handle:
            handle.write("#!/bin/sh\nprintf '\\377'\n")
        os.chmod(script, 0o755)
        environ = dict(self.environ, STUDIO_LUA=script)
        result = engine.collect_rules(environ, engine.subprocess.run)
        self.assertEqual(result["rules"], [])
        self.assertIsNotNone(result["error"])

    def test_collect_rules_never_raises_even_on_a_decode_error(self):
        def boom_run(argv, **kwargs):
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
        result = engine.collect_rules(self.environ, boom_run)
        self.assertEqual(result["rules"], [])
        self.assertIn("Could not run lua", result["error"])

    def test_the_rules_subcommand_returns_the_same_list(self):
        out = io.StringIO()
        code = engine.main(["rules"], environ=self.environ, run=engine.subprocess.run,
                           stdin=io.StringIO(""), stdout=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["rules"]), 3)

    def test_empty_match_and_props_stay_objects_not_arrays(self):
        # A separate fixture (not "basic"): a rule with no match and no props
        # at all, which is exactly the {} shape that a naive array/object test
        # ("does key count equal array length?") mistakes for an empty array.
        home = tempfile.mkdtemp()
        try:
            shutil.copytree(os.path.join(FIXTURES, "empty"),
                            os.path.join(home, ".config", "hypr"))
            environ = {"HOME": home, "PATH": os.environ["PATH"]}
            result = engine.collect_rules(environ, engine.subprocess.run)
            self.assertIsNone(result["error"])
            self.assertEqual(len(result["rules"]), 1)
            rule = result["rules"][0]
            self.assertIsInstance(rule["match"], dict)
            self.assertIsInstance(rule["props"], dict)
            self.assertEqual(rule["match"], {})
            self.assertEqual(rule["props"], {})
        finally:
            shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
