import unittest

from _load import load
from fakes import CLIENTS, FakeRun

engine = load()
ENVIRON = {"HOME": "/home/tester"}

OK = (0, "ok", "")


def runner():
    answers = {"hyprctl -j clients": (0, CLIENTS, "")}
    return FakeRun(answers), answers


# This build's `hyprctl dispatch <text>` evaluates `return hl.dispatch(<text>)`
# as Lua (see hyprctl_eval's docstring in bin/hypr-rules-studio), so
# preview_props talks to it by writing small Lua snippets, not classic
# dispatcher-name/argstring pairs. These builders mirror preview_props' own
# formatting exactly, using the engine's own (separately tested) lua_value
# for the escaping, so a test failure here means the sequencing/logic is
# wrong, not a hand-typed literal drifting out of sync with the code.

def selector(address="0x1"):
    return engine.lua_value("address:" + address)


def toggle_snippet(field, dispatcher, desired, address="0x1"):
    sel = selector(address)
    return ("local w = hl.get_window(%s) if w and w.%s ~= %s then hl.dispatch(hl.dsp.window.%s(%s)) end"
            % (sel, field, engine.lua_value(bool(desired)), dispatcher, sel))


def resize_snippet(w, h, address="0x1"):
    return "hl.dispatch(hl.dsp.window.resize({ x = %d, y = %d, window = %s }))" % (w, h, selector(address))


def move_snippet(x, y, address="0x1"):
    return "hl.dispatch(hl.dsp.window.move({ x = %d, y = %d, window = %s }))" % (x, y, selector(address))


def workspace_snippet(value, address="0x1"):
    return ("hl.dispatch(hl.dsp.window.move({ workspace = %s, window = %s }))"
            % (engine.lua_value(value), selector(address)))


def opacity_snippet(literal, address="0x1"):
    return ('hl.dispatch(hl.dsp.window.set_prop({ window = %s, prop = "opacity", value = %s }))'
            % (selector(address), literal))


def eval_call(lua_code):
    return "hyprctl eval " + lua_code


class PreviewTest(unittest.TestCase):
    def setUp(self):
        self.run, self.answers = runner()

    def stub(self, lua_code, result=OK):
        self.answers[eval_call(lua_code)] = result

    def test_floating_is_dispatched(self):
        self.stub(toggle_snippet("floating", "float", True))
        engine.preview_props(ENVIRON, self.run, "0x1", {"float": True})
        self.assertIn(eval_call(toggle_snippet("floating", "float", True)), self.run.calls)

    def test_float_false_is_dispatched_through_the_same_toggle(self):
        # There is no separate "settiled" in this Lua API - float is a
        # toggle either way, guarded by comparing the window's current
        # state, so "float: false" is a real, distinct call, not a no-op.
        self.stub(toggle_snippet("floating", "float", False))
        engine.preview_props(ENVIRON, self.run, "0x1", {"float": False})
        self.assertIn(eval_call(toggle_snippet("floating", "float", False)), self.run.calls)

    def test_tile_true_asks_for_floating_false(self):
        self.stub(toggle_snippet("floating", "float", False))
        engine.preview_props(ENVIRON, self.run, "0x1", {"tile": True})
        self.assertIn(eval_call(toggle_snippet("floating", "float", False)), self.run.calls)

    def test_floating_is_applied_before_size_and_position(self):
        # Resizing a tiled window does nothing, so the order is not incidental.
        self.stub(toggle_snippet("floating", "float", True))
        self.stub(resize_snippet(600, 400))
        self.stub(move_snippet(40, 60))
        engine.preview_props(ENVIRON, self.run, "0x1",
                             {"size": [600, 400], "move": [40, 60], "float": True})
        calls = self.run.calls
        self.assertLess(calls.index(eval_call(toggle_snippet("floating", "float", True))),
                        calls.index(eval_call(resize_snippet(600, 400))))

    def test_pin_true_and_false_both_reach_hyprland(self):
        # The old text-protocol version of this code could only ever pin
        # live, never unpin (there was no "unpin" dispatcher to send); pin
        # is a toggle here too, so the same guarded-toggle approach used for
        # float makes both directions real.
        self.stub(toggle_snippet("pinned", "pin", True))
        self.stub(toggle_snippet("pinned", "pin", False))
        pin_result = engine.preview_props(ENVIRON, self.run, "0x1", {"pin": True})
        unpin_result = engine.preview_props(ENVIRON, self.run, "0x1", {"pin": False})
        self.assertIn(eval_call(toggle_snippet("pinned", "pin", True)), self.run.calls)
        self.assertIn(eval_call(toggle_snippet("pinned", "pin", False)), self.run.calls)
        self.assertIn("pin", pin_result["applied"])
        self.assertIn("pin", unpin_result["applied"])

    def test_workspace_is_dispatched(self):
        self.stub(workspace_snippet("5"))
        engine.preview_props(ENVIRON, self.run, "0x1", {"workspace": "5"})
        self.assertIn(eval_call(workspace_snippet("5")), self.run.calls)

    def test_opacity_goes_through_set_prop_as_a_lua_number(self):
        self.stub(opacity_snippet("0.9"))
        engine.preview_props(ENVIRON, self.run, "0x1", {"opacity": "0.9"})
        self.assertIn(eval_call(opacity_snippet("0.9")), self.run.calls)

    def test_an_opacity_that_is_not_a_number_is_refused_up_front(self):
        # validate_rule now checks opacity's shape (I5), so "auto" never
        # gets far enough to need the skipped-live-preview path below.
        with self.assertRaises(engine.StudioError):
            engine.preview_props(ENVIRON, self.run, "0x1", {"opacity": "auto"})
        self.assertEqual([call for call in self.run.calls if "eval" in call], [])

    def test_what_cannot_be_tried_live_is_reported_not_silently_dropped(self):
        self.stub(toggle_snippet("floating", "float", True))
        result = engine.preview_props(ENVIRON, self.run, "0x1", {"no_focus": True, "float": True})
        self.assertEqual(result["skipped"], ["no_focus"])
        self.assertIn("float", result["applied"])

    def test_an_unknown_window_is_an_error(self):
        with self.assertRaises(engine.StudioError):
            engine.preview_props(ENVIRON, self.run, "0xdead", {"float": True})

    def test_the_props_are_validated_before_anything_is_dispatched(self):
        with self.assertRaises(engine.StudioError):
            engine.preview_props(ENVIRON, self.run, "0x1", {"rm": "-rf /"})
        self.assertEqual([call for call in self.run.calls if "eval" in call], [])

    def test_a_property_that_fails_does_not_hide_what_already_worked(self):
        # I3: the window IS floating now even though the resize that came
        # after it failed - that must show up in `applied`, not disappear
        # behind a raised exception that erases the whole call.
        self.stub(toggle_snippet("floating", "float", True))
        self.answers[eval_call(resize_snippet(600, 400))] = (1, "", "hyprctl: resize rejected")
        result = engine.preview_props(ENVIRON, self.run, "0x1", {"float": True, "size": [600, 400]})
        self.assertEqual(result["applied"], ["float"])
        self.assertIn("size", result["failed"])
        self.assertIn("resize rejected", result["failed"]["size"])

    def test_a_failure_does_not_stop_the_properties_that_come_after_it(self):
        self.answers[eval_call(resize_snippet(600, 400))] = (1, "", "hyprctl: resize rejected")
        self.stub(move_snippet(40, 60))
        result = engine.preview_props(ENVIRON, self.run, "0x1",
                                      {"size": [600, 400], "move": [40, 60]})
        self.assertIn("size", result["failed"])
        self.assertEqual(result["applied"], ["move"])


if __name__ == "__main__":
    unittest.main()
