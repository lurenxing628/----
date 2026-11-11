"""Complete production evidence, with no trial/command bookkeeping feedback loop."""

from typing import Any, Dict, NamedTuple, Tuple

from core.models.workbench_execution import ExecutionProjection
from core.models.workbench_trial import MAX_TRIAL_TASKS, reject
from core.services.execution.ledger_reader import ExecutionLedgerReadScope
from core.services.workbench.facts.production_capture import ProductionFactsCapture
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

    def __getitem__(self, name):
        if name not in self._capture.table_names:
            raise KeyError(name)
        return self._capture.table(name)

    def get(self, name, default=None):
        return self._capture.table(name) if name in self._capture.table_names else default


def facts_unchanged(admission, live):
    """Whether production still has the draft admission's source revisions under the same schema.

    ``live["capture"]`` is ``saved_capture`` of this admission, which already admitted its archive.
    """
    return live["capture"].matches_admitted(admission["facts"])


def execution_facts(tables, selected_refs, *, operation_refs, ledger: ExecutionLedgerReadScope) -> TrialExecutionFacts:
    refs = set(selected_refs)
    refs.update(operation_refs[row["op_id"]] for row in tables["Schedule"])
    for row in tables["WorkbenchProductionReports"]:
        refs.add(row["operation_ref"])
    if len(refs) > MAX_TRIAL_TASKS:
        reject("query_too_large", "试调及真实执行保护范围超过10000道工序，未遗漏范围外占用。", 413)
    loaded = ledger.reader.load(ledger, sorted(refs))
    values = ledger.reader.project_loaded(loaded, include_history=False)
    snapshots: Dict[str, Dict[str, Any]] = {}
    reported: Dict[str, ReportedExecution] = {}
    for row in values:
        snap = row.to_dict()
        snapshots[row.operation_ref] = snap
        reported[row.operation_ref] = reported_projection(row, snap)
    return TrialExecutionFacts(tuple(values), snapshots, reported, loaded["operations"])


def saved_capture(conn, admission):
    """This transaction's capture, seeded from a saved admission's facts while they still match production.

    Only a stored draft or scenario has a saved archive; a base being prepared reads its live capture directly.
    ``load_draft`` already admitted the archive when it decoded it.
    """
    capture = ProductionFactsCapture(conn)
    capture.seed_from_admitted_archive(admission["facts"])
    return capture


def live_context(conn, origin, capture, *, ledger: ExecutionLedgerReadScope, data_context):
    """Live production plus the execution of the trial's whole operation scope.

    origin is the trial source's members, prepared once: the whole scope is origin.operation_refs.
    capture is this transaction's production capture: a new base's own, or ``saved_capture`` of a stored admission.
    """
    facts = {"tables": LiveTables(capture)}
    preflight = PreflightFacts(conn, ledger=ledger, capture=capture)
    exec_facts = execution_facts(
        facts["tables"], origin.operation_refs,
        operation_refs=preflight.operation_refs, ledger=ledger)
    preflight.execution_projections.update((row.operation_ref, row) for row in exec_facts.projections)
    return {"facts": facts, "capture": capture, "execution": exec_facts.snapshots,
            "execution_reported": exec_facts.reported,
            "execution_operations": exec_facts.operations,
            "revisions": read_source_revisions(conn, LIVE_TRIAL_SOURCE_KEYS),
            "data_context_ref": data_context.ref(),
            "resource_facts": capture.resource_facts(),
            "baseline": run_baseline(capture=capture), "preflight_facts": preflight, "origin": origin}


def entity_maps(tables):
    return {(row["kind"], row["entity_key"]): row["ref"] for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}
