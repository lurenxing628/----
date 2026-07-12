#!/usr/bin/env python3
"""包级 / 文件级循环依赖扫描器(import-cycle scanner)。

补 checkup 函数调用图的盲区：其 cycle_count 是确信边上长度 2-8、最多 200 条的
simple-cycle 记录数，不是 import SCC。本工具按目录(包)与文件(模块)两种粒度，用 Tarjan 求强连通
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

默认扫描非测试代码(core/web/data/desktop/plugins/tools/scripts + 顶层 *.py)，排除 tests；--include-tests 纳入。
Py3.8 兼容、纯标准库。
"""
from __future__ import annotations

import argparse
import ast
import glob
import importlib.util
import json
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional, Sequence, Tuple

from tools import import_cycle_graph as _graph
from tools.import_cycle_analysis import classify, dyn_imports, expand_parent_packages, resolve_targets, tarjan
from tools.import_cycle_baseline import (
    CycleBaselineComparison,
    CycleBaselineError,
    baseline_scope,
    compare_with_baseline,
    current_signatures,
    default_baseline_path,
    print_new_cycles,
    write_baseline,
)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

PROD_ROOTS = ["core", "web", "data", "desktop", "plugins", "tools", "scripts", "*.py"]
TEST_ROOTS = ["tests"]
KINDS = ("hard", "cond", "lazy", "typeonly")
FILE_CYCLE_SEMANTICS = "explicit import edges plus implicit parent-package __init__ loading edges"

BASELINE_PATH = default_baseline_path(REPO_ROOT)
WITH_TESTS_BASELINE_PATH = default_baseline_path(REPO_ROOT, include_tests=True)


path_to_mod = _graph.module_from_path
cur_pkg_parts = _graph.current_package_parts
tdir = _graph.target_directory
render_text = _graph.render_text


_adj = _graph.adjacency
_merge = _graph.merge_edges
_dir_cycle_records = _graph.dir_cycle_records
_file_cycle_records = _graph.file_cycle_records
_delayed_dir_cycle_records = _graph.delayed_dir_cycle_records


def _remember_module(
    path: str,
    repo_root: str,
    file_to_mod: Dict[str, str],
    mod_to_file: Dict[str, str],
) -> None:
    if not path.endswith(".py") or not os.path.isfile(path):
        return
    absolute = os.path.abspath(path)
    rel = os.path.relpath(absolute, repo_root)
    module = path_to_mod(rel)
    file_to_mod[absolute] = module
    mod_to_file[module] = absolute


def _index_modules(roots: Sequence[str], repo_root: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    file_to_mod: Dict[str, str] = {}
    mod_to_file: Dict[str, str] = {}
    for root in roots:
        base = os.path.join(repo_root, root)
        if glob.has_magic(root):
            for path in sorted(glob.glob(base)):
                _remember_module(path, repo_root, file_to_mod, mod_to_file)
            continue
        if os.path.isfile(base):
            _remember_module(base, repo_root, file_to_mod, mod_to_file)
            continue
        if not os.path.isdir(base):
            continue
        for directory, dirs, files in os.walk(base):
            dirs[:] = [name for name in dirs if name != "__pycache__"]
            for filename in files:
                _remember_module(os.path.join(directory, filename), repo_root, file_to_mod, mod_to_file)
    return file_to_mod, mod_to_file


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
    include_directory_edge: bool = True,
) -> None:
    if target_mod == source_mod:
        return
    edges_file[kind][(source_mod, target_mod)].append((rel_path, line))
    target_dir = tdir(target_mod, mod_to_file, repo_root)
    if include_directory_edge and target_dir is not None and target_dir != source_dir:
        edges_dir[kind][(source_dir, target_dir)].append((rel_path, line, target_mod))


def _resolved_dynamic_target(
    target: str,
    package: Optional[str],
    pkg: List[str],
    source_mod: str,
) -> Optional[str]:
    if not target.startswith("."):
        return target
    if package == "__package__":
        package_name = ".".join(pkg)
    elif package == "__name__":
        package_name = source_mod
    else:
        package_name = str(package or "").strip()
    if not package_name:
        return None
    try:
        return importlib.util.resolve_name(target, package_name)
    except (ImportError, ValueError):
        return None


def _collect_module_edges(
    ab: str,
    mod: str,
    tree: ast.AST,
    file_to_mod: Dict[str, str],
    mod_to_file: Dict[str, str],
    edges_file: dict,
    explicit_edges_file: dict,
    edges_dir: dict,
    unresolved_dynamic_imports: List[dict],
    parent_package_init_edges: List[dict],
    repo_root: str,
) -> None:
    pkg = cur_pkg_parts(ab, mod)
    rel = os.path.relpath(ab, repo_root).replace("\\", "/")
    source_dir = os.path.dirname(os.path.relpath(ab, repo_root)).replace("\\", "/") or "."
    for node, kind in classify(tree):
        direct_targets = resolve_targets(node, pkg, mod_to_file, include_parent_packages=False)
        for target_mod in expand_parent_packages(direct_targets, mod_to_file):
            parent_init = target_mod not in direct_targets
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
                include_directory_edge=not parent_init,
            )
            if not parent_init:
                explicit_edges_file[kind][(mod, target_mod)].append((rel, node.lineno))  # type: ignore[attr-defined]
            if parent_init:
                parent_package_init_edges.append(
                    {
                        "source": mod,
                        "target": target_mod,
                        "file": rel,
                        "line": node.lineno,  # type: ignore[attr-defined]
                        "context": kind,
                    }
                )
    resolved_dynamic, unresolved_dynamic = dyn_imports(tree)
    for raw_target, package, kind, line in resolved_dynamic:
        target_mod = _resolved_dynamic_target(raw_target, package, pkg, mod)
        dynamic_targets = expand_parent_packages([target_mod], mod_to_file) if target_mod else []
        for dynamic_target in dynamic_targets:
            if dynamic_target not in mod_to_file:
                continue
            parent_init = dynamic_target != target_mod
            _add_edge(
                edges_file,
                edges_dir,
                kind=kind,
                source_mod=mod,
                target_mod=dynamic_target,
                source_dir=source_dir,
                rel_path=rel,
                line=line,
                mod_to_file=mod_to_file,
                repo_root=repo_root,
                include_directory_edge=not parent_init,
            )
            if not parent_init:
                explicit_edges_file[kind][(mod, dynamic_target)].append((rel, line))
            if parent_init:
                parent_package_init_edges.append(
                    {
                        "source": mod,
                        "target": dynamic_target,
                        "file": rel,
                        "line": line,
                        "context": kind,
                    }
                )
        if target_mod not in mod_to_file and raw_target.startswith("."):
            unresolved_dynamic_imports.append(
                {
                    "file": rel,
                    "line": line,
                    "context": kind,
                    "expression": f"relative target {raw_target!r} could not resolve in package {package!r}",
                }
            )
    for kind, line, expression in unresolved_dynamic:
        unresolved_dynamic_imports.append(
            {"file": rel, "line": line, "context": kind, "expression": expression}
        )


def scan(roots: Sequence[str], repo_root: str = REPO_ROOT) -> dict:
    """扫描给定根目录,返回三类环 + 边计数 + 解析失败的结构化结果。"""
    file_to_mod, mod_to_file = _index_modules(roots, repo_root)
    edges_file = {k: defaultdict(list) for k in KINDS}
    explicit_edges_file = {k: defaultdict(list) for k in KINDS}
    edges_dir = {k: defaultdict(list) for k in KINDS}
    parse_errors: List[dict] = []
    unresolved_dynamic_imports: List[dict] = []
    parent_package_init_edges: List[dict] = []

    for ab, mod in file_to_mod.items():
        try:
            with open(ab, encoding="utf-8") as handle:
                tree = ast.parse(handle.read())
        except (OSError, SyntaxError, UnicodeError) as exc:
            parse_errors.append({"file": os.path.relpath(ab, repo_root), "error": str(exc)})
            continue
        _collect_module_edges(
            ab,
            mod,
            tree,
            file_to_mod,
            mod_to_file,
            edges_file,
            explicit_edges_file,
            edges_dir,
            unresolved_dynamic_imports,
            parent_package_init_edges,
            repo_root,
        )

    hard_dir = edges_dir["hard"]
    hard_file = edges_file["hard"]
    explicit_hard_file = explicit_edges_file["hard"]
    rt_dir = _merge(edges_dir["hard"], edges_dir["cond"], edges_dir["lazy"])
    rt_file = _merge(edges_file["hard"], edges_file["cond"], edges_file["lazy"])
    explicit_rt_file = _merge(
        explicit_edges_file["hard"],
        explicit_edges_file["cond"],
        explicit_edges_file["lazy"],
    )

    hard_dir_sccs = tarjan(_adj(hard_dir))
    hard_file_sccs = tarjan(_adj(hard_file))
    explicit_hard_file_sccs = tarjan(_adj(explicit_hard_file))
    rt_dir_sccs = tarjan(_adj(rt_dir))
    rt_file_sccs = tarjan(_adj(rt_file))
    explicit_rt_file_sccs = tarjan(_adj(explicit_rt_file))

    return {
        "module_count": len(file_to_mod),
        "scan_roots": list(roots),
        "file_cycle_semantics": FILE_CYCLE_SEMANTICS,
        "parse_errors": parse_errors,
        "edge_counts": {k: sum(len(v) for v in edges_file[k].values()) for k in KINDS},
        "hard_dir_cycles": _dir_cycle_records(hard_dir_sccs, hard_dir),
        "hard_file_cycles": [sorted(c) for c in sorted(hard_file_sccs, key=len, reverse=True)],
        "hard_file_cycle_records": _file_cycle_records(hard_file_sccs, hard_file),
        "explicit_hard_file_cycles": _file_cycle_records(explicit_hard_file_sccs, explicit_hard_file),
        "delayed_dir_cycles": _delayed_dir_cycle_records(rt_dir_sccs, hard_dir_sccs, rt_dir),
        "runtime_file_cycle_count": len(rt_file_sccs),
        "runtime_file_cycles": _file_cycle_records(rt_file_sccs, rt_file),
        "explicit_runtime_file_cycles": _file_cycle_records(explicit_rt_file_sccs, explicit_rt_file),
        "parent_package_init_edges": sorted(
            parent_package_init_edges,
            key=lambda item: (item["source"], item["target"], item["line"]),
        ),
        "unresolved_dynamic_imports": sorted(
            unresolved_dynamic_imports,
            key=lambda item: (item["file"], item["line"], item["expression"]),
        ),
    }


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
        help="按 scope 匹配的 v2 基线阻断新增硬环或同成员圈内新增边；基线/解析异常 fail closed",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="把当前硬加载期环及圈内模块边写入 scope 对应基线(仅限人工核对差异后的受控刷新)",
    )
    parser.add_argument(
        "--baseline",
        default=None,
        help="显式基线路径；默认按是否 --include-tests 选择生产或含测试基线",
    )
    parser.add_argument(
        "--quiet-when-clean",
        action="store_true",
        help="无需报告时完全不输出(clean 含义随模式:相对基线无新增 / 无任何硬环)",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.baseline is None:
        args.baseline = default_baseline_path(REPO_ROOT, include_tests=bool(args.include_tests))
    return args


def _error(message: str) -> None:
    print(f"[import-cycles] {message}", file=sys.stderr, flush=True)


def _load_scan_result(args: argparse.Namespace) -> Tuple[Optional[dict], int]:
    roots = list(PROD_ROOTS) + (list(TEST_ROOTS) if args.include_tests else [])
    try:
        return scan(roots), 0
    except Exception as exc:
        _error(f"扫描自身异常，无法产出可信结果：{exc}")
        return None, 2


def _print_parse_errors(result: dict) -> None:
    errors = list(result.get("parse_errors") or [])
    _error(f"源码解析失败 {len(errors)} 个，正式循环门禁已阻断；请先修复下列文件：")
    for row in errors[:20]:
        _error(f"  - {row.get('file')}: {row.get('error')}")
    if len(errors) > 20:
        _error(f"  - 另有 {len(errors) - 20} 个解析失败")


def _print_result(
    result: dict,
    args: argparse.Namespace,
    comparison: Optional[CycleBaselineComparison],
) -> None:
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(render_text(result), flush=True)
    if not args.fail_on_new_cycle or comparison is None:
        return
    if comparison.has_new:
        print_new_cycles(result, comparison)
    else:
        dir_sigs, _ = current_signatures(result)
        print(f"[import-cycles] 无新增硬加载期环或圈内边(基线内 {len(dir_sigs)} 个现存目录环)。", flush=True)


def _baseline_comparison(
    args: argparse.Namespace,
    result: dict,
    scope: str,
) -> Tuple[Optional[CycleBaselineComparison], int]:
    try:
        comparison = compare_with_baseline(args.baseline, result, expected_scope=scope)
    except CycleBaselineError as exc:
        _error(str(exc))
        return None, 2
    if comparison.baseline_missing:
        _error(
            f"正式循环门禁缺少 {scope!r} 基线：{args.baseline}；"
            "请先查看完整扫描差异，确认无新增债务后再受控执行 --update-baseline"
        )
        return None, 2
    return comparison, 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    result, error_code = _load_scan_result(args)
    if result is None:
        return error_code

    formal_mode = bool(args.fail_on_new_cycle or args.fail_on_hard_cycle or args.update_baseline)
    if formal_mode and result["parse_errors"]:
        _print_result(result, args, None)
        _print_parse_errors(result)
        return 2

    scope = baseline_scope(bool(args.include_tests))
    dir_sigs, file_sigs = current_signatures(result)
    has_hard = bool(result["hard_dir_cycles"]) or bool(result["hard_file_cycles"])

    if args.update_baseline:
        try:
            write_baseline(args.baseline, result, scope=scope)
        except (CycleBaselineError, OSError) as exc:
            _error(f"无法写入循环依赖基线 {args.baseline}：{exc}")
            return 2
        rel = os.path.relpath(args.baseline, REPO_ROOT)
        print(
            f"[import-cycles] {scope} 基线已刷新：{len(dir_sigs)} 个硬目录环 + "
            f"{len(file_sigs)} 个硬文件环 -> {rel}",
            flush=True,
        )
        return 0

    comparison: Optional[CycleBaselineComparison] = None
    if args.fail_on_new_cycle:
        comparison, error_code = _baseline_comparison(args, result, scope)
        if comparison is None:
            _print_result(result, args, None)
            return error_code

    clean = comparison.clean if comparison is not None else not has_hard
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
    if comparison is not None and comparison.has_new:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
