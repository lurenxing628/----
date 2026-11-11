#!/usr/bin/env python3
"""动态引用扫描器 —— 补足纯静态 import 图的部分盲区。

纯 import 图抓不到：Flask 蓝图 side-effect 注册、g.services registry 装配、
importlib 动态加载、字符串模块名引用。本脚本识别其中一部分动态证据，
从 codemap 的 orphan_candidates 里扣除，产出仍需人工核验的精炼候选名单。

只读。读 codemap 产物，写 orphan_refined.json + dynamic_refs.json。

运行：python3 .codestable/checkup/scripts/dynamic_refs.py
可用 CHECKUP_OUT 指向临时目录。候选绝不能直接当死代码删除。
"""
from __future__ import annotations

import ast
import json
import os
import re
from typing import Any, Dict, List, Set

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
# 与 codemap_extract.py 输出位置保持一致（.codestable/checkup/latest/codemap）
CODEMAP = os.environ.get("CHECKUP_OUT") or os.path.join(HERE, "..", "latest", "codemap")
CODEMAP = os.path.abspath(CODEMAP)


def _load(name: str) -> Any:
    with open(os.path.join(CODEMAP, name), encoding="utf-8") as fh:
        return json.load(fh)


def _read(rel: str) -> str:
    with open(os.path.join(REPO_ROOT, rel), encoding="utf-8", errors="replace") as fh:
        return fh.read()


def main() -> None:
    modules: Dict[str, Any] = _load("modules.json")
    orphans: List[Dict[str, Any]] = _load("orphan_candidates.json")

    # 收集所有源码里出现的"字符串形式的模块名 / 文件 stem"引用
    # 1) importlib.import_module("x.y.z") / __import__("x.y")
    # 2) 路由注册表里的字符串模块名（如 scheduler_route_registrar 的 _ROUTE_MODULES）
    # 3) register_blueprint / import_module 的字符串参数
    # 4) g.services.<attr> 装配（request_services.py 里的 property 名）

    dynamic_referenced_mods: Set[str] = set()
    dynamic_evidence: Dict[str, List[str]] = {}

    # 全仓扫描字符串常量里出现的点分模块名 / 末段名
    all_src_files = [mi["rel"] for mi in modules.values()]
    # 也纳入 tests 与 web/bootstrap 的注册线索：直接全仓 .py
    extra_scan = []
    for root in ("web", "core", "app.py", "app_new_ui.py"):
        base = os.path.join(REPO_ROOT, root)
        if os.path.isfile(base):
            extra_scan.append(root)
        elif os.path.isdir(base):
            for dp, _, fns in os.walk(base):
                if "__pycache__" in dp:
                    continue
                for fn in fns:
                    if fn.endswith(".py"):
                        extra_scan.append(os.path.relpath(os.path.join(dp, fn), REPO_ROOT).replace("\\", "/"))
    scan_files = sorted(set(all_src_files) | set(extra_scan))

    # 模块末段名 -> 完整模块名（用于匹配 _ROUTE_MODULES 里的短名）
    stem_to_mods: Dict[str, List[str]] = {}
    for mn in modules:
        stem = mn.rsplit(".", 1)[-1]
        stem_to_mods.setdefault(stem, []).append(mn)

    str_const_re = re.compile(r"""["']([A-Za-z_][\w\.]*)["']""")

    for rel in scan_files:
        try:
            src = _read(rel)
        except OSError:
            continue
        for m in str_const_re.finditer(src):
            token = m.group(1)
            # 完整点分模块名命中
            if token in modules:
                dynamic_referenced_mods.add(token)
                dynamic_evidence.setdefault(token, []).append(rel)
            # 末段名命中（路由注册表常用短名，如 "scheduler_run"）
            elif token in stem_to_mods and ("." not in token):
                for full in stem_to_mods[token]:
                    # 只对 web.routes* 这类用短名注册的层放宽
                    if modules[full]["layer"].startswith("web.routes"):
                        dynamic_referenced_mods.add(full)
                        dynamic_evidence.setdefault(full, []).append(f"{rel}(stem)")

    # Flask 路由：凡 layer 属 web.routes* 且模块内出现 @bp. / Blueprint / register，视为活路由
    route_like: Set[str] = set()
    for mn, mi in modules.items():
        if not mi["layer"].startswith("web.routes"):
            continue
        try:
            src = _read(mi["rel"])
        except OSError:
            continue
        if re.search(r"@\w+\.(route|get|post|put|delete)\b", src) or "Blueprint(" in src or "register" in src:
            route_like.add(mn)

    # Excel/页面路由模块兜底：web/routes 下文件名含 pages/excel/routes 的，多为注册型
    for mn, mi in modules.items():
        if mi["layer"].startswith("web.routes"):
            base = os.path.basename(mi["rel"])
            if any(k in base for k in ("_pages", "_excel", "_routes", "_actions")):
                route_like.add(mn)

    refined = []
    for o in orphans:
        mn = o["module"]
        reasons = []
        if mn in dynamic_referenced_mods:
            reasons.append("string-ref:" + ",".join(sorted(set(dynamic_evidence.get(mn, [])))[:3]))
        if mn in route_like:
            reasons.append("flask-route")
        if not reasons:
            refined.append(o)

    refined_sorted = sorted(refined, key=lambda x: -x["lines"])

    def _dump(name: str, obj: Any) -> None:
        with open(os.path.join(CODEMAP, name), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, ensure_ascii=False, indent=1, sort_keys=True)
            fh.write("\n")

    _dump("dynamic_refs.json", {k: sorted(set(v)) for k, v in dynamic_evidence.items()})
    _dump("orphan_refined.json", refined_sorted)

    print("=== 动态引用扫描完成 ===")
    print(f"原始孤儿候选: {len(orphans)}")
    print(f"  其中 Flask 路由(动态注册): {sum(1 for o in orphans if o['module'] in route_like)}")
    print(f"  其中字符串/registry 引用: {sum(1 for o in orphans if o['module'] in dynamic_referenced_mods)}")
    print(f"精炼后真正可疑(无任何引用): {len(refined_sorted)}")
    print("\n--- 精炼后可疑死模块候选(前40，仍需 Agent 回代码验证) ---")
    for x in refined_sorted[:40]:
        print(f"  {x['lines']:5d}  {x['layer']:26s}  {x['rel']}")


if __name__ == "__main__":
    main()
