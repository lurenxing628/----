"""Use exact SQLite admission facts with the existing scheduler input builder."""

from core.models.workbench_preflight import normalize_preflight_input

from .preflight_facts import TABLES, PreflightFacts
from .run_input import _prepare, _projection_map
from .run_input_rows import batch_model, operation_model


def prepare_trial_adoption_input(conn, settings, projections, live):
    if not conn.in_transaction:
        raise RuntimeError("Saved scenario input requires the caller's current read transaction")
    settings = normalize_preflight_input(settings)
    facts = PreflightFacts(conn)
    # These tables were read on this same connection/transaction by live_context.
    # Do not re-read them with PARSE_DECLTYPES or change the global connection.
    facts.tables = {name: live["facts"]["tables"][name] for name in TABLES}
    facts.refs = {(row["kind"], row["entity_key"]): row["ref"]
                  for row in facts.tables["WorkbenchEntityRefs"] if row["active"]}
    facts.operation_refs = {int(row["source_key"]): row["ref"] for row in facts.tables["WorkbenchPlanSourceRefs"]
                            if row["kind"] == "operation" and row["active"]}
    raw_batches = facts.selected(settings["batch_refs"])
    batches = {row["batch_id"]: batch_model(row) for row in raw_batches}
    raw_ops = [row for row in facts.tables["BatchOperations"] if row["batch_id"] in batches]
    operations = [operation_model(row) for row in raw_ops]
    projected = _projection_map(projections, [facts.operation_ref(row) for row in raw_ops])
    return _prepare(conn, settings, facts, live["facts_hash"], raw_batches, batches, operations, projected)
