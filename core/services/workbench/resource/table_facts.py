"""Batch-loaded business cells, retaining whole relation combinations."""

import re
from collections import defaultdict
from dataclasses import asdict
from typing import Mapping, cast

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_resource_table_query import table_columns
from core.services.workbench.facts.table_cells import number_cell, relation_cell, status_cell, text_cell
from core.services.workbench.facts.table_index import ResourceTableIndex
from data.repositories.workbench_resource_dependencies import DEPENDENCIES
from data.repositories.workbench_resource_table_repo import WorkbenchResourceTableRepository

from .metrics import _KEYS, _index, _status

_OP_TYPE_DEPENDENCIES = {
    "machine_capabilities": "MachineOpTypes.op_type_id", "machines": "Machines.op_type_id",
    "legacy_suppliers": "Suppliers.op_type_id", "supplier_capabilities": "WorkbenchSupplierOpTypes.op_type_id",
    "skills": "OperatorSkill.op_type_id", "part_operations": "PartOperations.op_type_id",
    "batch_operations": "BatchOperations.op_type_id",
}


class ResourceTableFacts:
    def __init__(self, metrics, identities, *, scope_state=None):
        self.metrics = metrics
        self.identities = {(row["kind"], row["entity_key"]): row for row in identities if row["active"] == 1}
        self._maps, self._groups = {}, {}
        self._raw_maps = {}
        self.repo = WorkbenchResourceTableRepository(metrics.conn, metrics.logger)
        self._dependency_counts = (None if scope_state is None else {
            name: {row["resource_key"]: row["amount"] for row in rows}
            for name, rows in scope_state["dependencies"].items()
        })

    def identity(self, kind, code):
        row = self.identities.get((kind, code))
        if row is None or type(row["ref"]) is not str or re.fullmatch(r"[0-9a-f]{48}", row["ref"]) is None:
            raise WorkbenchCommandRejected("storage_failure", "这条资源在资料里查不到编号，列表没有打开，数据也没有被改动。请到资料总览核对后重试。", 500)
        return WorkbenchEntityIdentity(row["ref"], kind, code, row["revision"], True)

    def records(self, kind):
        return self.metrics._records(kind)

    def raw_lookup(self, name, key):
        """Index captured rows for single-state consumption without a full metric gate."""
        lookup_key = (name, key)
        if lookup_key not in self._raw_maps:
            self.metrics._load([name])
            self._raw_maps[lookup_key] = {row[key]: row for row in self.metrics.facts[name]}
        return self._raw_maps[lookup_key]

    def raw_record(self, kind, code):
        raw = self.raw_lookup(kind, _KEYS[kind]).get(code)
        if raw is None:
            raise WorkbenchCommandRejected("storage_failure", "这条资源的编号和实际记录对不上，操作没有执行。请联系维护人员核对数据。", 500)
        return raw

    def raw_related(self, kind, code):
        if code is None:
            return None
        return {"identity": asdict(self.identity(kind, code)), "record": self.raw_record(kind, code)}

    def mapped(self, name, key):
        if name not in self._maps:
            self.metrics._load([name])
            self._maps[name] = _index(self.metrics.facts[name], key)
        return self._maps[name]

    def grouped(self, name, key):
        if name not in self._groups:
            self.metrics._load([name])
            grouped = defaultdict(list)
            for row in self.metrics.facts[name]:
                grouped[row[key]].append(row)
            self._groups[name] = grouped
        return self._groups[name]

    def _project_dependency_counts(self, codes, names):
        dependency_counts = cast(Mapping[str, Mapping[str, int]], self._dependency_counts)
        return {code: {name: dependency_counts[source].get(code, 0) for name, source in names.items()}
                for code in codes}

    def assigned_counts(self, kind, codes):
        if self._dependency_counts is None:
            return self.repo.assigned_counts(kind, codes)
        aliases = {"BatchOperations": "batch_operations", "Schedule": "schedule"}
        names = {aliases.get(table, table + "." + column): table + "." + column
                 for table, column in DEPENDENCIES[kind]}
        return self._project_dependency_counts(codes, names)

    def op_type_dependencies(self, codes):
        return self._project_dependency_counts(codes, _OP_TYPE_DEPENDENCIES)

    def shift_patterns(self, codes):
        if "shift_pattern" not in self.metrics.facts:
            return self.repo.page_relations("shift_profile", codes)["pattern"] if codes else {}
        grouped = self.grouped("shift_pattern", "profile_id")
        return {code: grouped[code] for code in codes}

    def related(self, kind, code):
        if code is None:
            return None
        identity = self.identity(kind, code)
        raw = self.records(kind).get(code)
        if raw is None:
            raise WorkbenchCommandRejected("storage_failure", "这条资源的关联指向一条已经不存在的记录。请到资料总览核对后重试。", 500)
        return {"identity": asdict(identity), "record": raw}

    def supplier_types(self, code):
        legacy = self.records("supplier")[code]["op_type_id"]
        explicit = {row["op_type_id"] for row in self.grouped("capabilities", "supplier_id")[code]}
        return sorted(explicit | ({legacy} if legacy not in (None, "") else set()))

    def machine_types(self, code):
        legacy = self.records("machine")[code]["op_type_id"]
        explicit = {row["op_type_id"] for row in self.grouped("machine_capabilities", "machine_id")[code]}
        return sorted(explicit | ({legacy} if legacy else set()))

    def _relation_labels(self, kind, code, raw):
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

    def cells(self, kind, code, category):
        raw = self.records(kind)[code]
        result = {"business_code": text_cell(code), "label": text_cell(raw["name"])}
        if kind == "op_type":
            result.update(self._op_type_cells(code, raw, category))
        else:
            profiles = self.mapped(kind + "_profiles", kind + "_id") if kind in ("operator", "supplier") else {}
            result["status"] = status_cell(kind, _status(kind, raw, profiles.get(code)))
            for column, (related_kind, codes) in self._relation_labels(kind, code, raw).items():
                labels = []
                for key in codes:
                    related = self.related(related_kind, key)
                    if related is None:
                        raise WorkbenchCommandRejected("storage_failure", "这条资源的关联缺少编号。请到资料总览核对后重试。", 500)
                    labels.append(related["record"]["name"])
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
        rows, cells, legacy_values = {}, {}, {}
        for code in codes:
            identity = self.identity(query.kind, code)
            rows[code] = {"ref": identity.ref, "revision": identity.revision, "business_code": code}
            cells[code] = self.cells(query.kind, code, query.category)
            raw = self.records(query.kind)[code]
            profiles = self.mapped(query.kind + "_profiles", query.kind + "_id") if query.kind in ("operator", "supplier") else {}
            status = None if query.kind == "op_type" else _status(query.kind, raw, profiles.get(code))
            legacy_values[code] = {"business_code": code, "label": raw["name"], "status": status, "default_days": raw.get("default_days")}
            if not set(table_columns(query.kind, query.category)).issubset(cells[code]):
                raise WorkbenchCommandRejected("invalid_input", "当前视图和这些列对不上，列表没有打开。请刷新页面后重试。", 400)
        return ResourceTableIndex(rows, cells, legacy_values)
