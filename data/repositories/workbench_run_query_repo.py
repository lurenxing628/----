"""SQL pagination over durable run heads and their immutable read models."""

from __future__ import annotations

from typing import Any, Dict, List

from core.infrastructure.efficiency_indexes_schema import run_history_sort_expressions

from .base_repo import BaseRepository


class WorkbenchRunHistoryQueryRepository(BaseRepository):
    @staticmethod
    def _filter(scope):
        clauses, values = [], []
        if scope is not None:
            if scope.state != "all":
                clauses.append("j.state=?")
                values.append(scope.state)
            if scope.accepted_from is not None:
                clauses.extend(("j.accepted_at>=?", "j.accepted_at<=?"))
                values.extend((scope.accepted_from + "T00:00:00", scope.accepted_to + "T23:59:59.999999"))
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), values

    def count_jobs(self, scope=None) -> int:
        where, values = self._filter(scope)
        return self.execute("SELECT COUNT(*) FROM WorkbenchRunJobs j" + where, values).fetchone()[0]

    def active_jobs(self) -> List[Dict[str, Any]]:
        return self.fetchall("""SELECT run_ref,state,stage FROM WorkbenchRunJobs
            WHERE state IN ('queued','running') ORDER BY run_ref""")

    def list_jobs(self, scope) -> List[Dict[str, Any]]:
        where, values = self._filter(scope)
        # The stored ISO strings may use seconds or 1..6 fractional digits.
        # Padding only the fractional part retains exact datetime ordering and
        # treats 12:00:00 and 12:00:00.000000 as the same instant.
        field, order = "j." + scope.sort, scope.order.upper()
        seconds, fraction = run_history_sort_expressions(field)
        sorting = (seconds + " " + order + " NULLS LAST," + fraction + " " + order + ",j.run_ref " + order)
        values.extend((scope.size, (scope.page - 1) * scope.size))
        return self.fetchall("""SELECT j.run_ref,j.request_key,j.input_ref,j.state,j.stage,
            j.accepted_at,j.started_at,j.finished_at,j.executor_ref,
            a.projection_version AS scope_version,a.scope_json,
            d.projection_version AS header_version,d.header_json,
            r.receipt_ref,r.state AS receipt_state,r.recorded_at
            FROM (SELECT j.run_ref,j.request_key,j.input_ref,j.state,j.stage,
                j.accepted_at,j.started_at,j.finished_at,j.executor_ref
                FROM WorkbenchRunJobs j"""
            + where + " ORDER BY " + sorting + " LIMIT ? OFFSET ?) j\n"
            + """
            LEFT JOIN WorkbenchRunAdmissionReadModels a ON a.run_ref=j.run_ref
            LEFT JOIN WorkbenchRunDecisionReadModels d ON d.run_ref=j.run_ref
            LEFT JOIN WorkbenchRunReceipts r ON r.run_ref=j.run_ref"""
            + " ORDER BY " + sorting, values)
