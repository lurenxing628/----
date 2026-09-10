"""Copy the explicit complete base, including private legacy row fields."""

from core.models.workbench_trial import MAX_TRIAL_TASKS, issue, reject
from core.services.workbench.plan_baseline import _complete_rows
from core.services.workbench.plan_projection import project_plan
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from core.services.workbench.preflight_checks import stored_date
from core.services.workbench.run_candidate_facts import GenerationFacts, _table
from core.services.workbench.run_candidate_projection import candidate_summary, dispositions, validate_manifest
from core.services.workbench.run_candidate_storage import CandidateStore
from core.services.workbench.run_candidate_tasks import tasks_projection
from core.services.workbench.run_candidate_values import stored_json
from data.repositories.workbench_trial_raw_repo import WorkbenchTrialRawPlanRepository, read_raw_table
from data.repositories.workbench_trial_repo import new_ref

from .piece_adoption_trial import trial_piece_predecessors
from .plan_point_evidence import official_point_work
from .trial_facts import entity_maps, live_context
from .zero_duration_evidence import CandidatePointReader, point_basis


def _arrangement(payload, refs):
    from datetime import datetime

    result = {}
    for field, source in (("start", "start_time"), ("end", "end_time")):
        raw = payload.get(source)
        try:
            parsed = datetime.fromisoformat(raw)
            if parsed.tzinfo is not None or parsed.microsecond:
                raise ValueError("Not second-precision factory time")
            result[field] = parsed.isoformat(timespec="seconds")
        except (ValueError, TypeError):
            reject("trial_base_time_invalid", "基础安排时间无效或不能无损表示为工厂本地秒精度，未猜测时长。")
    for kind in ("machine", "operator"):
        key = payload.get(kind + "_id")
        result[kind + "_id"] = key
        result[kind + "_ref"] = refs.get((kind, key)) if key is not None else None
        if key is not None and result[kind + "_ref"] is None:
            reject("identity_missing", "原安排资源缺少永久引用，未匹配同号替代对象。")
    return result


def _row(payload, op, batch, refs, *, source_task_ref, source_row_ref, operation_ref, detail=None):
    current = _arrangement(payload, refs)
    return {"row_ref": new_ref(), "task_ref": new_ref(), "operation_ref": operation_ref,
            "source_task_ref": source_task_ref, "source_row_ref": source_row_ref,
            "current": current,
            "original": {"arrangement": current, "source_row": payload, "operation": op, "batch": batch,
                         "detail": detail, "locked": payload.get("locked", payload.get("lock_status") == "locked"),
                         "lock_known": "locked" in payload or payload.get("lock_status") in ("locked", "unlocked"),
                         "batch_ref": refs.get(("batch", op["batch_id"])), "predecessor_operation_refs": []}}


def _plan(conn, ref):
    service = WorkbenchPlanQueryService(conn)
    with service.read_snapshot():
        _, entry, _ = service._selected(ref)
        repo = WorkbenchTrialRawPlanRepository(conn)
        identity = entry.plan_identity
        if identity is None:
            reject("plan_unavailable", "所选计划缺少可用的永久身份，未切换到其他计划。")
        tables = {name: {row[key]: row for row in read_raw_table(conn, name)[1]}
                  for name, key in (("BatchOperations", "id"), ("Batches", "batch_id"))}
        detail = _complete_rows(repo, version=entry.locator.version, source=identity.source_table,
                                candidate_id=identity.candidate_id, scenario_id=entry.locator.scenario_id)
        tasks = service.references.get_task_refs(ref, detail)
        operations = service.references.get_operation_refs(row["op_id"] for row in detail)
        refs = entity_maps({"WorkbenchEntityRefs": read_raw_table(conn, "WorkbenchEntityRefs")[1]})
        raw, source_refs, table = _source_rows(conn, identity.source_table, detail)
        result, point_work = [], None
        for item in detail:
            op = tables["BatchOperations"].get(item["op_id"])
            batch = tables["Batches"].get(item["batch_id"])
            if op is None or batch is None or item["schedule_id"] not in source_refs:
                reject("trial_base_incomplete", "原计划工序、批次或来源行缺失。")
            item["due_date"] = batch["due_date"]
            result.append(_row(raw[item["schedule_id"]], op, batch, refs, source_task_ref=tasks[item["schedule_id"]],
                               source_row_ref=source_refs[item["schedule_id"]], operation_ref=operations[item["op_id"]], detail=item))
            if result[-1]["current"]["start"] == result[-1]["current"]["end"]:
                if identity.source_table != "schedule":
                    reject("point_evidence_unproven", "旧候选或模拟的零时长行没有已核验点证据。")
                if point_work is None:
                    point_work = official_point_work(conn, entry.locator.version)
                _attach_point_work(result[-1], point_work[item["op_id"]])
        _attach_parts(conn, result)
        operations = {int(row["source_key"]): row["ref"] for row in conn.execute(
            "SELECT source_key,ref FROM WorkbenchPlanSourceRefs WHERE kind='operation' AND active=1")}
        issues = [] if entry.completeness == "complete" else [issue("trial_base_incomplete", "基础方案完整性尚未证明，不能把未排完算作按期。")]
        return result, {"identity": project_plan(entry, ref), "source_table": table}, tables["BatchOperations"], operations, issues


def _date_issues(rows):
    issues = []
    for row in rows:
        for field in ("due_date", "ready_date"):
            value = row["original"]["batch"][field]
            if value is not None and (type(value) is not str or stored_date(value) is None):
                issues.append(issue("trial_base_date_invalid", "原批次交期或可开工日期无效；保留原值，不能正式采用。", row["task_ref"]))
    return issues


def _attach_parts(conn, rows):
    parts = {row["part_no"]: row for row in read_raw_table(conn, "Parts")[1]}
    for row in rows:
        row["original"]["part"] = parts.get(row["original"]["batch"]["part_no"])


def _source_rows(conn, source, detail):
    sources = {"schedule": ("Schedule", "schedule_row"), "candidate_rows": ("ScheduleCandidateRows", "candidate_row"),
               "adjustment_scenario_rows": ("ScheduleAdjustmentScenarioRow", "scenario_row")}
    table, kind = sources[source]
    wanted = {row["schedule_id"] for row in detail}
    raw = {row["id"]: row for row in read_raw_table(conn, table)[1] if row["id"] in wanted}
    source_refs = {int(row["source_key"]): row["ref"] for row in conn.execute(
        "SELECT source_key,ref FROM WorkbenchPlanSourceRefs WHERE kind=? AND active=1", (kind,))}
    return raw, source_refs, table


def _candidate(conn, ref):
    store = CandidateStore(conn)
    with store.snapshot():
        run_ref = store.candidate_run(ref)
        run, candidates = store.run(run_ref), store.candidates(run_ref)
        receipt = store.receipt(run)
        validate_manifest(run, candidates, receipt)
        candidate = next(row for row in candidates if row["candidate_ref"] == ref)
        capture = store.capture(run_ref)
        facts = GenerationFacts(capture)
        rows = store.tasks(ref)
        tasks_projection(rows, candidate, facts)
        point_reader = CandidatePointReader(candidate, facts)
        result = []
        for item in rows:
            gaps = []
            op = facts.operation(item["operation_ref"], item["payload"], gaps)
            batch = facts.tables["Batches"].get(op.get("batch_id"))
            if gaps or not op or batch is None:
                reject("trial_base_incomplete", "候选生成时原工序或批次快照缺失，未改用当前同号记录。")
            result.append(_row(item["payload"], op, batch, facts.entity_refs, source_task_ref=None,
                               source_row_ref=item["row_ref"], operation_ref=item["operation_ref"]))
            if result[-1]["current"]["start"] == result[-1]["current"]["end"]:
                _attach_point_work(result[-1], point_reader.work(item["operation_ref"], item["payload"]))
            result[-1]["original"]["part"] = facts.tables["Parts"].get(batch["part_no"])
        scope = dispositions(receipt)
        summary = candidate_summary(candidate, scope)
        issues = []
        if scope is None or {row["operation_ref"] for row in result} != set(scope) or summary["completeness"] != "complete":
            issues.append(issue("trial_base_incomplete", "候选未完整覆盖原受理工序，未隐藏未排入工序。"))
        extra = {"identity": {"candidate_ref": ref, "run_ref": run_ref, "kind": "candidate",
                               "display_name": summary["label"], "completeness": summary["completeness"]},
                 "capture": capture, "dispositions": scope, "artifact": candidate["artifact"]}
        return result, extra, facts.tables["BatchOperations"], {key: ref for ref, key in facts.operations.items()}, issues


def prepare_base(conn, intent):
    key, ref = next(iter(intent["base"].items()))
    rows, source, all_ops, operation_refs, issues = _plan(conn, ref) if key == "plan_ref" else _candidate(conn, ref)
    if not rows:
        reject("trial_base_empty", "基础方案没有真实任务行，未从摘要重造任务。")
    if len(rows) > MAX_TRIAL_TASKS:
        reject("query_too_large", "完整基础范围超过10000条，未按可见范围截断。", 413)
    issues.extend(_date_issues(rows))
    _predecessors(rows, all_ops, operation_refs, issues)
    live = live_context(conn, [row["operation_ref"] for row in rows])
    admission = {"input": intent, "source": source, "facts": live["facts"], "facts_hash": live["facts_hash"],
                 "baseline": live["baseline"], "execution": live["execution"], "base_issues": issues}
    _attach_original_context(rows, source, key, live)
    return admission, rows, live


def _attach_original_context(rows, source, key, live):
    original_execution = ({row["operation_ref"]: row for row in source["capture"]["execution"]}
                          if key == "candidate_ref" else live["execution"])
    original_tables = (stored_json(source["capture"]["facts_text"])
                       if key == "candidate_ref" else None)
    templates = _table(original_tables, "PartOperations") if original_tables is not None else live["facts"]["tables"]["PartOperations"]
    groups = _table(original_tables, "ExternalGroups") if original_tables is not None else live["facts"]["tables"]["ExternalGroups"]
    if templates is None or groups is None:
        reject("trial_base_incomplete", "候选生成时的工艺或外协组快照表缺失，未改用当前数据。")
    template_by_key = {(item["part_no"], item["seq"]): item for item in templates if item["status"] == "active"}
    group_by_key = {item["group_id"]: item for item in groups}
    for row in rows:
        original = row["original"]
        original.setdefault("execution", original_execution.get(row["operation_ref"]))
        template = template_by_key.get((original["batch"]["part_no"], original["operation"]["seq"]))
        original["template"] = template
        original["external_group"] = group_by_key.get(template["ext_group_id"]) if template else None


def _attach_point_work(row, work):
    original = row["original"]
    original.update({key: work[key] for key in ("operation", "batch", "execution")})
    original["point_basis"] = point_basis(work)


def _predecessors(rows, all_ops, operation_refs, issues):
    from core.models.workbench_piece_adoption import PieceAdoptionBlocked

    if any(row["original"]["operation"]["piece_id"] is not None for row in rows):
        try:
            predecessors = trial_piece_predecessors(rows, all_ops, operation_refs)
        except PieceAdoptionBlocked as exc:
            issues.append(issue(exc.code, str(exc)))
            return
        for row in rows:
            row["original"]["predecessor_operation_refs"] = predecessors[row["original"]["operation"]["id"]]
        return

    previous = _batch_predecessors(rows, all_ops, operation_refs, issues)
    for row in rows:
        key = row["original"]["operation"]["id"]
        if key in previous:
            if previous[key] is None:
                issues.append(issue("dependency_identity_missing", "前序永久身份缺失，不能按序号猜替代任务。", row["task_ref"]))
            else:
                row["original"]["predecessor_operation_refs"] = [previous[key]]


def _batch_predecessors(rows, all_ops, operation_refs, issues):
    from collections import defaultdict

    batches = {row["original"]["operation"]["batch_id"] for row in rows}
    chains = defaultdict(list)
    for op in all_ops.values():
        if op["batch_id"] in batches:
            chains[op["batch_id"], op["piece_id"]].append(op)
    previous = {}
    for chain in chains.values():
        if any(type(op["seq"]) is not int for op in chain) or len({op["seq"] for op in chain}) != len(chain):
            issues.append(issue("dependency_ambiguous", "同一批次分件的工序顺序不明确，不能确认前后序。"))
            continue
        ordered = sorted(chain, key=lambda op: op["seq"])
        for left, right in zip(ordered, ordered[1:]):
            previous[right["id"]] = operation_refs.get(left["id"])
    return previous
