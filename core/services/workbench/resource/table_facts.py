"""Batch-loaded business cells, retaining whole relation combinations."""

import re
from collections import defaultdict
from dataclasses import asdict
from typing import Mapping, cast

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.services.workbench.facts.table_cells import number_cell, relation_cell, status_cell, text_cell
from core.services.workbench.facts.table_index import ResourceTableIndex
from data.repositories.workbench_resource_dependencies import DEPENDENCIES
from data.repositories.workbench_resource_table_repo import WorkbenchResourceTableRepository

from .metrics import READ_FACTS, RESOURCE_KEYS, WorkbenchResourceMetricsService, index_resource_rows

OP_TYPE_DEPENDENCIES = {
    "machine_capabilities": "MachineOpTypes.op_type_id", "machines": "Machines.op_type_id",
    "supplier_capabilities": "WorkbenchSupplierOpTypes.op_type_id",
    "skills": "OperatorSkill.op_type_id", "part_operations": "PartOperations.op_type_id",
    "batch_operations": "BatchOperations.op_type_id",
}


def _change_relations(repo, roots, machine_authorizations):
    authorizations = repo.relation_rows("authorizations", (("operator_id", roots["operator"]),
        ("machine_id", roots["machine"] if machine_authorizations else ())))
    if machine_authorizations:
        # Permissions compare complete states for old and newly requested machines.
        # Expand these owners before reading machine capabilities and group bindings.
        roots["machine"].update(row["machine_id"] for row in authorizations if row["operator_id"] in roots["operator"])
    scopes = {
        "groups": (("machine_id", roots["machine"]), ("group_id", roots["machine_group"])),
        "operator_profiles": (("operator_id", roots["operator"]), ("shift_profile_id", roots["shift_profile"])),
        "supplier_profiles": (("supplier_id", roots["supplier"]),),
        "policies": (("op_type_id", roots["op_type"]),),
        "skills": (("operator_id", roots["operator"]),),
        "machine_capabilities": (("machine_id", roots["machine"]),),
        "capabilities": (("supplier_id", roots["supplier"]),),
    }
    return {"authorizations": authorizations,
            **{name: repo.relation_rows(name, selections) for name, selections in scopes.items()}}


def _related_change_codes(data, roots):
    codes = {"op_type": set(), "machine_group": set(), "shift_profile": set()}
    for name in ("machine", "skills", "machine_capabilities", "capabilities"):
        codes["op_type"].update(row["op_type_id"] for row in data[name] if row["op_type_id"] is not None)
    codes["machine_group"].update(row["group_id"] for row in data["groups"] if row["machine_id"] in roots["machine"])
    codes["shift_profile"].update(row["shift_profile_id"] for row in data["operator_profiles"]
                                  if row["operator_id"] in roots["operator"] and row["shift_profile_id"] is not None)
    return codes


def capture_change_facts(conn, logger, *, refs, codes, selected_refs=(), selected_codes=None,
                         machine_authorizations=False, known_identities=()):
    """Feed the same state projections with only this command's resource closure."""
    repo = WorkbenchResourceTableRepository(conn, logger)
    roots = {kind: set((codes or {}).get(kind, ())) for kind in RESOURCE_KEYS}
    known_by_ref = {row["ref"]: row for row in known_identities}
    missing_refs = [ref for ref in refs if ref not in known_by_ref]
    current = list(known_identities) + (repo.identities_by_refs(missing_refs) if missing_refs else [])
    identities = {(row["kind"], row["entity_key"]): row for row in current}
    for identity in current:
        if identity["kind"] in roots:
            roots[identity["kind"]].add(identity["entity_key"])
    wanted = {kind: values | set((selected_codes or {}).get(kind, ())) for kind, values in roots.items()}
    for identity in repo.identities_by_refs(selected_refs):
        if identity["kind"] in wanted:
            wanted[identity["kind"]].add(identity["entity_key"])
            identities[(identity["kind"], identity["entity_key"])] = identity
    data = {kind: repo.raw_rows(kind, values) if values else [] for kind, values in wanted.items()}
    data.update(_change_relations(repo, roots, machine_authorizations))
    authorized_machines = {row["machine_id"] for row in data["authorizations"] if row["operator_id"] in roots["operator"]}
    additional_machines = (roots["machine"] | authorized_machines) - wanted["machine"]
    if additional_machines:
        data["machine"].extend(repo.raw_rows("machine", additional_machines))
        wanted["machine"].update(additional_machines)
    related = _related_change_codes(data, roots)
    for kind, values in related.items():
        missing = values - wanted[kind]
        if missing:
            data[kind].extend(repo.raw_rows(kind, missing))
            wanted[kind].update(missing)
    shifts = sorted(roots["shift_profile"] | related["shift_profile"])
    patterns = repo.page_relations("shift_profile", shifts)["pattern"] if shifts else {}
    data["shift_pattern"] = [row for code in shifts for row in patterns[code]]
    for kind, values in wanted.items():
        missing = [code for code in values if (kind, code) not in identities]
        if missing:
            identities.update(((row["kind"], row["entity_key"]), row) for row in repo.identities_by_codes(kind, missing))
    metrics = WorkbenchResourceMetricsService(conn, logger, facts={name: data.get(name, []) for name in READ_FACTS["op_type"]})
    return ResourceTableFacts(metrics, identities.values())


class ResourceTableFacts:
    def __init__(self, metrics, identities, *, scope_state=None, identity_kinds=None, report_revisions=None):
        self.metrics = metrics
        self.identities = {(row["kind"], row["entity_key"]): row for row in identities}
        self.identities_by_ref = {row["ref"]: row for row in self.identities.values()}
        self.identity_kinds = set(identity_kinds) if identity_kinds is not None else set(RESOURCE_KEYS)
        self._maps, self._groups = {}, {}
        self._raw_maps = {}
        self.repo = WorkbenchResourceTableRepository(metrics.conn, metrics.logger)
        self.report_revisions = report_revisions
        self._dependency_counts = (None if scope_state is None else {
            name: {row["resource_key"]: row["amount"] for row in rows}
            for name, rows in scope_state["dependencies"].items()
        })

    def load_identity_kinds(self, kinds):
        missing = sorted(set(kinds) - self.identity_kinds)
        if missing:
            loaded = self.repo.identities(missing)
            self.identities.update(((row["kind"], row["entity_key"]), row) for row in loaded)
            self.identities_by_ref.update((row["ref"], row) for row in loaded)
            self.identity_kinds.update(missing)

    def find_by_ref(self, kind, ref):
        if kind not in self.identity_kinds:
            self.load_identity_kinds([kind])
        row = self.identities_by_ref.get(ref)
        if row is None or row["kind"] != kind:
            return None
        return self.identity(kind, row["entity_key"])

    def identity(self, kind, code):
        if kind not in self.identity_kinds:
            self.load_identity_kinds([kind])
        row = self.identities.get((kind, code))
        if row is None or type(row["ref"]) is not str or re.fullmatch(r"[0-9a-f]{48}", row["ref"]) is None:
            raise WorkbenchCommandRejected("storage_failure", "这条资源在资料里查不到编号，列表没有打开，数据也没有被改动。请到资料总览核对后重试。", 500)
        return WorkbenchEntityIdentity(row["ref"], kind, code, row["revision"], True)

    def raw_lookup(self, name, key):
        """Index captured rows for single-state consumption without a full metric gate."""
        lookup_key = (name, key)
        if lookup_key not in self._raw_maps:
            self.metrics._load([name])
            self._raw_maps[lookup_key] = {row[key]: row for row in self.metrics.facts[name]}
        return self._raw_maps[lookup_key]

    def raw_record(self, kind, code):
        raw = self.raw_lookup(kind, RESOURCE_KEYS[kind]).get(code)
        if raw is None:
            raise WorkbenchCommandRejected("storage_failure", "这条资源的编号和实际记录对不上，操作没有执行。请联系维护人员核对数据。", 500)
        return raw

    def raw_related(self, kind, code):
        if code is None:
            return None
        return {"identity": asdict(self.identity(kind, code)), "record": self.raw_record(kind, code)}

    def mapped(self, name, key):
        lookup_key = (name, key)
        if lookup_key not in self._maps:
            self.metrics._load([name])
            self._maps[lookup_key] = index_resource_rows(self.metrics.facts[name], key)
        return self._maps[lookup_key]

    def grouped(self, name, key):
        lookup_key = (name, key)
        if lookup_key not in self._groups:
            self.metrics._load([name])
            grouped = defaultdict(list)
            for row in self.metrics.facts[name]:
                grouped[row[key]].append(row)
            self._groups[lookup_key] = grouped
        return self._groups[lookup_key]

    def _project_dependency_counts(self, codes, names):
        dependency_counts = cast(Mapping[str, Mapping[str, int]], self._dependency_counts)
        return {code: {name: dependency_counts[source].get(code, 0) for name, source in names.items()}
                for code in codes}

    def assigned_counts(self, kind, codes):
        sources = [table + "." + column for table, column in DEPENDENCIES[kind]]
        if self._dependency_counts is None or any(source not in self._dependency_counts for source in sources):
            return self.repo.assigned_counts(kind, codes)
        aliases = {"BatchOperations": "batch_operations", "Schedule": "schedule"}
        names = {aliases.get(table, table + "." + column): table + "." + column
                 for table, column in DEPENDENCIES[kind]}
        return self._project_dependency_counts(codes, names)

    def op_type_dependencies(self, codes):
        if self._dependency_counts is None or any(
            source not in self._dependency_counts for source in OP_TYPE_DEPENDENCIES.values()
        ):
            return self.metrics.repo.op_type_dependencies(codes)
        return self._project_dependency_counts(codes, OP_TYPE_DEPENDENCIES)

    def shift_patterns(self, codes):
        if "shift_pattern" not in self.metrics.facts:
            return self.repo.page_relations("shift_profile", codes)["pattern"] if codes else {}
        grouped = self.grouped("shift_pattern", "profile_id")
        return {code: grouped[code] for code in codes}

    def related(self, kind, code):
        self.identity(kind, code)
        raw = self.metrics.kind_records(kind).get(code)
        if raw is None:
            raise WorkbenchCommandRejected("storage_failure", "这条资源的关联指向一条已经不存在的记录。请到资料总览核对后重试。", 500)
        return raw

    def supplier_types(self, code):
        return sorted({row["op_type_id"] for row in self.grouped("capabilities", "supplier_id")[code]})

    def machine_types(self, code):
        legacy = self.metrics.kind_records("machine")[code]["op_type_id"]
        explicit = {row["op_type_id"] for row in self.grouped("machine_capabilities", "machine_id")[code]}
        return sorted(explicit | ({legacy} if legacy else set()))

    def _relation_labels(self, kind, code):
        if kind == "machine":
            member = self.mapped("groups", "machine_id").get(code)
            return {"op_type_ref": ("op_type", self.machine_types(code)),
                    "group_ref": ("machine_group", [member["group_id"]] if member else [])}
        if kind == "operator":
            profile = self.mapped("operator_profiles", "operator_id").get(code)
            shift = profile["shift_profile_id"] if profile else None
            return {"skill_refs": ("op_type", [row["op_type_id"] for row in self.grouped("skills", "operator_id")[code]]),
                    "shift_profile_ref": ("shift_profile", [shift] if shift is not None else [])}
        return {"op_type_refs": ("op_type", self.supplier_types(code))} if kind == "supplier" else {}

    def cells(self, kind, code, category, *, raw, status):
        result = {"business_code": text_cell(code), "label": text_cell(raw["name"])}
        if kind == "op_type":
            result.update(self._op_type_cells(code, raw, category))
        else:
            result["status"] = status_cell(kind, status)
            for column, (related_kind, codes) in self._relation_labels(kind, code).items():
                labels = []
                for key in codes:
                    related = self.related(related_kind, key)
                    labels.append(related["name"])
                result[column] = relation_cell(labels)
            if kind == "supplier":
                result["default_days"] = number_cell(raw["default_days"], "天")
        return result

    def _op_type_cells(self, code, raw, category):
        result = {"remark": text_cell(raw["remark"]), "status": text_cell(None)}
        if category == "internal":
            value = self.metrics.availability(code)
            for field, metric, unit in (("available_machines", "machines", "台"), ("available_operators", "operators", "人")):
                result[field] = number_cell(value[metric] if value is not None else None, unit, missing="暂无数据")
        elif category == "external":
            policy = self.mapped("policies", "op_type_id").get(code)
            mode = policy["default_merge_mode"] if policy else None
            label = {"separate": "分别设置", "merged": "合并设置"}.get(mode, mode) if mode is not None else None
            result["default_merge_mode"] = text_cell(label, missing="未设置")
        return result

    def index(self, query, codes):
        rows, cells = {}, {}
        records = self.metrics.kind_records(query.kind)
        statuses = None if query.kind == "op_type" else self.metrics._statuses(query.kind)
        for code in codes:
            identity = self.identity(query.kind, code)
            rows[code] = {"ref": identity.ref, "revision": identity.revision, "business_code": code}
            raw = records[code]
            status = None if statuses is None else statuses[code]
            cells[code] = self.cells(query.kind, code, query.category, raw=raw, status=status)
        return ResourceTableIndex(rows, cells)
