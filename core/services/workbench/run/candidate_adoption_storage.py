"""Prove at adoption time that the archived admission still matches the live facts."""


from core.models.content import same
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_adoption import CandidateAdoptionBlocked
from core.services.workbench.facts.candidate_values import corrupt
from core.services.workbench.facts.run_input_codec import execution_snapshots_match

from .jobs_facts import run_baseline, run_execution_projections


def check_admission_current(capture, *, current_capture, ledger):
    baseline = run_baseline(capture=current_capture)
    if not same(baseline, capture["baseline"]):
        raise WorkbenchCommandRejected("snapshot_stale", "排产时的正式计划已经变了，这次没有采用，正式计划没有改动。请重新做排产检查。")
    try:
        matched = current_capture.matches_recorded(capture["revisions"])
    except ValueError:
        corrupt()
    if not matched:
        raise WorkbenchCommandRejected("snapshot_stale", "排产之后，排产范围、报工记录、设备人员或班表有变化，这次没有采用，正式计划没有改动。请重新排产后再试。")
    projections = run_execution_projections(capture["input"], capture=current_capture, ledger=ledger)
    require_official_baseline(baseline, projections)
    if not execution_snapshots_match([row.to_dict() for row in projections], capture["execution"]):
        raise WorkbenchCommandRejected("snapshot_stale", "排产时记下的报工记录已经变了，这次没有采用，正式计划没有改动。请重新排产后再试。")
    return baseline, projections


def require_official_baseline(baseline, projections):
    if not projections:
        return
    identity = projections[0].plan_identity
    if baseline["version"] is None:
        if identity is not None:
            raise CandidateAdoptionBlocked("empty_baseline_inconsistent", "系统里还没有正式计划，但报工记录上挂着计划编号，对不上，不能采用。请联系维护人员核对。")
        return
    if (not isinstance(identity, dict) or identity.get("plan_ref") != baseline["plan_ref"]
            or identity.get("version") != baseline["version"] or identity.get("kind") != "official"
            or identity.get("is_current_official") is not True or identity.get("completeness") != "complete"):
        raise CandidateAdoptionBlocked("baseline_not_current_official", "排产时对照的那份计划已经不是当前正式计划，不能采用。请重新做排产检查。")
