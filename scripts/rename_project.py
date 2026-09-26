"""Rename the skeleton's placeholder project name to your own.

Usage:

    python scripts/rename_project.py <new-name>

<new-name> is the distribution name, e.g. "order-service". This replaces
"my-project" with "order-service" and "my_project" with "order_service"
throughout the repository, renames src/my_project, and then deletes this
script, since a new project has no further use for it.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLD_DIST, OLD_PKG = "my-project", "my_project"
SKIP_DIRS = {".git", ".venv", ".mypy_cache", ".pytest_cache", ".ruff_cache"}


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"[a-z][a-z0-9-]*[a-z0-9]", sys.argv[1]):
        sys.exit(__doc__)

    new_dist = sys.argv[1]
    new_pkg = new_dist.replace("-", "_")

    for path in ROOT.rglob("*"):
        if not path.is_file() or SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        try:
            text = path.read_text()
        except UnicodeDecodeError:
            continue
        new_text = text.replace(OLD_DIST, new_dist).replace(OLD_PKG, new_pkg)
        if new_text != text:
            path.write_text(new_text)
            print(f"updated {path.relative_to(ROOT)}")

    (ROOT / "src" / OLD_PKG).rename(ROOT / "src" / new_pkg)
    print(f"renamed src/{OLD_PKG} -> src/{new_pkg}")

    Path(__file__).unlink()
    if not any(Path(__file__).parent.iterdir()):
        Path(__file__).parent.rmdir()
    print("removed scripts/rename_project.py")
    print("\nNow run: uv sync")


if __name__ == "__main__":
    main()
