"""Exact SQL pagination over one durable directory snapshot."""

from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot

from .history_storage import RunHistoryStore


def _catalog_payload(scope, rows, total, run_count):
    offset = (scope.page - 1) * scope.size
    return {
        "runs": rows,
        "page": {"number": scope.page, "size": scope.size, "total": total, "has_more": offset + scope.size < total},
        "run_count": run_count,
        "state": scope.state,
        "sort": scope.sort,
        "order": scope.order,
        "nulls": "last",
        "tie_breaker": "run_ref_same_order",
        "time_scope": {
            "accepted_from": scope.accepted_from,
            "accepted_to": scope.accepted_to,
            "field": "accepted_at",
            "boundary": "inclusive_dates",
            "time_basis": "factory_local",
        },
    }


class WorkbenchRunHistoryQueryService:
    def __init__(self, conn):
        self.conn = conn

    def catalog_for_snapshot(self, scope, *, bind_snapshot):
        with candidate_read_snapshot(self.conn):
            store = RunHistoryStore(self.conn)
            state = store.read_state()
            snapshot = bind_snapshot(scope.scope(), state)
            rows, total = store.read_page(scope, run_count=state["run_count"])
            return _catalog_payload(scope, rows, total, state["run_count"]), snapshot

    def latest_catalog(self, scope):
        with candidate_read_snapshot(self.conn):
            store = RunHistoryStore(self.conn)
            run_count = store.repo.count_jobs()
            rows, total = store.read_page(scope, run_count=run_count)
            return _catalog_payload(scope, rows, total, run_count)
