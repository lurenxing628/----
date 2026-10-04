"""排产检查核对排产会原样保留的原安排：正式计划里锁定的，以及落在本次不重排时段里的。

排产计算把这些安排原样留下，候选采用时却按现在的资料逐条复核（与 candidate_adoption_constraints 同一口径）；
两边对不上，排出的方案都采用不了。这里在开始前用排产计算同一套保留规则先找出这些安排，
指出是哪道工序、该去哪里改：时段里的可以在排产检查把不重排时段改短或不设；锁定的（以前采用时继承下来的）
工作台里没有解锁入口，只能改资料，或请维护人员解除锁定。
"""

from collections import defaultdict
from datetime import datetime
from types import SimpleNamespace

from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.errors import AppError, ValidationError
from core.models.operation_execution_event import parse_operation_event_time
from core.models.workbench_preflight import issue, local_date
from core.models.workbench_run_compute import CandidateRunInputError
from core.services.scheduler.calendar.service import CalendarService
from core.services.workbench.facts.preflight_checks import number
from core.services.workbench.facts.table_cells import number_text
from core.services.workbench.facts.zero_duration import PointEventError, estimate_point_event, internal_duration_hours

from .candidate_adoption_constraints import arrangement_problem, calendar_duration_conflict, external_holds_resources
from .input_config import candidate_config, hold_window, window_label
from .input_runtime import downtime_overlap, held_arrangements, held_machine_downtimes

_KEEP = "排产会原样保留这个安排，排出的方案都不能采用。"
# 设备人员资格问题逐项说清楚；工种、自制外协、供应商等工序资料问题合成一句。
_RESOURCE_REASONS = {
    "machine_missing": "设备已停用或不再做这个工种",
    "operator_missing": "人员已停用或不在岗",
    "operator_skill_missing": "人员没有这个工种的资格",
    "machine_authorization_missing": "人员没有这台设备的操作授权",
}


def _time(value):
    return value.isoformat(sep=" ")


def _name(value):
    return value if value is not None else "（未填）"


_SHORTEN = "到排产检查把不重排时段改短或不设"
_UNLOCK = "这道工序在正式计划里是锁定的，工作台里不能解锁；确需改排，请联系维护人员解除锁定"


class _Held:
    """一条保留安排在提示里的说法和出路。"""

    def __init__(self, seed, locked, window):
        self.seed, self.locked = seed, locked
        span = f"{_time(seed['start_time'])} 至 {_time(seed['end_time'])}"
        self.text = (f"这道工序在正式计划里锁定在 {span}" if locked
                     else f"这道工序在正式计划里排在 {span}，因不重排时段（{window_label(window)}）保持原安排")

    def action(self, fix):
        if self.locked:
            return f"请{fix}。{_UNLOCK}。"
        return f"请{fix}，或{_SHORTEN}。"


class _Context:
    def __init__(self, checks, calendar, downtimes, settings, batches, operations, contexts, finished):
        self.checks, self.calendar, self.downtimes, self.settings = checks, calendar, downtimes, settings
        self.finished = finished
        self.batches = {row["batch_id"]: row for row in batches}
        # 分件批次与分件采用同口径：分件工序按 1 件、共同工序按整批数量算工时。
        self.piece_batches = {op["batch_id"] for op in operations if op["piece_id"] is not None}
        self.external_contexts = contexts

    def quantity(self, op, batch):
        return 1 if op["piece_id"] is not None else batch["quantity"]

    def external_days(self, op):
        """与排产输入同口径：合并外协组按整组周期，其余按本道外协周期；读不出有效天数返回 None（由资料检查另行拦下）。"""
        context = self.external_contexts.get(op["id"]) or {}
        days = context.get("total_days") if context.get("merge_mode") == "merged" else op["ext_days"]
        return days if number(days, positive=True) else None


def _resource_problem(context, held, batch, raw):
    found = [item["code"] for item in context.checks.fields(batch, raw) + context.checks.resources(raw)]
    reasons = [_RESOURCE_REASONS[code] for code in found if code in _RESOURCE_REASONS]
    if len(reasons) < len(found):
        reasons.append("这道工序的工种、自制外协或供应商资料和原安排对不上")
    seed = held.seed
    return issue("locked_resource_invalid",
        f"{held.text}，用的是设备 {_name(seed['machine_id'])}、人员 {_name(seed['operator_id'])}，但"
        + "、".join(reasons) + "。" + _KEEP + held.action("到资料总览核对设备、人员和工种"))


def _release_problem(context, held, batch, raw, code):
    if code == "candidate_before_ready_date":
        return issue("locked_before_ready_date", f"{held.text}，但这批的齐套日期是 {batch['ready_date']}，比原安排晚。"
                     + _KEEP + held.action("到批次管理核对齐套日期"))
    _issues, day = context.checks.operation_readiness(batch, raw, context.settings)
    late = f"本序物料要到 {day} 才到齐" if day else "本序物料还没到齐"
    return issue("locked_material_late", f"{held.text}，但{late}。" + _KEEP + held.action("到批次管理核对物料到料"))


def _timing_problem(context, held, op, batch):
    seed = held.seed
    overlap = downtime_overlap(seed, context.downtimes)
    if overlap is not None:
        return issue("locked_downtime_conflict",
            f"{held.text}（设备 {seed['machine_id']}），但这台设备在 {_time(overlap[0])} 至 {_time(overlap[1])} 有停机。"
            "保留的安排排产时原样保留、不会避开停机，排出的方案都不能采用。" + held.action("到工作日历核对这条停机"))
    if seed["start_time"] == seed["end_time"]:
        return _point_problem(context, held, op, batch)
    if _duration_conflict(context, seed, op, batch):
        return issue("locked_calendar_conflict",
            f"{held.text}（设备 {seed['machine_id']}、人员 {seed['operator_id']}），但按现在的工作日历、个人日历和效率重算，"
            "这道工序的开工、完工时间和这段安排对不上（例如其间改成了休息或请假，或工时、效率改过）。" + _KEEP + held.action("到工作日历或这个人的个人日历核对这几天"))
    return None


def _duration_conflict(context, seed, op, batch):
    downtimes = context.downtimes.get(seed["machine_id"], ())
    if op["batch_id"] not in context.piece_batches:
        return calendar_duration_conflict(context.calendar, SimpleNamespace(**seed), SimpleNamespace(**op),
                                          SimpleNamespace(**batch), downtimes)
    try:
        total = internal_duration_hours(op["setup_hours"], op["unit_hours"], context.quantity(op, batch))
    except PointEventError:
        return False  # 工时或数量读不出来由资料检查和分件范围检查拦下，这里不重复报成时间对不上
    slot = estimate_internal_slot(calendar=context.calendar, op=SimpleNamespace(**op), batch=SimpleNamespace(**batch),
        machine_id=seed["machine_id"], operator_id=seed["operator_id"], base_time=seed["start_time"],
        prev_end=seed["start_time"], machine_timeline=(), operator_timeline=(), end_dt_exclusive=None,
        machine_downtimes=downtimes, last_op_type_by_machine=None, abort_after=None, total_hours_base=total)
    return bool(slot.efficiency_fallback_used or (slot.start_time, slot.end_time) != (seed["start_time"], seed["end_time"]))


def _point_problem(context, held, op, batch):
    """零工时安排与采用同口径：按现在的工时、班次和效率，这个时刻本身要成立。"""
    seed = held.seed
    try:
        start, _end = estimate_point_event(context.calendar, setup_hours=op["setup_hours"], unit_hours=op["unit_hours"],
            quantity=context.quantity(op, batch), machine_id=seed["machine_id"], operator_id=seed["operator_id"],
            priority=batch["priority"], start=seed["start_time"])
    except PointEventError as exc:
        reason = "这道工序现在有工时，不再是零工时工序。" if exc.code == "point_duration_nonzero" else str(exc)
    else:
        if start == seed["start_time"]:
            return None
        reason = f"按现在的工作日历，这一刻不能开工，最早要到 {_time(start)}。"
    return issue("locked_point_conflict", f"{held.text}，原安排是开工即完工的零工时安排，但{reason}"
                 + _KEEP + held.action("到批次管理核对这道工序的工时，或到工作日历核对这一天"))


def _external_problem(context, held, op):
    seed = held.seed
    if external_holds_resources(SimpleNamespace(**seed)):
        return issue("locked_external_resource_conflict",
            f"{held.text}，原安排占着设备 {_name(seed['machine_id'])}、人员 {_name(seed['operator_id'])}，"
            "但这道工序现在是外协，外协安排不能占本厂设备人员。" + _KEEP + held.action("到批次管理核对这道工序的自制外协设置"))
    days = context.external_days(op)
    if days is None:
        return None
    expected = context.calendar.add_calendar_days(seed["start_time"], days)
    if expected == seed["end_time"]:
        return None
    return issue("locked_external_cycle_conflict",
        f"{held.text}，但这道外协工序现在的周期是 {number_text(days)} 天，按工作日历应在 {_time(expected)} 回厂，"
        "和原安排的回厂时间对不上（例如改过外协周期或合并分组）。" + _KEEP + held.action("到批次管理核对这道工序的外协周期"))


def _completed(facts, operations, projections):
    """{批次: [(已完工工序, 实际完工)]}：排产计算以实际完工为准，同批后道的保留安排不能早于它开工。"""
    result = defaultdict(list)
    for op in operations:
        projection = projections.get(facts.operation_ref(op)) or {}
        if projection.get("execution_state") != "complete" or projection.get("confirmed_finish") is None:
            continue
        try:
            result[op["batch_id"]].append((op, parse_operation_event_time(projection["confirmed_finish"])))
        except (AppError, ValueError, TypeError):
            continue  # 完工时间读不出来由报工核对另行拦下
    return result


def _finish_problem(context, held, op):
    """与排产计算同口径（分件只比同一件和共同工序）：保留的安排早于同批已完工前道的实际完工，整次排产会被拦下。"""
    for done, finish in context.finished.get(op["batch_id"], ()):
        related = done["piece_id"] is None or op["piece_id"] is None or done["piece_id"] == op["piece_id"]
        if related and done["seq"] < op["seq"] and held.seed["start_time"] < finish:
            return issue("locked_predecessor_finish_conflict",
                f"{held.text}，但同批前道第 {done['seq']} 道（{done['op_type_name']}）实际 {_time(finish)} 才完工，"
                "晚于这个安排的开工，排产会被拦下。" + held.action("到现场记录核对前道的实际完工时间"))
    return None


def _seed_problem(context, held, op):
    """与候选采用逐行复核同一顺序：先资料和资格、物料和齐套日期，再按自制外协核对占用和时长。"""
    finish = _finish_problem(context, held, op)
    if finish is not None:
        return finish
    seed = held.seed
    batch = context.batches[op["batch_id"]]
    raw = dict(op, machine_id=seed["machine_id"], operator_id=seed["operator_id"])
    code = arrangement_problem(context.checks, batch, raw, seed["start_time"], context.settings)
    if code == "candidate_resource_invalid":
        return _resource_problem(context, held, batch, raw)
    if code is not None:
        return _release_problem(context, held, batch, raw, code)
    if seed["source"] == "internal":
        return _timing_problem(context, held, op, batch)
    return _external_problem(context, held, op)


def _cycle_problem(held, cycle):
    """合并外协组已有实际周期时，同组未报工成员的保留安排必须与它一致，否则排产会拒绝整次计算。"""
    start, end = datetime.fromisoformat(cycle["start"]), datetime.fromisoformat(cycle["end"])
    seed = held.seed
    if (seed["start_time"], seed["end_time"]) == (start, end):
        return None
    head = f"合并外协组已按报工确认实际周期 {_time(start)} 至 {_time(end)}，但同组"
    if held.locked:
        return issue("external_cycle_locked_conflict", head + held.text + "，排产会被拦下。"
                     f"{_UNLOCK}，解除后排产会让它跟同组按实际周期保留。")
    return issue("external_cycle_locked_conflict", head + held.text + "，排产会原样保留它，和实际周期对不上，排产会被拦下。"
                 f"请到现场记录核对同组报工的实际时间；报工无误时，请{_SHORTEN}。")


def _unreadable():
    return issue("freeze_window_unavailable", "排产要原样保留不重排时段里的原安排，但正式计划里这段时间的安排"
                 f"读不出来或者对不上，排产会被拦下。请{_SHORTEN}，或联系维护人员核对正式计划。")


def _skipped_freeze(meta, batches):
    refs = {row["batch_id"]: row["ref"] for row in batches}
    message = (f"这批后面工序的原安排在不重排时段（{window_label(meta.get('hold_window'))}）内，但前面还有没报工的工序原安排"
               "排在排产起日之前，或者还没排过，整批前后顺序保不住，这次这批不保留原安排，会和其它工序一起重排。"
               "如前道其实已经开工或做完，请先到现场记录登记报工再排产，就能保留后道的原安排。")
    return [issue("freeze_window_skipped", message, batch_ref=refs.get(batch_id), batch_id=batch_id)
            for batch_id in sorted(meta.get("freeze_skipped_batch_ids") or ())]


# 排产参数本身读不出来时，排产计算会直接报出是哪项参数；排产检查不替它拦，只按显式锁定核对。
_FREEZE_OFF = SimpleNamespace(freeze_window_enabled="no", freeze_window_days=0, degradation_events=())


def _held(facts, svc, settings, version, operations, held_ids):
    models = [SimpleNamespace(**op) for op in operations]
    try:
        cfg = candidate_config(facts.conn, settings)
    except ValidationError:
        cfg = _FREEZE_OFF
    seeds, meta = held_arrangements(
        svc, cfg=cfg, prev_version=version,
        start_dt=datetime.combine(local_date(settings["start_date"]), datetime.min.time()),
        operations=models, reschedulable_operations=[op for op in models if op.id in held_ids],
        schedule_rows=facts.schedule_through(version), hold_window=hold_window(facts.conn, settings)[0])
    return seeds, meta


def _marks(seeds, locked):
    """{工序: 保留标记}：排产检查结果里每道工序 held 字段的来源。"""
    return {seed["op_id"]: {"basis": "locked" if seed["op_id"] in locked else "hold_window",
                            "start": seed["start_time"].isoformat(), "end": seed["end_time"].isoformat()} for seed in seeds}


def held_arrangement_reasons(facts, svc, checks, settings, version, batches, operations, held_ids, cycles, projections):
    """返回 (阻断原因, 提醒, {工序: 保留标记})。

    held_ids 是这次要重排的工序（资料有效、自动分配待补）加上合并外协组派生保留的成员，与排产计算查锁定和不重排时段的范围一致；
    cycles 是这些成员的实际周期；其余外协按现在的外协周期、零工时按现在的班次、分件按每件数量复核，与采用同口径；
    projections 是这些工序的执行投影，已完工前道的实际完工按它核对。
    """
    if not held_ids:
        return [], [], {}
    by_id = {op["id"]: op for op in operations}
    try:
        seeds, meta = _held(facts, svc, settings, version, operations, held_ids)
    except CandidateRunInputError as exc:
        return [facts.public_issue(item, by_id[item["op_id"]]) if item.get("op_id") in by_id else item for item in exc.issues], [], {}
    except AppError:
        return [_unreadable()], [], {}
    contexts = {row["operation_id"]: row for row in facts.tables.get("BatchExternalContexts", [])}
    context = _Context(checks, CalendarService(facts.conn), held_machine_downtimes(svc, seeds), settings, batches, operations,
                       contexts, _completed(facts, operations, projections))
    locked = set(meta.get("explicit_locked_op_ids") or ())
    blockers = _seed_blockers(facts, context, seeds, by_id, locked, meta.get("hold_window"), cycles)
    # 合并外协组成员只在不在保留安排里时才由排产按实际周期派生、排产照常出结果；全都在保留安排里排产会直接停下。
    if held_ids <= {seed["op_id"] for seed in seeds}:
        blockers.append(_all_held(held_ids & locked, held_ids - locked))
    return blockers, _skipped_freeze(meta, batches), _marks(seeds, locked)


def _seed_blockers(facts, context, seeds, by_id, locked, window, cycles):
    blockers = []
    for seed in seeds:
        held = _Held(seed, seed["op_id"] in locked, window)
        op = by_id[seed["op_id"]]
        problem = _cycle_problem(held, cycles[op["id"]]) if op["id"] in cycles else _seed_problem(context, held, op)
        if problem is not None:
            blockers.append(facts.public_issue(problem, op))
    return blockers


def _all_held(locked, frozen):
    """要重排的工序全都原样保留时，排产计算没有可排的工序会直接停下；排产检查先说清楚。"""
    where = "、".join((["在正式计划里锁定"] if locked else []) + (["落在不重排时段里"] if frozen else []))
    fixes = ([_SHORTEN] if frozen else []) + (["请维护人员解除不需要的锁定（工作台里不能解锁）"] if locked else [])
    return issue("all_tasks_held", f"选中批次里要排的工序都{where}，排产会原样保留它们，这次没有可以重新排的工序，"
                 "排产会直接停下。请多勾选要排的批次，或" + "、".join(fixes) + "。")
