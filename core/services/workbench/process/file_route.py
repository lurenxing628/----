"""Atomic route-file domain operations, subordinate to the file coordinator.

preview_rows consumes decoded rows and complete facts from the caller's one read
snapshot. The coordinator binds bytes, scope, target and all facts, then compares
the entire ResourceActionPreview document again under BEGIN IMMEDIATE before
calling apply_rows. Private row data carries only the selected write inputs.
Neither method owns the caller's commit, receipt, file token or public stage DTO.
Affected part refs include unchanged rows for the coordinator's read refresh.
"""

from contextlib import ExitStack
from functools import lru_cache

from core.infrastructure.connection_guards import schema_contract_memo
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.services.process.workflow_state import record_confirmation
from data.repositories.part_repo import PartRepository

from .file_route_preview import RouteFilePreview, reject_duplicates
from .group_defaults import _default_suppliers
from .part_actions import WorkbenchProcessPartActionService
from .part_actions_facts import check_part_action_storage
from .route_apply import apply_route, discard_groups


class ProcessRouteFileOperations:
    def __init__(self, conn, logger=None):
        self.conn, self.logger = conn, logger
        self.tx = TransactionManager(conn)
        # 新建零件、确认路线共用本命令的结构和连接事实；命令内不执行 DDL、不改外键设置。
        self.facts = {}

    @property
    def contracts(self):
        return schema_contract_memo(self.conn)

    def preview_rows(self, decoded_rows, facts, target_ref=None):
        if not self.conn.in_transaction:
            raise RuntimeError("路线文件预检必须在调用方的完整事实快照事务中执行。")
        self.facts = facts
        self.current_identities = {row["ref"]: WorkbenchEntityIdentity(row["ref"], row["kind"], row["entity_key"],
                                   row["revision"], bool(row["active"])) for row in facts["identities"]}
        self.parts = {row["part_no"]: row for row in facts["parts"]}
        with ExitStack() as stack:
            preview = RouteFilePreview(self.conn, self.logger, facts, target_ref, stack)
            rows = [preview.row(source) for source in decoded_rows]
            reject_duplicates(rows)
            extra = {"affected_groups": preview.affected_groups(rows), "zero_review_required": False}
        return rows, extra

    def apply_rows(self, rows):
        if not self.conn.in_transaction:
            raise RuntimeError("路线文件保存必须在外层BEGIN IMMEDIATE事务中执行。")
        with self.tx.transaction():
            check_part_action_storage(self.conn, self.contracts)
            creator = WorkbenchProcessPartActionService(self.conn, self.logger, self.contracts)
            self.creations = {row["row"]: creator.prepare_create(row["input"],
                parts=self.parts,
                route_parsed="yes" if row["related"]["route"] is not None else "no")
                for row in rows if row["action"] == "create"}
            @lru_cache(maxsize=1)
            def default_catalog():
                return _default_suppliers(self.conn, self.facts["references"])

            results, affected_refs = [], set()
            for row in rows:
                result = self._apply_row(row, default_catalog, creator)
                results.append(result)
                affected_refs.add(result["entity_ref"])
            return results, sorted(affected_refs)

    def _apply_row(self, row, default_catalog_reader, creator):
        route = row["related"]["route"]
        fields = {}
        if row["action"] == "create":
            route_parsed = "yes" if route is not None else "no"
            outcome = creator.apply_create(self.creations[row["row"]])
            ref = outcome.data["entity_ref"]
            part = {"part_no": row["business_code"], "route_raw": row["after"]["route_raw"], "route_parsed": route_parsed}
            operations = []
        else:
            ref = row["entity_ref"]
            part, operations = row["expected"]["part"], row["expected"]["operations"]
            fields = self._text_fields(row)
        if route is not None:
            discard_groups(self.conn, row["business_code"], row["related"]["affected_groups"])
            apply_route(self.conn, part, operations, route, self.current_identities,
                        part_updates=fields, default_catalog_reader=default_catalog_reader)
            record_confirmation(self.conn, row["business_code"], "route", contracts=self.contracts)
        elif fields:
            PartRepository(self.conn).update(row["business_code"], fields)
        return {"row": row["row"], "result": "unchanged" if row["result"] == "unchanged" else "committed",
                "entity_ref": ref, "business_code": row["business_code"]}

    @staticmethod
    def _text_fields(row):
        columns = {"label": "part_name", "remark": "remark"}
        return {column: row["after"][key] for key, column in columns.items() if key in row["changes"]}
