"""Official points resolve immutable adoption lineage, not today's operation hours."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.services.scheduler.run.schedule_payload_contract import ValidatedScheduleRow
from core.services.workbench.facts.adoption_baseline_values import AdoptionBaselineUnavailable
from core.services.workbench.facts.zero_duration import PointEventError
from core.services.workbench.facts.zero_duration_evidence import CandidatePointReader, trial_point_evidence
from data.repositories.workbench_plan_baseline_repo import WorkbenchPlanBaselineRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .adoption_baseline import read_adoption_source


def official_point_work(conn, version, *, evidence=None, context=None):
    try:
        if evidence is None:
            refs = context.references if context is not None else WorkbenchPlanIdentityRepository(conn)
            plan_ref = refs.get_plan_ref(WorkbenchPlanLocator(version, "adopted"))
            history = context.history(version) if context is not None else WorkbenchPlanBaselineRepository(conn).get_history_result_summary(version)
            evidence = read_adoption_source(conn, plan_ref=plan_ref, version=version, history=history, context=context)
        if evidence is None or evidence["audit"]["version"] != version:
            raise PointEventError("point_evidence_missing", "这一版正式计划没有可核对的采用记录，证明不了这道零工时工序。")
        basis = evidence["basis"]
        if basis == "candidate_adoption":
            source = evidence["candidate_source"]
            reader = CandidatePointReader(source["candidate"], source["generation_facts"])
            return {row["payload"]["op_id"]: reader.work(row["operation_ref"], row["payload"])
                    for row in source["tasks"] if row["payload"]["start_time"] == row["payload"]["end_time"]}
        _, _, rows = evidence["trial_source"].source
        return {row["original"]["operation"]["id"]: {"witness": trial_point_evidence(row["original"], row["current"]),
                 **{key: row["original"][key] for key in ("operation", "batch", "execution")}}
                for row in rows if row["current"]["start"] == row["current"]["end"]}
    except (AdoptionBaselineUnavailable, PointEventError) as exc:
        raise WorkbenchCommandRejected("point_evidence_unproven", "零工时工序缺少可核对的原始采用记录，这里不当成正常零工时工序读。请刷新后重试。") from exc


def annotate_plan_points(conn, rows, *, source_table, context=None, intervals=None):
    from datetime import datetime

    from data.repositories.schedule_time_sql import parse_dt_for_sql

    result, versions = [], {}
    for index, original in enumerate(rows):
        row = original
        start, end = original["start_time"], original["end_time"]
        low, high = intervals[index] if intervals is not None else (parse_dt_for_sql(start), parse_dt_for_sql(end))
        if low is not None and high is not None and low == high:
            if source_table != "schedule":
                raise WorkbenchCommandRejected("point_evidence_unproven", "旧候选方案或试调行没有零工时工序的采用记录，读不出来。请刷新后重试。")
            version = original["version"]
            if version not in versions:
                versions[version] = context.point_work(version) if context is not None else official_point_work(conn, version)
            work = versions[version].get(original["op_id"])
            check = ValidatedScheduleRow(op_id=original["op_id"], source="internal", machine_id=original["machine_id"],
                operator_id=original["operator_id"], start_time=datetime.fromisoformat(low), end_time=datetime.fromisoformat(high))
            if work is None or not work["witness"].matches(check):
                raise WorkbenchCommandRejected("point_evidence_unproven", "零工时工序和原采用记录对不上。请刷新后重试。")
            # Keep only a plain immutable-work projection in read fingerprints.
            row = dict(
                original,
                _point_work={
                    **{key: value for key, value in work.items() if key != "witness"},
                    "quantity": work["witness"].quantity,
                },
            )
        result.append(row)
    return result
