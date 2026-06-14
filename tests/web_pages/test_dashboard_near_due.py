"""回归：首页临期（near_due）读取与端到端渲染。

1. _summary_near_due_count 独立非致命局部读取四态（缺键/坏值/非法结构→None、键在且 count==0→0、正常→N），
   与 _summary_overdue_count 刻意不同构：不返回 (0, error)、不并入全局 count_error→全摘要降级路径。
2. 首页 GET / 端到端渲出第 7 格「临期批次」体检格，不崩、值落合法三态（计数 / 暂无 / 数据不足）。
"""

from __future__ import annotations

import re

from web.routes.dashboard import _summary_near_due_count


def test_summary_near_due_count_missing_key_returns_none() -> None:
    # 旧摘要缺 near_due_batches 键 → None（第 7 格数据不足、临期 todo 缺席），不返回 0、不报错
    assert _summary_near_due_count({"overdue_batches": {"count": 0}}) is None


def test_summary_near_due_count_zero_is_zero_not_none() -> None:
    # 键在且 count==0 → 0（诚实空态），区别于缺键的 None
    assert _summary_near_due_count({"near_due_batches": {"count": 0}}) == 0


def test_summary_near_due_count_positive() -> None:
    assert _summary_near_due_count({"near_due_batches": {"count": 3, "items": []}}) == 3


def test_summary_near_due_count_bad_value_returns_none() -> None:
    # 坏 count（非整数）→ 局部降级 None，不泄漏脏值、不伪装成 0、不触发全摘要降级
    assert _summary_near_due_count({"near_due_batches": {"count": "2.9"}}) is None


def test_summary_near_due_count_non_dict_or_missing_count_returns_none() -> None:
    assert _summary_near_due_count(None) is None
    assert _summary_near_due_count({"near_due_batches": [1, 2]}) is None  # 非 dict payload
    assert _summary_near_due_count({"near_due_batches": {}}) is None  # 有键无 count


def test_summary_near_due_count_inconsistent_count_below_items_returns_none() -> None:
    # count 少于 items 条数：摘要内部不一致 → None（局部降级），不让 count 掩盖 items 里的真临期
    # （与超期 _summary_overdue_count 同构，但临期保持局部降级不并入全局 count_error）。
    assert _summary_near_due_count({"near_due_batches": {"count": 0, "items": [{"batch_id": "B1"}]}}) is None
    assert _summary_near_due_count(
        {"near_due_batches": {"count": 1, "items": [{"batch_id": "B1"}, {"batch_id": "B2"}]}}
    ) is None
    # count == len(items) 一致、或 count > len(items)（items 被 size-guard 裁剪）可信 → 返回 count
    assert _summary_near_due_count({"near_due_batches": {"count": 2, "items": [{"batch_id": "B1"}, {"batch_id": "B2"}]}}) == 2
    assert _summary_near_due_count({"near_due_batches": {"count": 5, "items": [{"batch_id": "B1"}]}}) == 5


def _extract_near_due_text(html: str) -> str:
    m = re.search(
        r"临期批次</span>\s*<span class=['\"]aps-dashboard-risk-value['\"]>\s*([^<]+)\s*</span>",
        html,
        re.S,
    )
    if not m:
        raise RuntimeError(f"未找到首页「临期批次」体检格，body={html[:500]!r}")
    return m.group(1).strip()


def test_dashboard_near_due_cell_renders_end_to_end(app_client, db_path) -> None:
    from core.infrastructure.database import get_connection

    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "priority_first",
                0,
                0,
                "success",
                (
                    '{"overdue_batches":{"count":0,"items":[]},'
                    '"near_due_batches":{"count":2,"items":['
                    '{"batch_id":"B1","due_date":"2026-06-20","finish_time":"2026-06-19 12:00:00"}'
                    '],"window_days":3}}'
                ),
                "reg",
            ),
        )
        conn.execute("INSERT INTO Parts (part_no, part_name) VALUES (?, ?)", ("P1", "测试零件"))
        conn.execute("INSERT INTO Batches (batch_id, part_no, quantity) VALUES (?, ?, ?)", ("B1", "P1", 1))
        op_cursor = conn.execute(
            "INSERT INTO BatchOperations (op_code, batch_id, seq, op_type_name) VALUES (?, ?, ?, ?)",
            ("OP1", "B1", 10, "测试工序"),
        )
        conn.execute(
            "INSERT INTO Schedule (op_id, start_time, end_time, lock_status, version) VALUES (?, ?, ?, ?, ?)",
            (op_cursor.lastrowid, "2026-05-06 08:00:00", "2026-05-06 10:00:00", "unlocked", 1),
        )
        conn.commit()
    finally:
        conn.close()

    resp = app_client.get("/")
    if resp.status_code != 200:
        body = resp.data.decode("utf-8", errors="ignore") if getattr(resp, "data", None) else ""
        raise RuntimeError(f"GET / 返回 {resp.status_code}，body={body[:500]}")
    html = resp.data.decode("utf-8", errors="ignore")
    if "Internal Server Error" in html or "Traceback" in html:
        raise RuntimeError("首页临期渲染出现错误页")
    # 第 7 格「临期批次」端到端渲出，值落合法三态之一（精确态由 contract + 读取单测覆盖）
    # 端到端真实渲出 count=2（identity 匹配、摘要可用、闸门放行）：第 7 格不是兜底"数据不足"/"暂无"
    assert _extract_near_due_text(html) == "2"
    # 临期窗口（3 天）来自 summary 冻结值，不把内部身份泄漏到可见文本
    for token in ("op_id", "schedule_id", "scenario_id", "candidate_id", "source_table"):
        assert f">{token}<" not in html
