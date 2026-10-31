"""Snapshot-bound process reads and route differences, without template writes."""

from collections import defaultdict
from contextlib import contextmanager
from typing import Any, Dict

from core.infrastructure.transaction import TransactionManager
from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.services.process.workflow_state import (
    active_entity_refs,
    build_template_source_facts,
    workflow_snapshot,
)
from core.services.workbench.facts.source_revisions import (
    PROCESS_SHARED_DICTIONARY_KEYS,
    PROCESS_SOURCE_KEYS,
    read_source_revisions,
)
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository

from .projection import project_group, project_operation, project_part, public_sequence
from .route_choices import changed_route_sequences, preview_existing_route, route_choice_context
from .route_facts import ProcessRouteFacts


def _check_part_ref(ref):
    """A part ref is 48 lowercase hex characters; anything else names no part."""
    if not isinstance(ref, str) or len(ref) != 48 or any(c not in "0123456789abcdef" for c in ref):
        raise WorkbenchCommandRejected("entity_not_found", "零件记录不存在，请返回列表重新选择。", 404)


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


class _RawProcessFacts(dict):
    """Raw process tables with on-demand catalog references for route imports."""

    def __init__(self, repo, base, base_identities):
        super().__init__(base, base_identities=base_identities)
        self._repo = repo
        self._catalog_loaded = False

    def _ensure_catalog(self):
        if self._catalog_loaded:
            return
        self._catalog_loaded = True
        super().__setitem__("references", self._repo.catalog_references())
        base_identities = self["base_identities"]
        seen = {row["ref"] for row in base_identities}
        identities = list(base_identities) + [
            row for row in self._repo.shared_identities() if row["ref"] not in seen
        ]
        identities.sort(key=lambda row: row["ref"])
        super().__setitem__("identities", identities)

    def __getitem__(self, key):
        if key in ("references", "identities") and not self._catalog_loaded:
            self._ensure_catalog()
        return super().__getitem__(key)


class WorkbenchProcessQueryService:
    def __init__(self, conn, logger=None, *, part_ref=None):
        # An empty string is a supplied ref too; only None means the whole collection.
        if part_ref is not None:
            _check_part_ref(part_ref)
        self.conn = conn
        self.repo = WorkbenchProcessQueryRepository(conn, logger=logger, part_ref=part_ref)
        self.identities = WorkbenchIdentityRepository(conn, logger=logger)
        self._facts = None
        self._raw_facts = None
        self._closure = None
        self._identities_by_ref = None
        self._table = None
        self._details = {}
        self._in_snapshot = False

    @staticmethod
    def _closure_identities(base_identities, operations, groups):
        identities = list(base_identities)
        for kind, key, rows in (
            ("template_operation", "id", operations),
            ("template_external_group", "group_id", groups),
        ):
            identities.extend(
                {
                    "ref": row["ref"],
                    "kind": kind,
                    "entity_key": str(row[key]),
                    "alternate_key": row.get("ref_alternate_key"),
                    "revision": row["revision"],
                    "active": 1,
                }
                for row in rows
                if row["ref"] is not None
            )
        return identities

    def _part_closure(self):
        if self._closure is not None:
            return self._closure
        parts = self.repo.parts()
        operations = self.repo.operations()
        groups = self.repo.groups()
        references = self.repo.workflow_references()
        identities = self._closure_identities(self.repo.part_identities(), operations, groups)
        closure = {
            "parts": parts,
            "operations": operations,
            "groups": groups,
            "references": references,
            "identities": identities,
        }
        if self._in_snapshot:
            self._closure = closure
            self._identities_by_ref = {row["ref"]: row for row in identities}
        return closure

    def raw_facts(self) -> Dict[str, Any]:
        if self._facts is not None:
            return self._facts
        if self._raw_facts is not None:
            return self._raw_facts
        if self.repo.part_ref is not None:
            closure = self._part_closure()
            parts = closure["parts"]
            operations = closure["operations"]
            groups = closure["groups"]
            base_identities = closure["identities"]
        else:
            parts = self.repo.parts()
            operations = self.repo.operations()
            groups = self.repo.groups()
            part_identities = [
                {
                    "ref": row["ref"],
                    "kind": "part",
                    "entity_key": row["part_no"],
                    "alternate_key": None,
                    "revision": row["revision"],
                    "active": 1,
                }
                for row in parts
                if row["ref"] is not None
            ]
            base_identities = self._closure_identities(part_identities, operations, groups)
        raw = _RawProcessFacts(
            self.repo,
            {"parts": parts, "operations": operations, "groups": groups},
            base_identities,
        )
        if self._in_snapshot:
            self._raw_facts = raw
            if self._identities_by_ref is None:
                self._identities_by_ref = {row["ref"]: row for row in base_identities}
        return raw

    def _scoped_detail_facts(self, closure) -> Dict[str, Any]:
        operations = closure["operations"]
        groups = closure["groups"]
        supplier_ids = [
            row["supplier_id"]
            for rows in (operations, groups)
            for row in rows
            if row["supplier_id"] is not None
        ]
        supplier_refs = self.repo.supplier_references(supplier_ids)
        op_types = {}
        for row in operations:
            if row["op_type_exists"] is not None and row["op_type_exists"] not in op_types:
                op_types[row["op_type_exists"]] = {
                    "op_type_id": row["op_type_exists"],
                    "name": row["op_type_label"],
                    "category": row["op_type_category"],
                }
        identities = list(closure["identities"])
        seen_refs = {row["ref"] for row in identities}
        for row in operations:
            if row["op_type_exists"] is not None and row["op_type_ref"] is not None and row["op_type_ref"] not in seen_refs:
                seen_refs.add(row["op_type_ref"])
                identities.append(
                    {
                        "ref": row["op_type_ref"],
                        "kind": "op_type",
                        "entity_key": row["op_type_exists"],
                        "alternate_key": None,
                        "revision": 1,
                        "active": 1,
                    }
                )
        for rows in (operations, groups):
            for row in rows:
                if row["supplier_exists"] is not None and row["supplier_ref"] is not None and row["supplier_ref"] not in seen_refs:
                    seen_refs.add(row["supplier_ref"])
                    identities.append(
                        {
                            "ref": row["supplier_ref"],
                            "kind": "supplier",
                            "entity_key": row["supplier_exists"],
                            "alternate_key": None,
                            "revision": 1,
                            "active": 1,
                        }
                    )
        references = {
            **closure["references"],
            **supplier_refs,
            "OpTypes": list(op_types.values()),
        }
        tables = {
            **references,
            "Parts": closure["parts"],
            "PartOperations": operations,
            "ExternalGroups": groups,
            "WorkbenchEntityRefs": identities,
        }
        source_facts, workflow = self._workflow_facts(tables)
        return {
            "parts": closure["parts"],
            "operations": operations,
            "groups": groups,
            "references": references,
            "identities": identities,
            "source_facts": source_facts,
            "workflow": workflow,
        }

    def _workflow_facts(self, tables):
        active_refs = active_entity_refs(tables)
        source_facts = build_template_source_facts(tables, active_refs)
        try:
            workflow = workflow_snapshot(
                self.conn, tables=tables, source_facts=source_facts, active_refs=active_refs
            )
        except RuntimeError as exc:
            raise WorkbenchCommandRejected(
                "storage_failure", "工艺确认记录或它的编号不完整，请联系维护人员核对资料。", 500
            ) from exc
        return source_facts, workflow

    def facts(self) -> Dict[str, Any]:
        if self._facts is not None:
            return self._facts
        if self.repo.part_ref is not None:
            closure = self._part_closure()
            seen = {row["ref"] for row in closure["identities"]}
            identities = list(closure["identities"]) + [
                row for row in self.repo.shared_identities() if row["ref"] not in seen
            ]
            identities.sort(key=lambda row: row["ref"])
            facts = {
                "parts": closure["parts"],
                "operations": closure["operations"],
                "groups": closure["groups"],
                "references": {**self.repo.catalog_references(), **closure["references"]},
                "identities": identities,
            }
        else:
            raw = self._raw_facts
            parts = raw["parts"] if raw is not None else self.repo.parts()
            operations = raw["operations"] if raw is not None else self.repo.operations()
            groups = raw["groups"] if raw is not None else self.repo.groups()
            facts = {"parts": parts, "operations": operations, "groups": groups,
                     "references": self.repo.references(), "identities": self.repo.identities()}
        tables = {**facts["references"], "Parts": facts["parts"],
                  "PartOperations": facts["operations"], "ExternalGroups": facts["groups"],
                  "WorkbenchEntityRefs": facts["identities"]}
        source_facts, workflow = self._workflow_facts(tables)
        result: Dict[str, Any] = dict(facts, source_facts=source_facts, workflow=workflow)
        if self._in_snapshot:
            self._facts = result
            self._identities_by_ref = {row["ref"]: row for row in result["identities"]}
        return result

    @staticmethod
    def _part_snapshot_facts(closure):
        references = closure["references"]
        return {
            "parts": closure["parts"],
            "operations": closure["operations"],
            "groups": closure["groups"],
            "references": {
                "WorkbenchProcessWorkflow": references["WorkbenchProcessWorkflow"],
                "WorkbenchProcessOperationConfirmations": references["WorkbenchProcessOperationConfirmations"],
            },
            "identities": [
                row
                for row in closure["identities"]
                if row["kind"] in ("part", "template_operation", "template_external_group")
            ],
        }

    @contextmanager
    def read_snapshot(self):
        with TransactionManager(self.conn).transaction():
            previous = self._facts
            previous_raw = self._raw_facts
            previous_closure = self._closure
            previous_identities = self._identities_by_ref
            previous_table = self._table
            previous_details = self._details
            previous_in_snapshot = self._in_snapshot
            self._facts = None
            self._raw_facts = None
            self._closure = None
            self._identities_by_ref = None
            self._table = None
            self._details = {}
            self._in_snapshot = True
            try:
                if self.repo.part_ref is None:
                    yield content_text(read_source_revisions(self.conn, PROCESS_SOURCE_KEYS))
                else:
                    closure = self._part_closure()
                    yield content_text(
                        {
                            "facts": self._part_snapshot_facts(closure),
                            "shared_revisions": read_source_revisions(self.conn, PROCESS_SHARED_DICTIONARY_KEYS),
                        }
                    )
            finally:
                self._facts = previous
                self._raw_facts = previous_raw
                self._closure = previous_closure
                self._identities_by_ref = previous_identities
                self._table = previous_table
                self._details = previous_details
                self._in_snapshot = previous_in_snapshot

    def raw_table(self):
        from .table import ProcessTable

        if self._table is not None:
            return self._table
        raw = self.raw_facts()
        grouped = defaultdict(list)
        for row in raw["operations"]:
            grouped[row["part_no"]].append(row)
        placeholder = {"origin": "legacy", "stage": "route", "ready": False}
        entities = [project_part(row, grouped[row["part_no"]], placeholder) for row in raw["parts"]]
        return ProcessTable(entities)

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
        if self.repo.part_ref is None or ref != self.repo.part_ref:
            _check_part_ref(ref)
        if self._identities_by_ref is not None and (self.repo.part_ref is None or self.repo.part_ref == ref):
            row = self._identities_by_ref.get(ref)
            identity = WorkbenchEntityIdentity(row["ref"], row["kind"], row["entity_key"], row["revision"], bool(row["active"])) if row else None
        else:
            identity = self.identities.get(ref)
        if identity is None or identity.kind != "part" or not identity.active:
            raise WorkbenchCommandRejected("entity_not_found", "这个零件已经不在了。请刷新列表后重新选择。", 404)
        return identity

    def page(self, query):
        return {**self.table().page(query), "create_context": None}

    def detail(self, ref):
        if ref in self._details:
            return self._details[ref]
        return self.resolved_detail(self.resolve(ref))

    def resolved_detail(self, identity):
        if identity.ref in self._details:
            return self._details[identity.ref]
        if self.repo.part_ref is not None and self._facts is None:
            closure = self._part_closure()
            row = next((row for row in closure["parts"] if row["ref"] == identity.ref), None)
            if row is None:
                raise WorkbenchCommandRejected("storage_failure", "零件编号和实际模板对不上。请刷新重试；仍不行请联系维护人员。", 500)
            facts = self._scoped_detail_facts(closure)
        else:
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
        part_group_ids = {group["group_id"] for group in part_groups}
        members = defaultdict(list)
        if part_group_ids:
            for operation in facts["operations"]:
                if operation["status"] == "active" and operation["ext_group_id"] in part_group_ids:
                    members[operation["ext_group_id"]].append(operation)
        source_facts = facts["source_facts"]
        groups = {group["group_id"]: project_group(group, members[group["group_id"]]) for group in part_groups}
        missing = {key: {"state": "unconfirmed", "confirmed_at": None, "confirmed_by": None} for key in ("source", "hours")}
        entity.update({"operations": [project_operation(row, workflow["operations"].get(row["ref"], missing), source_facts,
                                                       groups.get(row["ext_group_id"])) for row in operations],
                       "external_groups": list(groups.values())})
        if self._facts is not None or self._in_snapshot:
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
