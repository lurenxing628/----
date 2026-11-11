"""
Pre-commit hook：对暂存的 Python 文件做圈复杂度门禁。
只检查本次提交变更的文件，不阻断历史遗留的高复杂度代码。

阈值：单函数圈复杂度 > 15 即报错（项目门禁；比 Radon 的 C 上限 20 更严格）。
退出码 1 = 存在超标函数，0 = 全部通过。
"""
from __future__ import annotations

import subprocess
import sys

THRESHOLD = 15  # 项目门禁：单函数复杂度 > 15 即失败


def get_staged_py_files() -> list:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        capture_output=True, text=True, encoding="utf-8",
    )
    return [f.strip() for f in result.stdout.splitlines() if f.strip().endswith(".py")]


def check_complexity(files: list) -> tuple[list, list]:
    try:
        from radon.complexity import cc_rank, cc_visit
    except ImportError:
        print("radon not installed, skipping complexity check")
        return [], []

    violations = []
    skipped = []
    for filepath in files:
        try:
            with open(filepath, encoding="utf-8", errors="replace") as fh:
                source = fh.read()
            blocks = cc_visit(source)
            for block in blocks:
                if block.complexity > THRESHOLD:
                    rank = cc_rank(block.complexity)
                    violations.append(
                        f"  {filepath}:{block.lineno} "
                        f"{block.name} complexity={block.complexity} "
                        f"(rank {rank}, project_limit<={THRESHOLD})"
                    )
        except SyntaxError as e:
            skipped.append(
                f"{filepath} - SyntaxError: {getattr(e, 'msg', str(e))} "
                f"(line {getattr(e, 'lineno', '?')})"
            )
        except OSError as e:
            skipped.append(f"{filepath} - read failed: {e}")
        except Exception as e:
            skipped.append(f"{filepath} - unexpected error: {type(e).__name__}: {e}")
    return violations, skipped


def main() -> int:
    files = get_staged_py_files()
    if not files:
        return 0

    violations, skipped = check_complexity(files)

    if skipped:
        print(f"Complexity gate WARN: skipped {len(skipped)} file(s):")
        for s in skipped[:20]:
            print(f"  - {s}")
        if len(skipped) > 20:
            print(f"  ... ({len(skipped)} total)")

    if violations:
        print(f"Complexity gate FAILED ({len(violations)} violations):")
        for v in violations:
            print(v)
        print(f"\nProject threshold: single function complexity <= {THRESHOLD}")
        print("Refactor complex functions or split into smaller units.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
