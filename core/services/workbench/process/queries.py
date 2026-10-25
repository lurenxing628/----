"""Snapshot-bound process reads and route differences, without template writes."""

from collections import defaultdict
from contextlib import contextmanager

from core.infrastructure.transaction import TransactionManager
from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.services.process.template_source import TemplateSourceFacts
from core.services.process.workflow_state import workflow_snapshot
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository

from .projection import capabilities, project_group, project_operation, project_part, public_sequence
from .route_choices import changed_route_sequences, preview_existing_route, route_choice_context
from .route_facts import ProcessRouteFacts


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
    def __init__(self, conn, logger=None, *, part_ref=None):
        self.conn = conn
        self.repo = WorkbenchProcessQueryRepository(conn, logger=logger, part_ref=part_ref)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self._facts = None
        self._identities_by_ref = None
        self._table = None
        self._details = {}

    def facts(self):
        if self._facts is not None:
            return self._facts
        facts = {"parts": self.repo.parts(), "operations": self.repo.operations(), "groups": self.repo.groups(),
                 "references": self.repo.references(), "identities": self.repo.identities()}
        if self.repo.part_ref is not None:
            for kind, key, rows in (("template_operation", "id", facts["operations"]),
                                    ("template_external_group", "group_id", facts["groups"])):
                facts["identities"].extend({"ref": row["ref"], "kind": kind, "entity_key": str(row[key]),
                    "alternate_key": row["ref_alternate_key"], "revision": row["revision"], "active": 1}
                    for row in rows if row["ref"] is not None)
        try:
            workflow = workflow_snapshot(self.conn, tables={**facts["references"], "Parts": facts["parts"],
                "PartOperations": facts["operations"], "ExternalGroups": facts["groups"],
                "WorkbenchEntityRefs": facts["identities"]})
        except RuntimeError as exc:
            raise WorkbenchCommandRejected("storage_failure", "工艺确认记录或它的编号不完整，请联系维护人员核对资料。", 500) from exc
        return dict(facts, workflow=workflow)

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            previous = self._facts
            previous_identities = self._identities_by_ref
            previous_table = self._table
            previous_details = self._details
            self._facts = self.facts()
            self._identities_by_ref = {row["ref"]: row for row in self._facts["identities"]}
            self._table = None
            self._details = {}
            try:
                yield content_text(self._facts)
            finally:
                self._facts = previous
                self._identities_by_ref = previous_identities
                self._table = previous_table
                self._details = previous_details

    def table(self):
        from .table import ProcessTable

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
        if self._facts is None:
            identity = self.identities.get(ref)
        else:
            assert self._identities_by_ref is not None
            row = self._identities_by_ref.get(ref)
            identity = WorkbenchEntityIdentity(row["ref"], row["kind"], row["entity_key"], row["revision"], bool(row["active"])) if row else None
        if identity is None or identity.kind != "part" or not identity.active:
            raise WorkbenchCommandRejected("entity_not_found", "这个零件已经不在了。请刷新列表后重新选择。", 404)
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
        if ref in self._details:
            return self._details[ref]
        return self.resolved_detail(self.resolve(ref))

    def resolved_detail(self, identity):
        facts = self.facts()
        row = next((row for row in facts["parts"] if row["ref"] == identity.ref), None)
        if row is None:
            raise WorkbenchCommandRejected("storage_failure", "零件编号和实际模板对不上。请刷新重试；仍不行请联系维护人员。", 500)
        operations = [row for row in facts["operations"] if row["part_no"] == identity.entity_key]
        workflow = facts["workflow"][identity.entity_key]
        part_groups = [row for row in facts["groups"] if row["part_no"] == identity.entity_key]
        return self._project_detail(identity, row, operations, part_groups, workflow, facts)

    def _project_detail(self, identity, row, operations, part_groups, workflow, facts):
        entity = project_part(row, operations, workflow["workflow"])
        references = facts["references"]
        related_group_ids = {group["group_id"] for group in part_groups} | {
            op["ext_group_id"] for op in operations if op["ext_group_id"] is not None
        }
        related_groups = (
            [group for group in facts["groups"] if group["group_id"] in related_group_ids]
            if related_group_ids
            else []
        )
        members = defaultdict(list)
        if related_group_ids:
            for operation in facts["operations"]:
                if operation["status"] == "active" and operation["ext_group_id"] in related_group_ids:
                    members[operation["ext_group_id"]].append(operation)
        related_operations = [op for group_id in related_group_ids for op in members[group_id]]
        source_facts = TemplateSourceFacts(related_operations, related_groups, references["Suppliers"],
                                          references["WorkbenchSupplierOpTypes"], references["WorkbenchSupplierProfiles"])
        groups = {group["group_id"]: project_group(group, members[group["group_id"]]) for group in part_groups}
        missing = {key: {"state": "unconfirmed", "confirmed_at": None, "confirmed_by": None} for key in ("source", "hours")}
        entity.update({"operations": [project_operation(row, workflow["operations"].get(row["ref"], missing), source_facts,
                                                       groups.get(row["ext_group_id"])) for row in operations],
                       "external_groups": list(groups.values()),
                       "capabilities": capabilities()})
        if self._facts is not None:
            self._details[identity.ref] = entity
        return entity

    def route_difference(self, ref, preview, entity):
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
                                          "message": "现有模板里有不合法的工序号。请到基础资料核对工序号。"})
        result["changes"] = {key: [public_sequence(seq) for seq in values] for key, values in result["changes"].items()}
        return result

    def prepare_route(self, ref, body):
        """Parse and prepare the current route once, then project its review."""
        from .part_actions_facts import checked_process_facts
        from .route_apply import affected_group_rows
        from .route_preview import ProcessRoutePreviewService

        facts = self.facts()
        checked = checked_process_facts(self.resolve(ref), facts)
        identity, part, operations, groups, _ = checked
        route_facts = ProcessRouteFacts(facts)
        parser = ProcessRoutePreviewService(self.conn, facts=route_facts)
        with parser.reference_snapshot():
            preview = parser.preview(body)
        # Invalid routes are still useful review results; preparation must not
        # reject them before the complete diagnostics reach the page.
        changed = changed_route_sequences({row["seq"]: row for row in operations}, preview["operations"])
        preview = preview_existing_route(preview, operations, route_choice_context(operations, route_facts),
                                         changed=changed)
        affected = []
        if preview["can_confirm_route"]:
            affected = affected_group_rows(groups, operations, changed)
        entity = self._project_detail(identity, part, operations, groups, facts["workflow"][identity.entity_key],
                                      facts)
        return self.route_difference(ref, preview, entity), checked, affected
