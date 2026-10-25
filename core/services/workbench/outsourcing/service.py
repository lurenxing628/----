"""SELECT-only outsourcing catalog and original-instance history.

Judgement over WorkbenchOutsourcingRepository facts (missing schema, unknown
receipt, member drift, row caps) lives here; the repository only reads.
"""

from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Optional, TypedDict, cast

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_outsourcing import MAX_ROWS, page, pagination, reference, reject
from data.repositories.workbench_outsourcing_repo import WorkbenchOutsourcingRepository

from .projection import fact, receipt
from .source import WorkbenchOutsourcingSourceService


class CapturedReceiptFacts(TypedDict):
    header: Dict[str, Any]
    latest: Optional[Dict[str, Any]]


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
        return self.header_from_row(self.repo.header(ref))

    @staticmethod
    def header_from_row(header: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Admit a receipt header without reading its members again."""
        if header is None:
            reject("外协原登记不存在，未改读其他对象。", "entity_not_found", 404)
        if header["target"]["operation_refs"] != header["origin"]["operation_refs"]:
            reject("外协成员映射与原登记不一致，未忽略缺失成员。", "outsourcing_unavailable", 503)
        return header

    def latest(self, ref):
        return self.latest_from_row(self.repo.latest(ref))

    @staticmethod
    def latest_from_row(row):
        if row is None:
            reject("外协登记缺少确认事实，请恢复完整记录。", "outsourcing_unavailable", 503)
        return row

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
        return self.entry_from_facts(header, latest, now, sources=self.sources.capture([header["target"]]))

    def capture_receipts(self, batch_ref=None) -> Dict[str, CapturedReceiptFacts]:
        captured = self.repo.receipt_facts(self.refs(batch_ref))
        for rows in captured.values():
            rows["header"] = self.header_from_row(rows["header"])
        return cast(Dict[str, CapturedReceiptFacts], captured)

    def entry_from_facts(self, header, latest, now, *, sources):
        """Resolve a receipt from header/latest already admitted in the caller's snapshot."""
        source, issues, state = None, [], "current"
        try:
            source = sources.load(header["target"])
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
        return result, snapshot

    def detail(self, ref, *, as_of=None):
        reference(ref)
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing detail requires a caller-owned snapshot")
        item, snapshot = self._entry(ref, as_of or self.now())
        return {"item": item, "content": snapshot}

    def history(self, ref, *, number=1, size=20, as_of=None):
        pagination(number, size)
        result = self.detail(ref, as_of=as_of)
        rows, paging = self.repo.history(ref, number, size)
        result["history"] = {"items": [fact(row) for row in rows], "page": paging}
        return result

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
        captured = self.capture_receipts(batch_ref)
        sources = self.sources.capture([facts["header"]["target"] for facts in captured.values()])
        for facts in captured.values():
            item, snapshot = self.entry_from_facts(facts["header"], self.latest_from_row(facts["latest"]), now, sources=sources)
            snapshots.append(snapshot)
            if (status == "all" or (status == "awaiting" and item["awaiting_return"])
                    or (status == "overdue" and item["overdue"])
                    or (status == "returned" and not item["awaiting_return"])):
                rows.append(item)
        return {**page(rows, number, size), "content": snapshots,
                "as_of": now.isoformat(timespec="seconds"), "tracking_basis": "manual_receipt_facts"}

    def targets(self, *, batch_ref=None, query="", number=1, size=20):
        if batch_ref is not None:
            reference(batch_ref)
        if type(query) is not str or len(query) > 200 or "\x00" in query:
            reject("查找内容须为不超过 200 字的文字。", status=400)
        query = query.strip()
        pagination(number, size)
        if not self.conn.in_transaction:
            raise RuntimeError("Outsourcing targets require a caller-owned snapshot")
        target_rows, sources = self.sources.capture_targets(batch_ref, query)
        rows = [item for item, source in sources.load_target_rows(target_rows)]
        clock = sources.repo.plan_identity_revision()
        return {**page(rows, number, size), "content": {"rows": rows, "clock": clock, "query": query},
                "grouping_basis": "explicit_receipt_membership", "dates_inferred": False}
