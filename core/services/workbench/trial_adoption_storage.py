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
            _invalid("场景没有逐一覆盖原草稿任务，未重建缺失任务。")
        seen.add(source["row_ref"])
        rows.append(_saved_row(task, source))
    if seen != set(sources):
        _invalid("场景完整范围与原草稿不一致。")
    _require_links(saved["tasks"], rows)
    return saved, head, rows


def _require_head(saved, header, head, originals):
    admission = head["admission"]
    if (saved["scenario_ref"] != header["scenario_ref"] or saved["draft_ref"] != head["draft_ref"]
            or saved["status"] != "saved" or head["status"] != "saved"
            or saved["name"] != header["name"] or saved["saved_at"] != header["saved_at"]
            or head["revision"] != header["revision"] + 1):
        _invalid("保存场景与已关闭草稿的永久身份或版本不一致。")
    _require_saved_scope(saved, originals)
    for key, expected in (("base", admission["input"]["base"]), ("scope", admission["input"]["scope"]),
                          ("base_identity", admission["source"]["identity"]),
                          ("baseline", {name: admission["baseline"][name] for name in ("plan_ref", "version")})):
        if fingerprint(saved[key]) != fingerprint(expected):
            _invalid("场景的原基础、范围或正式基线不一致。")


def _require_saved_scope(saved, originals):
    if (saved["tasks_complete"] is not True or saved["scope_complete"] is not True
            or saved["unplanned_operations"] or not 0 < len(originals) <= MAX_TRIAL_TASKS
            or type(saved["task_count"]) is not int or saved["task_count"] != len(originals)
            or len(saved["tasks"]) != len(originals)):
        raise TrialAdoptionBlocked("scenario_scope_incomplete", "保存场景尚未完整覆盖原范围，不能正式采用。")


def _require_receipts(conn, saved, header, head):
    repo = WorkbenchCommandRepository(conn)
    created, persisted = repo.get(head["request_key"]), repo.get(header["request_key"])
    if (created is None or (created["action"], created["context_ref"]) != ("trial.create", head["base_ref"])
            or persisted is None or (persisted["action"], persisted["context_ref"]) != ("trial.save", head["draft_ref"])):
        _invalid("原草稿创建或场景保存回执缺失，不能证明完整持久来源。")
    result = repo.public_result(persisted, replayed=True)
    if result["result"] != "committed" or fingerprint(result["data"]) != fingerprint(saved):
        _invalid("场景快照与原保存回执不一致，未覆盖或重新生成快照。")


def _saved_row(task, source):
    original = source["original"]
    op, batch = original["operation"], original["batch"]
    expected = {"operation_ref": source["operation_ref"], "source_task_ref": source["task_ref"],
                "draft_ref": source["draft_ref"], "batch_ref": original["batch_ref"],
                "batch_id": batch["batch_id"], "part_no": batch["part_no"],
                "sequence": op["seq"], "piece_id": op["piece_id"], "source": op["source"],
                "predecessor_operation_refs": original["predecessor_operation_refs"]}
    if fingerprint({key: task[key] for key in expected}) != fingerprint(expected):
        _invalid("场景任务的原工序、批次、前序或草稿来源不一致。")
    for key in ("row_ref", "task_ref"):
        reference(task[key])
        if task[key] == source[key]:
            _invalid("场景任务身份不能冒充原草稿任务身份。")
    current = {key: task[key] for key in ("machine_ref", "operator_ref", "start", "end")}
    for kind in ("machine", "operator"):
        current[kind + "_id"] = source["current"][kind + "_id"]
    if fingerprint(current) != fingerprint(source["current"]):
        _invalid("场景保存的安排与已关闭草稿不一致，未使用当前安排替换。")
    for name in ("start", "end"):
        raw = current[name]
        parsed = datetime.fromisoformat(raw)
        if parsed.tzinfo is not None or parsed.microsecond or parsed.isoformat(timespec="seconds") != raw:
            _invalid("场景时间必须是可无损保存的工厂本地秒精度时间。")
    return {**source, "row_ref": task["row_ref"], "task_ref": task["task_ref"],
            "current": current, "original": deepcopy(original)}


def _require_links(tasks, rows):
    for key in ("row_ref", "task_ref", "operation_ref"):
        if len({row[key] for row in rows}) != len(rows):
            _invalid("场景永久行、任务或工序身份重复。")
    by_operation = {row["operation_ref"]: row["task_ref"] for row in rows}
    for task, row in zip(tasks, rows):
        expected = [by_operation[ref] for ref in row["original"]["predecessor_operation_refs"] if ref in by_operation]
        if task["predecessor_refs"] != expected:
            _invalid("场景前后序引用与保存的完整任务不一致。")


def schedule_rows(rows):
    return [SimpleNamespace(op_id=row["original"]["operation"]["id"],
                source=row["original"]["operation"]["source"],
                machine_id=row["current"]["machine_id"], operator_id=row["current"]["operator_id"],
                start_time=datetime.fromisoformat(row["current"]["start"]),
                end_time=datetime.fromisoformat(row["current"]["end"])) for row in rows]
