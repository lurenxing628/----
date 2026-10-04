"""Raw SQLite facts and a complete, streaming read-snapshot fingerprint."""

import hashlib
import json
from contextlib import contextmanager

from core.infrastructure.schema_probe import schema_objects, table_columns
from core.infrastructure.transaction import TransactionManager
from core.infrastructure.workbench_run_schema import RUN_TABLES
from core.infrastructure.workbench_trial_schema import TRIAL_TABLES
from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories.workbench_preflight_facts_repo import PREFLIGHT_TABLES, WorkbenchPreflightFactsRepository

TABLES = PREFLIGHT_TABLES
# 排产检查和排产计算都不读这些表的内容：OperationLogs 只写不读；排产账本是排产自己的记录；
# 试调草稿和方案只记试调过程（排产只读已采用方案的行，触发器保证它们不能改、不能删）；
# 看板处置只记处理进度。试调采用会改正式计划表，其他改动也都落在业务表上，仍参与比对。
NON_INPUT_TABLES = frozenset(("OperationLogs",) + RUN_TABLES + TRIAL_TABLES + (
    "WorkbenchDashboardStates", "WorkbenchDashboardHistory",
    "WorkbenchDashboardExternalStates", "WorkbenchDashboardExternalHistory"))
_NON_INPUT_ACTIONS = ("trial.", "dashboard.")
# 排产检查到开始排产之间：排产账本和排产回执仍要比对。一份检查结果只能开始一次排产，
# 先开始的那次写下的记录必须让同一份检查结果作废（计算过程中的比对才排除排产自己的记录）。
_PREFLIGHT_NON_INPUT_TABLES = NON_INPUT_TABLES - frozenset(RUN_TABLES)


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def non_input_row(table, row, receipt_columns, *, skip_runs=True):
    """这一行不影响排产输入：OperationLogs 的自增计数、排产自己的回执、试调和看板处置回执、“无改动”回执。

    回执只增不改；已提交、部分提交的其他回执和读不出来的行都保守地留在比对里。
    skip_runs=False 时排产回执也留在比对里（排产检查到开始排产之间用）。
    """
    if type(row) not in (list, tuple):
        return False
    if table == "sqlite_sequence":
        return len(row) == 2 and row[0] == "OperationLogs"
    if table != "WorkbenchCommandReceipts" or len(row) != len(receipt_columns):
        return False
    receipt = dict(zip(receipt_columns, row))
    action = receipt.get("action")
    if type(action) is str and (skip_runs and action == "scheduling.run" or action.startswith(_NON_INPUT_ACTIONS)):
        return True
    return _no_change_outcome(receipt.get("outcome_json"))


def _no_change_outcome(text):
    if type(text) is not str:
        return False
    try:
        outcome = json.loads(text)
    except ValueError:
        return False
    return type(outcome) is dict and outcome.get("result") == "unchanged"


def full_facts_fingerprint(conn):
    # Includes unselected execution/resources/calendars and all ledger revisions,
    # with the run worker's non-input exclusions except the run ledger itself.
    digest = hashlib.sha256()
    schema = schema_objects(conn)
    repo = WorkbenchPreflightFactsRepository(conn)
    receipt_columns = table_columns(conn, "WorkbenchCommandReceipts")
    digest.update(repr([tuple(row) for row in schema]).encode("utf-8"))
    for row in schema:
        if row[0] != "table" or row[1] in _PREFLIGHT_NON_INPUT_TABLES:
            continue
        digest.update(row[1].encode("utf-8"))
        for fact in repo.read_whole_table(row[1]):
            if non_input_row(row[1], fact, receipt_columns, skip_runs=False):
                continue
            encoded = repr(fact).encode("utf-8")
            digest.update(str(len(encoded)).encode("ascii") + b":" + encoded)
    return digest.hexdigest()


class PreflightFacts:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchPreflightFactsRepository(conn)
        self.tables = {}
        self.refs = {}
        self.operation_refs = {}

    @contextmanager
    def snapshot(self):
        with TransactionManager(self.conn).transaction():
            self.tables = self.repo.preflight_tables()
            self.refs = {(row["kind"], row["entity_key"]): row["ref"] for row in self.tables["WorkbenchEntityRefs"] if row["active"]}
            self.operation_refs = {int(row["source_key"]): row["ref"] for row in self.tables["WorkbenchPlanSourceRefs"]
                                   if row["kind"] == "operation" and row["active"]}
            yield full_facts_fingerprint(self.conn)

    def selected(self, refs):
        identities = {ref: key for (kind, key), ref in self.refs.items() if kind == "batch"}
        batches = {row["batch_id"]: row for row in self.tables["Batches"]}
        result = []
        for ref in refs:
            key = identities.get(ref)
            if key is None:
                raise WorkbenchCommandRejected("entity_not_found", "选中批次已失效，请刷新列表后重新选择。", 404)
            if key not in batches:
                raise WorkbenchCommandRejected("storage_failure", "批次编号和原记录对不上，检查没有继续。请刷新重试；仍不行请联系维护人员。", 500)
            result.append({**batches[key], "ref": ref})
        return result

    def operation_ref(self, op):
        ref = self.operation_refs.get(op["id"])
        if ref is None:
            raise WorkbenchCommandRejected("storage_failure", "工序编号缺失，请联系维护人员。", 500)
        return ref

    def schedule_through(self, version):
        """与排产输入同口径：version 及以前的正式安排，按 version,id 排序，同一工序后者为准。"""
        return sorted((row for row in self.tables["Schedule"] if row["version"] <= version), key=lambda row: (row["version"], row["id"]))

    def public_issue(self, item, op):
        """预检原因只带永久编号：内部工序 id 换成工序、批次编号，页面据此标出是哪批哪道。"""
        result = {key: value for key, value in item.items() if key != "op_id"}
        result.update(operation_ref=self.operation_ref(op), batch_ref=self.refs.get(("batch", op["batch_id"])), batch_id=op["batch_id"])
        return result
