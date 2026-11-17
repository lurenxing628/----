"""SQL filtering before pagination; no implicit entity or relationship creation."""

import json
from typing import Dict, Optional, Sequence

from core.models.workbench_resource_status import PUBLIC_STATUS_VALUES, public_status_sql
from core.models.workbench_resource_table_query import SqlOrder

from .base_repo import BaseRepository
from .sql_ranks import order_by
from .workbench_resource_state_repo import RESOURCE_KEYS

_TABLES = {**RESOURCE_KEYS, "supplier": ("Suppliers", "supplier_id")}


def _public_status(kind):
    """The shared public-status rule over this scope's ``source`` and ``profile`` aliases."""
    return public_status_sql(kind, "source.status", "profile.inactive_reason")


class WorkbenchResourceQueryRepository(BaseRepository):
    """``order`` 参数都来自表格列定义（``facts.table_columns.sql_order``）：只有能在 SQL 里排的列才会到这里。"""

    @staticmethod
    def _order(query, order: SqlOrder, key):
        return order_by(order, query.direction, alias="source", status=_public_status(query.kind), code="source." + key)

    def toolbar_keys(self, query, order: Optional[SqlOrder] = None):
        """工具栏范围内的编号；给了 ``order`` 按它排（导出等要顺序的读取），否则按编号（建格子索引、计数用）。"""
        key, source, where, params = self._scope(query)
        by = "source." + key if order is None else self._order(query, order, key)
        return [row["business_code"] for row in self.fetchall(
            "SELECT source." + key + " AS business_code" + source + where + " ORDER BY " + by, params)]

    def _scope(self, query, keys: Optional[Sequence[str]] = None):
        table, key = _TABLES[query.kind]
        source = f" FROM {table} AS source"
        if query.kind in ("operator", "supplier"):
            profile = "WorkbenchOperatorProfiles" if query.kind == "operator" else "WorkbenchSupplierProfiles"
            source += f" LEFT JOIN {profile} AS profile ON profile.{key}=source.{key}"
        conditions, params = [], []
        if query.query:
            conditions.append(f"(instr(lower(source.{key}),lower(?)) > 0 OR instr(lower(source.name),lower(?)) > 0)")
            params.extend([query.query] * 2)
        if query.status is not None:
            conditions.append(_public_status(query.kind) + "=?")
            params.append(query.status)
        if query.category is not None:
            conditions.append("(source.category=? OR source.category='both')" if query.kind == "op_type" else "source.category=?")
            params.append(query.category)
        if keys is not None:
            conditions.append(f"source.{key} IN (SELECT value FROM json_each(?))")
            params.append(json.dumps(keys))
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        return key, source, where, params

    def status_counts(self, query, keys: Optional[Sequence[str]] = None) -> Dict[str, int]:
        """工具栏范围（列筛选时再限到命中的 ``keys``）按对外状态计数：每种状态都有键，total 是各状态之和；
        设备另数实际绑定的设备组，人员另数技能登记条数。工种不走这里，它的能力计数在内存里算。"""
        key, source, where, params = self._scope(query, keys)
        counts: Dict[str, int] = dict.fromkeys(PUBLIC_STATUS_VALUES[query.kind], 0)
        status_rows = self.fetchall(
            f"SELECT {_public_status(query.kind)} AS status_key, COUNT(*) AS cnt{source}{where} GROUP BY status_key",
            params,
        )
        for row in status_rows:
            counts[row["status_key"]] = row["cnt"]
        counts["total"] = sum(row["cnt"] for row in status_rows)
        if query.kind == "machine":
            counts["groups"] = self.fetchvalue(
                f"SELECT COUNT(DISTINCT gm.group_id) FROM WorkbenchMachineGroupMembers AS gm "
                f"WHERE gm.machine_id IN (SELECT source.{key}{source}{where})",
                params,
            )
        elif query.kind == "operator":
            counts["skills"] = self.fetchvalue(
                f"SELECT COUNT(*) FROM OperatorSkill AS sk "
                f"WHERE sk.operator_id IN (SELECT source.{key}{source}{where})",
                params,
            )
        return counts

    def page_rows(self, query, order: SqlOrder):
        key, source, where, params = self._scope(query)
        join = " LEFT JOIN WorkbenchEntityRefs AS refs ON refs.kind=? AND refs.active=1 AND refs.entity_key=source." + key
        return self.fetchall(
            "SELECT source." + key + " AS business_code, refs.ref, refs.revision" + source + join + where
            + " ORDER BY " + self._order(query, order, key) + " LIMIT ? OFFSET ?",
            [query.kind] + params + [query.size, (query.number - 1) * query.size],
        )

    def create_relations(self, kind):
        """Only choice facts that can affect this kind's new record.

        New business-code/name uniqueness is checked in the write transaction;
        existing entities and unrelated collection counts are not prerequisites.
        """
        relations = {"machine": ("op_type", "machine_group"),
                     "operator": ("op_type", "shift_profile"), "supplier": ("op_type",)}.get(kind, ())
        if not relations:
            return None
        result = {}
        for relation in relations:
            table, key = _TABLES[relation]
            condition = ""
            if relation == "op_type":
                category = "external" if kind == "supplier" else "internal"
                condition = " WHERE source.category IN ('" + category + "','both')"
            result[relation] = self.fetchall(
                f"SELECT source.*,refs.ref,refs.revision FROM {table} source LEFT JOIN WorkbenchEntityRefs refs "
                f"ON refs.kind=? AND refs.active=1 AND refs.entity_key=source.{key}"
                + condition + f" ORDER BY source.{key}", (relation,))
        if kind == "operator":
            result["shift_pattern"] = self.fetchall(
                "SELECT * FROM WorkbenchShiftPatternDays ORDER BY profile_id,day_offset"
            )
        return result

    def summary(self):
        result = {kind: self.fetchvalue(f"SELECT COUNT(*) FROM {table}") for kind, (table, _) in _TABLES.items()}
        result["part"] = self.fetchvalue("SELECT COUNT(*) FROM Parts")
        result["material"] = self.fetchvalue("SELECT COUNT(*) FROM Materials")
        result["internal_op_types"] = self.fetchvalue("SELECT COUNT(*) FROM OpTypes WHERE category IN ('internal','both')")
        result["external_op_types"] = self.fetchvalue("SELECT COUNT(*) FROM OpTypes WHERE category IN ('external','both')")
        return result
