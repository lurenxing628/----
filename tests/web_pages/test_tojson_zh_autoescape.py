"""
回归测试：tojson_zh 不应返回 Markup（避免潜在 XSS）。

验证点：
- app.jinja_env.filters['tojson_zh'] 返回值不是 markupsafe.Markup
- 在开启 autoescape 的 Jinja2 环境下，JSON 中的 <script> 等应被转义为 &lt;script&gt;
"""

from __future__ import annotations

from tests._support.excel_templates import point_env_at_shared


def test_tojson_zh_autoescape(tmp_path, monkeypatch) -> None:
    import importlib

    monkeypatch.setenv("APS_ENV", "production")
    monkeypatch.setenv("APS_DB_PATH", str(tmp_path / "aps.db"))
    monkeypatch.setenv("APS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APS_BACKUP_DIR", str(tmp_path / "backups"))
    point_env_at_shared(monkeypatch)

    # production(DEBUG=False)下 create_app 会 atexit.register(_run_exit_backup)；转同进程 pytest 后，
    # 该 atexit 会在分片 shard 进程退出、capture 已关闭时 logging 触发 "I/O operation on closed file"，
    # 被门禁 full-test-debt 误判为 collection_error。被测点(jinja tojson_zh filter)不涉退出备份，
    # 故阻止其注册(同进程污染收口)。
    import web.bootstrap.factory as _factory

    monkeypatch.setattr(_factory, "_EXIT_BACKUP_REGISTERED", True)

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
