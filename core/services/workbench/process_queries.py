"""Snapshot-bound process reads and route differences, without template writes."""

import math
from collections import defaultdict
from contextlib import contextmanager
from datetime import date, datetime

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.services.process.workflow_state import workflow_snapshot
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository

from .process_projection import capabilities, project_group, project_operation, project_part, public_sequence


def _plain(value):
    if isinstance(value, (date, datetime)):
        return {"storage_type": type(value).__name__, "iso": value.isoformat()}
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return {"storage_type": "float", "value": str(value)}
    if isinstance(value, bytes):
        return {"storage_type": "blob", "hex": value.hex()}
    return value


def _route_changes(active, proposed):
    invalid = [row for row in active if any(item["code"] == "sequence_invalid" for item in row["issues"])]
    invalid_refs = {row["ref"] for row in invalid}
    old = {int(row["sequence"]): row for row in active if row["ref"] not in invalid_refs}
    new = {row["sequence"]: row for row in proposed}
    common = old.keys() & new.keys()
    retained = sorted(seq for seq in common if old[seq]["label"] == new[seq]["op_type_name"]
                      and old[seq]["op_type_ref"] == new[seq]["op_type_ref"])
    return {"added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
            "retained": retained, "same_sequence_changed": sorted(common - set(retained))}, invalid


class WorkbenchProcessQueryService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.repo = WorkbenchProcessQueryRepository(conn, logger=logger)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self._facts = None
        self._table = None

    def facts(self):
        if self._facts is not None:
            return self._facts
        try:
            workflow = workflow_snapshot(self.conn)
        except RuntimeError as exc:
            raise WorkbenchCommandRejected("storage_failure", "工艺确认记录或它的编号不完整，系统不会自动补资料。请刷新重试；仍不行请联系维护人员。", 500) from exc
        return {"parts": self.repo.parts(), "operations": self.repo.operations(), "groups": self.repo.groups(),
                "references": self.repo.references(), "identities": self.repo.identities(),
                "workflow": workflow}

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            previous = self._facts
            previous_table = self._table
            self._facts = self.facts()
            self._table = None
            try:
                yield input_fingerprint(_plain(self._facts))
            finally:
                self._facts = previous
                self._table = previous_table

    def table(self):
        from .process_table import ProcessTable

        if self._table is None:
            facts = self.facts()
            grouped = defaultdict(list)
            for row in facts["operations"]:
                grouped[row["part_no"]].append(row)
            entities = [project_part(row, grouped[row["part_no"]], facts["workflow"][row["part_no"]]["workflow"])
                        for row in facts["parts"]]
            table = ProcessTable(entities)
            if self._facts is not None:
                self._table = table
            return table
        return self._table

    def resolve(self, ref):
        if not isinstance(ref, str) or len(ref) != 48 or any(c not in "0123456789abcdef" for c in ref):
            raise WorkbenchCommandRejected("entity_not_found", "零件记录不存在，请返回列表重新选择。", 404)
        identity = self.identities.get(ref)
        if identity is None or identity.kind != "part" or not identity.active:
            raise WorkbenchCommandRejected("entity_not_found", "这个零件已经不在了，旧编号不会指到同号的新零件。请刷新列表后重新选择。", 404)
        return identity

    def page(self, query):
        facts = self.facts()
        grouped = defaultdict(list)
        for row in facts["operations"]:
            grouped[row["part_no"]].append(row)
        needle = query.query.casefold()
        matched = [project_part(row, grouped[row["part_no"]], facts["workflow"][row["part_no"]]["workflow"]) for row in facts["parts"]
                   if not needle or any(needle in str(row[key] or "").casefold() for key in ("part_no", "part_name", "route_raw"))]
        if query.stage is not None:
            matched = [row for row in matched if row["workflow"]["stage"] == query.stage]
        counts = {stage: sum(row["workflow"]["stage"] == stage for row in matched) for stage in ("route", "source", "hours", "ready")}
        counts["total"] = len(matched)
        matched.sort(key=lambda row: row["business_code"])

        def order(row):
            if query.sort == "operation_count":
                return row["relationships"]["operation_count"]
            if query.sort == "stage":
                return ("route", "source", "hours", "ready").index(row["workflow"]["stage"])
            return row[query.sort]

        matched.sort(key=order, reverse=query.direction == "desc")
        start = (query.number - 1) * query.size
        return {"entities": matched[start:start + query.size], "page": {
            "number": query.number, "size": query.size, "total": len(matched),
            "pages": max(1, (len(matched) + query.size - 1) // query.size),
            "sort": [{"field": query.sort, "direction": query.direction}]},
            "metrics": {"scope": "filtered", "counts": counts}, "capabilities": capabilities(), "create_context": None}

    def detail(self, ref):
        identity = self.resolve(ref)
        facts = self.facts()
        row = next((row for row in facts["parts"] if row["ref"] == identity.ref), None)
        if row is None:
            raise WorkbenchCommandRejected("storage_failure", "零件编号和实际模板对不上。请刷新重试；仍不行请联系维护人员。", 500)
        operations = [row for row in facts["operations"] if row["part_no"] == identity.entity_key]
        workflow = facts["workflow"][identity.entity_key]
        entity = project_part(row, operations, workflow["workflow"])
        members = defaultdict(list)
        for operation in facts["operations"]:
            if operation["status"] == "active" and operation["ext_group_id"] is not None:
                members[operation["ext_group_id"]].append(operation)
        groups = {row["group_id"]: project_group(row, members[row["group_id"]])
                  for row in facts["groups"] if row["part_no"] == identity.entity_key}
        missing = {key: {"state": "unconfirmed", "confirmed_at": None, "confirmed_by": None} for key in ("source", "hours")}
        entity.update({"operations": [project_operation(row, workflow["operations"].get(row["ref"], missing),
                                                       groups.get(row["ext_group_id"])) for row in operations],
                       "external_groups": list(groups.values()),
                       "capabilities": capabilities()})
        return entity

    def route_difference(self, ref, preview):
        entity = self.detail(ref)
        active = [row for row in entity["operations"] if row["status"] == "active"]
        changes, invalid = _route_changes(active, preview["operations"])
        result = {**preview, "part_ref": ref, "baseline": {"operation_count": len(active),
                "external_group_count": len(entity["external_groups"]), "has_published_template": bool(active)},
                "changes": changes,
                "write_context": None}
        result["operations"] = [{**row, "sequence": public_sequence(row["sequence"])} for row in preview["operations"]]
        result["diagnostics"] = [{**row, **({"sequence": public_sequence(row["sequence"])} if "sequence" in row else {})}
                                 for row in preview["diagnostics"]]
        if invalid:
            result["can_confirm_route"] = False
            result["diagnostics"].append({"code": "legacy_sequence_invalid", "severity": "error",
                                          "message": "现有模板里有不合法的工序号，系统不会自动改号，也不会悄悄删掉。请到基础资料核对工序号。"})
        result["changes"] = {key: [public_sequence(seq) for seq in values] for key, values in result["changes"].items()}
        return result
