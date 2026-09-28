"""Batched identity and page-state evidence for resource table projections."""

from collections import defaultdict

from .base_repo import BaseRepository
from .workbench_resource_dependencies import DEPENDENCIES


class WorkbenchResourceTableRepository(BaseRepository):
    def identities(self):
        return self.fetchall("""SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs
            WHERE kind IN ('op_type','machine','operator','supplier','machine_group','shift_profile')
            ORDER BY kind,entity_key,ref""")

    def assigned_counts(self, kind, codes):
        names = {"BatchOperations": "batch_operations", "Schedule": "schedule"}
        dependencies = [(names.get(table, table + "." + key), table, key) for table, key in DEPENDENCIES[kind]]
        result = {code: {name: 0 for name, _table, _key in dependencies} for code in codes}
        if not codes:
            return result
        marks = ",".join("?" for _ in codes)
        for name, table, key in dependencies:
            for row in self.fetchall(f"SELECT {key} AS code,COUNT(*) AS amount FROM {table} WHERE {key} IN ({marks}) GROUP BY {key}", codes):
                result[row["code"]][name] = row["amount"]
        return result

    def page_relations(self, kind, codes):
        result = {}
        tables = (("pattern", "WorkbenchShiftPatternDays", "profile_id", "day_offset"),) if kind == "shift_profile" else (
            ("part_operations", "PartOperations", "supplier_id", "id"),
            ("batch_operations", "BatchOperations", "supplier_id", "id"),
            ("external_groups", "ExternalGroups", "supplier_id", "group_id"))
        marks = ",".join("?" for _ in codes) or "NULL"
        for name, table, key, order in tables:
            grouped = defaultdict(list)
            sql = f"SELECT * FROM {table} WHERE {key} IN ({marks}) ORDER BY {key},{order}"
            if table == "WorkbenchShiftPatternDays":
                sql = f"""SELECT d.*,p.periods_json FROM WorkbenchShiftPatternDays d LEFT JOIN WorkbenchShiftDayPeriods p
                    ON p.profile_id=d.profile_id AND p.day_offset=d.day_offset
                    WHERE d.profile_id IN ({marks}) ORDER BY d.profile_id,d.day_offset"""
            for row in self.fetchall(sql, codes):
                grouped[row[key]].append(row)
            result[name] = grouped
        return result
