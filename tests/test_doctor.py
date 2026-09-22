import json
import os
import shutil
import tempfile
import unittest

from _load import load
from fakes import CLIENTS, FakeRun

engine = load()
HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
VERSION_JSON = '{"tag": "v0.56.2", "commit": "abc"}'


def answers(config_errors="[]"):
    return {"hyprctl -j clients": (0, CLIENTS, ""),
            "hyprctl -j configerrors": (0, config_errors, ""),
            "hyprctl -j version": (0, VERSION_JSON, "")}


class DoctorTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.home, ".config"))
        shutil.copytree(os.path.join(FIXTURES, "basic"),
                        os.path.join(self.home, ".config", "hypr"))
        self.environ = {"HOME": self.home, "PATH": os.environ["PATH"]}
        self.run = FakeRun(answers())

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def test_a_healthy_config_reports_nothing_wrong(self):
        report = engine.doctor(self.environ, self.run)
        self.assertTrue(report["healthy"])
        self.assertEqual(report["problems"], [])
        self.assertEqual(report["hyprland"], "v0.56.2")

    def test_a_config_that_does_not_load_is_the_first_problem(self):
        with open(os.path.join(self.home, ".config", "hypr", "hyprland.lua"), "a") as handle:
            handle.write("\nbroken(\n")
        report = engine.doctor(self.environ, self.run)
        self.assertFalse(report["healthy"])
        self.assertEqual(report["problems"][0]["kind"], "config-error")
        self.assertIn("hyprland.lua", report["problems"][0]["detail"])

    def test_lua_itself_being_unreachable_is_a_config_error(self):
        # No FakeRun involved: collect_rules always runs the real
        # subprocess.run, so this points it at a lua binary that does not
        # exist, the same way lua_bin() lets tests override it elsewhere.
        environ = dict(self.environ, STUDIO_LUA="/no/such/lua-binary")
        report = engine.doctor(environ, self.run)
        self.assertFalse(report["healthy"])
        self.assertTrue(any(p["kind"] == "config-error" for p in report["problems"]))

    def test_hyprland_config_errors_are_reported(self):
        run = FakeRun(answers('["Config error: unknown keyword foo"]'))
        report = engine.doctor(self.environ, run)
        self.assertFalse(report["healthy"])
        self.assertTrue(any(p["kind"] == "hyprland-error" for p in report["problems"]))

    def test_a_blank_configerrors_entry_is_not_a_problem(self):
        # A healthy real Hyprland answers `configerrors` with `[""]`, not
        # `[]`: that single blank string is its way of saying "no errors",
        # not an error worth reporting.
        run = FakeRun(answers('[""]'))
        report = engine.doctor(self.environ, run)
        self.assertTrue(report["healthy"])
        self.assertEqual(report["problems"], [])

    def test_a_missing_require_line_with_rules_saved_is_a_problem(self):
        engine.add_rule(self.environ, {"match": {"class": "^(kitty)$"}, "props": {"float": True}})
        config = os.path.join(self.home, ".config", "hypr", "hyprland.lua")
        with open(config) as handle:
            text = handle.read().replace(engine.REQUIRE_LINE, "")
        with open(config, "w") as handle:
            handle.write(text)
        report = engine.doctor(self.environ, self.run)
        self.assertTrue(any(p["kind"] == "not-loaded" for p in report["problems"]))

    def test_a_freshly_written_rules_file_is_not_flagged_as_stale(self):
        engine.add_rule(self.environ, {"match": {"class": "^(sanity)$"}, "props": {"float": True}})
        report = engine.doctor(self.environ, self.run)
        self.assertTrue(report["healthy"], report["problems"])

    def test_a_generated_file_that_does_not_match_the_store_is_stale(self):
        # I7: require line present and the file exists is not the same as
        # the file holding what was actually saved (killed mid-write, or
        # hand-edited afterwards).
        engine.add_rule(self.environ, {"match": {"class": "^(kitty)$"}, "props": {"float": True}})
        rules_file = os.path.join(self.home, ".config", "hypr", "rules-studio.lua")
        with open(rules_file, "a") as handle:
            handle.write("-- hand edited\n")
        report = engine.doctor(self.environ, self.run)
        self.assertFalse(report["healthy"])
        self.assertTrue(any(p["kind"] == "stale" for p in report["problems"]))

    def test_a_corrupted_store_is_flagged_so_the_purge_button_still_shows(self):
        # I7: rule_count is forced to 0 when the store cannot be read, which
        # would otherwise hide "Remove everything I wrote" - the one thing
        # that can fix it. state_error covers that case for the panel.
        store_dir = os.path.join(self.home, ".config", "hypr-rules-studio")
        os.makedirs(store_dir)
        with open(os.path.join(store_dir, "rules.json"), "w") as handle:
            handle.write("not json{{{")
        report = engine.doctor(self.environ, self.run)
        self.assertEqual(report["rule_count"], 0)
        self.assertTrue(report["state_error"])

    def test_a_healthy_report_has_no_state_error(self):
        report = engine.doctor(self.environ, self.run)
        self.assertFalse(report["state_error"])

    def test_a_corrupted_rules_store_is_a_problem_not_a_crash(self):
        store_dir = os.path.join(self.home, ".config", "hypr-rules-studio")
        os.makedirs(store_dir)
        with open(os.path.join(store_dir, "rules.json"), "w") as handle:
            handle.write("not json{{{")
        report = engine.doctor(self.environ, self.run)
        self.assertFalse(report["healthy"])
        self.assertTrue(any(p["kind"] == "state-error" for p in report["problems"]))

    def test_a_rule_of_ours_that_a_later_rule_overrides_is_reported(self):
        rules = [{"index": 0, "file": "rules-studio.lua", "line": 2, "source": "studio",
                  "match": {"class": "^(kitty)$"}, "props": {"float": True}},
                 {"index": 1, "file": "x.lua", "line": 9, "source": "omarchy",
                  "match": {"class": "^(kitty)$"}, "props": {"float": False}}]
        conflicts = engine.find_conflicts(rules)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["prop"], "float")
        self.assertEqual(conflicts[0]["winner"]["line"], 9)

    def test_a_rule_of_ours_nobody_overrides_is_not_a_conflict(self):
        rules = [{"index": 0, "file": "rules-studio.lua", "line": 2, "source": "studio",
                  "match": {"class": "^(kitty)$"}, "props": {"float": True}},
                 {"index": 1, "file": "x.lua", "line": 9, "source": "omarchy",
                  "match": {"class": "^(foot)$"}, "props": {"float": False}}]
        self.assertEqual(engine.find_conflicts(rules), [])

    def test_a_healthy_run_records_the_hyprland_version(self):
        engine.doctor(self.environ, self.run)
        with open(engine.state_path(self.environ)) as handle:
            state = json.load(handle)
        self.assertEqual(state["hyprland"], "v0.56.2")

    def test_state_write_failing_does_not_sink_a_healthy_report(self):
        # ~/.local/state is a plain file, so write_atomic can never create
        # ~/.local/state/hypr-rules-studio/ underneath it.
        os.makedirs(os.path.join(self.home, ".local"))
        with open(os.path.join(self.home, ".local", "state"), "w") as handle:
            handle.write("not a directory")
        report = engine.doctor(self.environ, self.run)
        self.assertTrue(report["healthy"])
        self.assertEqual(report["problems"], [])

    def test_breaking_after_an_update_says_so(self):
        engine.doctor(self.environ, self.run)                      # healthy on v0.56.2
        with open(os.path.join(self.home, ".config", "hypr", "hyprland.lua"), "a") as handle:
            handle.write("\nbroken(\n")
        run = FakeRun(answers())
        run.answers["hyprctl -j version"] = (0, '{"tag": "v0.57.0"}', "")
        report = engine.doctor(self.environ, run)
        self.assertTrue(report["updated_since_last_ok"])

    def test_hyprland_being_unreachable_does_not_sink_the_report(self):
        run = FakeRun({})                                          # nothing stubbed: every call fails
        report = engine.doctor(self.environ, run)
        self.assertFalse(report["healthy"])
        self.assertTrue(any("hyprctl" in p["detail"] for p in report["problems"]))


if __name__ == "__main__":
    unittest.main()
