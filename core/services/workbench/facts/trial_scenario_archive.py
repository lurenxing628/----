"""Verify saved scenario lineage; source draft supplies only immutable raw work."""

from dataclasses import dataclass

from core.models.workbench_trial import reference, reject
from core.models.workbench_trial_adoption import TrialAdoptionBlocked
from core.services.scheduler.run.schedule_payload_contract import ValidatedScheduleRow
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository

from .trial_origin import TrialOrigin
from .trial_policy import load_draft, load_scenario_with_resources


@dataclass(frozen=True)
class SavedTrialScenario:
    """A verified saved scenario, its draft head, save-time resources and its own rows."""

    saved: dict
    head: dict
    rows: list
    resources: dict
    origin: TrialOrigin


def load_verified_scenario(conn, scenario_ref):
    reference(scenario_ref)
    repo = WorkbenchTrialRepository(conn)
    header, saved, resources = load_scenario_with_resources(repo, scenario_ref)
    head, originals, source = load_draft(repo, header["draft_ref"])
    scenario_head = dict(head, scenario_revision=header["revision"])
    _require_head(saved, header, head)
    rows = bind_scenario_rows(saved, originals)
    origin = TrialOrigin.saved(scenario_head["admission"], rows, source)
    scenario = SavedTrialScenario(saved, scenario_head, rows, resources, origin)
    _require_saved_scope(scenario, originals)
    return scenario


def _require_head(saved, header, head):
    if (
        saved["scenario_ref"] != header["scenario_ref"]
        or saved["draft_ref"] != head["draft_ref"]
        or saved["status"] != "saved"
        or head["status"] != "saved"
        or saved["name"] != header["name"]
        or saved["saved_at"] != header["saved_at"]
        or type(head["revision"]) is not int
        or type(header["revision"]) is not int
        or head["revision"] != header["revision"] + 1
    ):
        reject("trial_snapshot_invalid", "试调方案和它的草稿编号或版本对不上。请刷新后重试。")


def _require_saved_scope(scenario, originals):
    saved = scenario.saved
    full = saved["scope_complete"] is True and not saved["unplanned_operations"]
    if (
        saved["tasks_complete"] is not True
        or (not full and not _material_stage_scope(scenario))
        or type(saved["task_count"]) is not int
        or saved["task_count"] != len(originals)
    ):
        raise TrialAdoptionBlocked("scenario_scope_incomplete", "试调方案没有覆盖原来的全部范围，不能正式采用。")


def _material_stage_scope(scenario):
    """Only the source's pending stage work stays unplanned; the scenario arranges every other member."""
    pending = {ref for ref, member in scenario.origin.unarranged.items() if member["deferred"]}
    unplanned = scenario.saved["unplanned_operations"]
    return bool(pending) and (
        scenario.saved["scope_complete"] is False
        and len(unplanned) == len(pending)
        and {row["operation_ref"] for row in unplanned} == pending
        and len(scenario.origin.unarranged) == len(pending)
    )


def bind_scenario_rows(saved, originals):
    """Every saved task on its own source draft row, as one trial row of the scenario.

    The only binding of a scenario back to its draft, for reading it and for adopting it. The source is the row
    the permanent ``source_row_ref`` column names, and it must be a row of this draft. That row, closed when the
    scenario was saved, holds the task's operation, arrangement and original work once; the bound row keeps them
    and its own ``source_row_ref``/``source_task_ref`` (the base the draft row came from), and names the draft row
    it came from as ``draft_row_ref``/``draft_task_ref``. The columns are unique per scenario, so equal counts make
    the binding one-to-one. Only then are the saved frozen members (shape admitted by ``scenario_snapshot``) checked
    to be operations of the bound rows.
    """
    sources = {row["row_ref"]: row for row in originals}
    rows = []
    for task in saved["tasks"]:
        source = sources.get(task["source_row_ref"])
        if source is None:
            reject("trial_snapshot_invalid", "试调方案与草稿工序不一致，请刷新后重试。")
        rows.append(_saved_row(task, source))
    if len(rows) != len(originals):
        reject("trial_snapshot_invalid", "保存的试调工序与原草稿范围不一致，请核对保存记录。")
    if not set(saved["frozen_operation_refs"]) <= {row["operation_ref"] for row in rows}:
        reject("trial_snapshot_invalid", "试调方案记下的不重排工序不在本方案的工序里。请刷新后重试。")
    return rows


def _saved_row(task, source):
    for key in ("row_ref", "task_ref"):
        if task[key] == source[key]:
            reject("trial_snapshot_invalid", "试调方案里的工序编号不能和草稿里的编号相同。请刷新后重试。")
    # 安排就是来源草稿行的 current，起止和草稿行一样只在试调行的唯一读边界（trial.constraints._admitted_interval）准入。
    return {**source, "row_ref": task["row_ref"], "task_ref": task["task_ref"],
            "draft_row_ref": source["row_ref"], "draft_task_ref": source["task_ref"]}


def scenario_issue_refs(issues, mapping):
    """Issue rows with their draft task refs renamed to the scenario's (``mapping``: draft ``task_ref`` to scenario
    ``task_ref``); a ref outside the mapping stays. Issue rows are shared with the draft admission and per-task
    lists, so renaming builds new rows."""
    return [
        dict(row, **{key: mapping[row[key]] for key in ("task_ref", "related_task_ref") if row.get(key) in mapping})
        for row in issues
    ]


def schedule_rows(rows, intervals_by_row):
    """归档场景的安排，按候选采用同一种排程行交给写库前守卫。"""
    return [
        ValidatedScheduleRow(
            op_id=row["original"]["operation"]["id"],
            source=row["original"]["operation"]["source"],
            machine_id=row["current"]["machine_id"],
            operator_id=row["current"]["operator_id"],
            start_time=intervals_by_row[row["row_ref"]][0],
            end_time=intervals_by_row[row["row_ref"]][1],
        )
        for row in rows
    ]
