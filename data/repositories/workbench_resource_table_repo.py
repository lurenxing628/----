"""Batched identity and page-state evidence for resource table projections."""

from collections import defaultdict

from .base_repo import BaseRepository


class WorkbenchResourceTableRepository(BaseRepository):
    def identities(self):
        return self.fetchall("""SELECT ref,kind,entity_key,revision,active FROM WorkbenchEntityRefs
            WHERE kind IN ('op_type','machine','operator','supplier','machine_group','shift_profile')
            ORDER BY kind,entity_key,ref""")

    def assigned_counts(self, kind, codes):
        key = {"machine": "machine_id", "operator": "operator_id"}[kind]
        result = {code: {"batch_operations": 0, "schedule": 0} for code in codes}
        if not codes:
            return result
        marks = ",".join("?" for _ in codes)
        for name, table in (("batch_operations", "BatchOperations"), ("schedule", "Schedule")):
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
            for row in self.fetchall(f"SELECT * FROM {table} WHERE {key} IN ({marks}) ORDER BY {key},{order}", codes):
                grouped[row[key]].append(row)
            result[name] = grouped
        return result
