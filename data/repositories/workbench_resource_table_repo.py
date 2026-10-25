"""Batched identity and page-state evidence for resource table projections."""

from collections import defaultdict

from .base_repo import BaseRepository
from .workbench_resource_dependencies import DEPENDENCIES, report_revision_rows
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


def _chunks(values):
    values = sorted(set(values))
    for start in range(0, len(values), 400):
        yield values[start:start + 400]


class WorkbenchResourceTableRepository(BaseRepository):
    def identities(self, kinds=("op_type", "machine", "operator", "supplier", "machine_group", "shift_profile")):
        marks = ",".join("?" for _ in kinds)
        return self.fetchall("SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs "
                             f"WHERE active=1 AND kind IN ({marks}) ORDER BY kind,entity_key,ref", kinds)

    def identities_by_refs(self, refs):
        rows = []
        for chunk in _chunks(refs):
            marks = ",".join("?" for _ in chunk)
            rows.extend(self.fetchall("SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs "
                                     f"WHERE active=1 AND ref IN ({marks}) ORDER BY kind,entity_key,ref", chunk))
        return rows

    def identities_by_codes(self, kind, codes):
        rows = []
        for chunk in _chunks(codes):
            marks = ",".join("?" for _ in chunk)
            rows.extend(self.fetchall("SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs "
                f"WHERE active=1 AND kind=? AND entity_key IN ({marks}) ORDER BY entity_key,ref", [kind] + chunk))
        return rows

    def raw_rows(self, kind, codes):
        table, key = _RESOURCE_TABLES[kind]
        return [row for chunk in _chunks(codes) for row in self.fetchall(
            f"SELECT * FROM {table} WHERE {key} IN ({','.join('?' for _ in chunk)}) ORDER BY {key}", chunk)]

    def relation_rows(self, name, scopes):
        """Capture only the requested owners, merging overlapping relationship scopes."""
        table, order = _RELATION_TABLES[name]
        rows = {}
        for column, values in scopes:
            for chunk in _chunks(values):
                marks = ",".join("?" for _ in chunk)
                for row in self.fetchall(f"SELECT * FROM {table} WHERE {column} IN ({marks}) ORDER BY {','.join(order)}", chunk):
                    rows[tuple(row[key] for key in order)] = row
        return [rows[key] for key in sorted(rows)]

    def name_owners(self, kind, names):
        table, key = _RESOURCE_TABLES[kind]
        result = dict.fromkeys(names)
        for chunk in _chunks(names):
            marks = ",".join("?" for _ in chunk)
            for row in self.fetchall(f"SELECT {key} AS business_code,name FROM {table} WHERE name IN ({marks}) ORDER BY {key}", chunk):
                result[row["name"]] = row["business_code"]
        return result

    def assigned_counts(self, kind, codes):
        names = {"BatchOperations": "batch_operations", "Schedule": "schedule"}
        dependencies = [(names.get(table, table + "." + key), table, key) for table, key in DEPENDENCIES[kind]]
        result = {code: {name: 0 for name, _table, _key in dependencies} for code in codes}
        for name, table, key in dependencies:
            if table == "WorkbenchProductionReportRevisions":
                for code, rows in report_revision_rows(self.conn, kind, key, codes).items():
                    result[code][name] = len(rows)
        for chunk in _chunks(codes):
            marks = ",".join("?" for _ in chunk)
            for name, table, key in dependencies:
                if table == "WorkbenchProductionReportRevisions":
                    continue
                for row in self.fetchall(f"SELECT {key} AS code,COUNT(*) AS amount FROM {table} WHERE {key} IN ({marks}) GROUP BY {key}", chunk):
                    result[row["code"]][name] = row["amount"]
        return result

    def page_relations(self, kind, codes):
        result = {}
        tables = (("pattern", "WorkbenchShiftPatternDays", "profile_id", "day_offset"),) if kind == "shift_profile" else (
            ("part_operations", "PartOperations", "supplier_id", "id"),
            ("batch_operations", "BatchOperations", "supplier_id", "id"),
            ("external_groups", "ExternalGroups", "supplier_id", "group_id"))
        for name, table, key, order in tables:
            grouped = defaultdict(list)
            for chunk in _chunks(codes):
                marks = ",".join("?" for _ in chunk)
                sql = f"SELECT * FROM {table} WHERE {key} IN ({marks}) ORDER BY {key},{order}"
                if table == "WorkbenchShiftPatternDays":
                    sql = f"""SELECT d.*,p.periods_json FROM WorkbenchShiftPatternDays d LEFT JOIN WorkbenchShiftDayPeriods p
                        ON p.profile_id=d.profile_id AND p.day_offset=d.day_offset
                        WHERE d.profile_id IN ({marks}) ORDER BY d.profile_id,d.day_offset"""
                for row in self.fetchall(sql, chunk):
                    grouped[row[key]].append(row)
            result[name] = grouped
        return result
