"""Carry the chosen material policy into trial moves and adoption."""

import json
from datetime import date, datetime, timedelta

from core.models.workbench_preflight import stored_hold_window_valid
from core.models.workbench_trial import issue, reject
from core.services.workbench.facts.preflight_checks import stored_date
from data.repositories.schedule_history_repo import ScheduleHistoryRepository


def plan_material_policy(conn, version):
    history = ScheduleHistoryRepository(conn).get_by_version(version)
    raw = history.result_summary if history else None
    if not raw:
        return {}
    try:
        summary = json.loads(raw)
    except (ValueError, TypeError):
        # Legacy history summaries were plain display text, with no run settings.
        return {}
    if not isinstance(summary, dict) or "material_policy" not in summary:
        return {}
    policy = summary["material_policy"]
    if (not isinstance(policy, dict) or type(policy.get("ready_check")) is not bool
            or policy.get("material_strategy") not in ("strict", "stage", "split")):
        reject("material_policy_invalid", "原计划的物料放行方式无效，请核对排产记录。")
    if not _window_valid(policy):
        reject("material_policy_invalid", "原计划记录的排产起止日期无效，请核对排产记录。")
    if "hold_window" in policy and not stored_hold_window_valid(policy["hold_window"]):
        reject("material_policy_invalid", "原计划记录的不重排时段无效，请核对排产记录。")
    return policy


def _window_valid(policy):
    # Plans adopted before the run window was recorded carry neither date.
    days = [policy.get(key) for key in ("start_date", "end_date")]
    if days == [None, None]:
        return True
    return all(type(day) is str and stored_date(day) == day for day in days) and days[0] <= days[1]


def _run_settings(admission):
    source = admission.get("source", {})
    return source.get("capture", {}).get("input", source.get("material_policy", {}))


def run_policy(admission):
    settings = _run_settings(admission)
    return {"ready_check": settings.get("ready_check", True),
            "material_strategy": settings.get("material_strategy", "strict")}


def run_window(admission):
    """The run dates that left stage work pending; {} when the source never recorded them.

    A candidate keeps its run input. Official plans record it when adopted;
    older plans have none, and their trials keep the saved span as before.
    """
    settings = _run_settings(admission)
    window = {key: stored_date(settings.get(key)) for key in ("start_date", "end_date")}
    if None in window.values():
        return {}
    # 来源记下的不重排时段随起止日一起带给正式计划；没记的旧来源不补，按交付设置推算。
    return dict(window, **({"hold_window": settings["hold_window"]} if "hold_window" in settings else {}))


def deferral_policy(admission, rows, checks, execution):
    """Run policy plus the dates that decide which stage work may stay pending.

    Work missing from the saved rows is judged by the source run's own end date,
    not by a later locked or moved row, exactly as the run and a direct adoption
    judge it. The end only moves later for a material or ready day that a saved,
    still unreported row waits for, so such a row is not turned into pending
    work. Rows with actual production keep their arrangement whatever the window
    and add no day. Without a recorded window the saved span is used as before.
    """
    policy = run_policy(admission)
    first = min(row["current"]["start"][:10] for row in rows)
    last = max(row["current"]["end"][:10] for row in rows)
    recorded = run_window(admission).get("end_date")
    if recorded is None or policy["material_strategy"] != "stage" or policy["ready_check"] is not True:
        return dict(policy, start_date=first, end_date=last)
    waits = [recorded]
    for row in rows:
        if not _window_classified(row, execution):
            continue
        batch, op = row["original"]["batch"], row["original"]["operation"]
        _problems, day = checks.operation_readiness(batch, op, dict(policy, end_date=last))
        waits.extend(value for value in (day, stored_date(batch["ready_date"])) if value)
    end = max(waits)
    # Only when every saved row starts after that end does the start move back to it.
    return dict(policy, start_date=min(first, end), end_date=end)


def adoption_settings(admission, rows, checks, execution):
    """The one-run input a trial adoption is rechecked with.

    试调判断哪些原安排不能改也用这份输入：不重排时段沿用来源排产记下的（裁到这次的起止日内；
    试调各行都在起止日内，裁剪不改变哪些原安排落在时段里）；来源没记的不带这个键，按交付设置推算。
    """
    settings = {"batch_refs": sorted({row["original"]["batch_ref"] for row in rows}),
                "missing_resource_policy": "auto_assign", "completed_policy": "preserve_actuals",
                **deferral_policy(admission, rows, checks, execution)}
    source = _run_settings(admission)
    if "hold_window" in source:
        settings["hold_window"] = _within(source["hold_window"], settings["start_date"], settings["end_date"])
    return settings


def hold_settings(admission, settings):
    """判断哪些原安排保留时用的排产输入：冻结从来源排产的起日起算，默认时段也从那天推算，
    与来源排产同一口径，不随试调各行最早的日子挪动；来源没记起止日的旧方案仍按试调起日。"""
    start = run_window(admission).get("start_date")
    return settings if start is None else dict(settings, start_date=start)


def _within(window, start_date, end_date):
    if window is None:
        return None
    low = start_date + "T00:00"
    high = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat() + "T00:00"
    start, end = max(window["start"], low), min(window["end"], high)
    return {"start": start, "end": end} if start < end else None


def _window_classified(row, execution):
    # Anchored or reported work is protected (or refused) by the run input before any date check.
    projection = execution.get(row["operation_ref"]) or {}
    return (row["original"].get("execution_anchor") is None
            and projection.get("execution_state", "unreported") == "unreported")


def material_issues(admission, checks, row):
    policy = {**run_policy(admission), "end_date": row["current"]["end"][:10]}
    original = row["original"]
    problems, day = checks.operation_readiness(original["batch"], original["operation"], policy)
    result = [issue(item["code"], item["message"], row["task_ref"]) for item in problems]
    if day and datetime.fromisoformat(row["current"]["start"]) < datetime.fromisoformat(day):
        result.append(issue("before_material_date", "安排早于本序物料到齐日期，请后移至 " + day + " 或之后。", row["task_ref"]))
    return result
