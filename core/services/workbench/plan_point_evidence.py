"""Official points resolve immutable adoption lineage, not today's operation hours."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository

from .plan_adoption_baseline import _audit
from .plan_adoption_baseline_identity import verify_arranged
from .plan_adoption_baseline_sources import candidate_source, trial_source
from .plan_adoption_baseline_values import AdoptionBaselineUnavailable
from .run_candidate_adoption_storage import load_adoption_candidate
from .run_candidate_facts import GenerationFacts
from .trial_adoption_storage import load_saved_scenario
from .zero_duration import PointEventError
from .zero_duration_evidence import CandidatePointReader, trial_point_evidence


def official_point_work(conn, version):
    try:
        refs = WorkbenchPlanIdentityRepository(conn)
        plan_ref = refs.get_plan_ref(WorkbenchPlanLocator(version, "adopted"))
        history = conn.execute("SELECT result_summary FROM ScheduleHistory WHERE version=?", (version,)).fetchone()
        recorded = _audit(conn, plan_ref, version, dict(history) if history else None)
        if recorded is None:
            raise PointEventError("point_evidence_missing", "No recorded workbench adoption proves this point.")
        basis, audit, _ = recorded
        load = candidate_source if basis == "candidate_adoption" else trial_source
        _, tables, arranged = load(conn, audit)
        verify_arranged(conn, plan_ref, version, tables, arranged)
        if basis == "candidate_adoption":
            candidate, _, tasks, capture = load_adoption_candidate(conn, audit["candidate_ref"])
            facts = GenerationFacts(capture)
            reader = CandidatePointReader(candidate, facts)
            return {row["payload"]["op_id"]: reader.work(row["operation_ref"], row["payload"])
                    for row in tasks if row["payload"]["start_time"] == row["payload"]["end_time"]}
        _, _, rows = load_saved_scenario(conn, audit["scenario_ref"])
        return {row["original"]["operation"]["id"]: {"witness": trial_point_evidence(row["original"], row["current"]),
                 **{key: row["original"][key] for key in ("operation", "batch", "execution")}}
                for row in rows if row["current"]["start"] == row["current"]["end"]}
    except (AdoptionBaselineUnavailable, PointEventError, KeyError, TypeError, ValueError) as exc:
        raise WorkbenchCommandRejected("point_evidence_unproven", "零时长安排缺少可核验的原始采用证据，未按合法点读取。") from exc


def annotate_plan_points(conn, rows, *, source_table="schedule"):
    from datetime import datetime
    from types import SimpleNamespace

    from data.repositories.schedule_time_sql import parse_dt_for_sql

    result, versions = [], {}
    for original in rows:
        row = dict(original)
        start, end = row["start_time"], row["end_time"]
        if parse_dt_for_sql(start) is not None and parse_dt_for_sql(start) == parse_dt_for_sql(end):
            if source_table != "schedule":
                raise WorkbenchCommandRejected("point_evidence_unproven", "旧候选或模拟行没有合法点证据。")
            version = row["version"]
            if version not in versions:
                versions[version] = official_point_work(conn, version)
            work = versions[version].get(row["op_id"])
            check = SimpleNamespace(op_id=row["op_id"], source="internal", machine_id=row["machine_id"],
                operator_id=row["operator_id"], start_time=datetime.fromisoformat(start), end_time=datetime.fromisoformat(end))
            if work is None or not work["witness"].matches(check):
                raise WorkbenchCommandRejected("point_evidence_unproven", "零时长安排与原采用证据不一致。")
            # Keep only a plain immutable-work projection in read fingerprints.
            row["_point_work"] = {key: value for key, value in work.items() if key != "witness"}
        result.append(row)
    return result
