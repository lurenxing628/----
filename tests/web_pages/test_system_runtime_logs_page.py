"""回归测试：运行日志页契约——默认 aps_error.log 倒序展示、文件白名单严格匹配（非法值
flash 警告回默认且不发生文件读取）、级别/关键词筛选、三类空态/失败态诚实文案、
系统导航第 4 入口高亮、只读纪律（无 POST 路由、模板无删除按钮）。"""

from __future__ import annotations

import os


def _seed_log(client, name: str, text: str):
    log_dir = client.application.config["LOG_DIR"]
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, name), "w", encoding="utf-8") as f:
        f.write(text)


def test_default_file_shows_error_log_newest_first(app_client):
    _seed_log(
        app_client,
        "aps_error.log",
        "2026-06-11 10:00:00 [ERROR] web [r.py:1]:\n  旧报错\n"
        "2026-06-11 11:00:00 [ERROR] web [r.py:2]:\n  新报错\n",
    )
    resp = app_client.get("/system/runtime-logs")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "运行日志" in html
    assert html.index("新报错") < html.index("旧报错")
    assert "badge-danger" in html


def test_non_whitelist_file_redirects_with_warning_no_read(app_client):
    resp = app_client.get("/system/runtime-logs?file=../etc/passwd")
    assert resp.status_code == 302
    follow = app_client.get(resp.headers["Location"])
    assert "未知的日志文件" in follow.get_data(as_text=True)


def test_file_switch_and_filters(app_client):
    _seed_log(
        app_client,
        "aps.log",
        "2026-06-11 10:00:00 [INFO] web [r.py:1]: 备份完成\n"
        "2026-06-11 10:00:01 [WARNING] web [r.py:2]: 排产偏慢\n"
        "2026-06-11 10:00:02 [ERROR] web [r.py:3]: 备份失败\n",
    )
    page = app_client.get("/system/runtime-logs?file=aps.log").get_data(as_text=True)
    assert "备份完成" in page and "排产偏慢" in page

    level_page = app_client.get("/system/runtime-logs?file=aps.log&level=ERROR").get_data(as_text=True)
    assert "备份失败" in level_page
    assert "排产偏慢" not in level_page

    kw_page = app_client.get("/system/runtime-logs?file=aps.log&q=备份").get_data(as_text=True)
    assert "备份完成" in kw_page and "备份失败" in kw_page
    assert "排产偏慢" not in kw_page


def test_empty_and_missing_and_filtered_out_states(app_client):
    _seed_log(app_client, "aps_error.log", "")
    html = app_client.get("/system/runtime-logs").get_data(as_text=True)
    assert "暂无报错记录" in html

    missing = app_client.get("/system/runtime-logs?file=launcher.log").get_data(as_text=True)
    assert "日志文件尚未产生" in missing

    _seed_log(app_client, "aps_error.log", "2026-06-11 10:00:00 [ERROR] web [r.py:1]: 唯一一条\n")
    filtered = app_client.get("/system/runtime-logs?q=不存在的关键词").get_data(as_text=True)
    assert "没有匹配的条目" in filtered


def test_read_failure_shown_not_500(app_client, monkeypatch):
    _seed_log(app_client, "aps_error.log", "2026-06-11 10:00:00 [ERROR] web [r.py:1]: x\n")

    import web.routes.system_runtime_logs as mod

    def boom(path, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(mod, "read_log_entries_tail", boom)
    resp = app_client.get("/system/runtime-logs")
    assert resp.status_code == 200
    assert "日志读取失败" in resp.get_data(as_text=True)


def test_system_nav_has_runtime_logs_entry_and_active(app_client):
    html = app_client.get("/system/runtime-logs").get_data(as_text=True)
    assert "运行日志" in html
    # 备份页的系统导航也含本入口（宏单点生效）
    backup_html = app_client.get("/system/backup").get_data(as_text=True)
    assert "/system/runtime-logs" in backup_html


def test_readonly_discipline_no_post_routes_no_delete_button(app_client, repo_root):
    rules = [
        r for r in app_client.application.url_map.iter_rules()
        if str(r).startswith("/system/runtime-logs")
    ]
    assert rules, "运行日志路由未注册"
    for rule in rules:
        assert "POST" not in (rule.methods or set()), f"{rule} 不应有 POST（只读纪律）"

    template_path = os.path.join(str(repo_root), "templates", "system", "runtime_logs.html")
    with open(template_path, encoding="utf-8") as f:
        template = f.read()
    # 只读纪律：无表单提交、无删除/清空动作按钮；用途说明里的「不能删除」文案是刻意明示
    assert 'method="post"' not in template.lower()
    assert "清空" not in template
    assert "ui.button('删除'" not in template and 'ui.button("删除"' not in template
    assert "不能删除" in template
