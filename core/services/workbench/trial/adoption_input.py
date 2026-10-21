"""Use exact SQLite admission facts with the existing scheduler input builder."""

from core.models.workbench_preflight import normalize_preflight_input
from core.services.workbench.run.input import _prepare_facts


def prepare_trial_adoption_input(conn, settings, projections, live, hold=None, *, capture, validated_projections=None):
    if not conn.in_transaction:
        raise RuntimeError("Saved scenario input requires the caller's current read transaction")
    settings = normalize_preflight_input(settings)
    facts = live["preflight_facts"]
    # These tables were read on this same connection/transaction by live_context.
    # Do not re-read them with PARSE_DECLTYPES or change the global connection.
    if capture.conn is not conn:
        raise RuntimeError("Trial input requires this transaction's own production capture")
    # Adoption validates in this caller-owned read transaction; it does not
    # hand this prepared input to an independent calculation.
    return _prepare_facts(conn, settings, facts, "", projections, None, live["baseline"],
                          validated_projections, hold=hold)
