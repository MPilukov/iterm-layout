"""Unit tests for the pure parts of iterm-layout (no iTerm needed)."""
import importlib.machinery
import importlib.util
import json
import os
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
_loader = importlib.machinery.SourceFileLoader("iterm_layout", os.path.join(HERE, "..", "iterm-layout"))
_spec = importlib.util.spec_from_loader("iterm_layout", _loader)
il = importlib.util.module_from_spec(_spec)
_loader.exec_module(il)


def pane(cols, rows, cwd="/tmp", claude=None):
    return {"tty": "/dev/ttys000", "cols": cols, "rows": rows, "title": "", "cwd": cwd, "claude": claude}


class InferLayoutTests(unittest.TestCase):
    def test_single_pane(self):
        self.assertEqual(il.shape(il.infer_layout([pane(80, 24)])), "1")

    def test_side_by_side(self):
        # two 80-column panes next to each other share the height
        tree = il.infer_layout([pane(80, 40), pane(80, 40)], bounds=(0, 0, 1400, 900))
        self.assertEqual(il.shape(tree), "V(1,1)")

    def test_stacked(self):
        tree = il.infer_layout([pane(160, 20), pane(160, 20)], bounds=(0, 0, 1400, 900))
        self.assertEqual(il.shape(tree), "H(1,1)")

    def test_one_tall_and_two_stacked(self):
        # left pane full height, right column split in two
        tree = il.infer_layout([pane(80, 41), pane(80, 20), pane(80, 20)], bounds=(0, 0, 1400, 900))
        self.assertEqual(il.shape(tree), "V(1,H(1,1))")

    def test_sizes_are_stripped_from_the_tree(self):
        tree = il.infer_layout([pane(80, 40), pane(80, 40)], bounds=(0, 0, 1400, 900))
        for leaf in il.leaves(tree):
            self.assertNotIn("cols", leaf)
            self.assertNotIn("tty", leaf)


class PaneCommandTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def test_plain_shell(self):
        self.assertEqual(il.pane_command({"cwd": self.dir}, set()), "cd " + self.dir)

    def test_missing_folder_is_skipped(self):
        self.assertEqual(il.pane_command({"cwd": "/no/such/dir"}, set()), "")

    def test_claude_session_resumes_with_its_flags(self):
        p = {"cwd": self.dir, "claude": {"session": "abc", "flags": ["--model", "x y"]}}
        self.assertEqual(il.pane_command(p, set()), f"cd {self.dir} && claude --model 'x y' --resume abc")

    def test_running_session_is_not_started_twice(self):
        p = {"cwd": self.dir, "claude": {"session": "abc", "flags": []}}
        self.assertIn("already open", il.pane_command(p, {"abc"}))
        self.assertNotIn("--resume", il.pane_command(p, {"abc"}))

    def test_without_claude_on_path_the_pane_is_a_plain_cd(self):
        p = {"cwd": self.dir, "claude": {"session": "abc", "flags": []}}
        self.assertEqual(il.pane_command(p, set(), has_claude=False), "cd " + self.dir)


class SnapshotTests(unittest.TestCase):
    def test_reads_a_saved_snapshot_and_builds_a_script(self):
        snap = {"ts": "2026-10-14 21:03:37", "windows": [{"bounds": [0, 33, 1400, 900], "tabs": [
            {"type": "V", "children": [
                {"type": "pane", "title": "", "cwd": "/tmp", "claude": None},
                {"type": "pane", "title": "", "cwd": "/tmp", "claude": {"session": "s1", "flags": []}}]}]}]}
        snap = json.loads(json.dumps(snap))
        self.assertEqual(il.counts(snap), (1, 2, 1))
        script = il.build_script(snap, set())
        self.assertIn("split vertically", script)
        self.assertIn("--resume s1", script)
        self.assertNotIn("--resume", il.build_script(snap, set(), has_claude=False))

    def test_fingerprint_ignores_time_titles_and_bounds(self):
        a = {"ts": "1", "windows": [{"bounds": [0, 0, 1, 1], "tabs": [{"type": "pane", "title": "a", "cwd": "/x"}]}]}
        b = {"ts": "2", "windows": [{"bounds": [5, 5, 9, 9], "tabs": [{"type": "pane", "title": "b", "cwd": "/x"}]}]}
        self.assertEqual(il.fingerprint(a), il.fingerprint(b))


if __name__ == "__main__":
    unittest.main()
