"""Exact pagination over one verified durable directory snapshot."""

from collections import defaultdict

from core.models.workbench_command import input_fingerprint
from core.models.workbench_run_history import local_datetime

from .run_history_projection import public_run
from .run_history_storage import RunHistoryStore
from .run_input_readonly import candidate_read_snapshot


class WorkbenchRunHistoryQueryService:
    def __init__(self, conn):
        self.conn = conn

    def catalog(self, scope):
        with candidate_read_snapshot(self.conn):
            jobs, candidates = RunHistoryStore(self.conn).read()
            by_run = defaultdict(list)
            for row in candidates:
                by_run[row["run_ref"]].append(row)
            rows = [public_run(job, by_run[job["run_ref"]]) for job in jobs]
            fingerprint = input_fingerprint({"jobs": jobs, "candidates": candidates})
            filtered = [row for row in rows if _matches(row, scope)]
            dated = [row for row in filtered if row[scope.sort] is not None]
            undated = [row for row in filtered if row[scope.sort] is None]
            dated.sort(key=lambda row: (local_datetime(row[scope.sort]), row["run_ref"]), reverse=scope.order == "desc")
            undated.sort(key=lambda row: row["run_ref"], reverse=scope.order == "desc")
            filtered = dated + undated
            offset = (scope.page - 1) * scope.size
            return {"runs": filtered[offset:offset + scope.size],
                    "page": {"number": scope.page, "size": scope.size, "total": len(filtered),
                             "has_more": offset + scope.size < len(filtered)},
                    "run_count": len(rows), "state": scope.state, "sort": scope.sort, "order": scope.order,
                    "nulls": "last", "tie_breaker": "run_ref_same_order",
                    "time_scope": {"accepted_from": scope.accepted_from, "accepted_to": scope.accepted_to,
                                   "field": "accepted_at", "boundary": "inclusive_dates", "time_basis": "factory_local"}}, fingerprint


def _matches(row, scope):
    accepted = local_datetime(row["accepted_at"]).date().isoformat()
    return (scope.state in ("all", row["state"])
            and (scope.accepted_from is None or scope.accepted_from <= accepted <= scope.accepted_to))
