"""单测：build_cockpit_hero 三态（失败/风险/平静）+ 超期精简主导线索三态（完整/缺失/裁剪）。

失败态走 resolve_result_status 归一（遗留别名 'fail'/大小写也判失败，禁裸 == 'failed'）+ 独立门控；
风险态 title 原样复用 todo[0]、rest=[1:]；失败态 rest=todo_items 全量；
精简线索逾期量用 due_exclusive=交期+1天00:00 边界、日期宽松解析（兼容 `/` 分隔），
裁剪态（count>len(items)）明示「基于前 N 条」不冒充全量最严重，缺失态降级笼统句。
"""

from __future__ import annotations

from typing import Any, Dict

from web.viewmodels.dashboard_cockpit_hero import build_cockpit_hero
from web.viewmodels.scheduler_workbench_links import build_workbench_plan_context


def _ctx() -> Dict[str, Any]:
    return build_workbench_plan_context(version=12, plan_role="adopted")


def _overdue_todo(title: str = "超期批次需要先看") -> Dict[str, Any]:
    return {
        "kind": "overdue",
        "severity": "danger",
        "title": title,
        "impact_text": "3 个批次会晚于交期，同类提醒已合并成这一条。",
        "evidence_text": "根据当前排产摘要里的超期批次统计生成。",
        "primary_action": {"label": "查看超期清单", "url": "/reports/overdue?version=12", "target_page": "overdue_report"},
        "secondary_action": {"label": "查看延期说明", "url": "/reports/overdue", "target_page": "delay_diagnosis"},
    }


def _resource_todo() -> Dict[str, Any]:
    return {
        "kind": "resource_overload",
        "severity": "warning",
        "title": "资源负荷偏高",
        "impact_text": "设备平均利用率约 91.0%，可能需要先看资源排班。",
        "evidence_text": "数据来源是当前排产摘要里的设备平均利用率。",
        "primary_action": {"label": "查看资源排班", "url": "/scheduler/resource-dispatch", "target_page": "resource_dispatch"},
        "secondary_action": {"label": "查看资源负荷", "url": "/reports/utilization", "target_page": "utilization_report"},
    }


def _build(**overrides: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "context": _ctx(),
        "todo_items": [],
        "latest_summary": None,
        "result_status": "success",
        "failed_run_applies_to_current_view": False,
        "empty_state": "当前没有必须马上处理的排产风险，可以继续查看甘特图或排产分析。",
    }
    data.update(overrides)
    return build_cockpit_hero(**data)


# --- hero 三态 ---


def test_failed_hero_when_failed_and_gate_applies() -> None:
    bundle = _build(
        todo_items=[_overdue_todo(), _resource_todo()],
        result_status="failed",
        failed_run_applies_to_current_view=True,
    )
    hero = bundle["hero"]
    assert hero["mode"] == "failed"
    assert hero["severity"] == "danger"
    assert hero["title"] == "最近一次排产没有成功"
    # 失败 hero primary→执行排产（context-free '/scheduler/'）、secondary→历史
    assert hero["primary_action"]["url"] == "/scheduler/"
    assert hero["primary_action"]["label"]
    assert hero["secondary_action"]["target_page"] == "history"
    # 失败态 rest = todo_items 全量，不丢
    assert len(bundle["rest_todos"]) == 2


def test_failed_hero_normalizes_legacy_alias_and_case() -> None:
    # 'fail' 遗留别名 + 大小写：归一后仍判失败（禁裸 == 'failed'）
    assert _build(result_status="FAIL", failed_run_applies_to_current_view=True)["hero"]["mode"] == "failed"
    assert _build(result_status="Failed", failed_run_applies_to_current_view=True)["hero"]["mode"] == "failed"


def test_failed_hero_suppressed_when_gate_false() -> None:
    # 门控假（看历史/预览/坏版本请求）→ 不显失败 hero，落回平静/风险态
    assert _build(result_status="failed", failed_run_applies_to_current_view=False)["hero"]["mode"] == "calm"
    risk = _build(
        todo_items=[_resource_todo()],
        result_status="failed",
        failed_run_applies_to_current_view=False,
    )
    assert risk["hero"]["mode"] == "risk"


def test_failed_hero_not_triggered_for_non_failed_status() -> None:
    # 门控真但结果非失败（success）→ 不显失败 hero
    assert _build(result_status="success", failed_run_applies_to_current_view=True)["hero"]["mode"] == "calm"


def test_risk_hero_reuses_first_todo_title_verbatim_and_splits_rest() -> None:
    bundle = _build(todo_items=[_resource_todo(), _overdue_todo()])
    hero = bundle["hero"]
    assert hero["mode"] == "risk"
    assert hero["title"] == "资源负荷偏高"  # title 原样复用 todo[0]
    assert hero["severity"] == "warning"
    assert hero["primary_action"]["url"] == "/scheduler/resource-dispatch"
    rest = bundle["rest_todos"]
    assert len(rest) == 1 and rest[0]["kind"] == "overdue"


def test_calm_hero_when_no_todos() -> None:
    bundle = _build(todo_items=[])
    hero = bundle["hero"]
    assert hero["mode"] == "calm"
    assert hero["severity"] == "ok"
    assert hero["title"] == "当前没有必须马上处理的排产风险"
    assert hero["primary_action"] is None
    assert bundle["rest_todos"] == []


# --- 精简主导线索三态（超期顶 hero）---


def test_overdue_clue_complete_picks_worst_with_due_exclusive_boundary() -> None:
    # B2 逾期最久：due 2026/06/12（斜杠）→ due_exclusive 2026-06-13 00:00；finish 2026-06-15 12:00 → 晚 2天12小时
    summary = {
        "overdue_batches": {
            "count": 2,
            "items": [
                {"batch_id": "B1", "due_date": "2026-06-12", "finish_time": "2026-06-13 06:00:00"},
                {"batch_id": "B2", "due_date": "2026/06/12", "finish_time": "2026-06-15 12:00:00"},
            ],
        }
    }
    impact = _build(todo_items=[_overdue_todo()], latest_summary=summary)["hero"]["impact_text"]
    assert "2 个批次会晚于交期" in impact
    # 完整片段锁定：due_exclusive 边界（2026-06-13 00:00），finish 06-15 12:00 → 晚 2 天 12 小时
    assert "逾期最久 B2 晚 2 天 12 小时" in impact
    assert "基于前" not in impact
    assert "可解析批次里" not in impact  # 全可解析，不挂解析失败 hedge


def test_overdue_clue_unparseable_item_is_honestly_hedged() -> None:
    # B1 交期无法解析被跳过（它 finish 更晚、本应最严重）→ 不能用确定口吻把次严重 B2 报成全量最久
    summary = {
        "overdue_batches": {
            "count": 2,
            "items": [
                {"batch_id": "B1", "due_date": "坏日期xyz", "finish_time": "2026-06-20 00:00:00"},
                {"batch_id": "B2", "due_date": "2026-06-12", "finish_time": "2026-06-14 06:00:00"},
            ],
        }
    }
    impact = _build(todo_items=[_overdue_todo()], latest_summary=summary)["hero"]["impact_text"]
    assert "2 个批次会晚于交期" in impact
    assert "可解析批次里逾期最久 B2" in impact  # 诚实标注，不冒充全量最严重
    assert "基于前" not in impact


def test_overdue_clue_missing_items_degrades_to_generic_sentence() -> None:
    # minimal 档只留 count、无 items → 笼统句，不冒充线索
    impact = _build(todo_items=[_overdue_todo()], latest_summary={"overdue_batches": {"count": 5}})["hero"]["impact_text"]
    assert "5 个批次会晚于交期" in impact
    assert "逾期最久" not in impact


def test_overdue_clue_unparseable_count_uses_indefinite_sentence() -> None:
    # count 不可解析（非整数/脏值）→ 不伪造数字，用「有批次会晚于交期」诚实降级；仍可附线索，
    # 但无法核验 items 是否被裁剪 → 线索用「可用清单里逾期最久」限定，不冒充全量最严重
    summary = {
        "overdue_batches": {
            "count": "脏值",
            "items": [{"batch_id": "B1", "due_date": "2026-06-12", "finish_time": "2026-06-14 06:00:00"}],
        }
    }
    impact = _build(todo_items=[_overdue_todo()], latest_summary=summary)["hero"]["impact_text"]
    assert "有批次会晚于交期" in impact
    # 整条 impact 都不应冒出伪造数字「N 个批次会晚于交期」（此前用 split[0] 切首段是恒真 no-op）
    assert "个批次会晚于交期" not in impact
    assert "基于前" not in impact  # count 不可解析→不触发截断 hedge
    # count 脏值无法核验全量 → 「可用清单里逾期最久」限定（不裸报绝对「逾期最久」冒充全量最严重）
    assert "可用清单里逾期最久 B1 晚 1 天 6 小时" in impact


def test_overdue_clue_boundary_delta_zero_aligns_with_core_overdue() -> None:
    # finish 恰在 due_exclusive（交期次日 0 点）：core 计为超期(finish>=due_exclusive)，
    # hero 同源保留 delta==0 参与竞选，给出「不到 1 小时」线索而非丢弃
    summary = {
        "overdue_batches": {
            "count": 1,
            "items": [{"batch_id": "B1", "due_date": "2026-06-12", "finish_time": "2026-06-13 00:00:00"}],
        }
    }
    impact = _build(todo_items=[_overdue_todo()], latest_summary=summary)["hero"]["impact_text"]
    assert "1 个批次会晚于交期" in impact
    assert "逾期最久 B1 晚 不到 1 小时" in impact


def test_overdue_clue_all_unparseable_says_cannot_judge() -> None:
    # 全部交期无法解析（脏历史摘要）→ 不静默退回笼统句掩盖，明示「暂不能判断逾期最久」
    summary = {
        "overdue_batches": {
            "count": 2,
            "items": [
                {"batch_id": "B1", "due_date": "见图纸", "finish_time": "2026-06-14 06:00:00"},
                {"batch_id": "B2", "due_date": "", "finish_time": "2026-06-15 06:00:00"},
            ],
        }
    }
    impact = _build(todo_items=[_overdue_todo()], latest_summary=summary)["hero"]["impact_text"]
    assert "2 个批次会晚于交期" in impact
    assert "暂不能判断逾期最久" in impact
    assert "逾期最久 B" not in impact  # 不冒充某条为最久


def test_overdue_clue_truncated_and_unparseable_combines_hedges() -> None:
    # 截断(count>len) 且部分解析失败 → 标注「基于前 N 条中可解析的」，两重 hedge 都诚实反映
    summary = {
        "overdue_batches": {
            "count": 9,
            "items": [
                {"batch_id": "BAD", "due_date": "坏", "finish_time": "2026-06-20 00:00:00"},
                {"batch_id": "B2", "due_date": "2026-06-12", "finish_time": "2026-06-14 06:00:00"},
            ],
        }
    }
    impact = _build(todo_items=[_overdue_todo()], latest_summary=summary)["hero"]["impact_text"]
    assert "9 个批次会晚于交期" in impact
    assert "基于前 2 条中可解析的" in impact
    assert "逾期最久 B2" in impact


def test_overdue_clue_truncated_says_based_on_first_n() -> None:
    # count(10) > len(items)(2)：被裁剪 → 明示「基于前 2 条」不冒充全量最严重
    summary = {
        "overdue_batches": {
            "count": 10,
            "items": [
                {"batch_id": "B1", "due_date": "2026-06-12", "finish_time": "2026-06-13 06:00:00"},
                {"batch_id": "B2", "due_date": "2026-06-12", "finish_time": "2026-06-14 06:00:00"},
            ],
        }
    }
    impact = _build(todo_items=[_overdue_todo()], latest_summary=summary)["hero"]["impact_text"]
    assert "10 个批次会晚于交期" in impact
    assert "基于前 2 条" in impact
    assert "逾期最久 B2" in impact


def test_overdue_clue_accepts_legacy_list_shape() -> None:
    # overdue_batches 为 list（legacy 形态）：_overdue_payload 归一为 count=len/items=list，
    # 线索照常产出，不因形态退化而丢线索。
    summary = {
        "overdue_batches": [
            {"batch_id": "B1", "due_date": "2026-06-12", "finish_time": "2026-06-13 06:00:00"},
            {"batch_id": "B2", "due_date": "2026-06-12", "finish_time": "2026-06-15 12:00:00"},
        ]
    }
    impact = _build(todo_items=[_overdue_todo()], latest_summary=summary)["hero"]["impact_text"]
    assert "2 个批次会晚于交期" in impact
    assert "逾期最久 B2 晚 2 天 12 小时" in impact
    assert "基于前" not in impact  # count==len（list 归一）不触发截断 hedge


def test_overdue_clue_all_within_due_returns_plain_count_sentence() -> None:
    # items 非空但全部 finish < due_exclusive（无可定位最久、且全部可解析）→ 退回纯 count 句，
    # 不编造「逾期最久」线索（诚实降级分支）。
    summary = {
        "overdue_batches": {
            "count": 2,
            "items": [
                {"batch_id": "B1", "due_date": "2026-06-20", "finish_time": "2026-06-13 06:00:00"},
                {"batch_id": "B2", "due_date": "2026-06-20", "finish_time": "2026-06-14 06:00:00"},
            ],
        }
    }
    impact = _build(todo_items=[_overdue_todo()], latest_summary=summary)["hero"]["impact_text"]
    assert impact == "2 个批次会晚于交期"
    assert "逾期最久" not in impact


# --- 日期解析整串匹配（修2：坏后缀不被静默截断冒充正常时间）---


def test_overdue_count_value_rejects_unicode_digits_without_crash() -> None:
    # '²'/'③'/'½' 等 unicode 数字 isdigit()==True 但 int() 抛 ValueError → 须当无法解析返回 None 降级，
    # 不冒泡崩溃（守卫语义：剔非整数→降级不抛）。
    from web.viewmodels.dashboard_cockpit_hero import _overdue_count_value

    for bad in ("²", "③", "½"):
        assert _overdue_count_value({"count": bad}) is None
    assert _overdue_count_value({"count": "5"}) == 5
    assert _overdue_count_value({"count": 5}) == 5


def test_parse_dt_rejects_garbage_suffix_with_full_string_match() -> None:
    # 整串匹配——坏后缀 / 非法时间不被截断成合法日期（否则漏计 unparseable、冒充正常逾期线索）
    from web.viewmodels.dashboard_cockpit_hero import _parse_dt

    assert _parse_dt("2026-06-12xyz") is None
    assert _parse_dt("2026-06-13 99:99:99") is None
    # 合法格式仍正常解析（兼容斜杠 / T 分隔 / 纯日期 / 分钟级）
    assert _parse_dt("2026-06-13 08:00:00") is not None
    assert _parse_dt("2026/06/12") is not None
    assert _parse_dt("2026-06-13T08:00") is not None
    assert _parse_dt("2026-06-13") is not None


def test_overdue_clue_garbage_suffix_finish_not_silently_truncated() -> None:
    # B1 完工时间带坏后缀 'xyz'（旧逻辑截断成 2026-06-20 会冒充最严重）→ 整串匹配应记 unparseable，
    # 只能诚实报次严重 B2 并挂「可解析批次里」标注，绝不让 B1 以截断日期冒充逾期最久
    summary = {
        "overdue_batches": {
            "count": 2,
            "items": [
                {"batch_id": "B1", "due_date": "2026-06-12", "finish_time": "2026-06-20xyz"},
                {"batch_id": "B2", "due_date": "2026-06-12", "finish_time": "2026-06-14 06:00:00"},
            ],
        }
    }
    impact = _build(todo_items=[_overdue_todo()], latest_summary=summary)["hero"]["impact_text"]
    assert "2 个批次会晚于交期" in impact
    assert "可解析批次里逾期最久 B2" in impact
    assert "B1" not in impact  # 坏后缀不得截断成 06-20 冒充最久
