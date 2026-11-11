"""Indexes shared by route parsing, retained choices and file application."""

from collections import defaultdict

from core.models.workbench_identity import WorkbenchEntityIdentity


class ProcessRouteFacts:
    def __init__(self, facts):
        self.references = None
        self.type_names = None
        self.supplier_names = None
        self.identities_by_kind = None
        self.parts = {row["part_no"]: row for row in facts["parts"]}
        self.identities = {
            row["ref"]: WorkbenchEntityIdentity(
                row["ref"], row["kind"], row["entity_key"], row["revision"], bool(row["active"])
            )
            for row in facts["identities"]
        }
        self.operations = defaultdict(list)
        self.group_parts = defaultdict(set)
        self.group_members = defaultdict(list)
        for row in facts["operations"]:
            self.operations[row["part_no"]].append(row)
            if row["ext_group_id"] is not None:
                self.group_parts[row["ext_group_id"]].add(row["part_no"])
                if row["status"] == "active":
                    self.group_members[row["ext_group_id"]].append(row)
        self.groups = defaultdict(list)
        self.groups_by_id = {}
        for row in facts["groups"]:
            self.groups[row["part_no"]].append(row)
            self.groups_by_id[row["group_id"]] = row
        if "references" in facts:
            self.attach_references(facts["references"])

    def attach_references(self, references, shared_identities=()):
        for row in shared_identities:
            ref = row["ref"]
            if ref not in self.identities:
                self.identities[ref] = WorkbenchEntityIdentity(
                    ref, row["kind"], row["entity_key"], row["revision"], bool(row["active"])
                )
        self.references = references
        self.type_names = {row["op_type_id"]: row["name"] for row in references["OpTypes"]}
        self.supplier_names = {row["supplier_id"]: row["name"] for row in references["Suppliers"]}
        by_kind = {"op_type": {}, "supplier": {}}
        for identity in sorted(self.identities.values(), key=lambda item: item.ref):
            if identity.active and identity.kind in by_kind:
                by_kind[identity.kind][identity.entity_key] = identity
        self.identities_by_kind = by_kind
