"""Shared private resource facts and identity checks, without public token handling."""

from dataclasses import asdict, dataclass
from typing import Optional

from core.models.resource_capabilities import supports_source
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from data.repositories.workbench_resource_dependencies import counted_references

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
        if pending:
            # 这次命令已读出引用证据就按它数，与证据同一份；否则查一次引用计数。
            references = self._references.get(kind)
            counts = None if references is None else {code: counted_references(kind, references[code]) for code in pending}
            if kind == "op_type":
                dependencies = self.facts.repo.assigned_counts(kind, pending) if counts is None else counts
                profiles = self.facts.raw_lookup("policies", "op_type_id")
                current.update({code: {"identity": asdict(self.identity_by_code(kind, code)),
                    "record": self.facts.raw_record(kind, code), "profile": profiles.get(code),
                    "dependencies": dependencies[code]} for code in pending})
            else:
                current.update(resource_table_states(self.facts, kind, pending, dependencies=counts))
        return {code: current[code] for code in codes}

    def capture_references(self, repo, kind, codes):
        self._references[kind] = repo.references_many(kind, codes)
        return self._references[kind]

    def state(self, kind, code):
        return self.states(kind, [code])[code]

    def selected_record(self, kind, identity, *, category=None):
        raw = self.facts.raw_record(kind, identity.entity_key)
        if kind != "op_type" and raw["status"] != "active":
            raise WorkbenchCommandRejected("constraint_conflict", "选中的关联资源已经停用，没有保存。请重新选择一个在用的。")
        if category is not None and not supports_source(raw["category"], category):
            raise WorkbenchCommandRejected("constraint_conflict", "选中工种的自制或外协归属和当前资源不匹配，没有保存。请换一个工种。")
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
