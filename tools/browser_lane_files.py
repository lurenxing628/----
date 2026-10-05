"""Compatibility inventory for the retired heavy browser test lane.

The browser tests were deleted. Pure Node contracts belong to the retained
pytest suite; there are no tests excluded into a separate browser lane.
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional, Sequence, Tuple

BROWSER_LANE_FILES: Tuple[str, ...] = ()


def is_browser_lane_file(path: str) -> bool:
    return str(path).replace("\\", "/") in BROWSER_LANE_FILES


def iter_test_files(root: str = "tests") -> List[str]:
    found = []
    for directory, _, filenames in os.walk(root):
        for name in filenames:
            if name.startswith("test_") and name.endswith(".py"):
                found.append(os.path.join(directory, name).replace("\\", "/"))
    return sorted(found)


def compute_browser_lane(required_paths: Sequence[str]) -> List[str]:
    del required_paths
    return list(BROWSER_LANE_FILES)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args not in (["--check"], ["--print"]):
        print("usage: python -m tools.browser_lane_files --check | --print", file=sys.stderr)
        return 2
    if args == ["--check"]:
        print("Browser lane retired: 0 files; retained Node contracts run in pytest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
