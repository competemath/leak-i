"""loogle's imports of the tree's copy of Batteries follow the names the pinned tree has.

loogle imports four files of Batteries (Util.Cache, Data.String.Matcher, Util.Pickle, Data.Array). The tree carries that copy as `Tengoku.Std.X` before its seed move
(2026-10-05) and as `Tengoku.Seed.Std.X` after it, and loogle-tengoku.patch names the old ones. A loogle built with the old names, run on a tree with the new ones, loads the
stale old copy beside the new one and stops: "import Tengoku.Std.Data.Array.Match failed, environment already contains ... from Tengoku.Seed.Std.Data.Array.Match" (this Space, from
2026-10-14). So the names are set from the tree, before every build of loogle: `adapt` is idempotent and goes both ways.
"""

from __future__ import annotations

import re
from pathlib import Path

FILES = ("Loogle/Cache.lean", "Loogle/Find.lean", "Loogle/Trie.lean", "LoogleMathlibCache.lean")
OLD, SEED = "Tengoku.Std.", "Tengoku.Seed.Std."


def tree_uses_seed(tengoku_dir: str | Path) -> bool:
    """Does the pinned tree carry the Batteries copy under Tengoku/Seed/Std (after the seed move)?"""
    return (Path(tengoku_dir) / "Tengoku" / "Seed" / "Std").is_dir()


def adapt(loogle_dir: str | Path, tengoku_dir: str | Path) -> list[str]:
    """Rewrite the `import` lines of loogle's sources to the names the tree has. Returns the files that changed (so the caller knows loogle has to be built again)."""
    src, dst = (OLD, SEED) if tree_uses_seed(tengoku_dir) else (SEED, OLD)
    pattern = re.compile(r"^(import\s+)" + re.escape(src), re.M)
    changed = []
    for rel in FILES:
        path = Path(loogle_dir) / rel
        try:
            with path.open(encoding="utf-8", newline="") as f:  # newline="": line endings are kept as they are
                text = f.read()
        except OSError:
            continue
        fixed = pattern.sub(lambda m: m.group(1) + dst, text)
        if fixed != text:
            with path.open("w", encoding="utf-8", newline="") as f:
                f.write(fixed)
            changed.append(rel)
    return changed
