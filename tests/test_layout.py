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


def snap(ts, cwd="/tmp", name=None):
    s = {"ts": ts, "windows": [{"bounds": [0, 0, 100, 100], "tabs": [{"type": "pane", "title": "", "cwd": cwd, "claude": None}]}]}
    if name:
        s["name"] = name
    return s


class NamesAndDeleteTests(unittest.TestCase):
    """Snapshots live in a temp folder: il.DIR is pointed there for each test."""

    def setUp(self):
        self.old_dir = il.DIR
        il.DIR = tempfile.mkdtemp()
        # newest first in `list`: 3 is the newest file name
        for i in (1, 2, 3):
            il.write(os.path.join(il.DIR, f"2026010{i}-000000.json"), snap(f"2026-01-0{i} 00:00:00", cwd=f"/w{i}"))

    def tearDown(self):
        import shutil
        shutil.rmtree(il.DIR, ignore_errors=True)
        il.DIR = self.old_dir

    def ts(self, arg):
        return il.load(il.resolve(arg))["ts"]

    def test_number_resolves_in_list_order(self):
        self.assertEqual(self.ts("1"), "2026-01-03 00:00:00")
        self.assertEqual(self.ts("3"), "2026-01-01 00:00:00")

    def test_name_is_stored_in_the_snapshot_and_resolves(self):
        il.set_name("2", "work")
        self.assertEqual(self.ts("work"), "2026-01-02 00:00:00")
        self.assertEqual([os.path.basename(f) for f in il.snapshots()],
                         ["20260103-000000.json", "20260102-000000.json", "20260101-000000.json"])

    def test_empty_name_removes_it(self):
        il.set_name("2", "work")
        il.set_name("work", "")
        self.assertNotIn("name", il.load(il.resolve("2")))
        with self.assertRaises(SystemExit):
            il.resolve("work")

    def test_numeric_name_is_refused(self):
        with self.assertRaises(SystemExit):
            il.set_name("1", "42")

    def test_same_name_picks_the_newest(self):
        il.set_name("3", "dup")
        il.set_name("1", "dup")
        self.assertEqual(self.ts("dup"), "2026-01-03 00:00:00")

    def test_unknown_name_or_number_exits_cleanly(self):
        for arg in ("nope", "9", "0", "²"):
            with self.assertRaises(SystemExit):
                il.resolve(arg)

    def test_delete_asks_and_keeps_on_no(self):
        self.assertFalse(il.delete("1", ask=lambda _: "n"))
        self.assertEqual(len(il.snapshots()), 3)

    def test_delete_on_yes_and_with_flag(self):
        self.assertTrue(il.delete("1", ask=lambda _: "y"))
        self.assertTrue(il.delete("1", yes=True))
        self.assertEqual([il.load(f)["ts"] for f in il.snapshots()], ["2026-01-01 00:00:00"])

    def test_cleanup_keeps_named_snapshots(self):
        il.set_name("3", "keep me")   # the oldest one
        old_keep = il.KEEP
        il.KEEP = 1
        try:
            il.prune()
        finally:
            il.KEEP = old_keep
        names = [(il.load(f)["ts"], il.load(f).get("name")) for f in il.snapshots()]
        self.assertEqual(names, [("2026-01-03 00:00:00", None), ("2026-01-01 00:00:00", "keep me")])

    def test_empty_selector_is_refused(self):
        for arg in ("", "  "):
            with self.assertRaises(SystemExit):
                il.resolve(arg)
        self.assertEqual(len(il.snapshots()), 3)

    def test_number_refers_to_the_list_that_was_shown(self):
        shown = il.snapshots()
        il.write(os.path.join(il.DIR, "20260109-000000.json"), snap("2026-01-09 00:00:00"))   # saved meanwhile
        self.assertEqual(il.load(il.resolve("1", shown))["ts"], "2026-01-03 00:00:00")

    def test_failed_write_keeps_the_old_file(self):
        path = il.snapshots()[0]
        before = open(path).read()
        with self.assertRaises(TypeError):
            il.write(path, {"ts": "x", "bad": object()})   # not JSON-serialisable mid-dump
        self.assertEqual(open(path).read(), before)
        self.assertEqual([f for f in os.listdir(il.DIR) if f.endswith(".tmp")], [])

    def test_yes_flag_is_only_parsed_for_delete(self):
        import sys
        argv = sys.argv
        try:
            sys.argv = ["iterm-layout", "name", "2", "--yes"]
            il.main()   # "--yes" is the name here, not a flag
        finally:
            sys.argv = argv
        self.assertEqual(il.load(il.resolve("2"))["name"], "--yes")

    def test_name_does_not_change_the_fingerprint(self):
        self.assertEqual(il.fingerprint(snap("a", name="x")), il.fingerprint(snap("b")))


if __name__ == "__main__":
    unittest.main()
