from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional, Sequence, Set, Tuple

BASELINE_NOTE = (
    "循环依赖硬加载期环基线。门禁(--fail-on-new-cycle)只挡基线外的新增环,"
    "现存环按治理节奏消除。受控更新:python3 -m tools.scan_import_cycles --update-baseline。"
)


@dataclass(frozen=True)
class CycleBaselineComparison:
    baseline_missing: bool
    new_dir: Set[str]
    new_file: Set[str]

    @property
    def has_new(self) -> bool:
        return bool(self.new_dir) or bool(self.new_file)

    @property
    def clean(self) -> bool:
        return not self.baseline_missing and not self.has_new


def default_baseline_path(repo_root: str) -> str:
    return os.path.join(repo_root, ".codestable", "checkup", "import_cycles_baseline.json")


def cycle_signature(members: Sequence[str]) -> str:
    return "|".join(sorted(members))


def current_signatures(result: dict) -> Tuple[Set[str], Set[str]]:
    dir_sigs = {cycle_signature(c["members"]) for c in result["hard_dir_cycles"]}
    file_sigs = {cycle_signature(c) for c in result["hard_file_cycles"]}
    return dir_sigs, file_sigs


def load_baseline(path: str) -> Optional[Tuple[Set[str], Set[str]]]:
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return (
        {str(x) for x in (data.get("hard_dir_cycles") or [])},
        {str(x) for x in (data.get("hard_file_cycles") or [])},
    )


def write_baseline(path: str, dir_sigs: Set[str], file_sigs: Set[str]) -> None:
    payload = {
        "note": BASELINE_NOTE,
        "schema_version": 1,
        "hard_dir_cycles": sorted(dir_sigs),
        "hard_file_cycles": sorted(file_sigs),
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.write("\n")


def compare_with_baseline(path: str, dir_sigs: Set[str], file_sigs: Set[str]) -> CycleBaselineComparison:
    baseline = load_baseline(path)
    if baseline is None:
        return CycleBaselineComparison(baseline_missing=True, new_dir=set(), new_file=set())
    base_dir, base_file = baseline
    return CycleBaselineComparison(
        baseline_missing=False,
        new_dir=dir_sigs - base_dir,
        new_file=file_sigs - base_file,
    )


def print_new_cycles(result: dict, new_dir: Set[str], new_file: Set[str]) -> None:
    print(
        f"⚠️ [import-cycles] 检出基线外新增硬加载期环:{len(new_dir)} 个目录环 + {len(new_file)} 个文件环",
        flush=True,
    )
    by_sig = {cycle_signature(c["members"]): c for c in result["hard_dir_cycles"]}
    for sig in sorted(new_dir):
        rec = by_sig.get(sig)
        members = rec["members"] if rec else sig.split("|")
        print(f"  + [目录环] {' ⇄ '.join(members)}", flush=True)
        if rec:
            for e in rec["edges"][:4]:
                extra = f"  (+{e['extra']})" if e["extra"] else ""
                print(f"        {e['src']}:{e['line']} -> {e['target']}{extra}", flush=True)
    for sig in sorted(new_file):
        print(f"  + [文件环] {' ⇄ '.join(sig.split('|'))}", flush=True)
    print(
        "  处理:新引入的环要断掉(跨包顶层 import 改延迟/类型导入,或下沉公共依赖为无反向依赖的叶子包);"
        "若确属设计接受,跑 `--update-baseline` 受控刷新基线。",
        flush=True,
    )
