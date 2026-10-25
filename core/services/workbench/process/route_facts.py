"""Indexes shared by route parsing, retained choices and file application."""

from collections import defaultdict

from core.models.workbench_identity import WorkbenchEntityIdentity


class ProcessRouteFacts:
    def __init__(self, facts):
        self.references = facts["references"]
        self.type_names = {row["op_type_id"]: row["name"] for row in self.references["OpTypes"]}
        self.supplier_names = {row["supplier_id"]: row["name"] for row in self.references["Suppliers"]}
        self.parts = {row["part_no"]: row for row in facts["parts"]}
        self.identities = {}
        self.identities_by_kind = {"op_type": {}, "supplier": {}}
        for row in facts["identities"]:
            identity = WorkbenchEntityIdentity(row["ref"], row["kind"], row["entity_key"],
                                               row["revision"], bool(row["active"]))
            self.identities[identity.ref] = identity
            if identity.active and identity.kind in self.identities_by_kind:
                self.identities_by_kind[identity.kind][identity.entity_key] = identity
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
