"""Snapshot-local indexes for immutable identities, locks, frozen arrangements and execution facts."""

from datetime import date, datetime, time
from types import SimpleNamespace

from core.errors import ValidationError
from core.models.workbench_trial import issue
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.run.input_config import candidate_config, hold_window, window_label
from core.services.workbench.run.input_runtime import held_arrangements

from .materials import adoption_settings, hold_settings


def frozen_arrangements(conn, admission, rows, live, checks):
    """{工序: 原安排}：正式采用时按来源排产的不重排时段原样保留的工序。

    与试调采用复核同一口径：同一份排产输入（冻结从来源排产的起日起算）、同一份正式计划、
    同一批要重排的工序，由排产计算同一套保留规则找出。正式计划里锁定的仍按固定工序处理，
    不在这里。冻结资料读不出来时抛 AppError，由调用方提示。
    """
    version = live["baseline"]["version"]
    if version is None:
        return {}
    settings = adoption_settings(admission, rows, checks, live["execution"])
    anchor = hold_settings(admission, settings)
    try:
        cfg = candidate_config(conn, settings)
    except ValidationError:
        # 排产参数本身读不出来时，正式采用会直接拦下并说明是哪项参数；这里不替它判冻结。
        return {}
    tables = live["facts"]["tables"]
    batch_ids = {row["original"]["batch"]["batch_id"] for row in rows}
    operations = [SimpleNamespace(**op) for op in tables["BatchOperations"] if op["batch_id"] in batch_ids]
    moving = _rescheduled_ids(rows, live)
    # 正式计划在 live 里已整表读出，锁定状态直接从中取，不再逐次从库里流式读一遍。
    schedule = sorted((row for row in tables["Schedule"] if row["version"] <= version), key=lambda row: (row["version"], row["id"]))
    seeds, meta = held_arrangements(
        ScheduleService(conn), cfg=cfg, prev_version=version,
        start_dt=datetime.combine(date.fromisoformat(anchor["start_date"]), time.min),
        operations=operations, reschedulable_operations=[op for op in operations if op.id in moving],
        schedule_rows=schedule, hold_window=hold_window(conn, anchor)[0])
    locked = set(meta.get("explicit_locked_op_ids") or ())
    return {seed["op_id"]: dict(seed, hold_window=meta.get("hold_window")) for seed in seeds if seed["op_id"] not in locked}


def _rescheduled_ids(rows, live):
    """采用时会重排的工序：未报工、未关闭；合并外协组按实际周期固定的成员也参与查找。

    资料不全、会被采用拦下的工序这里不再细分，它们的批次无论如何都采用不了。
    """
    tables = live["facts"]["tables"]
    ops = {row["id"]: row for row in tables["BatchOperations"]}
    batches = {row["batch_id"]: row for row in tables["Batches"]}
    result = set()
    for row in rows:
        original = row["original"]
        op, anchor = ops.get(original["operation"]["id"]), original.get("execution_anchor")
        if anchor is not None:
            if anchor["basis"] == "merged_external_actuals":
                result.add(original["operation"]["id"])
            continue
        batch = batches.get(op["batch_id"]) if op else None
        projection = live["execution"].get(row["operation_ref"]) or {}
        if (batch is not None and projection.get("execution_state") == "unreported"
                and op["status"] not in ("skipped", "processing", "completed")
                and batch["status"] not in ("completed", "cancelled")):
            result.add(op["id"])
    return result


def frozen_issue(row, seed, *, changed):
    held = "{} 至 {}".format(seed["start_time"].isoformat(sep=" "), seed["end_time"].isoformat(sep=" "))
    # 同批前道跟着时段里的后道一起保留，它自己的安排不一定落在时段里，所以说"因……保持原安排"。
    head = "这道工序在正式计划里排在 {}，因来源排产的不重排时段（{}）要保持原安排，正式采用会原样保留这个安排".format(
        held, window_label(seed["hold_window"]))
    if changed:
        return issue("frozen_arrangement_changed", head + "；试调里的安排和它不同，不能正式采用。"
                     "请从当前正式计划重新发起试调；" + _RERUN, row["task_ref"])
    return issue("task_frozen", head + "，试调不能改它。" + _RERUN, row["task_ref"])


_RERUN = "这道工序如要改排，请重新排产，并在排产检查里把不重排时段改短或不设。"


def frozen_note(item, seed):
    """按时段保留、试调不能改的工序上查出的问题：补一句为什么改不了、该怎么办。"""
    return dict(item, message=item["message"] + "这道工序因来源排产的不重排时段（{}）要保持原安排，试调不能改，正式采用会被拦下。".format(
        window_label(seed["hold_window"])) + _RERUN)


def keeps_frozen(row, seed):
    current = row["current"]
    return ((current["machine_id"], current["operator_id"]) == (seed["machine_id"], seed["operator_id"])
            and datetime.fromisoformat(current["start"]) == seed["start_time"]
            and datetime.fromisoformat(current["end"]) == seed["end_time"])


class TrialProtection:
    def __init__(self, live, frozen=None):
        self.frozen = frozen or {}
        tables = live["facts"]["tables"]
        self.identities = {row["ref"]: row for row in tables["WorkbenchPlanSourceRefs"] if row["kind"] == "operation"}
        self.latest = {}
        for row in tables["Schedule"]:
            old = self.latest.get(row["op_id"])
            if old is None or (row["version"], row["id"]) > (old["version"], old["id"]):
                self.latest[row["op_id"]] = row
        self.execution = live["execution"]
        self.operations = {row["id"]: row for row in tables["BatchOperations"]}
        self.batches = {row["batch_id"]: row for row in tables["Batches"]}

    def check(self, row):
        return self._identity_and_lock(row) or self._execution(row) or self._frozen(row) or self._closed(row)

    def _frozen(self, row):
        seed = self.frozen.get(row["original"]["operation"]["id"])
        return frozen_issue(row, seed, changed=False) if seed is not None else None

    def _identity_and_lock(self, row):
        original, ref = row["original"], row["task_ref"]
        op_id = original["operation"]["id"]
        identity = self.identities.get(row["operation_ref"])
        if identity is None or identity["active"] != 1 or identity["source_key"] != str(op_id):
            return issue("operation_identity_changed", "该工序已删除或被替换，无法继续调整。", ref)
        if not original["lock_known"]:
            return issue("lock_state_unknown", "这道工序是不是已固定读不到，这里不当成未固定处理。", ref)
        latest = self.latest.get(op_id)
        if latest is not None and latest["lock_status"] != "unlocked":
            return issue("task_locked", "固定工序不可调整。", ref)
        # 候选方案行的 locked 含因不重排时段保留的工序；正式计划里没锁的这类工序交给 _frozen 说明是哪个时段。
        if original["locked"] and op_id not in self.frozen:
            return issue("task_locked", "固定工序不可调整。", ref)
        return None

    def _execution(self, row):
        original, ref = row["original"], row["task_ref"]
        if (original.get("execution_anchor") or {}).get("basis") == "merged_external_actuals":
            return issue("execution_protected", "合并外协组已有实际记录，整组周期不能单独调整。", ref)
        execution = self.execution.get(row["operation_ref"])
        if execution is None or execution["data_quality"] == "invalid":
            return issue("execution_unproven", "这道工序的报工记录缺失或有坏数据，不能确认可以调整。", ref)
        for facts in (execution, original["execution"]):
            if facts and (facts["execution_state"] != "unreported" or facts["reports"] or facts["legacy_facts"]
                          or facts["first_actual_start"] or facts["confirmed_finish"]):
                return issue("execution_protected", "这道工序已经开工、报工或完工，不能用试调改安排。", ref)
        return None

    def _closed(self, row):
        op_id, ref = row["original"]["operation"]["id"], row["task_ref"]
        op = self.operations.get(op_id)
        batch = self.batches.get(op["batch_id"]) if op else None
        if op is None or batch is None or op["status"] not in ("pending", "scheduled") or batch["status"] not in ("pending", "scheduled", "processing"):
            return issue("operation_not_editable", "原工序或批次已关闭、跳过，或状态不能证明可调整。", ref)
        return None
