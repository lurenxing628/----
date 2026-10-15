"""Exact SQL pagination over one durable directory snapshot."""

from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot

from .history_storage import RunHistoryStore


class WorkbenchRunHistoryQueryService:
    def __init__(self, conn):
        self.conn = conn

    def catalog(self, scope):
        with candidate_read_snapshot(self.conn):
            rows, total, state = RunHistoryStore(self.conn).read(scope)
            offset = (scope.page - 1) * scope.size
            return {"runs": rows,
                    "page": {"number": scope.page, "size": scope.size, "total": total,
                             "has_more": offset + scope.size < total},
                    "run_count": state["run_count"], "state": scope.state, "sort": scope.sort, "order": scope.order,
                    "nulls": "last", "tie_breaker": "run_ref_same_order",
                    "time_scope": {"accepted_from": scope.accepted_from, "accepted_to": scope.accepted_to,
                                   "field": "accepted_at", "boundary": "inclusive_dates", "time_basis": "factory_local"}}, state
