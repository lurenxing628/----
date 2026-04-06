from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MAIN_ISS = REPO_ROOT / "installer" / "aps_win7.iss"
LEGACY_ISS = REPO_ROOT / "installer" / "aps_win7_legacy.iss"
CHECKLIST_MD = REPO_ROOT / "installer" / "SYNC_CHECKLIST.md"

SHARED_ROUTINES = [
    "SharedDataRootPath",
    "SharedLogDirPath",
    "LegacyDataRootPath",
    "LegacyLogDirPath",
    "RegisteredMainAppDirPath",
    "AppLogDirPath",
    "AppExePathFromDir",
    "ShouldDeleteSharedData",
    "DirHasEntries",
    "HasLegacyData",
    "HasSharedData",
    "CopyDirTree",
    "TryLoadTextFile",
    "ExtractKeyValue",
    "UnescapeJsonString",
    "ExtractJsonStringValue",
    "StateDirHasRuntimeSignals",
    "ResolveHelperExeFromStateDir",
    "KnownRuntimeSignalsExist",
    "ResolveStopHelperExe",
    "AppendMessage",
    "TryDeleteDirTree",
    "HasInstallCleanupTargets",
    "CleanupMigrationPartialData",
    "TryMigrateLegacyDataBeforeInstall",
    "TryStopApsRuntimeAtDir",
    "TryStopKnownApsRuntime",
    "RunPreInstallFullWipe",
    "PrepareToInstall",
]

ROUTINE_START_RE = re.compile(r"^(function|procedure)\s+([A-Za-z0-9_]+)\b", re.IGNORECASE)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_code_section(text: str) -> str:
    marker = "[Code]"
    start = text.find(marker)
    if start < 0:
        raise RuntimeError("未找到 [Code] 段")
    return text[start + len(marker) :].strip()


def _extract_routines(code_text: str) -> dict[str, str]:
    lines = code_text.splitlines()
    starts: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        match = ROUTINE_START_RE.match(line.strip())
        if match:
            starts.append((idx, match.group(2)))

    routines: dict[str, str] = {}
    for pos, (start_idx, name) in enumerate(starts):
        end_idx = starts[pos + 1][0] if pos + 1 < len(starts) else len(lines)
        block = "\n".join(line.rstrip() for line in lines[start_idx:end_idx]).strip()
        routines[name] = block
    return routines


def _first_diff_line(left: str, right: str) -> tuple[int, str, str] | None:
    left_lines = left.splitlines()
    right_lines = right.splitlines()
    max_len = max(len(left_lines), len(right_lines))
    for idx in range(max_len):
        left_line = left_lines[idx] if idx < len(left_lines) else "<EOF>"
        right_line = right_lines[idx] if idx < len(right_lines) else "<EOF>"
        if left_line != right_line:
            return idx + 1, left_line, right_line
    return None


def main() -> int:
    errors: list[str] = []

    if not CHECKLIST_MD.exists():
        errors.append(f"缺少同步清单：{CHECKLIST_MD}")
    if not MAIN_ISS.exists():
        errors.append(f"缺少主安装脚本：{MAIN_ISS}")
    if not LEGACY_ISS.exists():
        errors.append(f"缺少 legacy 安装脚本：{LEGACY_ISS}")
    if errors:
        for item in errors:
            print(f"[sync] ✗ {item}")
        return 1

    main_routines = _extract_routines(_extract_code_section(_read_text(MAIN_ISS)))
    legacy_routines = _extract_routines(_extract_code_section(_read_text(LEGACY_ISS)))

    for name in SHARED_ROUTINES:
        main_block = main_routines.get(name)
        legacy_block = legacy_routines.get(name)
        if main_block is None:
            errors.append(f"主安装脚本缺少共享例程：{name}")
            continue
        if legacy_block is None:
            errors.append(f"legacy 安装脚本缺少共享例程：{name}")
            continue
        if main_block != legacy_block:
            diff = _first_diff_line(main_block, legacy_block)
            if diff is None:
                errors.append(f"共享例程不一致：{name}")
            else:
                line_no, left_line, right_line = diff
                errors.append(
                    f"共享例程漂移：{name} 第 {line_no} 行不一致\n"
                    f"  main  : {left_line}\n"
                    f"  legacy: {right_line}"
                )

    if errors:
        print("[sync] 发现共享实现漂移：")
        for item in errors:
            print(f"- {item}")
        return 1

    print(f"[sync] 通过：已校验 {len(SHARED_ROUTINES)} 个共享例程，主脚本与 legacy 脚本保持一致。")
    print(f"[sync] 清单文件：{CHECKLIST_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
