#!/usr/bin/env python3
"""Preserve Git's complete pre-push stdin through the standard pre-commit hook."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Sequence


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    hook_path = Path(args[0])
    chain = hook_path.with_name("pre-push.pre-commit")
    raw_input = sys.stdin.buffer.read()
    descriptor, input_path = tempfile.mkstemp(prefix="aps-pre-push-input-")
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw_input)
        env = os.environ.copy()
        env["APS_PRE_PUSH_INPUT_FILE"] = input_path
        command = [str(chain), *args[1:]]
        if os.name == "nt":
            command.insert(0, "sh")
        return subprocess.run(command, input=raw_input, env=env).returncode
    finally:
        os.unlink(input_path)


if __name__ == "__main__":
    raise SystemExit(main())
