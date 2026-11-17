"""Explicit per-snapshot fact scope for process reads, exports and route previews."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.services.process.workflow_state import project_part_workflow
from core.services.workbench.facts.source_revisions import (
    PROCESS_SHARED_DICTIONARY_KEYS,
    PROCESS_SOURCE_KEYS,
    read_source_revisions,
)
from core.shared.refs import is_ref
from core.shared.strict_parse import wire_int

from .projection import (
    project_group,
    project_operation,
    project_part,
    project_part_counts,
)
from .route_choices import changed_route_sequences, preview_existing_route, route_choice_context
from .route_facts import ProcessRouteFacts
from .template_facts import ProcessFacts, ProcessRawFacts, ProcessWorkflowFacts, workflow_facts

if TYPE_CHECKING:
    from .queries import WorkbenchProcessQueryService


def check_part_ref(ref):
    """A part ref is 48 lowercase hex characters; anything else names no part."""
    if not is_ref(ref):
        raise WorkbenchCommandRejected("entity_not_found", "零件记录不存在，请返回列表重新选择。", 404)


def _route_changes(active, proposed, stored_sequences):
    # Compare stored sequences, not the projected ones: past 2**53-1 those are display text.
    invalid = [row for row in active if any(item["code"] == "sequence_invalid" for item in row["issues"])]
    invalid_refs = {row["ref"] for row in invalid}
    old = {stored_sequences[row["ref"]]: row for row in active if row["ref"] not in invalid_refs}
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
    merged = base_identities + [row for row in shared_identities if row["ref"] not in seen]
    merged.sort(key=lambda row: row["ref"])
    return merged


@dataclass
class ProcessFactScope:
    reader: WorkbenchProcessQueryService
    fingerprint_text: Optional[str] = None
    closure: Optional[ProcessRawFacts] = None
    raw_facts_cache: Optional[ProcessRawFacts] = None
    catalog: Optional[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = None
    full_facts: Optional[ProcessFacts] = None
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
    def _part_snapshot_facts(closure: ProcessRawFacts) -> Dict[str, Any]:
        return {
            "parts": closure.parts,
            "operations": closure.operations,
            "groups": closure.groups,
            "identities": [
                row for row in closure.identities
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

    def _part_closure(self) -> ProcessRawFacts:
        if self.closure is not None:
            return self.closure
        parts, operations, groups = self.repo.parts(), self.repo.operations(), self.repo.groups()
        identities = self._closure_identities(self.repo.part_identities(), operations, groups)
        self.closure = ProcessRawFacts(parts, operations, groups, identities)
        self.identities_by_ref = {row["ref"]: row for row in identities}
        return self.closure

    def load_catalog(self) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        if self.catalog is not None:
            return self.catalog
        self.catalog = (self.repo.catalog_references(), self.repo.shared_identities())
        return self.catalog

    def raw_facts(self) -> ProcessRawFacts:
        if self.full_facts is not None:
            return self.full_facts.raw
        if self.part_ref is not None:
            return self._part_closure()
        if self.raw_facts_cache is None:
            parts, operations, groups = self.repo.parts(), self.repo.operations(), self.repo.groups()
            part_identities = [
                {"ref": row["ref"], "kind": "part", "entity_key": row["part_no"],
                 "alternate_key": None, "revision": row["revision"], "active": 1}
                for row in parts if row["ref"] is not None
            ]
            identities = self._closure_identities(part_identities, operations, groups)
            self.raw_facts_cache = ProcessRawFacts(parts, operations, groups, identities)
            self.identities_by_ref = {row["ref"]: row for row in identities}
        return self.raw_facts_cache

    def facts(self) -> ProcessFacts:
        if self.full_facts is not None:
            return self.full_facts
        if self.part_ref is not None or self.raw_facts_cache is not None:
            base = self.raw_facts()
            references, shared_identities = self.load_catalog()
            raw = ProcessRawFacts(base.parts, base.operations, base.groups,
                                  _merge_identities(base.identities, shared_identities))
        else:
            raw = ProcessRawFacts(self.repo.parts(), self.repo.operations(), self.repo.groups(), self.repo.identities())
            references = self.repo.catalog_references()
        self.full_facts = ProcessFacts(raw, references, workflow_facts(raw, references))
        self.identities_by_ref = {row["ref"]: row for row in raw.identities}
        return self.full_facts

    def table(self):
        from .table import ProcessTable

        if self.table_cache is not None:
            return self.table_cache
        summaries = self.repo.part_table_summaries()
        self.table_cache = ProcessTable([
            project_part_counts(
                row,
                active_count=row["active_count"],
                internal_count=row["internal_count"],
                external_count=row["external_count"],
                workflow=project_part_workflow(row, row["active_count"] > 0),
            )
            for row in summaries
        ])
        return self.table_cache

    def resolve(self, ref):
        check_part_ref(ref)
        return self.identity_of(ref)

    def identity_of(self, ref):
        if self.identities_by_ref is not None and (self.part_ref is None or self.part_ref == ref):
            row = self.identities_by_ref.get(ref)
            identity = WorkbenchEntityIdentity.from_row(row) if row else None
        else:
            identity = self.reader.identities.get(ref)
        if identity is None or identity.kind != "part" or not identity.active:
            raise WorkbenchCommandRejected("entity_not_found", "这个零件已经不在了。请刷新列表后重新选择。", 404)
        return identity

    def page(self, query):
        if query.column_filters:
            return {**self.table().page(query), "create_context": None}
        counts, rows = self.repo.page_parts(query)
        total = counts["total"]
        entities = [
            project_part_counts(
                row,
                active_count=row["active_count"],
                internal_count=row["internal_count"],
                external_count=row["external_count"],
                workflow=project_part_workflow(row, row["active_count"] > 0),
            )
            for row in rows
        ]
        return {
            "entities": entities,
            "page": {
                "number": query.number,
                "size": query.size,
                "total": total,
                "pages": max(1, (total + query.size - 1) // query.size),
                "sort": query.ordering(),
            },
            "metrics": {"scope": "filtered", "counts": counts},
            "create_context": None,
        }

    def detail(self, ref):
        if ref in self.details:
            return self.details[ref]
        return self.resolved_detail(self.resolve(ref))

    def resolved_detail(self, identity):
        if identity.ref in self.details:
            return self.details[identity.ref]
        if self.part_ref is not None and self.full_facts is None:
            rows = self._part_closure()
            workflow = workflow_facts(rows, self.repo.supplier_references())
        else:
            facts = self.facts()
            rows, workflow = facts.raw, facts.workflow
        row = next((item for item in rows.parts if item["ref"] == identity.ref), None)
        if row is None:
            raise WorkbenchCommandRejected("storage_failure", "零件编号和实际模板对不上。请刷新重试；仍不行请联系维护人员。", 500)
        operations = [item for item in rows.operations if item["part_no"] == identity.entity_key]
        part_groups = [item for item in rows.groups if item["part_no"] == identity.entity_key]
        return self._project_detail(identity, row, operations, part_groups, workflow, rows.operations)

    def _project_detail(self, identity, row, operations, part_groups, workflow: ProcessWorkflowFacts, all_operations):
        part = workflow.parts[identity.entity_key]
        entity = project_part(row, operations, part.workflow)
        part_group_ids = {group["group_id"] for group in part_groups}
        members = defaultdict(list)
        if part_group_ids:
            for operation in all_operations:
                if operation["status"] == "active" and operation["ext_group_id"] in part_group_ids:
                    members[operation["ext_group_id"]].append(operation)
        groups = {group["group_id"]: project_group(group, members[group["group_id"]]) for group in part_groups}
        entity.update({
            "operations": [
                project_operation(
                    item,
                    part.confirmations[item["id"]],
                    workflow.source_facts,
                    groups.get(item["ext_group_id"]),
                )
                for item in operations
            ],
            "external_groups": list(groups.values()),
        })
        self.details[identity.ref] = entity
        return entity

    def route_difference(self, ref, preview, entity, operations):
        active = [row for row in entity["operations"] if row["status"] == "active"]
        stored_sequences = {row["ref"]: row["seq"] for row in operations}
        changes, invalid = _route_changes(active, preview["operations"], stored_sequences)
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
        result["operations"] = [{**row, "sequence": wire_int(row["sequence"])} for row in preview["operations"]]
        result["diagnostics"] = [
            {**row, **({"sequence": wire_int(row["sequence"])} if "sequence" in row else {})}
            for row in preview["diagnostics"]
        ]
        if invalid:
            result["can_confirm_route"] = False
            result["diagnostics"].append({
                "code": "legacy_sequence_invalid",
                "severity": "error",
                "message": "现有模板里有不合法的工序号。请到基础资料核对工序号。",
            })
        result["changes"] = {key: [wire_int(seq) for seq in values] for key, values in result["changes"].items()}
        return result

    def prepare_route(self, identity, body):
        from .part_actions_facts import checked_process_facts
        from .route_apply import affected_group_rows
        from .route_preview import ProcessRoutePreviewService

        facts = self.facts()
        checked = checked_process_facts(identity, facts)
        _, part, operations, groups, _ = checked
        route_facts = ProcessRouteFacts(facts.raw, references=facts.references)
        parser = ProcessRoutePreviewService(facts=route_facts)
        preview = parser.preview(body)
        changed = changed_route_sequences({row["seq"]: row for row in operations}, preview["operations"])
        preview = preview_existing_route(preview, operations, route_choice_context(operations, route_facts), changed=changed)
        affected = affected_group_rows(groups, operations, changed) if preview["can_confirm_route"] else []
        entity = self._project_detail(identity, part, operations, groups, facts.workflow, facts.raw.operations)
        return self.route_difference(identity.ref, preview, entity, operations), checked, affected
