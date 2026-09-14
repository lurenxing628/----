"""Verify saved scenario lineage; source draft supplies only immutable raw work."""

from copy import deepcopy
from datetime import datetime
from types import SimpleNamespace
from typing import NoReturn

from core.models.workbench_trial import MAX_TRIAL_TASKS, reference
from core.models.workbench_trial_adoption import TrialAdoptionBlocked
from core.models.workbench_trial_codec import fingerprint
from data.repositories.workbench_command_repo import WorkbenchCommandRepository
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository


def _invalid(message) -> NoReturn:
    raise TrialAdoptionBlocked("trial_snapshot_invalid", message)


def load_saved_scenario(conn, scenario_ref):
    reference(scenario_ref)
    repo = WorkbenchTrialRepository(conn)
    saved = repo.scenario(scenario_ref)
    header = dict(conn.execute("SELECT * FROM WorkbenchTrialScenarios WHERE scenario_ref=?", (scenario_ref,)).fetchone())
    head, originals = repo.get(header["draft_ref"])
    _require_head(saved, header, head, originals)
    _require_receipts(conn, saved, header, head)
    sources = {row["row_ref"]: row for row in originals}
    rows, seen = [], set()
    for task in saved["tasks"]:
        source = sources.get(task["source_row_ref"])
        if source is None or source["row_ref"] in seen:
            _invalid("试调方案没有逐条对上草稿里的工序，缺的工序不会自动补。请刷新后重试。")
        seen.add(source["row_ref"])
        rows.append(_saved_row(task, source))
    if seen != set(sources):
        _invalid("试调方案的范围和草稿不一致。请刷新后重试。")
    _require_links(saved["tasks"], rows)
    return saved, head, rows


def _require_head(saved, header, head, originals):
    admission = head["admission"]
    if (saved["scenario_ref"] != header["scenario_ref"] or saved["draft_ref"] != head["draft_ref"]
            or saved["status"] != "saved" or head["status"] != "saved"
            or saved["name"] != header["name"] or saved["saved_at"] != header["saved_at"]
            or head["revision"] != header["revision"] + 1):
        _invalid("试调方案和它的草稿编号或版本对不上。请刷新后重试。")
    _require_saved_scope(saved, originals)
    for key, expected in (("base", admission["input"]["base"]), ("scope", admission["input"]["scope"]),
                          ("base_identity", admission["source"]["identity"]),
                          ("baseline", {name: admission["baseline"][name] for name in ("plan_ref", "version")})):
        if fingerprint(saved[key]) != fingerprint(expected):
            _invalid("试调方案的来源、范围或建草稿时的正式计划对不上。请刷新后重试。")


def _require_saved_scope(saved, originals):
    if (saved["tasks_complete"] is not True or saved["scope_complete"] is not True
            or saved["unplanned_operations"] or not 0 < len(originals) <= MAX_TRIAL_TASKS
            or type(saved["task_count"]) is not int or saved["task_count"] != len(originals)
            or len(saved["tasks"]) != len(originals)):
        raise TrialAdoptionBlocked("scenario_scope_incomplete", "试调方案没有覆盖原来的全部范围，不能正式采用。")


def _require_receipts(conn, saved, header, head):
    repo = WorkbenchCommandRepository(conn)
    created, persisted = repo.get(head["request_key"]), repo.get(header["request_key"])
    if (created is None or (created["action"], created["context_ref"]) != ("trial.create", head["base_ref"])
            or persisted is None or (persisted["action"], persisted["context_ref"]) != ("trial.save", head["draft_ref"])):
        _invalid("找不到建草稿或保存试调方案的结果记录，来源无法确认。请刷新后重试。")
    result = repo.public_result(persisted, replayed=True)
    if result["result"] != "committed" or fingerprint(result["data"]) != fingerprint(saved):
        _invalid("试调方案的内容和保存结果对不上，这里不会重新生成。请刷新后重试。")


def _saved_row(task, source):
    original = source["original"]
    op, batch = original["operation"], original["batch"]
    expected = {"operation_ref": source["operation_ref"], "source_task_ref": source["task_ref"],
                "draft_ref": source["draft_ref"], "batch_ref": original["batch_ref"],
                "batch_id": batch["batch_id"], "part_no": batch["part_no"],
                "sequence": op["seq"], "piece_id": op["piece_id"], "source": op["source"],
                "predecessor_operation_refs": original["predecessor_operation_refs"]}
    if fingerprint({key: task[key] for key in expected}) != fingerprint(expected):
        _invalid("试调方案里的工序、批次、前序或草稿来源对不上。请刷新后重试。")
    for key in ("row_ref", "task_ref"):
        reference(task[key])
        if task[key] == source[key]:
            _invalid("试调方案里的工序编号不能和草稿里的编号相同。请刷新后重试。")
    current = {key: task[key] for key in ("machine_ref", "operator_ref", "start", "end")}
    for kind in ("machine", "operator"):
        current[kind + "_id"] = source["current"][kind + "_id"]
    if fingerprint(current) != fingerprint(source["current"]):
        _invalid("试调方案保存的安排和草稿不一致，这里不会用当前安排顶替。请刷新后重试。")
    for name in ("start", "end"):
        raw = current[name]
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is not None or parsed.microsecond or parsed.isoformat(timespec="seconds") != raw:
            _invalid("试调方案里的时间只能精确到秒，请按 2026-09-13 08:30:00 这样填写。")
    return {**source, "row_ref": task["row_ref"], "task_ref": task["task_ref"],
            "current": current, "original": deepcopy(original)}


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
    return [SimpleNamespace(op_id=row["original"]["operation"]["id"],
                source=row["original"]["operation"]["source"],
                machine_id=row["current"]["machine_id"], operator_id=row["current"]["operator_id"],
                start_time=datetime.fromisoformat(row["current"]["start"]),
                end_time=datetime.fromisoformat(row["current"]["end"])) for row in rows]
