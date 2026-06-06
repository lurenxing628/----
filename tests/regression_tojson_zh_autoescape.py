"""
回归测试：tojson_zh 不应返回 Markup（避免潜在 XSS）。

验证点：
- app.jinja_env.filters['tojson_zh'] 返回值不是 markupsafe.Markup
- 在开启 autoescape 的 Jinja2 环境下，JSON 中的 <script> 等应被转义为 &lt;script&gt;
"""

from __future__ import annotations


def test_tojson_zh_autoescape(tmp_path, monkeypatch) -> None:
    import importlib

    monkeypatch.setenv("APS_ENV", "production")
    monkeypatch.setenv("APS_DB_PATH", str(tmp_path / "aps.db"))
    monkeypatch.setenv("APS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APS_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(tmp_path / "templates_excel"))

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
