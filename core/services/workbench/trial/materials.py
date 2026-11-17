"""Carry the chosen material policy into trial moves and adoption.

Every function reads the run settings the trial's typed source recorded (``TrialSource.settings``): a candidate's
run input, or the material policy an official plan recorded when it was adopted.
"""

from datetime import date, timedelta

from core.models.workbench_preflight import normalize_preflight_input
from core.shared.stored_dates import stored_date


def run_policy(source):
    settings = source.settings
    return {"ready_check": settings["ready_check"], "material_strategy": settings["material_strategy"]}


def run_window(source):
    """The run dates that left stage work pending, as the source recorded them."""
    settings = source.settings
    # 来源记下的不重排时段随起止日一起带给正式计划；来源没设的不补，按交付设置推算。
    return {"start_date": settings["start_date"], "end_date": settings["end_date"],
            **({"hold_window": settings["hold_window"]} if "hold_window" in settings else {})}


def deferral_policy(source, rows, checks, execution, *, span):
    """Run policy plus the dates that decide which stage work may stay pending.

    ``span`` is the rows' first start day and last end day, taken from their admitted
    intervals. Work missing from the saved rows is judged by the source run's own end date,
    not by a later locked or moved row, exactly as the run and a direct adoption
    judge it. The end only moves later for a material or ready day that a saved,
    still unreported row waits for, so such a row is not turned into pending
    work. Rows with actual production keep their arrangement whatever the window
    and add no day. Without stage deferral the saved span is used.
    """
    policy = run_policy(source)
    first, last = span
    if policy["material_strategy"] != "stage" or policy["ready_check"] is not True:
        return dict(policy, start_date=first, end_date=last)
    recorded = run_window(source)["end_date"]
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


def adoption_settings(source, rows, checks, execution, *, span):
    """The one-run input a trial adoption is rechecked with.

    试调判断哪些原安排不能改也用这份输入：不重排时段沿用来源排产记下的（裁到这次的起止日内；
    试调各行都在起止日内，裁剪不改变哪些原安排落在时段里）；来源没记的不带这个键，按交付设置推算。
    ``span`` 是各行准入后的最早开始日与最晚结束日。
    这份输入在这里按提交侧同一入口（normalize_preflight_input）准入一次，下游（含 prepare_business_input）直接用。
    """
    settings = {"batch_refs": sorted({row["original"]["batch_ref"] for row in rows}),
                "missing_resource_policy": "auto_assign", "completed_policy": "preserve_actuals",
                **deferral_policy(source, rows, checks, execution, span=span)}
    recorded = source.settings
    if "hold_window" in recorded:
        settings["hold_window"] = _within(recorded["hold_window"], settings["start_date"], settings["end_date"])
    return normalize_preflight_input(settings)


def hold_settings(source, settings):
    """判断哪些原安排保留时用的排产输入：冻结从来源排产的起日起算，默认时段也从那天推算，
    与来源排产同一口径，不随试调各行最早的日子挪动。"""
    window = run_window(source)
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
