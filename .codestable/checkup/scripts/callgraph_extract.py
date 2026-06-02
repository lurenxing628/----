#!/usr/bin/env python3
"""函数级调用图 + 关键值数据流追踪（水下债普查·第二遍图驱动底座）。

补足模块级 import 图看不见的：函数粒度的扇入扇出/环/桥接/孤岛 + 危险值源头流向。
嫌疑清单由图算法机械生成（消除 Agent 显著性偏差），Agent 只核验不发现。
调用消解保守+标注：能确定的画实边，不能确定的标 ambiguous，动态调用单列不画假边。
只读。产物写到 .codestable/checkup/latest/callgraph/。Py3.8 兼容。
"""
from __future__ import annotations

import ast
import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT_DIR = os.path.abspath(os.environ.get("CHECKUP_CALLGRAPH")
                          or os.path.join(HERE, "..", "latest", "callgraph"))

FIRST_PARTY_ROOTS = ("core", "web", "data", "tools", "scripts", "plugins", "desktop")
EXCLUDE = {".git", "__pycache__", ".venv", "venv", "node_modules", "vendor",
           "backups", "evidence", ".ruff_cache", ".pytest_cache", "dist", "build"}

HARDCODED_HINT = ("RESOLUTION", "DEFAULT", "ADOPTED", "FALLBACK", "PLACEHOLDER", "DUMMY", "STUB")
SENSITIVE = ("scenario_id", "plan_role", "requested_role", "is_preview", "is_simulation",
             "version", "plan_resolution", "is_superseded_by_newer_version")
SINK_WRITE = ("execute", "executemany", "insert", "update", "delete", "commit", "save", "write", "create")
SINK_RENDER = ("render", "to_dict", "jsonify", "make_response")
SINK_RESOLVE = ("resolve_plan", "resolve_version", "resolve_plan_view", "build_plan_identity")


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
            out += [os.path.join(dp, fn) for fn in fns if fn.endswith(".py")]
    return sorted(out)


def _collect(tree: ast.AST, rel: str) -> Tuple[List[Any], Dict[str, str]]:
    funcs: List[Any] = []
    imports: Dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                imports[a.asname or a.name.split(".")[0]] = a.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for a in node.names:
                imports[a.asname or a.name] = (mod + "." + a.name) if mod else a.name

    def end(n: ast.AST, fb: int) -> int:
        return int(getattr(n, "end_lineno", fb) or fb)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append({"qual": rel + "::" + node.name, "rel": rel, "line": node.lineno,
                          "end": end(node, node.lineno), "cls": None, "name": node.name, "node": node})
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funcs.append({"qual": rel + "::" + node.name + "." + sub.name, "rel": rel,
                                  "line": sub.lineno, "end": end(sub, sub.lineno),
                                  "cls": node.name, "name": sub.name, "node": sub})
    return funcs, imports


def _calls(fnode: ast.AST) -> Tuple[Set[str], Set[str], Set[str]]:
    bare, attr, dyn = set(), set(), set()
    for n in ast.walk(fnode):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                bare.add(f.id)
                if f.id in ("getattr", "__import__", "import_module"):
                    dyn.add(f.id)
            elif isinstance(f, ast.Attribute):
                attr.add(f.attr)
                if f.attr == "getattr":
                    dyn.add(f.attr)
    return bare, attr, dyn


def _dataflow(fnode: ast.AST) -> Dict[str, List[str]]:
    s_sens, s_hard, w, r, rv = set(), set(), set(), set(), set()
    for n in ast.walk(fnode):
        if isinstance(n, ast.Name):
            if n.id in SENSITIVE:
                s_sens.add(n.id)
            if n.id.isupper() and any(h in n.id for h in HARDCODED_HINT):
                s_hard.add(n.id)
        elif isinstance(n, ast.Attribute) and n.attr in SENSITIVE:
            s_sens.add(n.attr)
        elif isinstance(n, ast.Call):
            f = n.func
            c = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
            lo = c.lower()
            if any(h in lo for h in SINK_WRITE):
                w.add(c)
            if any(h in lo for h in SINK_RENDER):
                r.add(c)
            if any(h in c for h in SINK_RESOLVE):
                rv.add(c)
    return {"src_sensitive": sorted(s_sens), "src_hardcoded": sorted(s_hard),
            "sinks_write": sorted(w), "sinks_render": sorted(r), "sinks_resolve": sorted(rv)}


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    all_funcs: Dict[str, Any] = {}
    name_to_quals: Dict[str, List[str]] = defaultdict(list)
    file_funcs: Dict[str, List[Any]] = defaultdict(list)
    file_imports: Dict[str, Dict[str, str]] = {}
    parse_errors: List[str] = []

    for fp in _iter_py():
        rel = _rel(fp)
        try:
            with open(fp, encoding="utf-8", errors="replace") as fh:
                tree = ast.parse(fh.read(), filename=rel)
        except (OSError, SyntaxError) as exc:
            parse_errors.append(rel + ": " + str(exc))
            continue
        funcs, imports = _collect(tree, rel)
        file_imports[rel] = imports
        for fi in funcs:
            all_funcs[fi["qual"]] = fi
            name_to_quals[fi["name"]].append(fi["qual"])
            file_funcs[rel].append(fi)

    edges: List[Dict[str, Any]] = []
    dynamic_unresolved: List[Dict[str, Any]] = []
    dataflow_nodes: Dict[str, Any] = {}

    for qual, fi in all_funcs.items():
        bare, attr, dyn = _calls(fi["node"])
        df = _dataflow(fi["node"])
        if any(df.values()):
            dataflow_nodes[qual] = df
        if dyn:
            dynamic_unresolved.append({"func": qual, "rel": fi["rel"], "line": fi["line"], "hints": sorted(dyn)})

        local = {f["name"] for f in file_funcs[fi["rel"]] if f["cls"] is None}
        methods = {f["name"] for f in file_funcs[fi["rel"]] if f["cls"] == fi["cls"]} if fi["cls"] else set()
        imports = file_imports.get(fi["rel"], {})

        for nm in bare:
            if nm in local:
                edges.append({"from": qual, "to": fi["rel"] + "::" + nm, "kind": "local", "ambiguous": False})
            else:
                cands = name_to_quals.get(nm, [])
                kind = "import" if nm in imports else "name"
                if len(cands) == 1:
                    edges.append({"from": qual, "to": cands[0], "kind": kind, "ambiguous": False})
                elif len(cands) > 1:
                    for c in cands:
                        edges.append({"from": qual, "to": c, "kind": kind, "ambiguous": True})

        for nm in attr:
            if nm in methods:
                edges.append({"from": qual, "to": fi["rel"] + "::" + fi["cls"] + "." + nm, "kind": "self", "ambiguous": False})
            else:
                cands = name_to_quals.get(nm, [])
                if 1 <= len(cands) <= 6:
                    for c in cands:
                        if c != qual:
                            edges.append({"from": qual, "to": c, "kind": "attr", "ambiguous": True})

    fan_out: Dict[str, int] = defaultdict(int)
    fan_in: Dict[str, int] = defaultdict(int)
    for e in edges:
        if not e["ambiguous"]:
            fan_out[e["from"]] += 1
            fan_in[e["to"]] += 1

    graph_metrics: Dict[str, Any] = {}
    try:
        import networkx as nx
        G = nx.DiGraph()
        G.add_nodes_from(all_funcs.keys())
        for e in edges:
            if not e["ambiguous"]:
                G.add_edge(e["from"], e["to"])
        cycles = []
        try:
            for cyc in nx.simple_cycles(G):
                if 2 <= len(cyc) <= 8:
                    cycles.append(cyc)
                if len(cycles) >= 200:
                    break
        except Exception:
            pass
        islands = [n for n in G.nodes if G.in_degree(n) == 0 and G.out_degree(n) == 0]
        articulation: List[str] = []
        try:
            UG = G.to_undirected()
            if UG.number_of_nodes():
                largest = max(nx.connected_components(UG), key=len)
                articulation = list(nx.articulation_points(UG.subgraph(largest)))
        except Exception:
            pass
        graph_metrics = {"node_count": G.number_of_nodes(), "edge_count": G.number_of_edges(),
                         "cycle_count": len(cycles), "island_count": len(islands),
                         "articulation_count": len(articulation)}
        _w("cycles.json", cycles)
        _w("islands.json", sorted(islands))
        _w("articulation_points.json", sorted(articulation))
    except ImportError:
        graph_metrics = {"error": "networkx 不可用"}

    risk = []
    for qual, df in dataflow_nodes.items():
        fi = all_funcs[qual]
        co = []
        if df["src_hardcoded"] and (df["sinks_render"] or df["sinks_resolve"]):
            co.append("hardcoded->render/resolve(P1假冒嫌疑)")
        if df["src_sensitive"] and df["sinks_write"]:
            co.append("sensitive-identity->write(越权写入嫌疑)")
        if any(s in df["src_sensitive"] for s in ("scenario_id", "is_preview", "is_simulation")) and df["sinks_render"]:
            co.append("preview->render(预览泄漏嫌疑)")
        if co:
            risk.append({"func": qual, "rel": fi["rel"], "line": fi["line"],
                         "fan_in": fan_in.get(qual, 0), "fan_out": fan_out.get(qual, 0),
                         "co_occurrence": co, **df})
    risk.sort(key=lambda x: (-len(x["co_occurrence"]), -x["fan_in"]))

    high_fan_in = sorted(({"func": q, "rel": all_funcs[q]["rel"], "line": all_funcs[q]["line"], "fan_in": c}
                          for q, c in fan_in.items() if c >= 5), key=lambda x: -x["fan_in"])[:60]

    _w("functions.json", {q: {"rel": fi["rel"], "line": fi["line"], "end": fi["end"], "cls": fi["cls"],
                              "name": fi["name"], "fan_in": fan_in.get(q, 0), "fan_out": fan_out.get(q, 0)}
                          for q, fi in all_funcs.items()})
    _w("edges.json", edges)
    _w("dynamic_unresolved.json", dynamic_unresolved)
    _w("dataflow_nodes.json", dataflow_nodes)
    _w("risk_dataflow.json", risk)
    _w("high_fan_in.json", high_fan_in)
    summary = {"total_functions": len(all_funcs), "total_edges": len(edges),
               "confident_edges": sum(1 for e in edges if not e["ambiguous"]),
               "ambiguous_edges": sum(1 for e in edges if e["ambiguous"]),
               "dynamic_unresolved_sites": len(dynamic_unresolved),
               "dataflow_flagged_funcs": len(dataflow_nodes), "risk_dataflow_count": len(risk),
               "high_fan_in_count": len(high_fan_in), "graph_metrics": graph_metrics,
               "parse_errors": parse_errors}
    _w("summary.json", summary)

    print("=== 函数级调用图 + 数据流提取完成 ===")
    print("函数数: %d  边: %d (确信 %d / 模糊 %d)" % (summary["total_functions"], summary["total_edges"],
          summary["confident_edges"], summary["ambiguous_edges"]))
    print("动态未消解: %d  数据流命中: %d" % (summary["dynamic_unresolved_sites"], summary["dataflow_flagged_funcs"]))
    print("图指标: %s" % graph_metrics)
    print("高风险数据流路径: %d  高扇入咽喉: %d" % (summary["risk_dataflow_count"], summary["high_fan_in_count"]))
    print("\n--- 高风险数据流路径 Top 15 ---")
    for r in risk[:15]:
        print("  fan_in=%3d  %s:%d  %s" % (r["fan_in"], r["rel"], r["line"], "/".join(r["co_occurrence"])))
    print("\n产物目录: " + OUT_DIR)


def _w(name: str, obj: Any) -> None:
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    main()
