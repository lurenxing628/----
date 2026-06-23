#!/usr/bin/env python3
"""函数级调用图 + 关键值数据流追踪（水下债普查·第二遍图驱动底座）。

补足模块级 import 图看不见的：函数粒度的扇入扇出/环/桥接/孤岛 + 危险值源头流向。
嫌疑清单由图算法机械生成（消除 Agent 显著性偏差），Agent 只核验不发现。
调用消解保守+标注：能确定的画实边，不能确定的标 ambiguous，动态调用单列不画假边。
只读源码。产物写到 .codestable/checkup/latest/callgraph/。Py3.8 兼容。
"""
from __future__ import annotations

import ast
import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT_DIR = os.path.abspath(os.environ.get("CHECKUP_CALLGRAPH") or os.path.join(HERE, "..", "latest", "callgraph"))

if HERE not in sys.path:
    sys.path.insert(0, HERE)
import callgraph_type_index as _cti  # 类型感知 attr 消解 leaf helper(拆出以免本文件触 500 行门禁)

FIRST_PARTY_ROOTS = ("core", "web", "data", "tools", "scripts", "plugins", "desktop")
EXCLUDE = {".git", "__pycache__", ".venv", "venv", "node_modules", "vendor",
           "backups", "evidence", ".ruff_cache", ".pytest_cache", "dist", "build"}

HARDCODED_HINT = ("RESOLUTION", "DEFAULT", "ADOPTED", "FALLBACK", "PLACEHOLDER", "DUMMY", "STUB")
SENSITIVE = ("scenario_id", "plan_role", "requested_role", "is_preview", "is_simulation",
             "version", "plan_resolution", "is_superseded_by_newer_version")
SINK_WRITE = ("execute", "executemany", "insert", "update", "delete", "commit", "save", "write", "create")
SINK_RENDER = ("render", "to_dict", "jsonify", "make_response")
SINK_RESOLVE = ("resolve_plan", "resolve_version", "resolve_plan_view", "build_plan_identity")

FuncInfo = Dict[str, Any]
IndexResult = Tuple[Dict[str, FuncInfo], Dict[str, List[str]], Dict[str, List[FuncInfo]], Dict[str, Dict[str, str]], List[Tuple[str, str, List[str]]], List[str]]
EdgeResult = Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Dict[str, List[str]]]]


def _rel(p: str) -> str:
    return os.path.relpath(p, REPO_ROOT).replace("\\", "/")


def _iter_py() -> List[str]:
    out: List[str] = []
    for root in FIRST_PARTY_ROOTS:
        base = os.path.join(REPO_ROOT, root)
        if not os.path.isdir(base):
            continue
        for dp, dns, fns in os.walk(base):
            dns[:] = [d for d in dns if d not in EXCLUDE]
            out.extend(os.path.join(dp, fn) for fn in fns if fn.endswith(".py"))
    return sorted(out)


def _end_lineno(node: ast.AST, fallback: int) -> int:
    return int(getattr(node, "end_lineno", fallback) or fallback)


def _function_info(rel: str, node: ast.AST, name: str, cls: Optional[str]) -> FuncInfo:
    qual_name = f"{cls}.{name}" if cls else name
    return {
        "qual": f"{rel}::{qual_name}",
        "rel": rel,
        "line": int(getattr(node, "lineno", 0) or 0),
        "end": _end_lineno(node, int(getattr(node, "lineno", 0) or 0)),
        "cls": cls,
        "name": name,
        "node": node,
    }


def _import_aliases(tree: ast.Module) -> Dict[str, str]:
    imports: Dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports[alias.asname or alias.name] = f"{module}.{alias.name}" if module else alias.name
    return imports


def _class_bases(tree: ast.Module) -> List[Tuple[str, List[str]]]:
    out: List[Tuple[str, List[str]]] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            bases = [b.id for b in node.bases if isinstance(b, ast.Name)] + \
                    [b.attr for b in node.bases if isinstance(b, ast.Attribute)]
            out.append((node.name, bases))
    return out


def _module_functions(tree: ast.Module, rel: str) -> List[FuncInfo]:
    funcs: List[FuncInfo] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(_function_info(rel, node, node.name, None))
    return funcs


def _class_functions(tree: ast.Module, rel: str) -> List[FuncInfo]:
    funcs: List[FuncInfo] = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        for sub in node.body:
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs.append(_function_info(rel, sub, sub.name, node.name))
    return funcs


def _collect(tree: ast.Module, rel: str) -> Tuple[List[FuncInfo], Dict[str, str]]:
    return _module_functions(tree, rel) + _class_functions(tree, rel), _import_aliases(tree)


def _call_name(func: ast.AST) -> Tuple[str, str]:
    if isinstance(func, ast.Name):
        return func.id, "bare"
    if isinstance(func, ast.Attribute):
        return func.attr, "attr"
    return "", ""


def _calls(fnode: ast.AST) -> Tuple[Set[str], Set[str], Set[str]]:
    bare, attr, dyn = set(), set(), set()
    for node in ast.walk(fnode):
        if not isinstance(node, ast.Call):
            continue
        name, kind = _call_name(node.func)
        if not name:
            continue
        if kind == "bare":
            bare.add(name)
        else:
            attr.add(name)
        if name in ("getattr", "__import__", "import_module"):
            dyn.add(name)
    return bare, attr, dyn


def _remember_identifier(name: str, sensitive: Set[str], hardcoded: Set[str]) -> None:
    if name in SENSITIVE:
        sensitive.add(name)
    if name.isupper() and any(hint in name for hint in HARDCODED_HINT):
        hardcoded.add(name)


def _call_flow(name: str, writes: Set[str], renders: Set[str], resolves: Set[str]) -> None:
    lowered = name.lower()
    if any(hint in lowered for hint in SINK_WRITE):
        writes.add(name)
    if any(hint in lowered for hint in SINK_RENDER):
        renders.add(name)
    if any(hint in name for hint in SINK_RESOLVE):
        resolves.add(name)


def _dataflow(fnode: ast.AST) -> Dict[str, List[str]]:
    sensitive, hardcoded, writes, renders, resolves = set(), set(), set(), set(), set()
    for node in ast.walk(fnode):
        if isinstance(node, ast.Name):
            _remember_identifier(node.id, sensitive, hardcoded)
        elif isinstance(node, ast.Attribute):
            _remember_identifier(node.attr, sensitive, hardcoded)
        elif isinstance(node, ast.Call):
            name, _kind = _call_name(node.func)
            _call_flow(name, writes, renders, resolves)
    return {
        "src_sensitive": sorted(sensitive),
        "src_hardcoded": sorted(hardcoded),
        "sinks_write": sorted(writes),
        "sinks_render": sorted(renders),
        "sinks_resolve": sorted(resolves),
    }


def _parse_file(fp: str, rel: str) -> Tuple[Optional[ast.Module], str]:
    try:
        with open(fp, encoding="utf-8", errors="replace") as fh:
            return ast.parse(fh.read(), filename=rel), ""
    except (OSError, SyntaxError) as exc:
        return None, f"{rel}: {exc}"


def _index_codebase() -> IndexResult:
    all_funcs: Dict[str, FuncInfo] = {}
    name_to_quals: Dict[str, List[str]] = defaultdict(list)
    file_funcs: Dict[str, List[FuncInfo]] = defaultdict(list)
    file_imports: Dict[str, Dict[str, str]] = {}
    class_bases: List[Tuple[str, str, List[str]]] = []
    parse_errors: List[str] = []

    for fp in _iter_py():
        rel = _rel(fp)
        tree, error = _parse_file(fp, rel)
        if error:
            parse_errors.append(error)
            continue
        funcs, imports = _collect(tree, rel) if tree is not None else ([], {})
        file_imports[rel] = imports
        for info in funcs:
            all_funcs[info["qual"]] = info
            name_to_quals[info["name"]].append(info["qual"])
            file_funcs[rel].append(info)
        if tree is not None:
            class_bases.extend((rel, clsname, bases) for clsname, bases in _class_bases(tree))
    return all_funcs, name_to_quals, file_funcs, file_imports, class_bases, parse_errors


def _local_function_names(file_funcs: Dict[str, List[FuncInfo]], info: FuncInfo) -> Set[str]:
    return {f["name"] for f in file_funcs[info["rel"]] if f["cls"] is None}


def _method_names(file_funcs: Dict[str, List[FuncInfo]], info: FuncInfo) -> Set[str]:
    if not info["cls"]:
        return set()
    return {f["name"] for f in file_funcs[info["rel"]] if f["cls"] == info["cls"]}


def _edge(source: str, target: str, kind: str, ambiguous: bool) -> Dict[str, Any]:
    return {"from": source, "to": target, "kind": kind, "ambiguous": ambiguous}


def _edge_key(edge: Dict[str, Any]) -> Tuple[str, str, str, bool]:
    return (str(edge["from"]), str(edge["to"]), str(edge["kind"]), bool(edge["ambiguous"]))


def _add_bare_edges(edges: List[Dict[str, Any]], qual: str, info: FuncInfo, names: Set[str],
                    local: Set[str], name_to_quals: Dict[str, List[str]], imports: Dict[str, str]) -> None:
    for name in sorted(names):
        if name in local:
            edges.append(_edge(qual, f"{info['rel']}::{name}", "local", False))
            continue
        candidates = sorted(name_to_quals.get(name, []))
        kind = "import" if name in imports else "name"
        if len(candidates) == 1:
            edges.append(_edge(qual, candidates[0], kind, False))
        elif len(candidates) > 1:
            edges.extend(_edge(qual, candidate, kind, True) for candidate in candidates)


def _add_attr_edges(edges: List[Dict[str, Any]], qual: str, info: FuncInfo, names: Set[str],
                    methods: Set[str], name_to_quals: Dict[str, List[str]]) -> None:
    for name in sorted(names):
        if name in methods:
            edges.append(_edge(qual, f"{info['rel']}::{info['cls']}.{name}", "self", False))
            continue
        candidates = sorted(candidate for candidate in name_to_quals.get(name, []) if candidate != qual)
        if 1 <= len(candidates) <= 6:
            edges.extend(_edge(qual, candidate, "attr", True) for candidate in candidates)


def _resolve_edges(all_funcs: Dict[str, FuncInfo], name_to_quals: Dict[str, List[str]],
                   file_funcs: Dict[str, List[FuncInfo]], file_imports: Dict[str, Dict[str, str]]) -> EdgeResult:
    edges: List[Dict[str, Any]] = []
    dynamic_unresolved: List[Dict[str, Any]] = []
    dataflow_nodes: Dict[str, Dict[str, List[str]]] = {}
    for qual, info in sorted(all_funcs.items()):
        bare, attr, dyn = _calls(info["node"])
        dataflow = _dataflow(info["node"])
        if any(dataflow.values()):
            dataflow_nodes[qual] = dataflow
        if dyn:
            dynamic_unresolved.append({"func": qual, "rel": info["rel"], "line": info["line"], "hints": sorted(dyn)})
        _add_bare_edges(edges, qual, info, bare, _local_function_names(file_funcs, info), name_to_quals,
                        file_imports.get(info["rel"], {}))
        _add_attr_edges(edges, qual, info, attr, _method_names(file_funcs, info), name_to_quals)
    return edges, dynamic_unresolved, dataflow_nodes


def _attr_method(to_qual: str) -> str:
    return to_qual.split("::", 1)[-1].split(".")[-1]


def _merge_typed(edges: List[Dict[str, Any]], typed: Set[Tuple[str, str]],
                 fully: Dict[Tuple[str, str], Set[str]]) -> List[Dict[str, Any]]:
    """用类型消解结果改写边:命中 typed 的 attr 模糊边升为 typed 实线;整组已定位的删假候选。

    typed/fully 由 callgraph_type_index.resolve_all 给出（self/参数注解/局部注解/构造/带返回注解
    的赋值 -> 唯一真实方法）。typed 边只在该 (from,to) 尚非确信边时补回，避免与现有边重复计数。
    """
    merged: List[Dict[str, Any]] = []
    for edge in edges:
        if edge["ambiguous"] and edge["kind"] == "attr":
            if (edge["from"], edge["to"]) in typed:
                continue  # 升级为 typed，稍后统一补回
            if (edge["from"], _attr_method(edge["to"])) in fully:
                continue  # 整组已类型定位，此候选为假，删除
        merged.append(edge)
    confident = {(edge["from"], edge["to"]) for edge in merged if not edge["ambiguous"]}
    for source, target in sorted(typed):
        if (source, target) not in confident:
            merged.append(_edge(source, target, "typed", False))
            confident.add((source, target))
    return merged


def _fan_counts(edges: List[Dict[str, Any]]) -> Tuple[Dict[str, int], Dict[str, int]]:
    fan_out: Dict[str, int] = defaultdict(int)
    fan_in: Dict[str, int] = defaultdict(int)
    for edge in edges:
        if edge["ambiguous"]:
            continue
        fan_out[edge["from"]] += 1
        fan_in[edge["to"]] += 1
    return fan_in, fan_out


def _write_json(name: str, obj: Any) -> None:
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        fh.write("\n")


def _cycle_key(cycle: List[str]) -> List[str]:
    if not cycle:
        return []
    smallest = min(range(len(cycle)), key=lambda idx: cycle[idx])
    return cycle[smallest:] + cycle[:smallest]


def _bounded_cycles(nx: Any, graph: Any) -> List[List[str]]:
    cycles: List[List[str]] = []
    for cycle in nx.simple_cycles(graph):
        if 2 <= len(cycle) <= 8:
            cycles.append(_cycle_key(list(cycle)))
        if len(cycles) >= 200:
            break
    return sorted(cycles)


def _articulation_points(nx: Any, graph: Any) -> List[str]:
    undirected = graph.to_undirected()
    if not undirected.number_of_nodes():
        return []
    largest = max(nx.connected_components(undirected), key=len)
    return list(nx.articulation_points(undirected.subgraph(largest)))


def _graph_metrics(all_funcs: Dict[str, FuncInfo], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        import networkx as nx
    except ImportError as exc:
        raise RuntimeError("缺少 networkx，不能生成可信的调用图指标。") from exc

    graph = nx.DiGraph()
    graph.add_nodes_from(all_funcs.keys())
    graph.add_edges_from((edge["from"], edge["to"]) for edge in edges if not edge["ambiguous"])
    cycles = _bounded_cycles(nx, graph)
    islands = [node for node in graph.nodes if graph.in_degree(node) == 0 and graph.out_degree(node) == 0]
    articulation = _articulation_points(nx, graph)
    _write_json("cycles.json", cycles)
    _write_json("islands.json", sorted(islands))
    _write_json("articulation_points.json", sorted(articulation))
    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "cycle_count": len(cycles),
        "island_count": len(islands),
        "articulation_count": len(articulation),
    }


def _risk_reasons(dataflow: Dict[str, List[str]]) -> List[str]:
    reasons: List[str] = []
    if dataflow["src_hardcoded"] and (dataflow["sinks_render"] or dataflow["sinks_resolve"]):
        reasons.append("hardcoded->render/resolve(P1假冒嫌疑)")
    if dataflow["src_sensitive"] and dataflow["sinks_write"]:
        reasons.append("sensitive-identity->write(越权写入嫌疑)")
    preview_sources = ("scenario_id", "is_preview", "is_simulation")
    if any(source in dataflow["src_sensitive"] for source in preview_sources) and dataflow["sinks_render"]:
        reasons.append("preview->render(预览泄漏嫌疑)")
    return reasons


def _risk_dataflow(dataflow_nodes: Dict[str, Dict[str, List[str]]], all_funcs: Dict[str, FuncInfo],
                   fan_in: Dict[str, int], fan_out: Dict[str, int]) -> List[Dict[str, Any]]:
    risk: List[Dict[str, Any]] = []
    for qual, dataflow in dataflow_nodes.items():
        reasons = _risk_reasons(dataflow)
        if not reasons:
            continue
        info = all_funcs[qual]
        risk.append({"func": qual, "rel": info["rel"], "line": info["line"],
                     "fan_in": fan_in.get(qual, 0), "fan_out": fan_out.get(qual, 0),
                     "co_occurrence": reasons, **dataflow})
    return sorted(risk, key=lambda item: (-len(item["co_occurrence"]), -item["fan_in"], item["rel"], item["line"], item["func"]))


def _high_fan_in(all_funcs: Dict[str, FuncInfo], fan_in: Dict[str, int]) -> List[Dict[str, Any]]:
    rows = (
        {"func": qual, "rel": all_funcs[qual]["rel"], "line": all_funcs[qual]["line"], "fan_in": count}
        for qual, count in fan_in.items() if count >= 5
    )
    return sorted(rows, key=lambda item: (-item["fan_in"], item["rel"], item["line"], item["func"]))[:60]


def _functions_payload(all_funcs: Dict[str, FuncInfo], fan_in: Dict[str, int],
                       fan_out: Dict[str, int]) -> Dict[str, Dict[str, Any]]:
    return {
        qual: {"rel": info["rel"], "line": info["line"], "end": info["end"], "cls": info["cls"],
               "name": info["name"], "fan_in": fan_in.get(qual, 0), "fan_out": fan_out.get(qual, 0)}
        for qual, info in all_funcs.items()
    }


def _summary(all_funcs: Dict[str, FuncInfo], edges: List[Dict[str, Any]],
             dynamic_unresolved: List[Dict[str, Any]], dataflow_nodes: Dict[str, Dict[str, List[str]]],
             risk: List[Dict[str, Any]], high_fan_in: List[Dict[str, Any]],
             graph_metrics: Dict[str, Any], parse_errors: List[str]) -> Dict[str, Any]:
    return {
        "total_functions": len(all_funcs),
        "total_edges": len(edges),
        "confident_edges": sum(1 for edge in edges if not edge["ambiguous"]),
        "ambiguous_edges": sum(1 for edge in edges if edge["ambiguous"]),
        "typed_edges": sum(1 for edge in edges if edge["kind"] == "typed"),
        "dynamic_unresolved_sites": len(dynamic_unresolved),
        "dataflow_flagged_funcs": len(dataflow_nodes),
        "risk_dataflow_count": len(risk),
        "high_fan_in_count": len(high_fan_in),
        "graph_metrics": graph_metrics,
        "parse_errors": parse_errors,
    }


def _write_outputs(all_funcs: Dict[str, FuncInfo], edges: List[Dict[str, Any]],
                   dynamic_unresolved: List[Dict[str, Any]], dataflow_nodes: Dict[str, Dict[str, List[str]]],
                   fan_in: Dict[str, int], fan_out: Dict[str, int], parse_errors: List[str]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    edges = sorted(edges, key=_edge_key)
    dynamic_unresolved = sorted(dynamic_unresolved, key=lambda item: (item["rel"], item["line"], item["func"]))
    graph_metrics = _graph_metrics(all_funcs, edges)
    risk = _risk_dataflow(dataflow_nodes, all_funcs, fan_in, fan_out)
    high_fan_in = _high_fan_in(all_funcs, fan_in)
    summary = _summary(all_funcs, edges, dynamic_unresolved, dataflow_nodes, risk, high_fan_in, graph_metrics, parse_errors)
    _write_json("functions.json", _functions_payload(all_funcs, fan_in, fan_out))
    _write_json("edges.json", edges)
    _write_json("dynamic_unresolved.json", dynamic_unresolved)
    _write_json("dataflow_nodes.json", dataflow_nodes)
    _write_json("risk_dataflow.json", risk)
    _write_json("high_fan_in.json", high_fan_in)
    _write_json("summary.json", summary)
    return summary, risk


def _raise_parse_errors(parse_errors: List[str]) -> None:
    if not parse_errors:
        return
    details = "\n".join(f"- {error}" for error in parse_errors[:20])
    if len(parse_errors) > 20:
        details += f"\n- 还有 {len(parse_errors) - 20} 个文件解析失败"
    raise RuntimeError(f"调用图扫描解析源码失败，不能产出可信调用图：\n{details}")


def _print_summary(summary: Dict[str, Any], risk: List[Dict[str, Any]]) -> None:
    print("=== 函数级调用图 + 数据流提取完成 ===")
    print(
        f"函数数: {summary['total_functions']}  边: {summary['total_edges']} "
        f"(确信 {summary['confident_edges']} / 模糊 {summary['ambiguous_edges']})"
    )
    print(f"动态未消解: {summary['dynamic_unresolved_sites']}  数据流命中: {summary['dataflow_flagged_funcs']}")
    print(f"图指标: {summary['graph_metrics']}")
    print(f"高风险数据流路径: {summary['risk_dataflow_count']}  高扇入咽喉: {summary['high_fan_in_count']}")
    print("\n--- 高风险数据流路径 Top 15 ---")
    for row in risk[:15]:
        print(f"  fan_in={row['fan_in']:3d}  {row['rel']}:{row['line']}  {'/'.join(row['co_occurrence'])}")
    print("\n产物目录: " + OUT_DIR)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    all_funcs, name_to_quals, file_funcs, file_imports, class_bases, parse_errors = _index_codebase()
    _raise_parse_errors(parse_errors)
    edges, dynamic_unresolved, dataflow_nodes = _resolve_edges(all_funcs, name_to_quals, file_funcs, file_imports)
    typed, fully = _cti.resolve_all(all_funcs, class_bases)
    edges = _merge_typed(edges, typed, fully)
    fan_in, fan_out = _fan_counts(edges)
    summary, risk = _write_outputs(all_funcs, edges, dynamic_unresolved, dataflow_nodes, fan_in, fan_out, parse_errors)
    _print_summary(summary, risk)


if __name__ == "__main__":
    main()
