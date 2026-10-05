"""Prove at adoption time that the archived admission still matches the live facts."""

import hashlib

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.models.workbench_run_job import durable_value
from data.repositories.workbench_run_facts_repo import WorkbenchRunFactsRepository

from .jobs_facts import production_facts_match, run_baseline, run_execution_projections


def check_admission_current(conn, capture):
    text = capture["facts_text"]
    if type(text) is not str or hashlib.sha256(text.encode("utf-8")).hexdigest() != capture["facts_hash"]:
        raise CandidateAdoptionBlocked("candidate_artifact_invalid", "排产时记下的数据校验不通过，不能采用，正式计划没有改动。请重新排产后再试。")
    baseline = run_baseline(conn)
    if baseline != capture["baseline"]:
        raise WorkbenchCommandRejected("snapshot_stale", "排产时的正式计划已经变了，这次没有采用，正式计划没有改动。请重新做排产检查。")
    facts = WorkbenchRunFactsRepository(conn)
    if baseline["version"] is None and facts.schedule_has_rows():
        raise CandidateAdoptionBlocked("empty_baseline_inconsistent", "系统里还有找不到所属版本的正式安排，不能采用。请联系维护人员核对。")
    if facts.schedule_has_rows_without_history():
        raise CandidateAdoptionBlocked("official_history_inconsistent", "有正式安排找不到所属的版本记录，不能采用。请联系维护人员核对。")
    if not production_facts_match(conn, text, capture["facts_hash"]):
        raise WorkbenchCommandRejected("snapshot_stale", "排产之后，排产范围、报工记录、设备人员或班表有变化，这次没有采用，正式计划没有改动。请重新排产后再试。")
    projections = run_execution_projections(conn, capture["input"])
    _require_official_baseline(baseline, projections)
    if durable_value(projections) != capture["execution"]:
        raise WorkbenchCommandRejected("snapshot_stale", "排产时记下的报工记录已经变了，这次没有采用，正式计划没有改动。请重新排产后再试。")
    return baseline, projections


def _require_official_baseline(baseline, projections):
    if baseline["version"] is None:
        if any(row.plan_identity is not None for row in projections):
            raise CandidateAdoptionBlocked("empty_baseline_inconsistent", "系统里还没有正式计划，但报工记录上挂着计划编号，对不上，不能采用。请联系维护人员核对。")
        return
    for row in projections:
        identity = row.plan_identity
        if (not isinstance(identity, dict) or identity.get("plan_ref") != baseline["plan_ref"]
                or identity.get("version") != baseline["version"] or identity.get("kind") != "official"
                or identity.get("is_current_official") is not True or identity.get("completeness") != "complete"):
            raise CandidateAdoptionBlocked("baseline_not_current_official", "排产时对照的那份计划已经不是当前正式计划，不能采用。请重新做排产检查。")
