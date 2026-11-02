"""Complete production evidence, with no trial/command bookkeeping feedback loop."""

from typing import Any, Dict, NamedTuple, Tuple

from core.models.content import same
from core.models.workbench_execution import ExecutionProjection
from core.models.workbench_trial import MAX_TRIAL_TASKS, reject
from core.services.scheduler.resource_pool_builder import CapturedResourceFacts
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.facts.schema_compat import project_facts
from core.services.workbench.facts.source_revisions import TRIAL_SOURCE_KEYS, read_source_revisions
from core.services.workbench.run.jobs_facts import run_baseline
from core.services.workbench.run.preflight_facts import PreflightFacts

from .occupancy import ReportedExecution, reported_projection

LIVE_TRIAL_SOURCE_KEYS = tuple(key for key in TRIAL_SOURCE_KEYS if key != "trial_records")


class TrialExecutionFacts(NamedTuple):
    projections: Tuple[ExecutionProjection, ...]
    snapshots: Dict[str, Dict[str, Any]]
    reported: Dict[str, ReportedExecution]
    operations: Dict[str, Dict[str, Any]]


class LiveTables:
    """Read and cache only the live tables required by trial validation and projection."""

    def __init__(self, capture):
        self._capture = capture

    def __contains__(self, name):
        return name in self._capture.table_names

    def __getitem__(self, name):
        if name not in self._capture.table_names:
            raise KeyError(name)
        return self._capture.table(name)

    def get(self, name, default=None):
        return self._capture.table(name) if name in self._capture.table_names else default


def facts_unchanged(admission, live):
    """Compare saved production content; preserve original historical metadata."""
    matched = live["capture"].matches_archive(admission["facts"])
    if matched is not None:
        return matched
    return same(project_facts(admission["facts"]), project_facts(live["capture"].archive(named=True)))


def execution_facts(tables, selected_refs, *, operation_refs, service) -> TrialExecutionFacts:
    refs = set(selected_refs)
    refs.update(operation_refs[row["op_id"]] for row in tables["Schedule"])
    for row in tables["WorkbenchProductionReports"]:
        refs.add(row["operation_ref"])
    if len(refs) > MAX_TRIAL_TASKS:
        reject("query_too_large", "试调及真实执行保护范围超过10000道工序，未遗漏范围外占用。", 413)
    with service.read_snapshot():
        loaded = service.load(sorted(refs))
        values = service.project_loaded(loaded, include_history=False)
    snapshots: Dict[str, Dict[str, Any]] = {}
    reported: Dict[str, ReportedExecution] = {}
    for row in values:
        snap = row.to_dict()
        snapshots[row.operation_ref] = snap
        reported[row.operation_ref] = reported_projection(row, snap)
    return TrialExecutionFacts(tuple(values), snapshots, reported, loaded["operations"])


def live_context(conn, origin, capture=None, *, execution_service, data_context):
    """Live production plus the execution of the trial's whole operation scope.

    origin is the trial source's members, prepared once: the whole scope is origin.operation_refs and
    origin.admission supplies the saved facts that scope was taken from. A capture is made when not given.
    """
    capture = capture if capture is not None else ProductionFactsCapture(conn)
    capture.seed_from_named_archive(origin.admission["facts"])
    facts = {"tables": LiveTables(capture)}
    capture.execution_service = execution_service
    preflight = PreflightFacts(conn, capture=capture)
    preflight.bind_capture(capture)
    exec_facts = execution_facts(
        facts["tables"], origin.operation_refs,
        operation_refs=preflight.operation_refs, service=execution_service)
    preflight.execution_projections.update((row.operation_ref, row) for row in exec_facts.projections)
    return {"facts": facts, "capture": capture, "execution": exec_facts.snapshots,
            "execution_reported": exec_facts.reported,
            "execution_operations": exec_facts.operations,
            "revisions": read_source_revisions(conn, LIVE_TRIAL_SOURCE_KEYS),
            "data_context_ref": data_context.ref(),
            "resource_facts": CapturedResourceFacts(preflight.tables, {}),
            "baseline": run_baseline(capture=capture), "preflight_facts": preflight, "origin": origin}


def entity_maps(tables):
    return {(row["kind"], row["entity_key"]): row["ref"] for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}
