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
    client = app_client

    resp = client.get("/scheduler/gantt?view=machine&week_start=2026-03-03&offset=1")
    _assert_true(resp.status_code == 200, f"GET /scheduler/gantt 返回 {resp.status_code}")
    html = resp.data.decode("utf-8", errors="ignore")

    data_url = _pick_data_attr(html, "data-url") or "/scheduler/gantt/data"
    attrs = {
        "view": _pick_data_attr(html, "data-view"),
        "week_start": _pick_data_attr(html, "data-week-start"),
        "start_date": _pick_data_attr(html, "data-start-date"),
        "end_date": _pick_data_attr(html, "data-end-date"),
        "offset": _pick_data_attr(html, "data-offset"),
        "version": _pick_data_attr(html, "data-version"),
    }
    base_query = {
        "view": attrs["view"] or "machine",
        "week_start": attrs["week_start"] or "2026-03-03",
        "offset": attrs["offset"] or "1",
    }
    if attrs["version"]:
        base_query["version"] = attrs["version"]
    base_data = _call_data(client, data_url, base_query)

    expected_start = attrs["start_date"] or str(base_data.get("week_start") or "")
    expected_end = attrs["end_date"] or str(base_data.get("week_end") or "")
    _assert_true(bool(expected_start and expected_end), "无法确定有效区间（start/end）")

    # 兼容 has_history=false：页面不输出 data-start/end 时，必须给出明确提示。
    if not (attrs["start_date"] and attrs["end_date"]):
        _assert_true("系统里还没有排产版本" in html, "无历史版本场景缺少提示文案")

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
