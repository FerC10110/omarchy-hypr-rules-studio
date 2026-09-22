import io
import json
import os
import shutil
import tempfile
import unittest

from _load import load

engine = load()

HYPRLAND_LUA = 'require("hypr.monitors")\nrequire("hypr.bindings")\n'


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.home, ".config", "hypr"))
        with open(os.path.join(self.home, ".config", "hypr", "hyprland.lua"), "w") as handle:
            handle.write(HYPRLAND_LUA)
        self.environ = {"HOME": self.home}

    def tearDown(self):
        shutil.rmtree(self.home, ignore_errors=True)

    def read(self, *parts):
        with open(os.path.join(self.home, *parts)) as handle:
            return handle.read()

    def add(self, **fields):
        base = {"match": {"class": "^(kitty)$"}, "props": {"float": True}}
        base.update(fields)
        return engine.add_rule(self.environ, base)

    def test_a_saved_rule_gets_an_id_and_comes_back_in_mine(self):
        rule = self.add()
        self.assertRegex(rule["id"], r"^[0-9a-f]{32}$")
        self.assertEqual(engine.load_store(self.environ)["rules"][0]["id"], rule["id"])

    def test_the_lua_file_is_written_with_the_managed_markers(self):
        self.add()
        text = self.read(".config", "hypr", "rules-studio.lua")
        self.assertIn(">>> hypr-rules-studio", text)
        self.assertIn('o.window({ class = "^(kitty)$" }, { float = true })', text)
        self.assertIn("<<< hypr-rules-studio", text)

    def test_sizes_and_positions_render_as_lua_tables(self):
        self.add(props={"size": [1200, 800], "move": [40, 60]})
        text = self.read(".config", "hypr", "rules-studio.lua")
        self.assertIn("size = { 1200, 800 }", text)
        self.assertIn("move = { 40, 60 }", text)

    def test_strings_are_quoted_and_escaped(self):
        self.add(match={"title": 'a"b'}, props={"workspace": "5"})
        text = self.read(".config", "hypr", "rules-studio.lua")
        self.assertIn('title = "a\\"b"', text)
        self.assertIn('workspace = "5"', text)

    def test_the_require_line_is_added_once(self):
        self.add()
        self.add(match={"class": "^(foot)$"})
        text = self.read(".config", "hypr", "hyprland.lua")
        self.assertEqual(text.count('require("hypr.rules-studio")'), 1)

    def test_the_config_is_backed_up_before_the_first_edit(self):
        self.add()
        backups = [name for name in os.listdir(os.path.join(self.home, ".config", "hypr"))
                   if name.startswith("hyprland.lua.bak.")]
        self.assertEqual(len(backups), 1)
        with open(os.path.join(self.home, ".config", "hypr", backups[0])) as handle:
            self.assertEqual(handle.read(), HYPRLAND_LUA)

    def test_a_rule_can_be_removed_and_the_lua_follows(self):
        rule = self.add()
        engine.remove_rule(self.environ, rule["id"])
        self.assertEqual(engine.load_store(self.environ)["rules"], [])
        self.assertNotIn("kitty", self.read(".config", "hypr", "rules-studio.lua"))

    def test_removing_an_unknown_id_is_an_error(self):
        with self.assertRaises(engine.StudioError):
            engine.remove_rule(self.environ, "f" * 32)

    def test_purge_removes_the_file_and_the_require_line(self):
        self.add()
        engine.purge(self.environ)
        self.assertFalse(os.path.exists(os.path.join(self.home, ".config", "hypr", "rules-studio.lua")))
        self.assertNotIn("rules-studio", self.read(".config", "hypr", "hyprland.lua"))
        self.assertEqual(engine.load_store(self.environ)["rules"], [])

    def test_purge_only_removes_the_exact_require_line_not_a_comment_mentioning_it(self):
        # I6: a substring test on REQUIRE_LINE would delete a user's own
        # comment that merely mentions the require text.
        self.add()
        config = os.path.join(self.home, ".config", "hypr", "hyprland.lua")
        comment = '-- I decided not to use require("hypr.rules-studio") here'
        with open(config, "a") as handle:
            handle.write(comment + "\n")
        engine.purge(self.environ)
        lines = self.read(".config", "hypr", "hyprland.lua").splitlines()
        self.assertIn(comment, lines)
        self.assertNotIn(engine.REQUIRE_LINE, lines)

    def test_purge_backs_up_the_config_before_rewriting_it(self):
        self.add()
        before = self.read(".config", "hypr", "hyprland.lua")
        backups_before = {name for name in os.listdir(os.path.join(self.home, ".config", "hypr"))
                          if name.startswith("hyprland.lua.bak.")}
        engine.purge(self.environ)
        backups_after = {name for name in os.listdir(os.path.join(self.home, ".config", "hypr"))
                         if name.startswith("hyprland.lua.bak.")}
        new_backups = backups_after - backups_before
        self.assertEqual(len(new_backups), 1)
        with open(os.path.join(self.home, ".config", "hypr", next(iter(new_backups)))) as handle:
            self.assertEqual(handle.read(), before)

    def test_two_backups_in_the_same_process_get_distinct_filenames(self):
        # I9: nanosecond resolution instead of whole seconds, so purge-then-
        # save-again (both fast) do not collide and silently lose one.
        self.add()
        engine.purge(self.environ)
        self.add()
        backups = [name for name in os.listdir(os.path.join(self.home, ".config", "hypr"))
                   if name.startswith("hyprland.lua.bak.")]
        self.assertEqual(len(backups), len(set(backups)))
        self.assertGreaterEqual(len(backups), 2)

    def test_a_rule_needs_at_least_one_match_field(self):
        with self.assertRaises(engine.StudioError):
            engine.add_rule(self.environ, {"match": {}, "props": {"float": True}})

    def test_a_rule_needs_at_least_one_property(self):
        with self.assertRaises(engine.StudioError):
            engine.add_rule(self.environ, {"match": {"class": "kitty"}, "props": {}})

    def test_unknown_properties_are_refused(self):
        with self.assertRaises(engine.StudioError):
            engine.add_rule(self.environ, {"match": {"class": "kitty"}, "props": {"rm": "-rf"}})

    def test_a_match_regex_that_python_cannot_compile_is_refused(self):
        with self.assertRaises(engine.StudioError):
            engine.add_rule(self.environ, {"match": {"class": "^(kitty"}, "props": {"float": True}})

    def test_a_newline_in_a_match_value_is_refused(self):
        with self.assertRaises(engine.StudioError):
            engine.add_rule(self.environ, {"match": {"title": "a\nb"}, "props": {"float": True}})

    def test_a_newline_in_a_string_prop_is_refused(self):
        with self.assertRaises(engine.StudioError):
            engine.add_rule(self.environ, {"match": {"class": "kitty"}, "props": {"workspace": "5\n"}})

    def test_a_carriage_return_in_the_comment_is_refused(self):
        with self.assertRaises(engine.StudioError):
            self.add(comment="note\rend")

    def test_opacity_that_does_not_look_like_a_number_is_refused(self):
        # I5: validate_rule protects the config, not just the editor form.
        with self.assertRaises(engine.StudioError):
            self.add(props={"opacity": "abc"})

    def test_opacity_with_one_two_or_three_numbers_is_accepted(self):
        self.add(props={"opacity": "0.9"})
        self.add(match={"class": "^(foot)$"}, props={"opacity": "0.9 0.6"})
        self.add(match={"class": "^(alacritty)$"}, props={"opacity": "1 1 1"})

    def test_opacity_with_four_numbers_is_refused(self):
        with self.assertRaises(engine.StudioError):
            self.add(props={"opacity": "1 1 1 1"})

    def test_a_store_missing_version_is_healed_not_a_crash(self):
        # C2: a hand-edited rules.json without "version" used to raise a
        # bare KeyError out of with_props_text.
        store_dir = os.path.join(self.home, ".config", "hypr-rules-studio")
        os.makedirs(store_dir)
        with open(os.path.join(store_dir, "rules.json"), "w") as handle:
            handle.write('{"rules": []}')
        store = engine.load_store(self.environ)
        self.assertEqual(store["version"], engine.STORE_VERSION)
        self.assertEqual(engine.with_props_text(store)["rules"], [])

    def test_render_lua_neutralizes_control_characters_in_the_comment(self):
        # Bypasses validate_rule entirely, the way a hand-edited rules.json
        # would: a raw control byte in the comment must never reach the file,
        # since a "--" comment line has no escape of its own to cover it.
        store = {"version": 1, "rules": [{"id": "a" * 32, "match": {"class": "kitty"},
                                           "props": {"float": True}, "comment": "note\rend"}]}
        text = engine.render_lua(store)
        self.assertNotIn("note\rend", text)
        self.assertIn("-- note end", text)
        path = os.path.join(self.home, "direct.lua")
        with open(path, "w") as handle:
            handle.write(text)
        import subprocess
        done = subprocess.run(["/usr/bin/lua", "-e", "o = { window = function() end }; dofile('%s')" % path],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_render_lua_escapes_control_characters_so_the_lua_stays_valid(self):
        # Bypasses validate_rule entirely, the way a hand-edited rules.json
        # would: render_lua must still never emit a broken Lua literal.
        store = {"version": 1, "rules": [{"id": "a" * 32, "match": {"title": "a\nb\tc"},
                                           "props": {"float": True}, "comment": ""}]}
        text = engine.render_lua(store)
        self.assertNotIn("a\nb\tc", text)
        self.assertIn('title = "a\\nb\\tc"', text)
        path = os.path.join(self.home, "direct.lua")
        with open(path, "w") as handle:
            handle.write(text)
        import subprocess
        done = subprocess.run(["/usr/bin/lua", "-e", "o = { window = function() end }; dofile('%s')" % path],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_an_unwritable_config_directory_is_a_studio_error_not_a_crash(self):
        hypr_dir = os.path.join(self.home, ".config", "hypr")
        mode = os.stat(hypr_dir).st_mode
        os.chmod(hypr_dir, 0o555)
        try:
            with self.assertRaises(engine.StudioError):
                self.add()
        finally:
            os.chmod(hypr_dir, mode)

    def test_purge_restores_the_config_byte_identical_with_no_trailing_blank_line(self):
        self.add()
        engine.purge(self.environ)
        self.assertEqual(self.read(".config", "hypr", "hyprland.lua"), HYPRLAND_LUA)

    def test_purge_restores_the_config_byte_identical_with_one_trailing_blank_line(self):
        text = HYPRLAND_LUA + "\n"
        with open(os.path.join(self.home, ".config", "hypr", "hyprland.lua"), "w") as handle:
            handle.write(text)
        self.add()
        engine.purge(self.environ)
        self.assertEqual(self.read(".config", "hypr", "hyprland.lua"), text)

    def test_purge_restores_the_config_byte_identical_with_two_trailing_blank_lines(self):
        text = HYPRLAND_LUA + "\n\n"
        with open(os.path.join(self.home, ".config", "hypr", "hyprland.lua"), "w") as handle:
            handle.write(text)
        self.add()
        engine.purge(self.environ)
        self.assertEqual(self.read(".config", "hypr", "hyprland.lua"), text)

    def test_the_generated_lua_loads_in_lua(self):
        self.add(props={"size": [1200, 800], "opacity": "1 1", "pin": True})
        path = os.path.join(self.home, ".config", "hypr", "rules-studio.lua")
        import subprocess
        done = subprocess.run(["/usr/bin/lua", "-e", "o = { window = function() end }; dofile('%s')" % path],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_the_subcommands_speak_json(self):
        out = io.StringIO()
        code = engine.main(["save-rule"], environ=self.environ, run=None,
                           stdin=io.StringIO(json.dumps({"match": {"class": "^(kitty)$"},
                                                         "props": {"float": True}})),
                           stdout=out)
        payload = json.loads(out.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(len(payload["rules"]), 1)

    def test_mine_includes_a_one_line_props_text_per_rule(self):
        self.add(props={"float": True, "size": [1200, 800]})
        rules = engine.dispatch(["mine"], self.environ, None, None)["rules"]
        self.assertEqual(rules[0]["props_text"], "float=true size=1200x800")

    def test_save_rule_and_remove_rule_responses_also_carry_props_text(self):
        # The panel's "My rules" list (Task 9) is populated straight from
        # these responses, not a follow-up `mine` call, so they need the
        # same one-line summary `mine` has.
        out = io.StringIO()
        engine.main(["save-rule"], environ=self.environ, run=None,
                    stdin=io.StringIO(json.dumps({"match": {"class": "^(kitty)$"},
                                                  "props": {"pin": True}})),
                    stdout=out)
        saved = json.loads(out.getvalue())
        self.assertEqual(saved["rules"][0]["props_text"], "pin=true")

        out2 = io.StringIO()
        engine.main(["remove-rule", saved["rules"][0]["id"]], environ=self.environ, run=None,
                    stdin=io.StringIO(""), stdout=out2)
        self.assertEqual(json.loads(out2.getvalue())["rules"], [])

    def test_props_text_is_never_written_to_the_rules_file(self):
        # A derived field for the panel must not leak into what we persist
        # or regenerate the Lua from.
        self.add(props={"float": True})
        engine.dispatch(["mine"], self.environ, None, None)
        with open(os.path.join(self.home, ".config", "hypr-rules-studio", "rules.json")) as handle:
            stored = json.load(handle)
        self.assertNotIn("props_text", stored["rules"][0])


if __name__ == "__main__":
    unittest.main()
