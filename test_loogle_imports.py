"""loogle_imports: loogle's imports of the tree's Batteries copy follow the tree (Tengoku.Std.X before the seed move, Tengoku.Seed.Std.X after it)."""

import tempfile
import unittest
from pathlib import Path

import loogle_imports as li

OLD_FILES = {  # as loogle-tengoku.patch writes them
    "Loogle/Cache.lean": "import Tengoku.Std.Util.Cache\n\nopen Lean Meta\n",
    "Loogle/Find.lean": "import Lean\nimport Tengoku.Std.Data.String.Matcher\nimport Tengoku.Std.Util.Pickle\n\nimport Loogle.Cache\n",
    "Loogle/Trie.lean": "import Lean.Data.Format\nimport Tengoku.Std.Data.Array\n\nnamespace Loogle\n",
    "LoogleMathlibCache.lean": "import Tengoku\nimport Loogle.Find\n",
}


def build(files: dict[str, str], seed: bool):
    d = Path(tempfile.mkdtemp())
    loogle, tree = d / "loogle", d / "tengoku"
    for rel, text in files.items():
        (loogle / rel).parent.mkdir(parents=True, exist_ok=True)
        (loogle / rel).write_bytes(text.encode())
    (tree / "Tengoku" / ("Seed/Std" if seed else "Std")).mkdir(parents=True)
    return loogle, tree


def read(loogle: Path, rel: str) -> str:
    return (loogle / rel).read_bytes().decode()  # as stored: line endings are not translated


class Adapt(unittest.TestCase):
    def test_a_tree_after_the_seed_move_gets_the_seed_names(self):
        loogle, tree = build(OLD_FILES, seed=True)
        changed = li.adapt(loogle, tree)
        self.assertEqual(sorted(changed), ["Loogle/Cache.lean", "Loogle/Find.lean", "Loogle/Trie.lean"])
        self.assertEqual(read(loogle, "Loogle/Cache.lean"), "import Tengoku.Seed.Std.Util.Cache\n\nopen Lean Meta\n")
        self.assertIn("import Tengoku.Seed.Std.Data.String.Matcher\nimport Tengoku.Seed.Std.Util.Pickle\n", read(loogle, "Loogle/Find.lean"))
        self.assertIn("import Tengoku.Seed.Std.Data.Array\n", read(loogle, "Loogle/Trie.lean"))

    def test_the_other_imports_are_untouched(self):
        loogle, tree = build(OLD_FILES, seed=True)
        li.adapt(loogle, tree)
        self.assertEqual(read(loogle, "LoogleMathlibCache.lean"), OLD_FILES["LoogleMathlibCache.lean"])
        find = read(loogle, "Loogle/Find.lean")
        self.assertTrue(find.startswith("import Lean\n"))
        self.assertTrue(find.endswith("import Loogle.Cache\n"))
        self.assertIn("import Lean.Data.Format\n", read(loogle, "Loogle/Trie.lean"))

    def test_it_is_idempotent(self):
        loogle, tree = build(OLD_FILES, seed=True)
        li.adapt(loogle, tree)
        before = {rel: read(loogle, rel) for rel in OLD_FILES}
        self.assertEqual(li.adapt(loogle, tree), [])
        self.assertEqual({rel: read(loogle, rel) for rel in OLD_FILES}, before)

    def test_a_tree_before_the_seed_move_gets_the_old_names_back(self):
        loogle, tree = build(OLD_FILES, seed=True)
        li.adapt(loogle, tree)
        (tree / "Tengoku" / "Seed" / "Std").rmdir()
        (tree / "Tengoku" / "Seed").rmdir()
        (tree / "Tengoku" / "Std").mkdir()
        self.assertEqual(sorted(li.adapt(loogle, tree)), ["Loogle/Cache.lean", "Loogle/Find.lean", "Loogle/Trie.lean"])
        for rel in OLD_FILES:
            self.assertEqual(read(loogle, rel), OLD_FILES[rel])

    def test_a_tree_with_the_old_names_leaves_old_names_alone(self):
        loogle, tree = build(OLD_FILES, seed=False)
        self.assertEqual(li.adapt(loogle, tree), [])

    def test_only_import_lines_change(self):
        text = "/- see Tengoku.Std.Util.Cache -/\n-- import Tengoku.Std.Data.Array\nimport Tengoku.Std.Data.Array\ndef s := \"Tengoku.Std.\"\n"
        loogle, tree = build({"Loogle/Trie.lean": text}, seed=True)
        li.adapt(loogle, tree)
        self.assertEqual(read(loogle, "Loogle/Trie.lean"), "/- see Tengoku.Std.Util.Cache -/\n-- import Tengoku.Std.Data.Array\nimport Tengoku.Seed.Std.Data.Array\ndef s := \"Tengoku.Std.\"\n")

    def test_a_module_that_merely_starts_like_the_old_prefix_is_not_one(self):
        loogle, tree = build({"Loogle/Trie.lean": "import Tengoku.StdExtra.Foo\nimport Tengoku.Stdlib\n"}, seed=True)
        self.assertEqual(li.adapt(loogle, tree), [])

    def test_a_file_that_is_not_there_is_skipped(self):
        loogle, tree = build({"Loogle/Cache.lean": OLD_FILES["Loogle/Cache.lean"]}, seed=True)
        self.assertEqual(li.adapt(loogle, tree), ["Loogle/Cache.lean"])

    def test_indented_and_crlf_import_lines(self):
        loogle, tree = build({"Loogle/Find.lean": "import Tengoku.Std.Util.Pickle\r\nimport  Tengoku.Std.Data.Array\r\n"}, seed=True)
        li.adapt(loogle, tree)
        self.assertEqual(read(loogle, "Loogle/Find.lean"), "import Tengoku.Seed.Std.Util.Pickle\r\nimport  Tengoku.Seed.Std.Data.Array\r\n")

    def test_the_four_files_are_the_four_the_patch_changes(self):
        patch = (Path(__file__).resolve().parent / "loogle-tengoku.patch").read_text()
        for rel in li.FILES:
            self.assertIn(f"diff --git a/{rel} b/{rel}", patch)

    def test_tree_uses_seed(self):
        _, with_seed = build({}, seed=True)
        _, without = build({}, seed=False)
        self.assertTrue(li.tree_uses_seed(with_seed))
        self.assertFalse(li.tree_uses_seed(without))


class Cli(unittest.TestCase):
    """The image build runs the module as a script, after `git apply loogle-tengoku.patch` and before `lake build`."""

    def run_cli(self, seed):
        import subprocess
        import sys

        loogle, tree = build(OLD_FILES, seed=seed)
        r = subprocess.run([sys.executable, str(Path(li.__file__)), str(loogle), str(tree)], capture_output=True, text=True)
        return r, loogle

    def test_it_rewrites_for_a_seed_tree_and_says_so(self):
        r, loogle = self.run_cli(True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Seed layout", r.stdout)
        self.assertIn("3 file(s) changed", r.stdout)
        self.assertIn("import Tengoku.Seed.Std.Util.Cache", read(loogle, "Loogle/Cache.lean"))

    def test_it_leaves_an_old_tree_alone(self):
        r, loogle = self.run_cli(False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("0 file(s) changed", r.stdout)
        self.assertEqual(read(loogle, "Loogle/Cache.lean"), OLD_FILES["Loogle/Cache.lean"])

    def test_wrong_arguments_are_refused(self):
        import subprocess
        import sys

        r = subprocess.run([sys.executable, str(Path(li.__file__))], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("usage", r.stderr)

    def test_the_dockerfile_runs_it_between_the_patch_and_the_build(self):
        d = (Path(__file__).resolve().parent / "Dockerfile").read_text()
        self.assertIn("COPY --chown=user loogle-tengoku.patch loogle_imports.py ${HOME}/loogle/", d)
        run = next(ln for ln in d.splitlines() if ln.startswith("RUN git apply loogle-tengoku.patch"))
        self.assertLess(run.index("git apply"), run.index("python3 loogle_imports.py . ../tengoku"))
        self.assertLess(run.index("python3 loogle_imports.py . ../tengoku"), run.index("lake build"))


if __name__ == "__main__":
    unittest.main()
