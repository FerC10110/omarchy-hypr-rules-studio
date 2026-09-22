"""A stand-in for subprocess.run: answers by command, records every call."""
import subprocess


class FakeRun:
    def __init__(self, answers):
        """answers: {"<argv joined by spaces>": (returncode, stdout, stderr)}"""
        self.answers = answers
        self.calls = []

    def __call__(self, argv, **kwargs):
        key = " ".join(argv)
        self.calls.append(key)
        code, out, err = self.answers.get(key, (127, "", "not stubbed: " + key))
        return subprocess.CompletedProcess(argv, code, out, err)


CLIENTS = """[
  {"address": "0x1", "class": "kitty", "title": "nvim", "initialClass": "kitty",
   "initialTitle": "kitty", "tags": ["terminal*"], "floating": false, "pinned": false,
   "fullscreen": 0, "xwayland": false, "workspace": {"id": 1, "name": "1"}},
  {"address": "0x2", "class": "firefox", "title": "Picture-in-Picture",
   "initialClass": "firefox", "initialTitle": "Mozilla Firefox", "tags": [],
   "floating": true, "pinned": true, "fullscreen": 0, "xwayland": false,
   "workspace": {"id": 2, "name": "2"}}
]"""
