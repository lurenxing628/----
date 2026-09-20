"""One bounded directory read; task payloads and current resource tables stay unread."""

from core.infrastructure.workbench_run_schema import workbench_run_contract_issues
from core.models.workbench_run_history import (
    MAX_DIRECTORY_BYTES,
    MAX_DIRECTORY_ROWS,
    MAX_DOCUMENT_BYTES,
    inconsistent,
    reject,
)
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
        if workbench_run_contract_issues(self.conn):
            reject("run_schema_unavailable", "排产记录结构不完整，请联系维护人员。", 503)

    def _capacity(self):
        total = 0
        for facts in self.repo.directory_capacity().values():
            _bounded(facts["rows"], MAX_DIRECTORY_ROWS)
            _bounded(facts["max_document_bytes"], MAX_DOCUMENT_BYTES)
            total += facts["bytes"]
        _bounded(total, MAX_DIRECTORY_BYTES)
        _bounded(self.repo.candidate_count(), MAX_DIRECTORY_ROWS)

    def _require_parents(self):
        # These anti-joins also catch unfiltered/off-page orphans with foreign_keys disabled by an older writer.
        if any(self.repo.orphan_probe().values()):
            inconsistent()

    def read(self):
        self.require_schema()
        self._capacity()
        self._require_parents()
        return self.repo.list_jobs(), self.repo.list_candidates()
