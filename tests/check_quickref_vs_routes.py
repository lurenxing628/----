from __future__ import annotations

import importlib.util
import logging
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, Optional, Set, Tuple, cast

from flask import Flask


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _set_isolated_runtime_env(root: str) -> Dict[str, Optional[str]]:
    env_keys = [
        "APS_ENV",
        "APS_DB_PATH",
        "APS_LOG_DIR",
        "APS_BACKUP_DIR",
        "APS_EXCEL_TEMPLATE_DIR",
    ]
    previous = {key: os.environ.get(key) for key in env_keys}
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(Path(root) / "aps.db")
    os.environ["APS_LOG_DIR"] = str(Path(root) / "logs")
    os.environ["APS_BACKUP_DIR"] = str(Path(root) / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(Path(root) / "templates_excel")
    return previous


def _restore_env(previous: Dict[str, Optional[str]]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _load_app_for_scan(repo_root: str) -> Tuple[Flask, str]:
    module_name = f"_aps_quickref_check_app_{time.time_ns()}"
    app_path = Path(repo_root) / "app.py"
    spec = importlib.util.spec_from_file_location(module_name, app_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载应用入口：{app_path}")
    module = importlib.util.module_from_spec(spec)
    try:
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        app = getattr(module, "app", None)
        if app is not None:
            return cast(Flask, app), module_name
        create_app = getattr(module, "create_app", None)
        if not callable(create_app):
            raise RuntimeError("app.py 未导出 create_app")
        return cast(Flask, create_app()), module_name
    except Exception:
        sys.modules.pop(module_name, None)
        raise


def _close_temp_log_handlers(root: str) -> None:
    temp_root = os.path.normcase(os.path.abspath(root))
    handled: Set[int] = set()
    loggers = [logging.getLogger()]
    loggers.extend(
        logger
        for logger in logging.root.manager.loggerDict.values()
        if isinstance(logger, logging.Logger)
    )
    for logger in loggers:
        for handler in list(getattr(logger, "handlers", [])):
            handler_id = id(handler)
            handler_path = getattr(handler, "baseFilename", "")
            try:
                handler_path_norm = os.path.normcase(os.path.abspath(handler_path)) if handler_path else ""
            except Exception:
                handler_path_norm = ""
            if not handler_path_norm.startswith(temp_root):
                continue
            try:
                logger.removeHandler(handler)
            except Exception:
                pass
            if handler_id in handled:
                continue
            handled.add(handler_id)
            try:
                handler.close()
            except Exception:
                pass


def main() -> int:
    repo_root = find_repo_root()
    doc_path = Path(repo_root) / "开发文档" / "系统速查表.md"
    txt = doc_path.read_text(encoding="utf-8", errors="strict")

    # 提取格式：- `GET /path`：xxx
    pat = re.compile(r"^-\s+`(GET|POST)\s+([^`]+)`", re.M)
    doc_eps = [(m.group(1), m.group(2).strip()) for m in pat.finditer(txt)]

    # 启动 app 并读取 url_map（隔离目录，避免污染真实 db/logs/backups）
    added_repo_root = False
    module_name = ""
    with tempfile.TemporaryDirectory(prefix="aps_quickref_check_") as root:
        previous_env = _set_isolated_runtime_env(root)
        try:
            if repo_root not in sys.path:
                sys.path.insert(0, repo_root)
                added_repo_root = True
            app, module_name = _load_app_for_scan(repo_root)

            rule_set: Set[Tuple[str, str]] = set()
            for r in app.url_map.iter_rules():
                if r.rule.startswith("/static"):
                    continue
                methods = set(r.methods or [])
                for m in ("GET", "POST"):
                    if m in methods:
                        rule_set.add((m, str(r.rule)))
        finally:
            if module_name:
                sys.modules.pop(module_name, None)
            if added_repo_root:
                try:
                    sys.path.remove(repo_root)
                except ValueError:
                    pass
            _close_temp_log_handlers(root)
            _restore_env(previous_env)

    doc_set = set(doc_eps)
    missing_in_code = sorted([ep for ep in doc_set if ep not in rule_set])
    # 当前约定为：除 /static 外，其余 GET/POST 路由都应进入系统速查表。
    undocumented_in_doc = sorted([ep for ep in rule_set if ep not in doc_set])

    out = []
    out.append("# 系统速查表接口对比（文档 vs 实现）")
    out.append("")
    out.append(f"- 生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}")
    out.append(f"- 文档：`{doc_path}`")
    out.append(f"- 文档接口条目（GET/POST）：{len(doc_eps)}")
    out.append(f"- 实现接口条目（GET/POST，排除 /static）：{len(rule_set)}")
    out.append("")
    out.append("## 结论")
    out.append(f"- 文档列出但实现缺失：{len(missing_in_code)}")
    out.append(f"- 实现存在但文档未列出：{len(undocumented_in_doc)}")
    out.append("")

    out.append("## 文档列出但实现缺失（如有）")
    if not missing_in_code:
        out.append("- 无")
    else:
        for m, p in missing_in_code[:200]:
            out.append(f"- `{m} {p}`")
    out.append("")

    out.append("## 实现存在但文档未列出（抽样前 80 条）")
    if not undocumented_in_doc:
        out.append("- 无")
    else:
        for m, p in undocumented_in_doc[:80]:
            out.append(f"- `{m} {p}`")
    out.append("")

    out_path = Path(repo_root) / "evidence" / "Conformance" / "quickref_vs_routes.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(str(out_path))
    if missing_in_code or undocumented_in_doc:
        print("ERROR: 系统速查表与实现存在差异，请先同步文档与路由。")
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

