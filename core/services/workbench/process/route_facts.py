"""Indexes shared by route parsing, retained choices and file application."""

from collections import defaultdict

from core.models.workbench_identity import WorkbenchEntityIdentity


class ProcessRouteFacts:
    def __init__(self, facts):
        self._facts = facts
        self._catalog_loaded = False
        self._references = None
        self._type_names = None
        self._supplier_names = None
        self._identities_by_kind = None
        self.parts = {row["part_no"]: row for row in facts["parts"]}
        self.identities = {
            row["ref"]: WorkbenchEntityIdentity(
                row["ref"], row["kind"], row["entity_key"], row["revision"], bool(row["active"])
            )
            for row in (facts["base_identities"] if "base_identities" in facts else facts["identities"])
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

    def _ensure_catalog(self):
        if self._catalog_loaded:
            return
        self._catalog_loaded = True
        references = self._facts["references"]
        self._references = references
        self._type_names = {row["op_type_id"]: row["name"] for row in references["OpTypes"]}
        self._supplier_names = {row["supplier_id"]: row["name"] for row in references["Suppliers"]}
        by_kind = {"op_type": {}, "supplier": {}}
        for row in self._facts["identities"]:
            ref = row["ref"]
            if ref in self.identities:
                identity = self.identities[ref]
            else:
                identity = WorkbenchEntityIdentity(
                    ref, row["kind"], row["entity_key"], row["revision"], bool(row["active"])
                )
                self.identities[ref] = identity
            if identity.active and identity.kind in by_kind:
                by_kind[identity.kind][identity.entity_key] = identity
        self._identities_by_kind = by_kind

    @property
    def references(self):
        self._ensure_catalog()
        return self._references

    @property
    def type_names(self):
        self._ensure_catalog()
        return self._type_names

    @property
    def supplier_names(self):
        self._ensure_catalog()
        return self._supplier_names

    @property
    def identities_by_kind(self):
        self._ensure_catalog()
        return self._identities_by_kind
