"""Carry the chosen material policy into trial moves and adoption."""

from datetime import date, datetime, timedelta

from core.models.scheduler_history_parser import parse_result_summary_payload
from core.models.workbench_preflight import stored_hold_window_valid
from core.models.workbench_trial import issue, reject
from core.services.workbench.facts.preflight_checks import stored_date


def plan_material_policy(history):
    raw = history["result_summary"] if history is not None else None
    # Every official plan's adoption audit records the run's material policy and dates.
    summary = parse_result_summary_payload(raw).payload
    if summary is None or "material_policy" not in summary:
        reject("material_policy_invalid", "原计划没有记录物料放行方式和排产起止日期，请核对排产记录。")
    policy = summary["material_policy"]
    if (not isinstance(policy, dict) or type(policy.get("ready_check")) is not bool
            or policy.get("material_strategy") not in ("strict", "stage")):
        reject("material_policy_invalid", "原计划的物料放行方式无效，请核对排产记录。")
    if not _window_valid(policy):
        reject("material_policy_invalid", "原计划记录的排产起止日期无效，请核对排产记录。")
    if "hold_window" in policy and not stored_hold_window_valid(policy["hold_window"]):
        reject("material_policy_invalid", "原计划记录的不重排时段无效，请核对排产记录。")
    return policy


def _window_valid(policy):
    days = [policy.get(key) for key in ("start_date", "end_date")]
    return all(type(day) is str and stored_date(day) == day for day in days) and days[0] <= days[1]


def _run_settings(admission):
    """A candidate source keeps its run input; an official plan source keeps its validated material policy."""
    source = admission["source"]
    return source["capture"]["input"] if "capture" in source else source["material_policy"]


def run_policy(admission):
    settings = _run_settings(admission)
    # material_strategy is optional in a run input and means whole-batch readiness when omitted.
    return {"ready_check": settings["ready_check"], "material_strategy": settings.get("material_strategy", "strict")}


def run_window(admission):
    """The run dates that left stage work pending, as the source recorded them.

    A candidate keeps its run input. Official plans record it when adopted.
    """
    settings = _run_settings(admission)
    # 来源记下的不重排时段随起止日一起带给正式计划；来源没设的不补，按交付设置推算。
    return {"start_date": settings["start_date"], "end_date": settings["end_date"],
            **({"hold_window": settings["hold_window"]} if "hold_window" in settings else {})}


def deferral_policy(admission, rows, checks, execution):
    """Run policy plus the dates that decide which stage work may stay pending.

    Work missing from the saved rows is judged by the source run's own end date,
    not by a later locked or moved row, exactly as the run and a direct adoption
    judge it. The end only moves later for a material or ready day that a saved,
    still unreported row waits for, so such a row is not turned into pending
    work. Rows with actual production keep their arrangement whatever the window
    and add no day. Without stage deferral the saved span is used.
    """
    policy = run_policy(admission)
    first = min(row["current"]["start"][:10] for row in rows)
    last = max(row["current"]["end"][:10] for row in rows)
    if policy["material_strategy"] != "stage" or policy["ready_check"] is not True:
        return dict(policy, start_date=first, end_date=last)
    recorded = run_window(admission)["end_date"]
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
    与来源排产同一口径，不随试调各行最早的日子挪动。"""
    window = run_window(admission)
    start = window["start_date"]
    out = dict(settings, start_date=start)
    if "hold_window" in window:
        out["hold_window"] = _within(window["hold_window"], start, max(window["end_date"], settings["end_date"]))
    return out


def _within(window, start_date, end_date):
    if window is None:
        return None
    low = start_date + "T00:00"
    high = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat() + "T00:00"
    start, end = max(window["start"], low), min(window["end"], high)
    return {"start": start, "end": end} if start < end else None


def _window_classified(row, execution):
    # Anchored or reported work is protected (or refused) by the run input before any date check.
    return (row["original"].get("execution_anchor") is None
            and execution[row["operation_ref"]]["execution_state"] == "unreported")


def material_issues(admission, checks, row):
    policy = {**run_policy(admission), "end_date": row["current"]["end"][:10]}
    original = row["original"]
    problems, day = checks.operation_readiness(original["batch"], original["operation"], policy)
    result = [issue(item["code"], item["message"], row["task_ref"]) for item in problems]
    if day and datetime.fromisoformat(row["current"]["start"]) < datetime.fromisoformat(day):
        result.append(issue("before_material_date", "安排早于本序物料到齐日期，请后移至 " + day + " 或之后。", row["task_ref"]))
    return result
