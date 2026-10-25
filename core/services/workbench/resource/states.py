"""Shared private resource facts and identity checks, without public token handling."""

from dataclasses import asdict, dataclass
from typing import Optional

from core.models.resource_capabilities import supports_source
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity

from .table_states import resource_table_states


@dataclass
class ResourceChange:
    action: str
    business_code: str
    identity: Optional[WorkbenchEntityIdentity]
    fields: dict
    related: dict


class ResourceChangePreparation:
    """One operation's captured resource rows, identities and complete current states."""

    def __init__(self, facts, *, name_reader=None, names=None):
        self.facts = facts
        self._states = {}
        self._names = names or {}
        self._name_reader = name_reader
        self._references = {}

    def identity(self, kind, ref):
        identity = self.find_by_ref(kind, ref)
        if identity is None:
            raise WorkbenchCommandRejected("entity_not_found", "这条资源已经删除了，请刷新后重新选择。", 404)
        return identity

    def find_by_ref(self, kind, ref):
        return self.facts.find_by_ref(kind, ref)

    def identity_by_code(self, kind, code):
        return self.facts.identity(kind, code)

    def current(self, kind, identity):
        current = self.identity(kind, identity.ref)
        if current != identity:
            raise WorkbenchCommandRejected("stale_write", "资源或相关资料已经变了，请刷新后重新核对。")
        return current

    def find_identity(self, kind, code):
        if kind not in self.facts.identity_kinds:
            self.facts.load_identity_kinds([kind])
        return self.identity_by_code(kind, code) if (kind, code) in self.facts.identities else None

    def raw(self, kind, code):
        from .metrics import RESOURCE_KEYS

        return self.facts.raw_lookup(kind, RESOURCE_KEYS[kind]).get(code)

    def states(self, kind, codes):
        current = self._states.setdefault(kind, {})
        pending = sorted(set(codes) - set(current))
        for offset in range(0, len(pending), 200):
            chunk = pending[offset:offset + 200]
            references = self._references.get(kind)
            if kind == "op_type":
                if references is None:
                    dependencies = self.facts.metrics.repo.op_type_dependencies(chunk)
                else:
                    from .table_facts import OP_TYPE_DEPENDENCIES

                    dependencies = {code: {name: len(references[code][source])
                        for name, source in OP_TYPE_DEPENDENCIES.items()} for code in chunk}
                profiles = self.facts.raw_lookup("policies", "op_type_id")
                current.update({code: {"identity": asdict(self.identity_by_code(kind, code)),
                    "record": self.facts.raw_record(kind, code), "profile": profiles.get(code),
                    "dependencies": dependencies[code]} for code in chunk})
            else:
                counts, supplier_refs = None, None
                if references is not None:
                    if kind == "supplier":
                        supplier_refs = {name: {code: references[code][table] for code in chunk}
                            for name, table in (("part_operations", "PartOperations.supplier_id"),
                                                ("batch_operations", "BatchOperations.supplier_id"),
                                                ("external_groups", "ExternalGroups.supplier_id"))}
                    else:
                        aliases = {"BatchOperations": "batch_operations", "Schedule": "schedule"}
                        counts = {code: {aliases.get(table.split(".")[0], table): len(rows)
                            for table, rows in references[code].items()} for code in chunk}
                current.update(resource_table_states(self.facts, kind, chunk, dependencies=counts,
                                                     supplier_references=supplier_refs))
        return {code: current[code] for code in codes}

    def capture_references(self, repo, kind, codes):
        self._references[kind] = repo.references_many(
            kind, sorted(set(codes)), report_revisions=self.facts.report_revisions
        )
        return self._references[kind]

    def state(self, kind, code):
        return self.states(kind, [code])[code]

    def selected_record(self, kind, identity, *, category=None):
        raw = self.facts.raw_record(kind, identity.entity_key)
        if raw.get("status", "active") != "active":
            raise WorkbenchCommandRejected("constraint_conflict", "选中的关联资源已经停用，没有保存。请重新选择一个在用的。")
        if category is not None and not supports_source(raw.get("category"), category):
            raise WorkbenchCommandRejected("constraint_conflict", "选中工种的自制或外协归属和当前资源不匹配，没有保存。请换一个工种。")
        if identity.entity_key != identity.entity_key.strip():
            raise WorkbenchCommandRejected("constraint_conflict", "关联编号前后带空格，没有保存，以免写错到别的记录上。请去掉前后的空格。")
        return identity, raw

    def name_owner(self, kind, name):
        if self._name_reader is not None:
            owners = self._names.setdefault(kind, {})
            if name not in owners:
                owners.update(self._name_reader(kind, [name]))
            return owners[name]
        if kind not in self._names:
            self._names[kind] = {row["name"]: code for code, row in self.facts.raw_lookup(kind,
                {"op_type": "op_type_id", "machine_group": "group_id", "shift_profile": "profile_id"}[kind]).items()}
        return self._names[kind].get(name)

    def authorizations(self, kind, code):
        key = "machine_id" if kind == "machine" else "operator_id"
        return self.facts.grouped("authorizations", key)[code]

    def export_state(self, kind, code):
        from .file_projection import resource_export_state

        return resource_export_state(self.facts, kind, code)
