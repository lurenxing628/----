"""
回归测试：tojson_zh 不应返回 Markup（避免潜在 XSS）。

验证点：
- app.jinja_env.filters['tojson_zh'] 返回值不是 markupsafe.Markup
- 在开启 autoescape 的 Jinja2 环境下，JSON 中的 <script> 等应被转义为 &lt;script&gt;
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    tmpdir = tempfile.mkdtemp(prefix="aps_regression_tojson_")
    os.environ["APS_ENV"] = "production"
    os.environ["APS_DB_PATH"] = str(Path(tmpdir) / "aps.db")
    os.environ["APS_LOG_DIR"] = str(Path(tmpdir) / "logs")
    os.environ["APS_BACKUP_DIR"] = str(Path(tmpdir) / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(Path(tmpdir) / "templates_excel")

    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    import importlib

    app_mod = importlib.import_module("app")
    app = app_mod.create_app()

    f = app.jinja_env.filters.get("tojson_zh")
    if not callable(f):
        raise RuntimeError("缺少 Jinja filter：tojson_zh")

    payload = {"x": "<script>alert(1)</script>"}
    out = f(payload, 2)

    from markupsafe import Markup  # noqa: WPS433 (local import in test)

    if isinstance(out, Markup):
        raise RuntimeError("tojson_zh 返回了 Markup：存在潜在 XSS 风险")

    # 模拟开启 autoescape 的渲染环境
    import jinja2

    env = jinja2.Environment(autoescape=True)
    env.filters["tojson_zh"] = f
    rendered = env.from_string("{{ value | tojson_zh(2) }}").render(value=payload)

    if "<script>" in rendered or "</script>" in rendered:
        raise RuntimeError("autoescape 未生效：渲染结果仍包含 <script> 标签")
    if "&lt;script&gt;" not in rendered:
        raise RuntimeError("autoescape 未按预期转义 <script>（缺少 &lt;script&gt;）")

    print("OK")


if __name__ == "__main__":
    main()

