import unittest

from _load import load

engine = load()


def rule(index, match, props, file="/usr/share/omarchy/default/hypr/apps/x.lua", line=1):
    return {"index": index, "file": file, "line": line, "source": "omarchy",
            "match": match, "props": props}


WINDOW = {"address": "0x1", "class": "firefox", "title": "Picture-in-Picture",
          "initialClass": "firefox", "initialTitle": "Mozilla Firefox", "tags": ["pip"],
          "workspace": "2", "floating": True, "pinned": False, "fullscreen": False,
          "xwayland": False}


class MatchTest(unittest.TestCase):
    def test_a_class_regex_matches_the_window_class(self):
        self.assertEqual(engine.matches({"class": "^(firefox)$"}, WINDOW), (True, True))

    def test_a_class_regex_that_does_not_match_is_out(self):
        self.assertEqual(engine.matches({"class": "^(kitty)$"}, WINDOW), (False, True))

    def test_every_field_in_the_match_must_hold(self):
        both = {"class": "firefox", "title": "^Picture"}
        self.assertEqual(engine.matches(both, WINDOW), (True, True))
        self.assertEqual(engine.matches({"class": "firefox", "title": "^Nope"}, WINDOW), (False, True))

    def test_booleans_match_the_window_state(self):
        self.assertEqual(engine.matches({"float": True}, WINDOW), (True, True))
        self.assertEqual(engine.matches({"pin": True}, WINDOW), (False, True))

    def test_initial_class_and_title_are_matched_too(self):
        self.assertEqual(engine.matches({"initial_title": "^Mozilla"}, WINDOW), (True, True))

    def test_a_tag_match_reads_the_window_tags(self):
        self.assertEqual(engine.matches({"tag": "pip"}, WINDOW), (True, True))
        self.assertEqual(engine.matches({"tag": "terminal"}, WINDOW), (False, True))

    def test_a_regex_python_cannot_compile_is_uncertain_not_a_crash(self):
        applies, certain = engine.matches({"class": "^(firefox"}, WINDOW)
        self.assertTrue(applies)
        self.assertFalse(certain)

    def test_an_unknown_match_field_makes_the_verdict_uncertain(self):
        applies, certain = engine.matches({"content_type": "video"}, WINDOW)
        self.assertFalse(certain)


class TagsTest(unittest.TestCase):
    def test_a_plus_tag_is_added_and_a_minus_tag_removed(self):
        self.assertEqual(engine.apply_tags({"tag": "+pip"}, ["a"]), ["a", "pip"])
        self.assertEqual(engine.apply_tags({"tag": "-a"}, ["a", "b"]), ["b"])

    def test_a_bare_tag_is_added_once(self):
        self.assertEqual(engine.apply_tags({"tag": "pip"}, ["pip"]), ["pip"])

    def test_props_without_a_tag_leave_them_alone(self):
        self.assertEqual(engine.apply_tags({"float": True}, ["a"]), ["a"])


class ResolveTest(unittest.TestCase):
    def setUp(self):
        self.window = dict(WINDOW, tags=[])
        self.rules = [
            rule(0, {"class": ".*"}, {"tag": "+default-opacity"}),
            rule(1, {"title": "(Picture.?in.?Picture)"}, {"tag": "+pip"}),
            rule(2, {"tag": "pip"}, {"float": True, "pin": True, "tag": "-default-opacity",
                                     "size": [600, 338]}),
            rule(3, {"class": "^(kitty)$"}, {"float": True}),
            rule(4, {"tag": "default-opacity"}, {"opacity": "0.985 0.96"}),
        ]

    def test_only_the_rules_whose_match_holds_are_applied(self):
        applied = engine.resolve(self.rules, self.window)["applied"]
        self.assertEqual([r["index"] for r in applied], [0, 1, 2])

    def test_a_tag_added_by_an_earlier_rule_lets_a_later_one_match(self):
        applied = engine.resolve(self.rules, self.window)["applied"]
        self.assertIn(2, [r["index"] for r in applied])

    def test_a_tag_removed_by_an_earlier_rule_stops_a_later_one(self):
        # Rule 2 removes default-opacity, so rule 4 must not apply.
        self.assertNotIn(4, [r["index"] for r in engine.resolve(self.rules, self.window)["applied"]])

    def test_the_effective_value_of_a_property_names_the_rule_that_set_it(self):
        effective = engine.resolve(self.rules, self.window)["effective"]
        self.assertEqual(effective["float"]["value"], True)
        self.assertEqual(effective["float"]["index"], 2)
        self.assertEqual(effective["size"]["line"], 1)

    def test_a_later_rule_overrides_an_earlier_value(self):
        rules = [rule(0, {"class": "firefox"}, {"opacity": "1 1"}),
                 rule(1, {"class": "firefox"}, {"opacity": "0.9 0.9"})]
        effective = engine.resolve(rules, self.window)["effective"]
        self.assertEqual((effective["opacity"]["value"], effective["opacity"]["index"]), ("0.9 0.9", 1))

    def test_the_simulated_tags_are_compared_with_the_real_ones(self):
        result = engine.resolve(self.rules, dict(self.window, tags=["pip"]))
        self.assertEqual(result["tags"]["simulated"], ["pip"])
        self.assertEqual(result["tags"]["actual"], ["pip"])
        self.assertFalse(result["tags"]["mismatch"])

    def test_a_simulation_that_does_not_match_reality_is_flagged(self):
        result = engine.resolve(self.rules, dict(self.window, tags=["something-else"]))
        self.assertTrue(result["tags"]["mismatch"])

    def test_tag_only_props_do_not_count_as_effective_values(self):
        # A rule whose only job is tagging should not show up as "this is what
        # is happening to your window".
        effective = engine.resolve(self.rules, self.window)["effective"]
        self.assertNotIn("tag", effective)

    def test_every_applied_rule_carries_a_one_line_summary(self):
        applied = engine.resolve(self.rules, self.window)["applied"]
        self.assertEqual(applied[2]["props_text"], "float=true pin=true size=600x338 tag=-default-opacity")

    def test_the_effective_entry_carries_a_ready_to_show_line(self):
        # I1: the Inspector's "What you end up with" block renders this
        # straight - the engine builds the display string, not QML.
        effective = engine.resolve(self.rules, self.window)["effective"]
        self.assertEqual(effective["size"]["text"], "size=600x338")
        self.assertEqual(effective["float"]["text"], "float=true")


if __name__ == "__main__":
    unittest.main()
