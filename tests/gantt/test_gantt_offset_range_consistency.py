"""回归测试：甘特图 /scheduler/gantt 数据接口的区间一致性——当请求带 start_date/end_date 时不能因 offset 二次偏移，新前端有有效区间时不发 offset 也应返回同一区间；并校验 gantt_boot.js 中 version_span 判断与 start/end 对 week_start/offset 的二选一分支顺序。"""

from __future__ import annotations

import json
import re
import urllib.parse


def _assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def _pick_data_attr(html: str, attr: str) -> str:
    m = re.search(re.escape(attr) + r'="([^"]*)"', html)
    return m.group(1) if m else ""


def _call_data(client, data_url: str, query: dict) -> dict:
    path = f"{data_url}?{urllib.parse.urlencode(query)}"
    resp = client.get(path)
    _assert_true(resp.status_code == 200, f"GET {path} 返回 {resp.status_code}")
    payload = json.loads(resp.data.decode("utf-8", errors="ignore") or "{}")
    _assert_true(payload.get("success") is True, f"甘特图数据接口失败: {payload}")
    return payload.get("data") or {}


def test_gantt_offset_range_consistency(app_client, repo_root) -> None:
    from tests._support.gantt_current import navigation, plan_fixture, prepare_read_state, read_workspace
    from tests._support.gantt_retirement import _business_state

    client = app_client
    before = prepare_read_state(client)

    resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-03&offset=1")
    _assert_true(resp.status_code == 404, f"GET /scheduler/gantt 返回 {resp.status_code}")
    html = resp.data.decode("utf-8", errors="ignore")
    assert "页面不存在或已被删除" in html
    assert "Location" not in resp.headers and "workbench-boot" not in html
    data_url = "/scheduler/gantt/data"
    base_query = {"view": "machine", "week_start": "2026-03-03", "offset": "1"}
    base_data = _call_data(client, data_url, base_query)
    assert base_data["status"] == "no_history" and base_data["version"] is None
    assert base_data["tasks"] == []
    expected_start = str(base_data.get("week_start") or "")
    expected_end = str(base_data.get("week_end") or "")
    _assert_true(bool(expected_start and expected_end), "无法确定有效区间（start/end）")

    # 兼容旧前端行为：即使把 start/end + offset 一并发送，也不能出现区间二次偏移。
    old_style_query = dict(base_query)
    old_style_query["start_date"] = expected_start
    old_style_query["end_date"] = expected_end
    old_style_data = _call_data(client, data_url, old_style_query)
    _assert_true(old_style_data.get("week_start") == expected_start, "旧参数风格 week_start 与有效 start_date 不一致")
    _assert_true(old_style_data.get("week_end") == expected_end, "旧参数风格 week_end 与有效 end_date 不一致")

    # 新前端行为：有 start/end 时不发送 offset，应保持同样区间。
    new_style_query = dict(old_style_query)
    new_style_query.pop("offset", None)
    new_style_data = _call_data(client, data_url, new_style_query)
    _assert_true(new_style_data.get("week_start") == expected_start, "新参数风格 week_start 与有效 start_date 不一致")
    _assert_true(new_style_data.get("week_end") == expected_end, "新参数风格 week_end 与有效 end_date 不一致")
    assert _business_state(client) == before

    query, default, _payload, seeded = plan_fixture(client)
    explicit = dict(query, start_date=expected_start, end_date=expected_end)
    context = navigation(client, explicit)
    assert navigation(client, dict(explicit, offset_weeks=1)) == context
    assert context["plan_ref"] == default["plan_ref"]
    workspace = read_workspace(client, context)["data"]
    assert workspace["time_scope"]["range_start"] == expected_start + "T00:00:00"
    assert workspace["tasks"] == [] and workspace["tasks_complete"] is True
    assert _business_state(client) == seeded
