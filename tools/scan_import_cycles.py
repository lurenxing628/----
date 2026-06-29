#!/usr/bin/env python3
"""包级 / 文件级循环依赖扫描器(import-cycle scanner)。

补 checkup 调用图 cycle_count 的盲区:cycle_count 是函数级 SCC,看不到"包与包
之间互相 import 成环"。本工具按目录(包)与文件(模块)两种粒度,用 Tarjan 求强连通
分量,定位真正可能在加载期 ImportError 的硬环。

import 四分类(决定一条 import 边算不算"加载期耦合"):
  hard      无条件顶层 import(模块加载期必执行)—— 真正可能 ImportError 的环
  cond      顶层 try / 非 TYPE_CHECKING 的 if 块内(条件加载)
  lazy      函数体内(延迟加载,by-design 拆环手段)
  typeonly  TYPE_CHECKING 块体(运行时不执行,不计入耦合)

三类结果分开报:
  ① 硬加载期目录环(只 hard 边)—— 治理重点
  ② 硬加载期文件环(只 hard 边)
  ③ 延迟/条件耦合环(运行时图相对硬加载期图新增,by-design 缓解为主)

退出码:
  0  正常(无硬加载期环,或未加 --fail-on-hard-cycle)
  1  --fail-on-hard-cycle 且检出硬加载期目录环 / 文件环
  2  工具自身错误

口径要点(经 Codex 对抗核验修正,详见 .codestable/audits/2026-06-28-circular-imports/):
  - `from . import 兄弟模块` 不连"包根"假边:仅当确有 name 来自 __init__/包符号时才连包根。
  - TYPE_CHECKING 的 else 归运行时(此前整块跳过会漏 else 边)。
  - 动态 importlib.import_module("字面量") 按顶层/函数内定 hard/lazy。
  - 运行时图 = hard + cond + lazy(排除 typeonly,运行时不执行)。

默认只扫生产代码(core/web/data/desktop/tools/scripts),排除 tests;--include-tests 纳入。
Py3.8 兼容、纯标准库。
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

PROD_ROOTS = ["core", "web", "data", "desktop", "tools", "scripts"]
TEST_ROOTS = ["tests"]
KINDS = ("hard", "cond", "lazy", "typeonly")


def path_to_mod(rel: str) -> str:
    parts = rel[:-3].split(os.sep)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def cur_pkg_parts(ab: str, mod: str) -> List[str]:
    parts = mod.split(".")
    return parts if os.path.basename(ab) == "__init__.py" else parts[:-1]


def resolve_rel(pkg: List[str], level: int, module: Optional[str]) -> str:
    base = pkg[: len(pkg) - (level - 1)]
    return ".".join(base + module.split(".")) if module else ".".join(base)


def tdir(mod: str, mod_to_file: Dict[str, str], repo_root: str) -> Optional[str]:
    f = mod_to_file.get(mod)
    return os.path.dirname(os.path.relpath(f, repo_root)) if f else None


def classify(tree: ast.AST) -> List[Tuple[ast.AST, str]]:
    """把每条 import 语句归到 hard / cond / lazy / typeonly。"""
    out: List[Tuple[ast.AST, str]] = []

    def stmt(s: ast.AST, ctx: str) -> None:
        if isinstance(s, (ast.Import, ast.ImportFrom)):
            out.append((s, ctx))
        elif isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for b in s.body:
                stmt(b, "lazy")
        elif isinstance(s, ast.ClassDef):
            for b in s.body:
                stmt(b, ctx)
        elif isinstance(s, ast.If):
            t = s.test
            tc = (isinstance(t, ast.Name) and t.id == "TYPE_CHECKING") or (
                isinstance(t, ast.Attribute) and t.attr == "TYPE_CHECKING"
            )
            if tc:
                for b in s.body:
                    stmt(b, "typeonly")
                for b in s.orelse:
                    stmt(b, ctx)  # else 运行时必执行
            else:
                for b in s.body:
                    stmt(b, "cond")
                for b in s.orelse:
                    stmt(b, "cond")
        elif isinstance(s, ast.Try):
            for b in s.body:
                stmt(b, "cond")
            for h in s.handlers:
                for b in h.body:
                    stmt(b, "cond")
            for b in s.orelse:
                stmt(b, "cond")
            for b in s.finalbody:
                stmt(b, ctx)
        elif isinstance(s, ast.With):
            for b in s.body:
                stmt(b, ctx)

    for s in tree.body:  # type: ignore[attr-defined]
        stmt(s, "hard")
    return out


def dyn_imports(tree: ast.AST) -> List[Tuple[str, bool, int]]:
    """收集 importlib.import_module("字面量"):返回 (模块, 是否在函数内, 行号)。"""
    res: List[Tuple[str, bool, int]] = []

    def walk(node: ast.AST, infunc: bool) -> None:
        for c in ast.iter_child_nodes(node):
            nf = infunc or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            if isinstance(c, ast.Call):
                f = c.func
                nm = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else None)
                if (
                    nm == "import_module"
                    and c.args
                    and isinstance(c.args[0], ast.Constant)
                    and isinstance(c.args[0].value, str)
                ):
                    res.append((c.args[0].value, nf, c.lineno))
            walk(c, nf)

    walk(tree, False)
    return res


def resolve_targets(node: ast.AST, pkg: List[str], mod_to_file: Dict[str, str]) -> List[str]:
    """把一条 import 语句解析成本仓内的目标模块列表。

    修正点:`from . import 兄弟模块` 不连"包根"假边——只有当某个 name 来自包
    __init__ 的符号(不是子模块)时,才把包根算成依赖。
    """
    tg: List[str] = []
    if isinstance(node, ast.ImportFrom):
        base = resolve_rel(pkg, node.level, node.module) if (node.level and node.level > 0) else node.module
        if not base:
            return tg
        names = [a.name for a in node.names]
        for n in names:
            if (base + "." + n) in mod_to_file:
                tg.append(base + "." + n)  # 兄弟/子模块 = 真边
        if base in mod_to_file:
            all_sub = bool(names) and all((base + "." + n) in mod_to_file for n in names)
            if not all_sub:  # 有 name 来自 __init__ 符号 -> 才依赖包根
                tg.append(base)
    else:
        for a in node.names:
            tg.append(a.name)
    return [t for t in tg if t in mod_to_file]


def tarjan(graph: Dict[str, List[str]]) -> List[List[str]]:
    """迭代版 Tarjan 求 SCC(size>1 即环);迭代避免深递归爆栈。"""
    nodes = set(graph) | {w for vs in graph.values() for w in vs}
    idx: Dict[str, int] = {}
    low: Dict[str, int] = {}
    on: Dict[str, bool] = {}
    st: List[str] = []
    sccs: List[List[str]] = []
    cnt = [0]

    def strongconnect(v: str) -> None:
        work = [(v, 0)]
        while work:
            node, pi = work[-1]
            if pi == 0:
                idx[node] = low[node] = cnt[0]
                cnt[0] += 1
                st.append(node)
                on[node] = True
            recurse = False
            nb = graph.get(node, ())
            i = pi
            while i < len(nb):
                w = nb[i]
                if w not in idx:
                    work[-1] = (node, i + 1)
                    work.append((w, 0))
                    recurse = True
                    break
                elif on.get(w):
                    low[node] = min(low[node], idx[w])
                i += 1
            if recurse:
                continue
            if low[node] == idx[node]:
                comp = []
                while True:
                    w = st.pop()
                    on[w] = False
                    comp.append(w)
                    if w == node:
                        break
                if len(comp) > 1:
                    sccs.append(comp)
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])

    for v in list(nodes):
        if v not in idx:
            strongconnect(v)
    return sccs


def _adj(edge_map: Dict[Tuple[str, str], list]) -> Dict[str, List[str]]:
    a: Dict[str, set] = defaultdict(set)
    for (s, t) in edge_map:
        a[s].add(t)
    return {k: list(v) for k, v in a.items()}


def _merge(*maps: Dict[Tuple[str, str], list]) -> Dict[Tuple[str, str], list]:
    m: Dict[Tuple[str, str], list] = defaultdict(list)
    for em in maps:
        for k, v in em.items():
            m[k].extend(v)
    return m


def _index_modules(roots: Sequence[str], repo_root: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    file_to_mod: Dict[str, str] = {}
    mod_to_file: Dict[str, str] = {}
    for root in roots:
        base = os.path.join(repo_root, root)
        if not os.path.isdir(base):
            continue
        for dp, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if f.endswith(".py"):
                    ab = os.path.join(dp, f)
                    rel = os.path.relpath(ab, repo_root)
                    m = path_to_mod(rel)
                    file_to_mod[ab] = m
                    mod_to_file[m] = ab
    return file_to_mod, mod_to_file


def _dir_cycle_records(sccs: List[List[str]], dmap: Dict[Tuple[str, str], list]) -> List[dict]:
    out: List[dict] = []
    for comp in sorted(sccs, key=len, reverse=True):
        cs = set(comp)
        ev: List[dict] = []
        for (s, t), locs in dmap.items():
            if s in cs and t in cs:
                rel, line, tmod = locs[0]
                ev.append({"src": rel, "line": line, "target": tmod, "extra": len(locs) - 1})
        out.append({"members": sorted(comp), "edges": ev})
    return out


def scan(roots: Sequence[str], repo_root: str = REPO_ROOT) -> dict:
    """扫描给定根目录,返回三类环 + 边计数 + 解析失败的结构化结果。"""
    file_to_mod, mod_to_file = _index_modules(roots, repo_root)
    edges_file = {k: defaultdict(list) for k in KINDS}
    edges_dir = {k: defaultdict(list) for k in KINDS}
    parse_errors: List[dict] = []

    for ab, mod in file_to_mod.items():
        try:
            with open(ab, encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
        except Exception as exc:
            parse_errors.append({"file": os.path.relpath(ab, repo_root), "error": str(exc)})
            continue
        pkg = cur_pkg_parts(ab, mod)
        rel = os.path.relpath(ab, repo_root)
        sd = os.path.dirname(rel)
        for node, kind in classify(tree):
            for tmod in resolve_targets(node, pkg, mod_to_file):
                if tmod == mod:
                    continue
                edges_file[kind][(mod, tmod)].append((rel, node.lineno))  # type: ignore[attr-defined]
                td = tdir(tmod, mod_to_file, repo_root)
                if td is not None and td != sd:
                    edges_dir[kind][(sd, td)].append((rel, node.lineno, tmod))  # type: ignore[attr-defined]
        for tmod, infunc, ln in dyn_imports(tree):
            if tmod in mod_to_file and tmod != mod:
                kind = "lazy" if infunc else "hard"
                edges_file[kind][(mod, tmod)].append((rel, ln))
                td = tdir(tmod, mod_to_file, repo_root)
                if td is not None and td != sd:
                    edges_dir[kind][(sd, td)].append((rel, ln, tmod))

    hard_dir = edges_dir["hard"]
    hard_file = edges_file["hard"]
    rt_dir = _merge(edges_dir["hard"], edges_dir["cond"], edges_dir["lazy"])
    rt_file = _merge(edges_file["hard"], edges_file["cond"], edges_file["lazy"])

    hard_dir_sccs = tarjan(_adj(hard_dir))
    hard_file_sccs = tarjan(_adj(hard_file))
    rt_dir_sccs = tarjan(_adj(rt_dir))
    rt_file_sccs = tarjan(_adj(rt_file))

    hardsets = [frozenset(c) for c in hard_dir_sccs]
    delayed: List[dict] = []
    for comp in sorted(rt_dir_sccs, key=len, reverse=True):
        cs = frozenset(comp)
        if any(cs == h for h in hardsets):
            continue
        cset = set(comp)
        ev: List[dict] = []
        for (s, t), locs in rt_dir.items():
            if s in cset and t in cset:
                rel, line, tmod = locs[0]
                ev.append({"src": rel, "line": line, "target": tmod, "extra": len(locs) - 1})
        delayed.append({"members": sorted(comp), "edges": ev})

    return {
        "module_count": len(file_to_mod),
        "parse_errors": parse_errors,
        "edge_counts": {k: sum(len(v) for v in edges_file[k].values()) for k in KINDS},
        "hard_dir_cycles": _dir_cycle_records(hard_dir_sccs, hard_dir),
        "hard_file_cycles": [sorted(c) for c in sorted(hard_file_sccs, key=len, reverse=True)],
        "delayed_dir_cycles": delayed,
        "runtime_file_cycle_count": len(rt_file_sccs),
    }


def render_text(result: dict) -> str:
    lines: List[str] = []
    p = lines.append
    ec = result["edge_counts"]
    p("=" * 70)
    p(f"[import-cycles] 模块文件数:{result['module_count']} | 解析失败:{len(result['parse_errors'])}")
    p(f"[import-cycles] 边计数  hard:{ec['hard']} cond:{ec['cond']} lazy:{ec['lazy']} typeonly:{ec['typeonly']}")
    p("=" * 70)
    p("")
    p(f"① 硬加载期目录环(只 hard 边):{len(result['hard_dir_cycles'])} 个")
    for c in result["hard_dir_cycles"]:
        p(f"  [size={len(c['members'])}] {' ⇄ '.join(c['members'])}")
        for e in c["edges"][:8]:
            extra = f"  (+{e['extra']})" if e["extra"] else ""
            p(f"      {e['src']}:{e['line']} -> {e['target']}{extra}")
    p("")
    p(f"② 硬加载期文件环(只 hard 边):{len(result['hard_file_cycles'])} 个")
    for c in result["hard_file_cycles"]:
        p(f"  {c}")
    p("")
    p(f"③ 延迟/条件耦合环(运行时图新增,by-design 缓解为主):{len(result['delayed_dir_cycles'])} 个")
    for c in result["delayed_dir_cycles"]:
        p(f"  [size={len(c['members'])}] {' ⇄ '.join(c['members'])}")
        for e in c["edges"][:4]:
            p(f"      {e['src']}:{e['line']} -> {e['target']}")
    p("")
    p(
        f"[import-cycles] 运行时文件环:{result['runtime_file_cycle_count']} 个"
        f"(对比硬加载期文件环 {len(result['hard_file_cycles'])} 个)"
    )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="包级/文件级循环依赖扫描器")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON(供门禁/checkup 消费)")
    parser.add_argument("--include-tests", action="store_true", help="把 tests 也纳入扫描(默认只扫生产代码)")
    parser.add_argument(
        "--fail-on-hard-cycle",
        action="store_true",
        help="检出硬加载期目录环/文件环时退出码 1(门禁用)",
    )
    parser.add_argument(
        "--quiet-when-clean",
        action="store_true",
        help="无硬加载期环时完全不输出(钩子高频跑用)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    roots = list(PROD_ROOTS) + (list(TEST_ROOTS) if args.include_tests else [])
    try:
        result = scan(roots)
    except Exception as exc:
        print(f"[import-cycles] 扫描失败:{exc}", flush=True)
        return 2

    has_hard = bool(result["hard_dir_cycles"]) or bool(result["hard_file_cycles"])

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif not (args.quiet_when_clean and not has_hard):
        print(render_text(result), flush=True)

    if args.fail_on_hard_cycle and has_hard:
        if not args.json:
            print(
                f"[import-cycles] ⚠️ 检出硬加载期环(目录 {len(result['hard_dir_cycles'])} / "
                f"文件 {len(result['hard_file_cycles'])}),按 --fail-on-hard-cycle 阻断。",
                flush=True,
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
