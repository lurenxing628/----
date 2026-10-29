"""Complete production evidence, with no trial/command bookkeeping feedback loop."""

from core.models.content import same
from core.models.workbench_trial import MAX_TRIAL_TASKS, reject
from core.services.scheduler.resource_pool_builder import CapturedResourceFacts
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.production_capture import ProductionFactsCapture
from core.services.workbench.facts.schema_compat import project_facts
from core.services.workbench.facts.trial_origin import context_operation_refs
from core.services.workbench.run.jobs_facts import run_baseline
from core.services.workbench.run.preflight_facts import PreflightFacts


def facts_unchanged(admission, live):
    """Compare saved production content; preserve original historical metadata."""
    return same(project_facts(admission["facts"]), project_facts(live["facts"]))


def execution_facts(tables, selected_refs, *, operation_refs, service):
    refs = set(selected_refs)
    refs.update(operation_refs[row["op_id"]] for row in tables["Schedule"] if row["op_id"] in operation_refs)
    for row in tables.get("WorkbenchProductionReports", []):
        refs.add(row["operation_ref"])
    if len(refs) > MAX_TRIAL_TASKS:
        reject("query_too_large", "试调及真实执行保护范围超过10000道工序，未遗漏范围外占用。", 413)
    values = service.project_operations(sorted(refs))
    return {row.operation_ref: row.to_dict() for row in values}, values


def live_context(conn, rows, admission, capture=None, *, execution_service, source_facts=None):
    """Live production plus the execution of the trial's whole operation scope.

    admission supplies the trial source and the facts that scope was taken from.
    source_facts is the candidate source's GenerationFacts when the caller already decoded it.
    """
    capture = capture if capture is not None else ProductionFactsCapture(conn)
    facts = capture.archive(named=True)
    capture.execution_service = execution_service
    preflight = PreflightFacts(conn, capture=capture)
    preflight.bind_capture(capture)
    source = admission["source"]
    if source_facts is None and "capture" in source:
        source_facts = GenerationFacts(source["capture"])
    projections, prepared = execution_facts(facts["tables"], context_operation_refs(rows, admission, source_facts),
                                            operation_refs=preflight.operation_refs, service=execution_service)
    preflight.execution_projections.update((row.operation_ref, row) for row in prepared)
    return {"facts": facts, "execution": projections,
            "resource_facts": CapturedResourceFacts(preflight.tables, {}),
            "baseline": run_baseline(capture=capture), "preflight_facts": preflight, "source_facts": source_facts}


def entity_maps(tables):
    return {(row["kind"], row["entity_key"]): row["ref"] for row in tables["WorkbenchEntityRefs"] if row["active"] == 1}
