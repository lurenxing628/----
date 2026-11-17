"""Batched identity and page-state evidence for resource table projections."""

import json
from collections import defaultdict

from .base_repo import BaseRepository
from .workbench_resource_dependencies import DEPENDENCIES, report_reference_counts
from .workbench_resource_state_repo import RESOURCE_KEYS

_RESOURCE_TABLES = dict(RESOURCE_KEYS, supplier=("Suppliers", "supplier_id"))
_RELATION_TABLES = {
    "groups": ("WorkbenchMachineGroupMembers", ("machine_id",)),
    "operator_profiles": ("WorkbenchOperatorProfiles", ("operator_id",)),
    "supplier_profiles": ("WorkbenchSupplierProfiles", ("supplier_id",)),
    "policies": ("WorkbenchOpTypePolicies", ("op_type_id",)),
    "skills": ("OperatorSkill", ("operator_id", "op_type_id")),
    "authorizations": ("OperatorMachine", ("operator_id", "machine_id")),
    "machine_capabilities": ("MachineOpTypes", ("machine_id", "op_type_id")),
    "capabilities": ("WorkbenchSupplierOpTypes", ("supplier_id", "op_type_id")),
}
_MEMBER_TABLES = {
    "machine_group": ("WorkbenchMachineGroupMembers", "group_id"),
    "shift_profile": ("WorkbenchOperatorProfiles", "shift_profile_id"),
}


class WorkbenchResourceTableRepository(BaseRepository):
    def identities(self, kinds=("op_type", "machine", "operator", "supplier", "machine_group", "shift_profile")):
        marks = ",".join("?" for _ in kinds)
        return self.fetchall("SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs "
                             f"WHERE active=1 AND kind IN ({marks}) ORDER BY kind,entity_key,ref", kinds)

    def identities_by_refs(self, refs):
        if not refs:
            return []
        return self.fetchall(
            "SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs "
            "WHERE active=1 AND ref IN (SELECT value FROM json_each(?)) ORDER BY kind,entity_key,ref",
            (json.dumps(list(refs)),),
        )

    def identities_by_codes(self, kind, codes):
        return self.fetchall(
            "SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs "
            "WHERE active=1 AND kind=? AND entity_key IN (SELECT value FROM json_each(?)) ORDER BY entity_key,ref",
            (kind, json.dumps(list(codes))),
        )

    def raw_rows(self, kind, codes):
        table, key = _RESOURCE_TABLES[kind]
        return self.fetchall(
            f"SELECT * FROM {table} WHERE {key} IN (SELECT value FROM json_each(?)) ORDER BY {key}",
            (json.dumps(list(codes)),),
        )

    def relation_rows(self, name, scopes):
        """Capture only the requested owners, merging overlapping relationship scopes."""
        table, order = _RELATION_TABLES[name]
        rows = {}
        for column, values in scopes:
            if not values:
                continue
            for row in self.fetchall(
                f"SELECT * FROM {table} WHERE {column} IN (SELECT value FROM json_each(?)) ORDER BY {','.join(order)}",
                (json.dumps(list(values)),),
            ):
                rows[tuple(row[key] for key in order)] = row
        return [rows[key] for key in sorted(rows)]

    def name_owners(self, kind, names):
        table, key = _RESOURCE_TABLES[kind]
        result = dict.fromkeys(names)
        for row in self.fetchall(
            f"SELECT {key} AS business_code,name FROM {table} WHERE name IN (SELECT value FROM json_each(?)) ORDER BY {key}",
            (json.dumps(list(result)),),
        ):
            result[row["name"]] = row["business_code"]
        return result

    def assigned_counts(self, kind, codes):
        """删除前的引用计数，唯一入口：按 ``DEPENDENCIES`` 的公开计数名，每条资源每类引用各一个数。"""
        result = {code: {dependency.name: 0 for dependency in DEPENDENCIES[kind]} for code in codes}
        encoded = json.dumps(list(result))
        for dependency in DEPENDENCIES[kind]:
            if dependency.table == "WorkbenchProductionReportRevisions":
                for code, amount in report_reference_counts(self.conn, kind, dependency.column, encoded).items():
                    result[code][dependency.name] = amount
                continue
            rows = self.fetchall(
                f"SELECT {dependency.column} AS code, COUNT(*) AS amount FROM {dependency.table} "
                f"WHERE {dependency.column} IN (SELECT value FROM json_each(?)) GROUP BY {dependency.column}",
                (encoded,),
            )
            for row in rows:
                result[row["code"]][dependency.name] = row["amount"]
        return result

    def member_counts(self, kind, codes):
        table, key = _MEMBER_TABLES[kind]
        result = dict.fromkeys(codes, 0)
        rows = self.fetchall(
            f"SELECT {key} AS code, COUNT(*) AS amount FROM {table} "
            f"WHERE {key} IN (SELECT value FROM json_each(?)) GROUP BY {key}",
            (json.dumps(list(result)),),
        )
        for row in rows:
            result[row["code"]] = row["amount"]
        return result

    def page_relations(self, kind, codes):
        if kind != "shift_profile":
            raise ValueError(f"Unsupported page_relations kind: {kind!r}")
        grouped = defaultdict(list)
        for row in self.fetchall(
            "SELECT * FROM WorkbenchShiftPatternDays "
            "WHERE profile_id IN (SELECT value FROM json_each(?)) ORDER BY profile_id, day_offset",
            (json.dumps(list(codes)),),
        ):
            grouped[row["profile_id"]].append(row)
        return {"pattern": grouped}
