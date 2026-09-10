"""Retired log HTML maps to the real read API; source, filters, errors and read-only contracts remain."""

from __future__ import annotations

import json
import os
from pathlib import Path

from tests.gantt.test_gantt_url_persistence import _Boot

_API = "/api/workbench/v1/system/logs"


def _seed_log(client, name: str, text: str):
    log_dir = client.application.config["LOG_DIR"]
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, name), "w", encoding="utf-8") as f:
        f.write(text)


def _read(client, **query):
    response = client.get(_API, query_string=dict(file="aps_error.log", **query) if "file" not in query else query)
    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["ok"] and payload["data"]["scope"] == "bounded-log-windows"
    return payload["data"]


def _text(data):
    return "\n".join(row["summary"] + "\n" + row["body"] for row in data["rows"])


def _source(data, name):
    return next(row for row in data["sources"] if row["source"] == name)


def _retired(client, path="/system/runtime-logs"):
    response = client.get(path)
    assert response.status_code == 410 and "Location" not in response.headers
    html = response.get_data(as_text=True)
    assert "旧入口已退役" in html and "/static/js/" not in html and "/static/css/" not in html
    return html


def test_default_file_shows_error_log_newest_first(app_client):
    _seed_log(app_client, "aps_error.log",
              "2026-06-11 10:00:00 [ERROR] web [r.py:1]:\n  旧报错\n"
              "2026-06-11 11:00:00 [ERROR] web [r.py:2]:\n  新报错\n")
    _retired(app_client)
    data = _read(app_client)
    text = _text(data)
    assert text.index("新报错") < text.index("旧报错")
    assert len(data["rows"]) == 2 and all(row["level"] == "ERROR" and row["file"] == "aps_error.log" for row in data["rows"])
    assert _source(data, "aps_error.log")["state"] == "available"


def test_non_whitelist_file_redirects_with_warning_no_read(app_client, monkeypatch):
    import core.services.workbench.system_reads as mod
    calls = []
    def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError("An invalid log source must fail before any file read")
    monkeypatch.setattr(mod, "read_log_entries_tail", forbidden)
    _retired(app_client, "/system/runtime-logs?file=../etc/passwd")
    response = app_client.get(_API, query_string={"file": "../etc/passwd"})
    assert response.status_code == 400
    payload = response.get_json()
    assert payload["error"]["code"] == "invalid_input" and payload["committed"] is False
    assert "不支持该日志来源" in payload["error"]["message"]
    assert calls == []


def test_file_switch_and_filters(app_client):
    _seed_log(app_client, "aps.log",
              "2026-06-11 10:00:00 [INFO] web [r.py:1]: 备份完成\n"
              "2026-06-11 10:00:01 [WARNING] web [r.py:2]: 排产偏慢\n"
              "2026-06-11 10:00:02 [ERROR] web [r.py:3]: 备份失败\n")
    page = _text(_read(app_client, file="aps.log"))
    assert "备份完成" in page and "排产偏慢" in page
    level_page = _text(_read(app_client, file="aps.log", level="ERROR"))
    assert "备份失败" in level_page and "排产偏慢" not in level_page
    kw_page = _text(_read(app_client, file="aps.log", query="备份"))
    assert "备份完成" in kw_page and "备份失败" in kw_page and "排产偏慢" not in kw_page


def test_empty_and_missing_and_filtered_out_states(app_client):
    _seed_log(app_client, "aps_error.log", "")
    empty = _read(app_client)
    assert empty["rows"] == [] and _source(empty, "aps_error.log")["state"] == "empty"
    assert _source(empty, "aps_error.log")["count"] == 0
    missing = _read(app_client, file="launcher.log")
    assert missing["rows"] == [] and _source(missing, "launcher.log")["state"] == "missing"
    assert _source(missing, "launcher.log")["count"] is None
    _seed_log(app_client, "aps_error.log", "2026-06-11 10:00:00 [ERROR] web [r.py:1]: 唯一一条\n")
    filtered = _read(app_client, query="不存在的关键词")
    assert filtered["rows"] == [] and filtered["page"]["total"] == 0
    assert _source(filtered, "aps_error.log")["state"] == "available" and _source(filtered, "aps_error.log")["count"] == 1


def test_read_failure_shown_not_500(app_client, monkeypatch):
    _seed_log(app_client, "aps_error.log", "2026-06-11 10:00:00 [ERROR] web [r.py:1]: x\n")
    import core.services.workbench.system_reads as mod
    def boom(path, **kwargs):
        raise OSError("permission denied")
    monkeypatch.setattr(mod, "read_log_entries_tail", boom)
    _retired(app_client)
    data = _read(app_client)
    source = _source(data, "aps_error.log")
    assert data["rows"] == [] and source["state"] == "error" and source["count"] is None
    assert "日志文件无法读取" in source["message"]


def test_system_nav_has_runtime_logs_entry_and_active(app_client):
    _retired(app_client)
    _retired(app_client, "/system/backup")
    navigation = {"version": 1, "view": "system", "context": {}}
    response = app_client.get("/workbench", query_string={"view": "system", "nav": json.dumps(navigation)})
    assert response.status_code == 200
    parser = _Boot()
    parser.feed(response.get_data(as_text=True))
    assert json.loads("".join(parser.parts))["navigation"] == navigation
    # The canonical host remains connected to the same nonempty live read route.
    _seed_log(app_client, "aps_error.log", "2026-06-11 10:00:00 [ERROR] web [r.py:1]: 导航后可读取\n")
    assert "导航后可读取" in _text(_read(app_client))


def test_readonly_discipline_no_post_routes_no_delete_button(app_client, repo_root):
    rules = [r for r in app_client.application.url_map.iter_rules()
             if str(r).startswith("/system/runtime-logs") or str(r).startswith(_API)]
    assert rules, "运行日志路由未注册"
    for rule in rules:
        assert "POST" not in (rule.methods or set()), str(rule)
    assert app_client.post("/system/runtime-logs").status_code == 405
    assert app_client.post(_API).status_code == 405
    assert not (Path(repo_root) / "templates/system/runtime_logs.html").exists()
    html = _retired(app_client)
    assert 'method="post"' not in html.lower() and "<button" not in html
    _seed_log(app_client, "aps_error.log", "2026-06-11 10:00:00 [ERROR] web [r.py:1]: 只读保留\n")
    log = Path(app_client.application.config["LOG_DIR"]) / "aps_error.log"
    before = log.read_bytes()
    data = _read(app_client)
    assert data["rows"] and all("write_context" not in row for row in data["rows"])
    assert log.read_bytes() == before
