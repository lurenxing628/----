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

from tools.import_cycle_analysis import classify, dyn_imports, resolve_targets, tarjan
from tools.import_cycle_baseline import (
    compare_with_baseline,
    current_signatures,
    default_baseline_path,
    print_new_cycles,
    write_baseline,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

PROD_ROOTS = ["core", "web", "data", "desktop", "tools", "scripts"]
TEST_ROOTS = ["tests"]
KINDS = ("hard", "cond", "lazy", "typeonly")

BASELINE_PATH = default_baseline_path(REPO_ROOT)


def path_to_mod(rel: str) -> str:
    parts = rel[:-3].split(os.sep)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def cur_pkg_parts(ab: str, mod: str) -> List[str]:
    parts = mod.split(".")
    return parts if os.path.basename(ab) == "__init__.py" else parts[:-1]


def tdir(mod: str, mod_to_file: Dict[str, str], repo_root: str) -> Optional[str]:
    f = mod_to_file.get(mod)
    return os.path.dirname(os.path.relpath(f, repo_root)) if f else None


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


def _add_edge(
    edges_file: dict,
    edges_dir: dict,
    *,
    kind: str,
    source_mod: str,
    target_mod: str,
    source_dir: str,
    rel_path: str,
    line: int,
    mod_to_file: Dict[str, str],
    repo_root: str,
) -> None:
    if target_mod == source_mod:
        return
    edges_file[kind][(source_mod, target_mod)].append((rel_path, line))
    target_dir = tdir(target_mod, mod_to_file, repo_root)
    if target_dir is not None and target_dir != source_dir:
        edges_dir[kind][(source_dir, target_dir)].append((rel_path, line, target_mod))


def _collect_module_edges(
    ab: str,
    mod: str,
    tree: ast.AST,
    file_to_mod: Dict[str, str],
    mod_to_file: Dict[str, str],
    edges_file: dict,
    edges_dir: dict,
    repo_root: str,
) -> None:
    pkg = cur_pkg_parts(ab, mod)
    rel = os.path.relpath(ab, repo_root)
    source_dir = os.path.dirname(rel)
    for node, kind in classify(tree):
        for target_mod in resolve_targets(node, pkg, mod_to_file):
            _add_edge(
                edges_file,
                edges_dir,
                kind=kind,
                source_mod=mod,
                target_mod=target_mod,
                source_dir=source_dir,
                rel_path=rel,
                line=node.lineno,  # type: ignore[attr-defined]
                mod_to_file=mod_to_file,
                repo_root=repo_root,
            )
    for target_mod, infunc, line in dyn_imports(tree):
        if target_mod in mod_to_file:
            _add_edge(
                edges_file,
                edges_dir,
                kind="lazy" if infunc else "hard",
                source_mod=mod,
                target_mod=target_mod,
                source_dir=source_dir,
                rel_path=rel,
                line=line,
                mod_to_file=mod_to_file,
                repo_root=repo_root,
            )


def _delayed_dir_cycle_records(rt_dir_sccs: List[List[str]], hard_dir_sccs: List[List[str]], rt_dir: dict) -> List[dict]:
    hardsets = [frozenset(c) for c in hard_dir_sccs]
    delayed: List[dict] = []
    for comp in sorted(rt_dir_sccs, key=len, reverse=True):
        cs = frozenset(comp)
        if any(cs == h for h in hardsets):
            continue
        delayed.append(_runtime_cycle_record(comp, rt_dir))
    return delayed


def _runtime_cycle_record(comp: List[str], rt_dir: dict) -> dict:
    cset = set(comp)
    ev: List[dict] = []
    for (s, t), locs in rt_dir.items():
        if s in cset and t in cset:
            rel, line, tmod = locs[0]
            ev.append({"src": rel, "line": line, "target": tmod, "extra": len(locs) - 1})
    return {"members": sorted(comp), "edges": ev}


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
        _collect_module_edges(ab, mod, tree, file_to_mod, mod_to_file, edges_file, edges_dir, repo_root)

    hard_dir = edges_dir["hard"]
    hard_file = edges_file["hard"]
    rt_dir = _merge(edges_dir["hard"], edges_dir["cond"], edges_dir["lazy"])
    rt_file = _merge(edges_file["hard"], edges_file["cond"], edges_file["lazy"])

    hard_dir_sccs = tarjan(_adj(hard_dir))
    hard_file_sccs = tarjan(_adj(hard_file))
    rt_dir_sccs = tarjan(_adj(rt_dir))
    rt_file_sccs = tarjan(_adj(rt_file))

    return {
        "module_count": len(file_to_mod),
        "parse_errors": parse_errors,
        "edge_counts": {k: sum(len(v) for v in edges_file[k].values()) for k in KINDS},
        "hard_dir_cycles": _dir_cycle_records(hard_dir_sccs, hard_dir),
        "hard_file_cycles": [sorted(c) for c in sorted(hard_file_sccs, key=len, reverse=True)],
        "delayed_dir_cycles": _delayed_dir_cycle_records(rt_dir_sccs, hard_dir_sccs, rt_dir),
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


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="包级/文件级循环依赖扫描器")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON(供门禁/checkup 消费)")
    parser.add_argument("--include-tests", action="store_true", help="把 tests 也纳入扫描(默认只扫生产代码)")
    parser.add_argument(
        "--fail-on-hard-cycle",
        action="store_true",
        help="检出任何硬加载期目录环/文件环即退出码 1(治理完成后用,严格禁环)",
    )
    parser.add_argument(
        "--fail-on-new-cycle",
        action="store_true",
        help="只在出现基线外新增硬加载期环时退出码 1(治理期门禁推荐:现存环按节奏消,只挡回潮)",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="把当前硬加载期环写入基线文件(受控刷新),退出码 0",
    )
    parser.add_argument(
        "--baseline",
        default=BASELINE_PATH,
        help="基线文件路径(默认 .codestable/checkup/import_cycles_baseline.json)",
    )
    parser.add_argument(
        "--quiet-when-clean",
        action="store_true",
        help="无需报告时完全不输出(钩子高频跑用;clean 含义随模式:无新增环 / 无任何硬环)",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def _load_scan_result(args: argparse.Namespace) -> Tuple[Optional[dict], int]:
    roots = list(PROD_ROOTS) + (list(TEST_ROOTS) if args.include_tests else [])
    try:
        return scan(roots), 0
    except Exception as exc:
        print(f"[import-cycles] 扫描失败:{exc}", flush=True)
        return None, 2


def _print_result(result: dict, args: argparse.Namespace, comparison: object) -> None:
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(render_text(result), flush=True)
    if not args.fail_on_new_cycle:
        return
    if comparison.baseline_missing:
        rel = os.path.relpath(args.baseline, REPO_ROOT)
        print(
            f"[import-cycles] 未建立基线(先跑 `python3 -m tools.scan_import_cycles --update-baseline` 写 {rel});本次跳过新增判定。",
            flush=True,
        )
    elif comparison.has_new:
        print_new_cycles(result, comparison.new_dir, comparison.new_file)
    else:
        dir_sigs, _ = current_signatures(result)
        print(f"[import-cycles] 无新增硬加载期环(基线内 {len(dir_sigs)} 现存环按治理节奏消除)。", flush=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    result, error_code = _load_scan_result(args)
    if result is None:
        return error_code

    dir_sigs, file_sigs = current_signatures(result)
    has_hard = bool(result["hard_dir_cycles"]) or bool(result["hard_file_cycles"])

    if args.update_baseline:
        write_baseline(args.baseline, dir_sigs, file_sigs)
        rel = os.path.relpath(args.baseline, REPO_ROOT)
        print(
            f"[import-cycles] 基线已刷新:{len(dir_sigs)} 个硬目录环 + {len(file_sigs)} 个硬文件环 -> {rel}",
            flush=True,
        )
        return 0

    comparison = compare_with_baseline(args.baseline, dir_sigs, file_sigs)
    clean = comparison.clean if args.fail_on_new_cycle else not has_hard

    if args.quiet_when_clean and clean and not args.json:
        return 0

    _print_result(result, args, comparison)

    if args.fail_on_hard_cycle and has_hard:
        if not args.json:
            print(
                f"[import-cycles] ⚠️ 检出硬加载期环(目录 {len(result['hard_dir_cycles'])} / "
                f"文件 {len(result['hard_file_cycles'])}),按 --fail-on-hard-cycle 阻断。",
                flush=True,
            )
        return 1
    if args.fail_on_new_cycle and comparison.has_new:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
