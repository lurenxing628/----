"""Compatibility CLI for the retired heavy browser test lane."""

from __future__ import annotations

import argparse
import sys
from typing import Optional, Sequence


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="The heavy browser test lane is retired.")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--report-dir", default="")
    args = parser.parse_args(argv)
    message = "Browser lane retired: its tests were deleted; retained Node contracts run with python -m pytest tests."
    print(message, file=sys.stdout if args.list else sys.stderr)
    return 0 if args.list else 2


if __name__ == "__main__":
    raise SystemExit(main())
