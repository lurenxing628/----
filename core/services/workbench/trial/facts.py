"""Complete production evidence, with no trial/command bookkeeping feedback loop."""

from core.models.content import same
from core.models.workbench_trial import MAX_TRIAL_TASKS, reject
from core.services.scheduler.resource_pool_builder import CapturedResourceFacts
from core.services.workbench.facts.candidate_store import cached_generation_facts
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.facts.run_data_context import RunDataContext
from core.services.workbench.facts.schema_compat import project_facts
from core.services.workbench.facts.source_revisions import TRIAL_SOURCE_KEYS, read_source_revisions
from core.services.workbench.facts.trial_origin import context_operation_refs
from core.services.workbench.run.jobs_facts import run_baseline
from core.services.workbench.run.preflight_facts import PreflightFacts

LIVE_TRIAL_SOURCE_KEYS = tuple(key for key in TRIAL_SOURCE_KEYS if key != "trial_records")


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


def execution_facts(tables, selected_refs, *, operation_refs, service):
    refs = set(selected_refs)
    refs.update(operation_refs[row["op_id"]] for row in tables["Schedule"] if row["op_id"] in operation_refs)
    for row in tables["WorkbenchProductionReports"]:
        refs.add(row["operation_ref"])
    if len(refs) > MAX_TRIAL_TASKS:
        reject("query_too_large", "试调及真实执行保护范围超过10000道工序，未遗漏范围外占用。", 413)
    with service.read_snapshot():
        values = service.project_loaded(service.load(sorted(refs)), include_history=False)
    return {row.operation_ref: row.to_dict() for row in values}, values


def live_context(conn, rows, admission, capture=None, *, execution_service, source_facts=None, data_context=None):
    """Live production plus the execution of the trial's whole operation scope.

    admission supplies the trial source and the facts that scope was taken from.
    source_facts is the candidate source's GenerationFacts when the caller already decoded it.
    """
    capture = capture if capture is not None else ProductionFactsCapture(conn)
    capture.seed_from_named_archive(admission["facts"])
    facts = {"tables": LiveTables(capture)}
    capture.execution_service = execution_service
    preflight = PreflightFacts(conn, capture=capture)
    preflight.bind_capture(capture)
    source = admission["source"]
    if source_facts is None and "capture" in source:
        source_facts = cached_generation_facts(source["capture"])
    projections, prepared = execution_facts(facts["tables"], context_operation_refs(rows, admission, source_facts),
                                            operation_refs=preflight.operation_refs, service=execution_service)
    preflight.execution_projections.update((row.operation_ref, row) for row in prepared)
    return {"facts": facts, "capture": capture, "execution": projections,
            "revisions": read_source_revisions(conn, LIVE_TRIAL_SOURCE_KEYS),
            "data_context_ref": (data_context if data_context is not None else RunDataContext(conn)).ref(),
            "resource_facts": CapturedResourceFacts(preflight.tables, {}),
            "baseline": run_baseline(capture=capture), "preflight_facts": preflight, "source_facts": source_facts}


def entity_maps(tables):
    return {(row["kind"], row["entity_key"]): row["ref"] for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}
