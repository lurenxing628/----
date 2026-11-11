"""Explicit per-snapshot fact scope for process reads, exports and route previews."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity, is_entity_ref
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

from .projection import project_group, project_operation, project_part, public_sequence
from .route_choices import changed_route_sequences, preview_existing_route, route_choice_context
from .route_facts import ProcessRouteFacts

if TYPE_CHECKING:
    from .queries import WorkbenchProcessQueryService


def check_part_ref(ref):
    """A part ref is 48 lowercase hex characters; anything else names no part."""
    if not is_entity_ref(ref):
        raise WorkbenchCommandRejected("entity_not_found", "零件记录不存在，请返回列表重新选择。", 404)


def _route_changes(active, proposed):
    invalid = [row for row in active if any(item["code"] == "sequence_invalid" for item in row["issues"])]
    invalid_refs = {row["ref"] for row in invalid}
    old = {int(row["sequence"]): row for row in active if row["ref"] not in invalid_refs}
    new = {row["sequence"]: row for row in proposed}
    common = old.keys() & new.keys()
    retained = sorted(
        seq for seq in common
        if old[seq]["label"] == new[seq]["op_type_name"] and old[seq]["op_type_ref"] == new[seq]["op_type_ref"]
    )
    return ({
        "added": sorted(new.keys() - old.keys()),
        "removed": sorted(old.keys() - new.keys()),
        "retained": retained,
        "same_sequence_changed": sorted(common - set(retained)),
    }, invalid)


def _merge_identities(base_identities: List[Dict[str, Any]], shared_identities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = {row["ref"] for row in base_identities}
    merged = list(base_identities) + [row for row in shared_identities if row["ref"] not in seen]
    merged.sort(key=lambda row: row["ref"])
    return merged


@dataclass
class ProcessFactScope:
    reader: WorkbenchProcessQueryService
    fingerprint_text: Optional[str] = None
    closure: Optional[Dict[str, Any]] = None
    raw_facts_cache: Optional[Dict[str, Any]] = None
    catalog: Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = None
    full_facts: Optional[Dict[str, Any]] = None
    identities_by_ref: Optional[Dict[str, Dict[str, Any]]] = None
    table_cache: Any = None
    details: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @property
    def conn(self):
        return self.reader.conn

    @property
    def repo(self):
        return self.reader.repo

    @property
    def part_ref(self) -> Optional[str]:
        return self.repo.part_ref

    @staticmethod
    def _closure_identities(base_identities, operations, groups) -> List[Dict[str, Any]]:
        identities = list(base_identities)
        for kind, key, rows in (("template_operation", "id", operations), ("template_external_group", "group_id", groups)):
            identities.extend(
                {"ref": row["ref"], "kind": kind, "entity_key": str(row[key]),
                 "alternate_key": row.get("ref_alternate_key"), "revision": row["revision"], "active": 1}
                for row in rows if row["ref"] is not None
            )
        return identities

    @staticmethod
    def _part_snapshot_facts(closure) -> Dict[str, Any]:
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
                row for row in closure["identities"]
                if row["kind"] in ("part", "template_operation", "template_external_group")
            ],
        }

    def state_fingerprint(self) -> str:
        if self.fingerprint_text is not None:
            return self.fingerprint_text
        if self.part_ref is None:
            self.fingerprint_text = content_text(read_source_revisions(self.conn, PROCESS_SOURCE_KEYS))
        else:
            closure = self._part_closure()
            self.fingerprint_text = content_text({
                "facts": self._part_snapshot_facts(closure),
                "shared_revisions": read_source_revisions(self.conn, PROCESS_SHARED_DICTIONARY_KEYS),
            })
        return self.fingerprint_text

    def _part_closure(self) -> Dict[str, Any]:
        if self.closure is not None:
            return self.closure
        parts, operations, groups = self.repo.parts(), self.repo.operations(), self.repo.groups()
        references = self.repo.workflow_references()
        identities = self._closure_identities(self.repo.part_identities(), operations, groups)
        self.closure = {"parts": parts, "operations": operations, "groups": groups,
                        "references": references, "identities": identities}
        self.identities_by_ref = {row["ref"]: row for row in identities}
        return self.closure

    def load_catalog(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        if self.catalog is not None:
            return self.catalog
        self.catalog = (self.repo.catalog_references(), self.repo.shared_identities())
        return self.catalog

    def raw_facts(self) -> Dict[str, Any]:
        if self.full_facts is not None:
            return self.full_facts
        if self.raw_facts_cache is not None:
            return self.raw_facts_cache
        if self.part_ref is not None:
            closure = self._part_closure()
            parts, operations, groups, base_identities = (
                closure["parts"], closure["operations"], closure["groups"], closure["identities"]
            )
        else:
            parts, operations, groups = self.repo.parts(), self.repo.operations(), self.repo.groups()
            part_identities = [
                {"ref": row["ref"], "kind": "part", "entity_key": row["part_no"],
                 "alternate_key": None, "revision": row["revision"], "active": 1}
                for row in parts if row["ref"] is not None
            ]
            base_identities = self._closure_identities(part_identities, operations, groups)
        self.raw_facts_cache = {"parts": parts, "operations": operations, "groups": groups, "identities": base_identities}
        if self.identities_by_ref is None:
            self.identities_by_ref = {row["ref"]: row for row in base_identities}
        return self.raw_facts_cache

    def _workflow_facts(self, tables):
        active_refs = active_entity_refs(tables)
        source_facts = build_template_source_facts(tables, active_refs)
        try:
            workflow = workflow_snapshot(self.conn, tables=tables, source_facts=source_facts, active_refs=active_refs)
        except RuntimeError as exc:
            raise WorkbenchCommandRejected(
                "storage_failure", "工艺确认记录或它的编号不完整，请联系维护人员核对资料。", 500
            ) from exc
        return source_facts, workflow

    def _scoped_detail_facts(self, closure) -> Dict[str, Any]:
        operations, groups = closure["operations"], closure["groups"]
        supplier_refs = self.repo.supplier_references()
        op_types = {}
        for row in operations:
            if row["op_type_exists"] is not None and row["op_type_exists"] not in op_types:
                op_types[row["op_type_exists"]] = {
                    "op_type_id": row["op_type_exists"], "name": row["op_type_label"], "category": row["op_type_category"]
                }
        identities = list(closure["identities"])
        seen_refs = {row["ref"] for row in identities}
        for row in operations:
            if row["op_type_exists"] is not None and row["op_type_ref"] is not None and row["op_type_ref"] not in seen_refs:
                seen_refs.add(row["op_type_ref"])
                identities.append({"ref": row["op_type_ref"], "kind": "op_type", "entity_key": row["op_type_exists"],
                                   "alternate_key": None, "revision": 1, "active": 1})
        for rows in (operations, groups):
            for row in rows:
                if row["supplier_exists"] is not None and row["supplier_ref"] is not None and row["supplier_ref"] not in seen_refs:
                    seen_refs.add(row["supplier_ref"])
                    identities.append({"ref": row["supplier_ref"], "kind": "supplier", "entity_key": row["supplier_exists"],
                                       "alternate_key": None, "revision": 1, "active": 1})
        references = {**closure["references"], **supplier_refs, "OpTypes": list(op_types.values())}
        tables = {**references, "Parts": closure["parts"], "PartOperations": operations,
                  "ExternalGroups": groups, "WorkbenchEntityRefs": identities}
        source_facts, workflow = self._workflow_facts(tables)
        return {"parts": closure["parts"], "operations": operations, "groups": groups, "references": references,
                "identities": identities, "source_facts": source_facts, "workflow": workflow}

    def facts(self) -> Dict[str, Any]:
        if self.full_facts is not None:
            return self.full_facts
        if self.part_ref is not None:
            closure = self._part_closure()
            catalog_refs, shared_identities = self.load_catalog()
            facts = {
                "parts": closure["parts"], "operations": closure["operations"], "groups": closure["groups"],
                "references": {**catalog_refs, **closure["references"]},
                "identities": _merge_identities(closure["identities"], shared_identities),
            }
        elif self.raw_facts_cache is not None:
            raw = self.raw_facts_cache
            catalog_refs, shared_identities = self.load_catalog()
            facts = {
                "parts": raw["parts"], "operations": raw["operations"], "groups": raw["groups"],
                "references": {**catalog_refs, **self.repo.workflow_references()},
                "identities": _merge_identities(raw["identities"], shared_identities),
            }
        else:
            facts = {"parts": self.repo.parts(), "operations": self.repo.operations(), "groups": self.repo.groups(),
                     "references": self.repo.references(), "identities": self.repo.identities()}
        tables = {**facts["references"], "Parts": facts["parts"], "PartOperations": facts["operations"],
                  "ExternalGroups": facts["groups"], "WorkbenchEntityRefs": facts["identities"]}
        source_facts, workflow = self._workflow_facts(tables)
        self.full_facts = dict(facts, source_facts=source_facts, workflow=workflow)
        self.identities_by_ref = {row["ref"]: row for row in self.full_facts["identities"]}
        return self.full_facts

    def raw_table(self):
        from .table import ProcessTable

        raw = self.raw_facts()
        grouped = defaultdict(list)
        for row in raw["operations"]:
            grouped[row["part_no"]].append(row)
        placeholder = {"origin": "legacy", "stage": "route", "ready": False}
        return ProcessTable([project_part(row, grouped[row["part_no"]], placeholder) for row in raw["parts"]])

    def table(self):
        from .table import ProcessTable

        if self.table_cache is not None:
            return self.table_cache
        facts = self.facts()
        grouped = defaultdict(list)
        for row in facts["operations"]:
            grouped[row["part_no"]].append(row)
        self.table_cache = ProcessTable([
            project_part(row, grouped[row["part_no"]], facts["workflow"][row["part_no"]]["workflow"])
            for row in facts["parts"]
        ])
        return self.table_cache

    def resolve(self, ref):
        check_part_ref(ref)
        return self.identity_of(ref)

    def identity_of(self, ref):
        if self.identities_by_ref is not None and (self.part_ref is None or self.part_ref == ref):
            row = self.identities_by_ref.get(ref)
            identity = (
                WorkbenchEntityIdentity(row["ref"], row["kind"], row["entity_key"], row["revision"], bool(row["active"]))
                if row else None
            )
        else:
            identity = self.reader.identities.get(ref)
        if identity is None or identity.kind != "part" or not identity.active:
            raise WorkbenchCommandRejected("entity_not_found", "这个零件已经不在了。请刷新列表后重新选择。", 404)
        return identity

    def page(self, query):
        return {**self.table().page(query), "create_context": None}

    def detail(self, ref):
        if ref in self.details:
            return self.details[ref]
        return self.resolved_detail(self.resolve(ref))

    def resolved_detail(self, identity):
        if identity.ref in self.details:
            return self.details[identity.ref]
        if self.part_ref is not None and self.full_facts is None:
            closure = self._part_closure()
            row = next((item for item in closure["parts"] if item["ref"] == identity.ref), None)
            if row is None:
                raise WorkbenchCommandRejected("storage_failure", "零件编号和实际模板对不上。请刷新重试；仍不行请联系维护人员。", 500)
            facts = self._scoped_detail_facts(closure)
        else:
            facts = self.facts()
            row = next((item for item in facts["parts"] if item["ref"] == identity.ref), None)
            if row is None:
                raise WorkbenchCommandRejected("storage_failure", "零件编号和实际模板对不上。请刷新重试；仍不行请联系维护人员。", 500)
        operations = [item for item in facts["operations"] if item["part_no"] == identity.entity_key]
        workflow = facts["workflow"][identity.entity_key]
        part_groups = [item for item in facts["groups"] if item["part_no"] == identity.entity_key]
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
        entity.update({
            "operations": [
                project_operation(item, workflow["operations"].get(item["ref"], missing), source_facts, groups.get(item["ext_group_id"]))
                for item in operations
            ],
            "external_groups": list(groups.values()),
        })
        self.details[identity.ref] = entity
        return entity

    def route_difference(self, ref, preview, entity):
        active = [row for row in entity["operations"] if row["status"] == "active"]
        changes, invalid = _route_changes(active, preview["operations"])
        result = {
            **preview,
            "part_ref": ref,
            "baseline": {
                "operation_count": len(active),
                "external_group_count": len(entity["external_groups"]),
                "has_published_template": bool(active),
            },
            "changes": changes,
            "write_context": None,
        }
        result["operations"] = [{**row, "sequence": public_sequence(row["sequence"])} for row in preview["operations"]]
        result["diagnostics"] = [
            {**row, **({"sequence": public_sequence(row["sequence"])} if "sequence" in row else {})}
            for row in preview["diagnostics"]
        ]
        if invalid:
            result["can_confirm_route"] = False
            result["diagnostics"].append({
                "code": "legacy_sequence_invalid",
                "severity": "error",
                "message": "现有模板里有不合法的工序号。请到基础资料核对工序号。",
            })
        result["changes"] = {key: [public_sequence(seq) for seq in values] for key, values in result["changes"].items()}
        return result

    def prepare_route(self, identity, body):
        from .part_actions_facts import checked_process_facts
        from .route_apply import affected_group_rows
        from .route_preview import ProcessRoutePreviewService

        facts = self.facts()
        checked = checked_process_facts(identity, facts)
        _, part, operations, groups, _ = checked
        route_facts = ProcessRouteFacts(facts)
        parser = ProcessRoutePreviewService(facts=route_facts)
        preview = parser.preview(body)
        changed = changed_route_sequences({row["seq"]: row for row in operations}, preview["operations"])
        preview = preview_existing_route(preview, operations, route_choice_context(operations, route_facts), changed=changed)
        affected = affected_group_rows(groups, operations, changed) if preview["can_confirm_route"] else []
        entity = self._project_detail(identity, part, operations, groups, facts["workflow"][identity.entity_key], facts)
        return self.route_difference(identity.ref, preview, entity), checked, affected
