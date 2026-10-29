"""Verify saved scenario lineage; source draft supplies only immutable raw work."""

from datetime import datetime
from typing import NoReturn

from core.infrastructure.read_evidence import verified_read
from core.models.workbench_trial import MAX_TRIAL_TASKS, reference
from core.models.workbench_trial_adoption import TrialAdoptionBlocked
from core.services.scheduler.run.schedule_payload_contract import ValidatedScheduleRow
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository

from .trial_origin import operation_contexts
from .trial_policy import (
    copy_draft_rows,
    load_draft_with_key,
    load_scenario_record_with_key,
    max_trial_tasks,
    trial_cache_get,
    trial_cache_memo,
)

_SAVED_SCENARIO_CACHE = {}


def _invalid(message) -> NoReturn:
    raise TrialAdoptionBlocked("trial_snapshot_invalid", message)


def load_saved_scenario(conn, scenario_ref):
    reference(scenario_ref)
    return verified_read(conn, ("saved_trial_scenario", scenario_ref), lambda: _load_saved_scenario(conn, scenario_ref))


def _load_saved_scenario(conn, scenario_ref):
    repo = WorkbenchTrialRepository(conn)
    header, saved, scenario_key = load_scenario_record_with_key(repo, scenario_ref)
    head, originals, draft_key = load_draft_with_key(repo, header["draft_ref"])
    cache_key = (
        (
            scenario_key,
            draft_key,
            header.get("scenario_ref"),
            header.get("draft_ref"),
            header.get("name"),
            header.get("revision"),
            header.get("saved_at"),
            head.get("draft_ref"),
            head.get("status"),
            head.get("revision"),
            head.get("base_ref"),
        )
        if scenario_key is not None and draft_key is not None
        else None
    )
    max_tasks = min(MAX_TRIAL_TASKS, max_trial_tasks())
    if cache_key is not None and 0 < len(originals) <= max_tasks:
        cached_rows = trial_cache_get(_SAVED_SCENARIO_CACHE, cache_key)
        if cached_rows is not None:
            return saved, dict(head, scenario_revision=header["revision"]), copy_draft_rows(cached_rows)
    _require_head(saved, header, head, originals)
    sources = {row["row_ref"]: row for row in originals}
    rows, seen = [], set()
    for task in saved["tasks"]:
        source = sources.get(task["source_row_ref"])
        if source is None or source["row_ref"] in seen:
            _invalid("试调方案与草稿工序不一致，请刷新后重试。")
        seen.add(source["row_ref"])
        rows.append(_saved_row(task, source))
    _require_links(saved["tasks"], rows)
    if cache_key is not None:
        trial_cache_memo(_SAVED_SCENARIO_CACHE, cache_key, copy_draft_rows(rows))
    return saved, dict(head, scenario_revision=header["revision"]), rows


def _require_head(saved, header, head, originals):
    admission = head["admission"]
    if (saved["scenario_ref"] != header["scenario_ref"] or saved["draft_ref"] != head["draft_ref"]
            or saved["status"] != "saved" or head["status"] != "saved"
            or saved["name"] != header["name"] or saved["saved_at"] != header["saved_at"]
            or type(head["revision"]) is not int or type(header["revision"]) is not int
            or head["revision"] != header["revision"] + 1):
        _invalid("试调方案和它的草稿编号或版本对不上。请刷新后重试。")
    _require_saved_scope(saved, originals, admission)


def _require_saved_scope(saved, originals, admission):
    full = saved["scope_complete"] is True and not saved["unplanned_operations"]
    if (saved["tasks_complete"] is not True or (not full and not _material_stage_scope(saved, originals, admission))
            or not 0 < len(originals) <= min(MAX_TRIAL_TASKS, max_trial_tasks())
            or type(saved["task_count"]) is not int or saved["task_count"] != len(originals)
            or len(saved["tasks"]) != len(originals)):
        raise TrialAdoptionBlocked("scenario_scope_incomplete", "试调方案没有覆盖原来的全部范围，不能正式采用。")


def _material_stage_scope(saved, originals, admission):
    contexts = operation_contexts(originals, admission)
    pending = {ref for ref, row in contexts.items() if not row["arranged"] and row["deferred"]}
    unplanned = saved["unplanned_operations"]
    return bool(pending) and (saved["scope_complete"] is False
        and len(unplanned) == len(pending) and {row["operation_ref"] for row in unplanned} == pending
        and {row["operation_ref"] for row in originals} == set(contexts) - pending)


def _saved_row(task, source):
    for key in ("row_ref", "task_ref"):
        reference(task[key])
        if task[key] == source[key]:
            _invalid("试调方案里的工序编号不能和草稿里的编号相同。请刷新后重试。")
    current = dict(source["current"])
    for key in ("machine_ref", "operator_ref", "start", "end"):
        current[key] = task[key]
    for name in ("start", "end"):
        raw = current[name]
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is not None or parsed.isoformat() != raw:
            _invalid("试调方案里的时间格式无效，不能正式采用。请刷新后重试。")
    return {**source, "row_ref": task["row_ref"], "task_ref": task["task_ref"],
            "current": current, "original": source["original"]}


def _require_links(tasks, rows):
    for key in ("row_ref", "task_ref", "operation_ref"):
        if len({row[key] for row in rows}) != len(rows):
            _invalid("试调方案里有重复的工序。请刷新后重试。")
    by_operation = {row["operation_ref"]: row["task_ref"] for row in rows}
    for task, row in zip(tasks, rows):
        expected = [by_operation[ref] for ref in row["original"]["predecessor_operation_refs"] if ref in by_operation]
        if task["predecessor_refs"] != expected:
            _invalid("试调方案里的前后序和保存的工序对不上。请刷新后重试。")


def schedule_rows(rows):
    """归档场景的安排，按候选采用同一种排程行交给写库前守卫。"""
    return [ValidatedScheduleRow(op_id=row["original"]["operation"]["id"],
                source=row["original"]["operation"]["source"],
                machine_id=row["current"]["machine_id"], operator_id=row["current"]["operator_id"],
                start_time=datetime.fromisoformat(row["current"]["start"]),
                end_time=datetime.fromisoformat(row["current"]["end"])) for row in rows]
