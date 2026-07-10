#!/usr/bin/env python3
"""APS Checkup 全项目静态分析提取器。

目的：用 AST 把整个项目的可机械验证事实提取成结构化 JSON，作为后续审计
共享真值表，避免每个审查者各自 grep、各凭感觉。

只读、不修改任何源码。产物默认写到 .codestable/checkup/latest/codemap/。

提取内容：
1. modules.json     —— 每个 .py 模块：路径、所属层、行数、import 的一方依赖、定义的函数/类
2. import_edges.json —— 模块级 import 有向边（仅一方包 core/web/data/tools/scripts）
3. defs.json        —— 每个顶层/类级函数与类的定义清单（名字、所在文件:行、是否下划线私有、参数数）
4. symbol_index.json —— 符号名 -> 定义位置列表（用于发现重名定义/疑似重复）
5. func_bodies.json —— 小函数（<=12 行）的归一化函数体指纹，用于发现复制粘贴
6. layering.json    —— 跨层 import 违规候选（按 ARCHITECTURE 声明的红线）
7. summary.json     —— 汇总统计

运行：python3 .codestable/checkup/scripts/codemap_extract.py
可用 CHECKUP_OUT 指向临时目录，先比较再决定是否更新正式快照。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
# 输出到稳定的 .codestable/checkup/latest/codemap（数据与脚本分家；可用环境变量 CHECKUP_OUT 覆盖）
OUT_DIR = os.environ.get("CHECKUP_OUT") or os.path.join(HERE, "..", "latest", "codemap")
OUT_DIR = os.path.abspath(OUT_DIR)

# 纳入分析的一方源码根（排除 tests/ —— 它单独由门禁专题处理；排除 vendor/backups/evidence）
FIRST_PARTY_ROOTS = ("core", "web", "data", "tools", "scripts", "plugins", "desktop")
# 纯第一方包前缀（用于判定 import 是否一方依赖）
FIRST_PARTY_PKGS = ("core", "web", "data", "tools", "scripts", "plugins", "desktop", "config")

EXCLUDE_DIR_PARTS = {".git", "__pycache__", ".venv", "venv", "node_modules", "vendor",
                     "backups", "evidence", ".ruff_cache", ".pytest_cache", "dist", "build"}


def _rel(path: str) -> str:
    return os.path.relpath(path, REPO_ROOT).replace("\\", "/")


def _layer_of(rel_path: str) -> str:
    p = rel_path
    if p.startswith("core/services/scheduler/run/"):
        return "core.services.scheduler.run"
    if p.startswith("core/services/scheduler/"):
        return "core.services.scheduler"
    if p.startswith("core/services/report/"):
        return "core.services.report"
    if p.startswith("core/services/"):
        return "core.services.other"
    if p.startswith("core/models/"):
        return "core.models"
    if p.startswith("core/algorithms/"):
        return "core.algorithms"
    if p.startswith("core/infrastructure/"):
        return "core.infrastructure"
    if p.startswith("core/shared/"):
        return "core.shared"
    if p.startswith("core/plugins/"):
        return "core.plugins"
    if p.startswith("data/repositories/"):
        return "data.repositories"
    if p.startswith("web/routes/domains/"):
        return "web.routes.domains"
    if p.startswith("web/routes/"):
        return "web.routes"
    if p.startswith("web/viewmodels/"):
        return "web.viewmodels"
    if p.startswith("web/bootstrap/"):
        return "web.bootstrap"
    if p.startswith("web/"):
        return "web.other"
    if p.startswith("tools/"):
        return "tools"
    if p.startswith("scripts/"):
        return "scripts"
    return p.split("/", 1)[0]


def _iter_py_files() -> List[str]:
    out: List[str] = []
    for root in FIRST_PARTY_ROOTS:
        base = os.path.join(REPO_ROOT, root)
        if not os.path.isdir(base):
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIR_PARTS]
            for fn in filenames:
                if fn.endswith(".py"):
                    out.append(os.path.join(dirpath, fn))
    return sorted(out)


def _module_name(rel_path: str) -> str:
    """rel 路径 -> 点分模块名（去掉 .py，__init__ 归到包）。"""
    p = rel_path[:-3]  # strip .py
    if p.endswith("/__init__"):
        p = p[: -len("/__init__")]
    return p.replace("/", ".")


def _resolve_relative(module_name: str, node: ast.ImportFrom) -> Optional[str]:
    """把 from . / from .. 解析成绝对点分模块名（基于当前模块名）。"""
    level = int(getattr(node, "level", 0) or 0)
    if level == 0:
        return node.module
    parts = module_name.split(".")
    # __init__ 已归并到包名；普通模块的相对导入以其所在包为基准
    base = parts[:-level] if len(parts) >= level else []
    tail = (node.module or "").split(".") if node.module else []
    resolved = base + [t for t in tail if t]
    return ".".join(resolved) if resolved else None


def _is_first_party(mod: Optional[str]) -> bool:
    if not mod:
        return False
    root = mod.split(".", 1)[0]
    return root in FIRST_PARTY_PKGS


def _norm_body_fingerprint(node: ast.AST) -> str:
    """对函数体做结构归一化指纹：抹掉变量名/常量值，只留结构，用于发现复制粘贴。

    使用 ast.dump 但不含 attributes（行号），再剥离字符串/数字常量值。
    """
    class _Scrub(ast.NodeTransformer):
        def visit_Constant(self, n: ast.Constant) -> ast.AST:
            return ast.copy_location(ast.Constant(value="__C__"), n)

    try:
        scrubbed = _Scrub().visit(ast.parse(ast.unparse(node)) if hasattr(ast, "unparse") else node)
    except Exception:
        scrubbed = node
    try:
        dumped = ast.dump(scrubbed, annotate_fields=False, include_attributes=False)
    except TypeError:
        dumped = ast.dump(scrubbed)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:16]


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    files = _iter_py_files()

    modules: Dict[str, Any] = {}
    import_edges: List[Dict[str, str]] = []
    defs: List[Dict[str, Any]] = []
    symbol_index: Dict[str, List[str]] = defaultdict(list)
    func_bodies: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    parse_errors: List[str] = []

    modname_by_rel: Dict[str, str] = {}
    for fp in files:
        modname_by_rel[_rel(fp)] = _module_name(_rel(fp))

    for fp in files:
        rel = _rel(fp)
        modname = modname_by_rel[rel]
        layer = _layer_of(rel)
        try:
            with open(fp, encoding="utf-8", errors="replace") as fh:
                src = fh.read()
        except OSError as exc:
            parse_errors.append(f"{rel}: read error {exc}")
            continue
        nlines = src.count("\n") + 1
        try:
            tree = ast.parse(src, filename=rel)
        except SyntaxError as exc:
            parse_errors.append(f"{rel}:{exc.lineno}: SyntaxError {exc.msg}")
            modules[modname] = {"rel": rel, "layer": layer, "lines": nlines,
                                "parse_error": True, "imports": [], "defs": []}
            continue

        fp_imports: Set[str] = set()
        local_defs: List[str] = []

        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_first_party(alias.name):
                        fp_imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                resolved = _resolve_relative(modname, node)
                if _is_first_party(resolved):
                    fp_imports.add(resolved)

        # 顶层 def/class + 类内方法
        def _record_def(
            name: str,
            lineno: int,
            kind: str,
            args: int,
            parent: Optional[str],
            body_node: ast.AST,
            *,
            rel_path: str,
            layer_name: str,
            module_defs: List[str],
        ) -> None:
            module_defs.append(name)
            defs.append({
                "name": name, "rel": rel_path, "line": lineno, "kind": kind,
                "private": name.startswith("_"), "args": args,
                "parent": parent, "layer": layer_name,
            })
            symbol_index[name].append(f"{rel_path}:{lineno}")
            # 小函数体指纹（仅 def）
            if kind in ("function", "method"):
                body_lines = (getattr(body_node, "end_lineno", lineno) or lineno) - lineno + 1
                if body_lines <= 12:
                    fps = _norm_body_fingerprint(body_node)
                    func_bodies[fps].append({"name": name, "rel": rel_path, "line": lineno, "lines": body_lines})

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _record_def(
                    node.name,
                    node.lineno,
                    "function",
                    len(node.args.args),
                    None,
                    node,
                    rel_path=rel,
                    layer_name=layer,
                    module_defs=local_defs,
                )
            elif isinstance(node, ast.ClassDef):
                _record_def(
                    node.name,
                    node.lineno,
                    "class",
                    0,
                    None,
                    node,
                    rel_path=rel,
                    layer_name=layer,
                    module_defs=local_defs,
                )
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        _record_def(
                            sub.name,
                            sub.lineno,
                            "method",
                            len(sub.args.args),
                            node.name,
                            sub,
                            rel_path=rel,
                            layer_name=layer,
                            module_defs=local_defs,
                        )

        modules[modname] = {
            "rel": rel, "layer": layer, "lines": nlines,
            "imports": sorted(fp_imports), "defs": sorted(set(local_defs)),
        }
        for tgt in sorted(fp_imports):
            import_edges.append({"from": modname, "from_layer": layer, "to": tgt})

    # 层级图（聚合到 layer）
    layer_edges: Dict[Tuple[str, str], int] = defaultdict(int)
    for e in import_edges:
        # 目标模块名 -> 找它的 layer（若目标是包，取最近匹配）
        tgt_mod = e["to"]
        tgt_layer = None
        if tgt_mod in modules:
            tgt_layer = modules[tgt_mod]["layer"]
        else:
            # 目标可能是包名，找前缀匹配的任一模块
            for mn, mi in modules.items():
                if mn == tgt_mod or mn.startswith(tgt_mod + "."):
                    tgt_layer = mi["layer"]
                    break
        if tgt_layer:
            layer_edges[(e["from_layer"], tgt_layer)] += 1

    # 分层违规候选（ARCHITECTURE 声明的红线）
    layering_violations: List[Dict[str, Any]] = []
    for e in import_edges:
        fl, tl = e["from_layer"], e["to"]
        # 红线 1：算法层不得依赖 services
        if fl == "core.algorithms" and tl.startswith("core.services"):
            layering_violations.append({"rule": "algorithms->services", **e})
        # 红线 2：models 不得依赖 services / data / web
        if fl == "core.models" and (tl.startswith("core.services") or tl.startswith("data") or tl.startswith("web")):
            layering_violations.append({"rule": "models->upper", **e})
        # 红线 3：viewmodels 不得依赖 data / core.services / web.routes
        if fl == "web.viewmodels" and (tl.startswith("data") or tl.startswith("core.services") or tl.startswith("web.routes")):
            layering_violations.append({"rule": "viewmodels->forbidden", **e})
        # 红线 4：routes 不得直接依赖 data.repositories
        if fl in ("web.routes", "web.routes.domains") and tl.startswith("data.repositories"):
            layering_violations.append({"rule": "routes->repositories", **e})
        # 观察：业务代码依赖 tools（门禁脚手架）—— 业务不该反向依赖门禁工具
        if fl.startswith(("core", "web", "data")) and (tl == "tools" or tl.startswith("tools.")):
            layering_violations.append({"rule": "business->tools", **e})

    # 重名定义（同名符号在多文件定义，疑似重复/漂移）
    dup_symbols = {name: locs for name, locs in symbol_index.items()
                   if len(locs) >= 3 and not name.startswith("__")}
    # 复制粘贴候选（同一函数体指纹出现在多处）
    dup_bodies = {fps: occ for fps, occ in func_bodies.items() if len(occ) >= 3}

    # 写出
    def _dump(name: str, obj: Any) -> None:
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")

    # 模块级反向引用：每个模块被哪些一方模块 import（用于死代码/孤儿模块发现）
    # 注意：import 目标可能是包名或具体模块名，做前缀归并到已知模块
    rev_deps: Dict[str, Set[str]] = defaultdict(set)
    known_mods = set(modules.keys())
    for e in import_edges:
        tgt = e["to"]
        if tgt in known_mods:
            rev_deps[tgt].add(e["from"])
        else:
            # 目标是包名：把包内所有模块都视为"可能被引用"（保守，避免误报死代码）
            for mn in known_mods:
                if mn == tgt or mn.startswith(tgt + "."):
                    rev_deps[mn].add(e["from"])
    # 零被引用的模块（排除入口约定：__init__、app、launcher、__main__、scripts/tools 顶层脚本）
    orphan_candidates = []
    for mn, mi in modules.items():
        if mn in rev_deps:
            continue
        rel = mi["rel"]
        base = os.path.basename(rel)
        if base == "__init__.py" or mi["layer"] in ("scripts", "tools"):
            continue
        if base in ("app.py", "app_new_ui.py", "config.py") or rel.startswith("desktop/"):
            continue
        orphan_candidates.append({"module": mn, "rel": rel, "layer": mi["layer"], "lines": mi["lines"]})

    _dump("modules.json", modules)
    _dump("rev_deps.json", {k: sorted(v) for k, v in rev_deps.items()})
    _dump("orphan_candidates.json", sorted(orphan_candidates, key=lambda x: -x["lines"]))
    _dump("import_edges.json", import_edges)
    _dump("defs.json", defs)
    _dump("symbol_index.json", {k: v for k, v in symbol_index.items()})
    _dump("dup_symbols.json", dup_symbols)
    _dump("dup_bodies.json", dup_bodies)
    _dump("layering.json", layering_violations)
    _dump("layer_edges.json", {f"{a} -> {b}": c for (a, b), c in sorted(layer_edges.items())})

    summary = {
        "total_modules": len(modules),
        "total_lines": sum(m["lines"] for m in modules.values()),
        "parse_errors": parse_errors,
        "total_defs": len(defs),
        "total_import_edges": len(import_edges),
        "modules_by_layer": dict(sorted(
            ((lyr, sum(1 for m in modules.values() if m["layer"] == lyr))
             for lyr in {m["layer"] for m in modules.values()}), key=lambda x: -x[1])),
        "lines_by_layer": dict(sorted(
            ((lyr, sum(m["lines"] for m in modules.values() if m["layer"] == lyr))
             for lyr in {m["layer"] for m in modules.values()}), key=lambda x: -x[1])),
        "layering_violation_count_by_rule": {
            r: sum(1 for v in layering_violations if v["rule"] == r)
            for r in sorted({v["rule"] for v in layering_violations})
        },
        "dup_symbol_count": len(dup_symbols),
        "dup_body_cluster_count": len(dup_bodies),
        "dup_body_total_occurrences": sum(len(v) for v in dup_bodies.values()),
        "top_dup_symbols": dict(sorted(
            ((k, len(v)) for k, v in dup_symbols.items()), key=lambda x: -x[1])[:40]),
        "top_dup_bodies": sorted(
            ([occ[0]["name"], len(occ)] for occ in dup_bodies.values()),
            key=lambda x: -x[1])[:40],
    }
    _dump("summary.json", summary)

    # 控制台摘要
    print("=== CODEMAP 提取完成 ===")
    print(f"模块数: {summary['total_modules']}  总行数: {summary['total_lines']}  定义数: {summary['total_defs']}")
    print(f"import 边: {summary['total_import_edges']}  解析错误: {len(parse_errors)}")
    print(f"重名符号(>=3处): {summary['dup_symbol_count']}  复制函数体簇(>=3): {summary['dup_body_cluster_count']} (共 {summary['dup_body_total_occurrences']} 处)")
    print("\n--- 各层模块数 ---")
    for lyr, n in summary["modules_by_layer"].items():
        print(f"  {n:4d}  {lyr}")
    print("\n--- 分层违规候选(按规则) ---")
    for r, n in summary["layering_violation_count_by_rule"].items():
        print(f"  {n:4d}  {r}")
    print("\n--- Top 重名符号 ---")
    for k, n in list(summary["top_dup_symbols"].items())[:20]:
        print(f"  {n:3d}  {k}")
    if parse_errors:
        print("\n--- 解析错误 ---")
        for e in parse_errors[:20]:
            print(f"  {e}")
    print(f"\n产物目录: {OUT_DIR}")


if __name__ == "__main__":
    main()
