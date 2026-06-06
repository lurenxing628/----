"""
回归测试：模板中 url_for() 引用的 endpoint 必须存在。

背景：
- 若模板引用了不存在的 endpoint，Jinja 渲染阶段会抛 werkzeug.routing.BuildError，
  最终表现为页面直接 500（错误码 1000）。
- 该类问题在“模板/前端先更新、后端/EXE 未同步更新”的场景里很常见。

策略：
- 扫描 templates/ 与 web_new_test/templates/ 内的 *.html
- 提取形如 url_for('blueprint.endpoint', ...) 的字面量 endpoint
- 启动 create_app() 并读取 app.view_functions（即已注册 endpoint 集合）
- 若发现 url_for 引用缺失的 endpoint：直接失败（raise SystemExit(1)）
- safe_url_for(...) 引用缺失仅提示（因为它本身允许 endpoint 不存在，不会导致 500）
"""

from __future__ import annotations

import os
import re
from collections import defaultdict
from pathlib import Path
from typing import DefaultDict, Dict, List, Tuple


def iter_template_files(repo_root: str) -> List[str]:
    roots = [
        os.path.join(repo_root, "templates"),
        os.path.join(repo_root, "web_new_test", "templates"),
    ]
    out: List[str] = []
    for r in roots:
        if not os.path.isdir(r):
            continue
        for dirpath, _dirnames, filenames in os.walk(r):
            for fn in filenames:
                if not fn.lower().endswith(".html"):
                    continue
                out.append(os.path.join(dirpath, fn))
    out.sort()
    return out


def collect_endpoints_from_templates(repo_root: str) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """
    返回：
    - url_for 引用：endpoint -> [relpath:line, ...]
    - safe_url_for 引用：endpoint -> [relpath:line, ...]
    """
    pat_url_for = re.compile(r"(?<!safe_)url_for\(\s*['\"]([^'\"]+)['\"]")
    pat_safe = re.compile(r"safe_url_for\(\s*['\"]([^'\"]+)['\"]")

    url_refs: DefaultDict[str, List[str]] = defaultdict(list)
    safe_refs: DefaultDict[str, List[str]] = defaultdict(list)

    for fpath in iter_template_files(repo_root):
        rel = os.path.relpath(fpath, repo_root).replace("\\", "/")
        try:
            txt = Path(fpath).read_text(encoding="utf-8", errors="strict")
        except Exception:
            # 极端情况下允许容错读取（避免因个别文件编码导致测试崩溃）
            txt = Path(fpath).read_text(encoding="utf-8", errors="ignore")

        for i, line in enumerate(txt.splitlines(), start=1):
            for m in pat_url_for.finditer(line):
                ep = (m.group(1) or "").strip()
                if ep:
                    url_refs[ep].append(f"{rel}:{i}")
            for m in pat_safe.finditer(line):
                ep = (m.group(1) or "").strip()
                if ep:
                    safe_refs[ep].append(f"{rel}:{i}")

    return dict(url_refs), dict(safe_refs)


def test_template_urlfor_endpoints(app_client, repo_root) -> None:
    url_refs, safe_refs = collect_endpoints_from_templates(str(repo_root))
    registered = set(app_client.application.view_functions.keys())

    missing_url = {ep: refs for ep, refs in url_refs.items() if ep not in registered}
    missing_safe = {ep: refs for ep, refs in safe_refs.items() if ep not in registered}

    if missing_safe:
        print("[WARN] safe_url_for 引用的 endpoint 未注册（允许存在此情况，但建议确认是否应补齐路由）：")
        for ep in sorted(missing_safe.keys()):
            locs = ", ".join(missing_safe[ep][:8])
            more = "" if len(missing_safe[ep]) <= 8 else f" ... (+{len(missing_safe[ep]) - 8})"
            print(f"  - {ep}: {locs}{more}")
        print("")

    if missing_url:
        print("[FAIL] 模板 url_for 引用的 endpoint 未注册（会导致页面渲染阶段 500）：")
        for ep in sorted(missing_url.keys()):
            locs = ", ".join(missing_url[ep][:12])
            more = "" if len(missing_url[ep]) <= 12 else f" ... (+{len(missing_url[ep]) - 12})"
            print(f"  - {ep}: {locs}{more}")
        raise AssertionError("模板 url_for 引用的 endpoint 未注册（会导致页面渲染阶段 500）；详见上方输出")

