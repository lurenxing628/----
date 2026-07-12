from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

SCHEMA_VERSION = 2
SCOPE_PRODUCTION = "production"
SCOPE_WITH_TESTS = "production-and-tests"
BASELINE_NOTE = (
    "循环依赖硬加载期环基线。正式门禁同时锁定 scope/roots/文件加载语义，检查圈成员、"
    "圈内规范化有向模块边和含行号的未解析动态导入；删边、消圈或 SCC 缩小允许，新增债务阻断。"
)
CycleMap = Dict[str, Set[str]]
CycleEdge = Tuple[str, str]


class CycleBaselineError(ValueError):
    """基线存在但无法可信读取。"""


@dataclass
class CycleBaseline:
    scope: str
    scan_roots: Tuple[str, ...]
    file_cycle_semantics: str
    dir_cycles: CycleMap
    file_cycles: CycleMap
    unresolved_dynamic_imports: Set[str]


@dataclass
class CycleBaselineComparison:
    baseline_missing: bool
    new_dir: Set[str]
    new_file: Set[str]
    new_dir_edges: Set[CycleEdge]
    new_file_edges: Set[CycleEdge]
    new_unresolved_dynamic_imports: Set[str]

    @property
    def has_new(self) -> bool:
        return bool(
            self.new_dir
            or self.new_file
            or self.new_dir_edges
            or self.new_file_edges
            or self.new_unresolved_dynamic_imports
        )

    @property
    def clean(self) -> bool:
        return not self.baseline_missing and not self.has_new


def baseline_scope(include_tests: bool) -> str:
    return SCOPE_WITH_TESTS if include_tests else SCOPE_PRODUCTION


def default_baseline_path(repo_root: str, include_tests: bool = False) -> str:
    filename = "import_cycles_with_tests_baseline.json" if include_tests else "import_cycles_production_baseline.json"
    return os.path.join(repo_root, ".codestable", "checkup", filename)


def cycle_signature(members: Sequence[str]) -> str:
    return "|".join(sorted(str(member) for member in members))


def edge_signature(source: str, target: str) -> str:
    return f"{source} -> {target}"


def _module_from_source_path(path: str) -> str:
    normalized = str(path).replace("\\", "/")
    if normalized.endswith(".py"):
        normalized = normalized[:-3]
    if normalized.endswith("/__init__"):
        normalized = normalized[: -len("/__init__")]
    return normalized.replace("/", ".")


def _edge_from_record(record: dict) -> str:
    source = str(record.get("source") or _module_from_source_path(str(record.get("src") or ""))).strip()
    target = str(record.get("target") or "").strip()
    if not source or not target:
        raise CycleBaselineError("扫描结果中的循环边缺少 source/target，不能生成可信基线")
    return edge_signature(source, target)


def _cycle_map(records: Sequence[dict]) -> CycleMap:
    cycles: CycleMap = {}
    for record in records:
        signature = cycle_signature(record.get("members") or [])
        if not signature:
            raise CycleBaselineError("扫描结果中的循环缺少 members，不能生成可信基线")
        cycles[signature] = {_edge_from_record(edge) for edge in list(record.get("edges") or [])}
    return cycles


def current_cycle_maps(result: dict) -> Tuple[CycleMap, CycleMap]:
    return (
        _cycle_map(result.get("hard_dir_cycles") or []),
        _cycle_map(result.get("hard_file_cycle_records") or []),
    )


def current_signatures(result: dict) -> Tuple[Set[str], Set[str]]:
    dir_cycles, file_cycles = current_cycle_maps(result)
    return set(dir_cycles), set(file_cycles)


def unresolved_dynamic_signatures(result: dict) -> Set[str]:
    return {
        "|".join(
            (
                str(row.get("file") or ""),
                str(int(row.get("line") or 0)),
                str(row.get("context") or ""),
                str(row.get("expression") or ""),
            )
        )
        for row in list(result.get("unresolved_dynamic_imports") or [])
    }


def _load_cycle_rows(value: object, *, field: str, path: str) -> CycleMap:
    if not isinstance(value, list):
        raise CycleBaselineError(f"基线 {path} 的 {field} 必须是数组；请人工核对后受控重建 v{SCHEMA_VERSION} 基线")
    cycles: CycleMap = {}
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise CycleBaselineError(f"基线 {path} 的 {field}[{index}] 必须是对象")
        members = row.get("members")
        edges = row.get("edges")
        if not isinstance(members, list) or not members or not all(isinstance(item, str) and item for item in members):
            raise CycleBaselineError(f"基线 {path} 的 {field}[{index}].members 非法")
        if not isinstance(edges, list) or not all(isinstance(item, str) and " -> " in item for item in edges):
            raise CycleBaselineError(f"基线 {path} 的 {field}[{index}].edges 非法")
        signature = cycle_signature(members)
        if signature in cycles:
            raise CycleBaselineError(f"基线 {path} 的 {field} 存在重复循环成员：{signature}")
        cycles[signature] = set(edges)
    return cycles


def load_baseline(path: str, *, expected_scope: str) -> Optional[CycleBaseline]:
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CycleBaselineError(f"无法读取循环依赖基线 {path}：{exc}；请修复文件后重试") from exc
    if not isinstance(data, dict):
        raise CycleBaselineError(f"循环依赖基线 {path} 顶层必须是对象")
    version = data.get("schema_version")
    if version != SCHEMA_VERSION:
        raise CycleBaselineError(
            f"循环依赖基线 {path} 的 schema_version={version!r} 不受支持；当前只支持 {SCHEMA_VERSION}，"
            "请先查看扫描差异，再受控重建基线"
        )
    scope = str(data.get("scope") or "").strip()
    if scope != expected_scope:
        raise CycleBaselineError(
            f"循环依赖基线 {path} 的 scope={scope!r}，当前扫描要求 {expected_scope!r}；生产与含测试基线不可混用"
        )
    scan_roots = data.get("scan_roots")
    if not isinstance(scan_roots, list) or not all(isinstance(item, str) and item for item in scan_roots):
        raise CycleBaselineError(f"循环依赖基线 {path} 的 scan_roots 非法")
    file_cycle_semantics = str(data.get("file_cycle_semantics") or "").strip()
    if not file_cycle_semantics:
        raise CycleBaselineError(f"循环依赖基线 {path} 缺少 file_cycle_semantics")
    unresolved = data.get("unresolved_dynamic_imports")
    if not isinstance(unresolved, list) or not all(isinstance(item, str) and item for item in unresolved):
        raise CycleBaselineError(f"循环依赖基线 {path} 的 unresolved_dynamic_imports 非法")
    return CycleBaseline(
        scope=scope,
        scan_roots=tuple(scan_roots),
        file_cycle_semantics=file_cycle_semantics,
        dir_cycles=_load_cycle_rows(data.get("hard_dir_cycles"), field="hard_dir_cycles", path=path),
        file_cycles=_load_cycle_rows(data.get("hard_file_cycles"), field="hard_file_cycles", path=path),
        unresolved_dynamic_imports=set(unresolved),
    )


def _payload_rows(cycles: CycleMap) -> List[dict]:
    return [
        {"members": signature.split("|"), "edges": sorted(edges)}
        for signature, edges in sorted(cycles.items())
    ]


def write_baseline(path: str, result: dict, *, scope: str) -> None:
    dir_cycles, file_cycles = current_cycle_maps(result)
    scan_roots = list(result.get("scan_roots") or [])
    file_cycle_semantics = str(result.get("file_cycle_semantics") or "").strip()
    if not scan_roots or not all(isinstance(root, str) and root for root in scan_roots):
        raise CycleBaselineError("扫描结果缺少合法 scan_roots，拒绝写入不完整基线")
    if not file_cycle_semantics:
        raise CycleBaselineError("扫描结果缺少 file_cycle_semantics，拒绝写入不完整基线")
    payload = {
        "note": BASELINE_NOTE,
        "schema_version": SCHEMA_VERSION,
        "scope": scope,
        "scan_roots": scan_roots,
        "file_cycle_semantics": file_cycle_semantics,
        "hard_dir_cycles": _payload_rows(dir_cycles),
        "hard_file_cycles": _payload_rows(file_cycles),
        "unresolved_dynamic_imports": sorted(unresolved_dynamic_signatures(result)),
    }
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.write("\n")


def _baseline_supersets(signature: str, baseline: CycleMap) -> List[str]:
    members = set(signature.split("|"))
    return [
        baseline_signature
        for baseline_signature in baseline
        if members <= set(baseline_signature.split("|"))
    ]


def _new_cycle_signatures(current: CycleMap, baseline: CycleMap) -> Set[str]:
    return {
        signature
        for signature in current
        if not _baseline_supersets(signature, baseline)
    }


def _new_edges(current: CycleMap, baseline: CycleMap) -> Set[CycleEdge]:
    out: Set[CycleEdge] = set()
    for signature, edges in current.items():
        matches = _baseline_supersets(signature, baseline)
        if not matches:
            continue
        accepted_edges = set().union(*(baseline[match] for match in matches))
        out.update((signature, edge) for edge in edges - accepted_edges)
    return out


def compare_with_baseline(path: str, result: dict, *, expected_scope: str) -> CycleBaselineComparison:
    baseline = load_baseline(path, expected_scope=expected_scope)
    if baseline is None:
        return CycleBaselineComparison(True, set(), set(), set(), set(), set())
    current_roots = tuple(str(root) for root in list(result.get("scan_roots") or []))
    if current_roots != baseline.scan_roots:
        raise CycleBaselineError(
            f"循环依赖基线 {path} 的 scan_roots={list(baseline.scan_roots)!r}，"
            f"当前扫描 roots={list(current_roots)!r}；扫描范围变化必须人工核对后受控重建基线"
        )
    current_semantics = str(result.get("file_cycle_semantics") or "").strip()
    if current_semantics != baseline.file_cycle_semantics:
        raise CycleBaselineError(
            f"循环依赖基线 {path} 的 file_cycle_semantics 与当前扫描器不一致；请人工核对后受控重建基线"
        )
    current_dir, current_file = current_cycle_maps(result)
    return CycleBaselineComparison(
        baseline_missing=False,
        new_dir=_new_cycle_signatures(current_dir, baseline.dir_cycles),
        new_file=_new_cycle_signatures(current_file, baseline.file_cycles),
        new_dir_edges=_new_edges(current_dir, baseline.dir_cycles),
        new_file_edges=_new_edges(current_file, baseline.file_cycles),
        new_unresolved_dynamic_imports=(
            unresolved_dynamic_signatures(result) - baseline.unresolved_dynamic_imports
        ),
    )


def print_new_cycles(result: dict, comparison: CycleBaselineComparison) -> None:
    print(
        "⚠️ [import-cycles] 检出基线外新增硬加载期债务："
        f"{len(comparison.new_dir)} 个目录环 + {len(comparison.new_file)} 个文件环 + "
        f"{len(comparison.new_dir_edges)} 条目录圈内边 + {len(comparison.new_file_edges)} 条文件圈内边 + "
        f"{len(comparison.new_unresolved_dynamic_imports)} 个未解析动态导入",
        flush=True,
    )
    by_sig = {cycle_signature(c["members"]): c for c in result["hard_dir_cycles"]}
    for signature in sorted(comparison.new_dir):
        record = by_sig.get(signature)
        members = record["members"] if record else signature.split("|")
        print(f"  + [目录环] {' ⇄ '.join(members)}", flush=True)
        for edge in list((record or {}).get("edges") or [])[:4]:
            print(f"        {edge['src']}:{edge['line']} -> {edge['target']}", flush=True)
    for signature in sorted(comparison.new_file):
        print(f"  + [文件环] {' ⇄ '.join(signature.split('|'))}", flush=True)
    for signature, edge in sorted(comparison.new_dir_edges):
        print(f"  + [目录圈内新增边] {edge}  (圈：{' ⇄ '.join(signature.split('|'))})", flush=True)
    for signature, edge in sorted(comparison.new_file_edges):
        print(f"  + [文件圈内新增边] {edge}  (圈：{' ⇄ '.join(signature.split('|'))})", flush=True)
    for unresolved in sorted(comparison.new_unresolved_dynamic_imports):
        print(f"  + [新增未解析动态导入] {unresolved}", flush=True)
    print("  处理：先断开新增依赖；确需接受时，必须先人工核对差异，再用 --update-baseline 受控刷新。", flush=True)
