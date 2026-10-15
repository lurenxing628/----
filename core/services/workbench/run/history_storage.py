"""Read one SQL page of immutable admission and decision projections."""

from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.workbench_run_schema import workbench_run_contract_issues
from core.models.workbench_run_history import (
    MAX_DIRECTORY_BYTES,
    MAX_DOCUMENT_BYTES,
    inconsistent,
    reject,
)
from core.services.workbench.facts.decision_read_models import public_run_head, read_model_json
from data.repositories.workbench_run_query_repo import WorkbenchRunHistoryQueryRepository


def _bounded(value, limit):
    if type(value) is not int or value < 0:
        inconsistent()
    if value > limit:
        reject("run_history_capacity_exceeded", "排产记录超过读取上限，请缩小查询范围后重试。", 413)


class RunHistoryStore:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchRunHistoryQueryRepository(conn)

    def require_schema(self):
        if schema_contract_memo(self.conn).get_schema(workbench_run_contract_issues):
            reject("run_schema_unavailable", "排产记录结构不完整，请联系维护人员。", 503)

    def read(self, scope):
        self.require_schema()
        total = self.repo.count_jobs(scope)
        run_count = total if scope.state == "all" and scope.accepted_from is None else self.repo.count_jobs()
        rows, byte_count = [], 0
        for head in self.repo.list_jobs(scope):
            for field in ("scope_json", "header_json"):
                raw = head[field]
                if raw is not None:
                    size = len(raw.encode("utf-8")) if type(raw) is str else -1
                    _bounded(size, MAX_DOCUMENT_BYTES)
                    byte_count += size
            _bounded(byte_count, MAX_DIRECTORY_BYTES)
            admission = read_model_json(head, "scope_json")
            header = (read_model_json(head, "header_json")
                      if head["header_version"] is not None or head["header_json"] is not None else None)
            rows.append(public_run_head(head, admission, header))
        state = {"read_contract_version": 1, "run_count": run_count, "active_runs": self.repo.active_jobs()}
        return rows, total, state
