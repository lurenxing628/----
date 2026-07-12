from __future__ import annotations

import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple


def module_from_path(rel: str) -> str:
    parts = rel[:-3].replace("\\", "/").split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def current_package_parts(path: str, module: str) -> List[str]:
    parts = module.split(".")
    return parts if os.path.basename(path) == "__init__.py" else parts[:-1]


def target_directory(module: str, mod_to_file: Dict[str, str], repo_root: str) -> Optional[str]:
    path = mod_to_file.get(module)
    if not path:
        return None
    return os.path.dirname(os.path.relpath(path, repo_root)).replace("\\", "/") or "."


def adjacency(edge_map: Dict[Tuple[str, str], list]) -> Dict[str, List[str]]:
    rows: Dict[str, set] = defaultdict(set)
    for source, target in edge_map:
        rows[source].add(target)
    return {source: list(targets) for source, targets in rows.items()}


def merge_edges(*maps: Dict[Tuple[str, str], list]) -> Dict[Tuple[str, str], list]:
    merged: Dict[Tuple[str, str], list] = defaultdict(list)
    for edge_map in maps:
        for edge, locations in edge_map.items():
            merged[edge].extend(locations)
    return merged


def dir_cycle_records(sccs: List[List[str]], dmap: Dict[Tuple[str, str], list]) -> List[dict]:
    records: List[dict] = []
    for component in sorted(sccs, key=len, reverse=True):
        members = set(component)
        by_module_edge: Dict[Tuple[str, str], list] = defaultdict(list)
        for (source_dir, target_dir), locations in dmap.items():
            if source_dir not in members or target_dir not in members:
                continue
            for rel, line, target_mod in locations:
                by_module_edge[(module_from_path(rel), target_mod)].append((rel, line))
        evidence: List[dict] = []
        for (source_mod, target_mod), locations in sorted(by_module_edge.items()):
            rel, line = sorted(locations, key=lambda item: (item[0], item[1]))[0]
            evidence.append(
                {
                    "source": source_mod,
                    "target": target_mod,
                    "src": rel,
                    "line": line,
                    "extra": len(locations) - 1,
                }
            )
        records.append({"members": sorted(component), "edges": evidence})
    return records


def file_cycle_records(sccs: List[List[str]], fmap: Dict[Tuple[str, str], list]) -> List[dict]:
    records: List[dict] = []
    for component in sorted(sccs, key=len, reverse=True):
        members = set(component)
        evidence: List[dict] = []
        for (source_mod, target_mod), locations in sorted(fmap.items()):
            if source_mod not in members or target_mod not in members:
                continue
            rel, line = sorted(locations, key=lambda item: (item[0], item[1]))[0]
            evidence.append(
                {
                    "source": source_mod,
                    "target": target_mod,
                    "src": rel,
                    "line": line,
                    "extra": len(locations) - 1,
                }
            )
        records.append({"members": sorted(component), "edges": evidence})
    return records


def _runtime_cycle_record(component: List[str], runtime_dir: dict) -> dict:
    members = set(component)
    evidence: List[dict] = []
    for (source, target), locations in runtime_dir.items():
        if source in members and target in members:
            rel, line, target_mod = locations[0]
            evidence.append(
                {"src": rel, "line": line, "target": target_mod, "extra": len(locations) - 1}
            )
    return {"members": sorted(component), "edges": evidence}


def delayed_dir_cycle_records(
    runtime_sccs: List[List[str]],
    hard_sccs: List[List[str]],
    runtime_dir: dict,
) -> List[dict]:
    hard_sets = [frozenset(component) for component in hard_sccs]
    return [
        _runtime_cycle_record(component, runtime_dir)
        for component in sorted(runtime_sccs, key=len, reverse=True)
        if not any(frozenset(component) == hard_set for hard_set in hard_sets)
    ]


def render_text(result: dict) -> str:
    lines: List[str] = []
    append = lines.append
    edge_counts = result["edge_counts"]
    append("=" * 70)
    append(f"[import-cycles] 模块文件数:{result['module_count']} | 解析失败:{len(result['parse_errors'])}")
    append(
        f"[import-cycles] 边计数  hard:{edge_counts['hard']} cond:{edge_counts['cond']} "
        f"lazy:{edge_counts['lazy']} typeonly:{edge_counts['typeonly']}"
    )
    append(f"[import-cycles] 父包初始化隐式边:{len(result['parent_package_init_edges'])}")
    for row in result["parent_package_init_edges"][:20]:
        append(f"  ^ {row['file']}:{row['line']} [{row['context']}] {row['source']} -> {row['target']}")
    if len(result["parent_package_init_edges"]) > 20:
        append(f"  ^ ... 另有 {len(result['parent_package_init_edges']) - 20} 条，完整清单见 JSON")
    append(f"[import-cycles] 未解析动态导入:{len(result['unresolved_dynamic_imports'])}")
    for row in result["unresolved_dynamic_imports"]:
        append(f"  ? {row['file']}:{row['line']} [{row['context']}] {row['expression']}")
    for row in result["parse_errors"]:
        append(f"  ! {row['file']}: {row['error']}")
    append("=" * 70)
    append("")
    append(f"① 硬加载期目录环(只 hard 边):{len(result['hard_dir_cycles'])} 个")
    for cycle in result["hard_dir_cycles"]:
        append(f"  [size={len(cycle['members'])}] {' ⇄ '.join(cycle['members'])}")
        for edge in cycle["edges"][:8]:
            extra = f"  (+{edge['extra']})" if edge["extra"] else ""
            append(f"      {edge['src']}:{edge['line']} -> {edge['target']}{extra}")
    append("")
    append(
        f"② Python 加载文件环(hard 显式边 + 父包初始化边):{len(result['hard_file_cycles'])} 个；"
        f"其中纯显式 import 文件环:{len(result['explicit_hard_file_cycles'])} 个"
    )
    for cycle in result["hard_file_cycles"]:
        append(f"  {cycle}")
    append("")
    append(f"③ 延迟/条件耦合环(运行时图新增,by-design 缓解为主):{len(result['delayed_dir_cycles'])} 个")
    for cycle in result["delayed_dir_cycles"]:
        append(f"  [size={len(cycle['members'])}] {' ⇄ '.join(cycle['members'])}")
        for edge in cycle["edges"][:4]:
            append(f"      {edge['src']}:{edge['line']} -> {edge['target']}")
    append("")
    append(
        f"[import-cycles] 运行时文件环:{result['runtime_file_cycle_count']} 个"
        f"(对比硬加载期文件环 {len(result['hard_file_cycles'])} 个；"
        f"纯显式运行时文件环 {len(result['explicit_runtime_file_cycles'])} 个)"
    )
    for cycle in result["runtime_file_cycles"]:
        append(f"  [size={len(cycle['members'])}] {' ⇄ '.join(cycle['members'])}")
        for edge in cycle["edges"][:4]:
            append(f"      {edge['src']}:{edge['line']} -> {edge['target']}")
    return "\n".join(lines)
