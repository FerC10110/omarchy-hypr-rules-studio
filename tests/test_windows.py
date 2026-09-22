import io
import json
import unittest

from _load import load
from fakes import CLIENTS, FakeRun

engine = load()
ENVIRON = {"HOME": "/home/tester", "PATH": "/usr/bin"}


class WindowsTest(unittest.TestCase):
    def setUp(self):
        self.run = FakeRun({"hyprctl -j clients": (0, CLIENTS, "")})

    def test_windows_are_listed_with_the_fields_the_panel_needs(self):
        windows = engine.list_windows(ENVIRON, self.run)["windows"]
        self.assertEqual(len(windows), 2)
        first = windows[0]
        self.assertEqual(first["address"], "0x1")
        self.assertEqual(first["class"], "kitty")
        self.assertEqual(first["initialTitle"], "kitty")
        self.assertEqual(first["workspace"], "1")
        self.assertEqual(first["tags"], ["terminal"])

    def test_a_trailing_star_is_stripped_from_tags(self):
        # hyprctl marks tags applied by rules with "*"; the rule names have none.
        self.assertEqual(engine.list_windows(ENVIRON, self.run)["windows"][0]["tags"], ["terminal"])

    def test_find_window_returns_the_one_with_that_address(self):
        window = engine.find_window(ENVIRON, self.run, "0x2")
        self.assertEqual(window["class"], "firefox")

    def test_an_unknown_address_is_an_error(self):
        with self.assertRaises(engine.StudioError):
            engine.find_window(ENVIRON, self.run, "0x9")

    def test_hyprctl_failing_is_a_clear_error(self):
        run = FakeRun({"hyprctl -j clients": (1, "", "Couldn't connect to Hyprland")})
        with self.assertRaises(engine.StudioError) as caught:
            engine.list_windows(ENVIRON, run)
        self.assertIn("Hyprland", str(caught.exception))

    def test_the_windows_subcommand_prints_them(self):
        out = io.StringIO()
        code = engine.main(["windows"], environ=ENVIRON, run=self.run,
                           stdin=io.StringIO(""), stdout=out)
        self.assertEqual(code, 0)
        self.assertEqual(len(json.loads(out.getvalue())["windows"]), 2)


if __name__ == "__main__":
    unittest.main()
