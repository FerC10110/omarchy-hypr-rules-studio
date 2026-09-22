"""The QML/engine boundary, which no unit test can reach from Python.

`engineCall(args, stdin, onDone)` takes stdin as a VALUE. The Process's
`onStarted` serialises it exactly once (`write(JSON.stringify(call.stdin))`),
the same contract Runbook's panel uses. A call site that hands it a string
from `JSON.stringify(...)` gets double-encoded: the engine then reads a JSON
string where it requires an object and answers "The panel sent something that
is not an object", so Save and Test on this window do nothing at all.

That is invisible to every other test here, because they all drive the engine
directly and never go through Panel.qml.
"""

import os
import re
import unittest

PANEL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Panel.qml")


def call_arguments(source, function_name):
    """Yield (line number, argument list) for every call to `function_name`.

    Splits on the commas that sit at paren/brace/bracket depth zero, so an
    object literal or a nested call stays in one piece.
    """
    for match in re.finditer(r"\b" + re.escape(function_name) + r"\(", source):
        start = match.end()
        depth, index, in_string, quote, escaped = 1, start, False, "", False
        while index < len(source) and depth > 0:
            char = source[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    in_string = False
            elif char in "\"'":
                in_string, quote = True, char
            elif char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            index += 1
        inner = source[start:index - 1]
        args, depth, current, in_string, quote, escaped = [], 0, "", False, "", False
        for char in inner:
            if in_string:
                current += char
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    in_string = False
                continue
            if char in "\"'":
                in_string, quote = True, char
            elif char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            if char == "," and depth == 0:
                args.append(current.strip())
                current = ""
            else:
                current += char
        args.append(current.strip())
        yield source[:match.start()].count("\n") + 1, args


class PanelEngineContractTest(unittest.TestCase):
    def setUp(self):
        with open(PANEL, encoding="utf-8") as handle:
            self.source = handle.read()

    def test_the_process_serialises_stdin_exactly_once(self):
        self.assertIn("write(JSON.stringify(call.stdin)", self.source,
                      "Panel.qml no longer serialises stdin in onStarted; this "
                      "contract test is checking something that moved.")

    def test_no_call_site_pre_encodes_its_stdin(self):
        offenders = []
        for line, args in call_arguments(self.source, "engineCall"):
            if len(args) >= 2 and "JSON.stringify" in args[1]:
                offenders.append("Panel.qml:%d passes %s" % (line, args[1]))
        self.assertEqual([], offenders,
                         "engineCall takes a value, not a string: onStarted "
                         "stringifies it. These call sites double-encode it, "
                         "and the engine rejects what arrives:\n  "
                         + "\n  ".join(offenders))

    def test_the_write_paths_still_send_something(self):
        """Guards the opposite mistake: dropping the payload entirely."""
        sending = {}
        for _, args in call_arguments(self.source, "engineCall"):
            command = re.search(r'"([a-z-]+)"', args[0])
            if command and len(args) >= 2:
                sending.setdefault(command.group(1), args[1])
        for command in ("save-rule", "preview"):
            self.assertIn(command, sending, command + " no longer calls the engine")
            self.assertNotEqual("undefined", sending[command],
                                command + " must send its payload on stdin")



class PanelNoticeTest(unittest.TestCase):
    """An error you cannot finish reading is the same as no error at all."""

    def setUp(self):
        with open(PANEL, encoding="utf-8") as handle:
            self.source = handle.read()

    def test_errors_do_not_clear_themselves(self):
        body = re.search(r"function showNotice\(.*?\n  \}", self.source, re.S)
        self.assertIsNotNone(body, "showNotice moved")
        self.assertIn("noticeTimer.stop()", body.group(0),
                      "an error notice must not be on the auto-clear timer")

    def test_a_confirmation_stays_long_enough_to_read(self):
        interval = re.search(r"id: noticeTimer; interval: (\d+)", self.source)
        self.assertIsNotNone(interval, "noticeTimer moved")
        self.assertGreaterEqual(int(interval.group(1)), 8000,
                                "these notices run to two lines; give them time")


if __name__ == "__main__":
    unittest.main()
