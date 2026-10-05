"""SELECT-only outsourcing catalog and original-instance history.

Judgement over WorkbenchOutsourcingRepository facts (missing schema, unknown
receipt, member drift, row caps) lives here; the repository only reads.
"""

from contextlib import contextmanager
from datetime import datetime

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_outsourcing import MAX_ROWS, bounded, page, pagination, reference, reject
from data.repositories.workbench_outsourcing_repo import WorkbenchOutsourcingRepository

from .projection import fact, receipt
from .source import WorkbenchOutsourcingSourceService


class WorkbenchOutsourcingService:
    def __init__(self, conn, *, clock=None):
        self.conn, self.clock = conn, clock or datetime.now
        self.repo = WorkbenchOutsourcingRepository(conn)
        self.sources = WorkbenchOutsourcingSourceService(conn)

    # ---- judgement over repository facts ----

    def require_schema(self):
        if self.repo.schema_issues():
            reject("真实外协登记结构尚未完整接入；未补表或改动原资料。", "outsourcing_unavailable", 503)

    def header(self, ref):
        header = self.repo.header(ref)
        if header is None:
            reject("外协原登记不存在，未改读其他对象。", "entity_not_found", 404)
        if header["target"]["operation_refs"] != header["origin"]["operation_refs"]:
            reject("外协成员映射与原登记不一致，未忽略缺失成员。", "outsourcing_unavailable", 503)
        return bounded(header)

    def latest(self, ref):
        row = self.repo.latest(ref)
        if row is None:
            reject("外协登记缺少确认事实，请恢复完整记录。", "outsourcing_unavailable", 503)
        return bounded(row)

    def refs(self, batch_ref=None):
        refs = self.repo.refs(batch_ref, MAX_ROWS)
        if len(refs) > MAX_ROWS:
            reject("外协登记超过10000项，请限定批次。", "query_too_large", 413)
        return refs

    # ---- snapshots and projections ----

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            self.require_schema()
            yield

    def now(self):
        now = self.clock()
        if not isinstance(now, datetime) or now.tzinfo is not None:
            raise ValueError("Outsourcing time must be factory local")
        return now.replace(microsecond=0)

    def _entry(self, ref, now):
        header, latest = self.header(ref), self.latest(ref)
        return self.entry_from_facts(header, latest, now)

    def entry_from_facts(self, header, latest, now):
        """Resolve a receipt from header/latest already admitted in the caller's snapshot."""
        source, issues, state = None, [], "current"
        try:
            source = self.sources.load(header["target"])
            if source["identity"] != header["identity"]:
                state = "identity_drift"
                issues = [{"code": "identity_drift", "message": "原登记的工序或所属批次已变化，请重新核对。"}]
        except WorkbenchCommandRejected as exc:
            if exc.code not in ("identity_missing", "identity_drift", "entity_not_found", "constraint_conflict"):
                raise
            state = "source_unavailable"
            issues = [{"code": exc.code, "message": str(exc)}]
        result = receipt(header, latest, now, source_state=state, issues=issues)
        result["can_preview"] = state == "current"
        snapshot = {"header": header, "latest_fact_ref": latest["fact_ref"], "source": source, "issues": issues}
        return bounded(result), snapshot

    def detail(self, ref, *, as_of=None):
        reference(ref)
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing detail requires a caller-owned snapshot")
        item, snapshot = self._entry(ref, as_of or self.now())
        return {"item": item, "fingerprint": input_fingerprint(snapshot)}

    def history(self, ref, *, number=1, size=20, as_of=None):
        pagination(number, size)
        result = self.detail(ref, as_of=as_of)
        rows, paging = self.repo.history(ref, number, size)
        result["history"] = {"items": [fact(row) for row in bounded(rows)], "page": paging}
        return bounded(result)

    def receipts(self, *, batch_ref=None, status="all", number=1, size=20, as_of=None):
        if batch_ref is not None:
            reference(batch_ref)
        if status not in ("all", "awaiting", "overdue", "returned"):
            reject("外协筛选状态无效。", status=400)
        pagination(number, size)
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing list requires a caller-owned snapshot")
        now = as_of or self.now()
        rows, snapshots = [], []
        for ref in self.refs(batch_ref):
            item, snapshot = self._entry(ref, now)
            snapshots.append(snapshot)
            matches = {"all": True, "awaiting": item["awaiting_return"], "overdue": item["overdue"], "returned": not item["awaiting_return"]}
            if matches[status]:
                rows.append(item)
        return bounded({**page(rows, number, size), "fingerprint": input_fingerprint(bounded(snapshots)),
                        "as_of": now.isoformat(timespec="seconds"), "tracking_basis": "manual_receipt_facts"})

    def targets(self, *, batch_ref=None, query="", number=1, size=20):
        if batch_ref is not None:
            reference(batch_ref)
        if type(query) is not str or len(query) > 200 or "\x00" in query:
            reject("查找内容须为不超过 200 字的文字。", status=400)
        query = query.strip()
        pagination(number, size)
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing targets require a caller-owned snapshot")
        rows = self.sources.targets(batch_ref, query)
        clock = self.repo.plan_identity_revision()
        return bounded({**page(rows, number, size), "fingerprint": input_fingerprint({"rows": rows, "clock": clock, "query": query}),
                        "grouping_basis": "explicit_receipt_membership", "dates_inferred": False})
