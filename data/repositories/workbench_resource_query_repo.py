"""SQL filtering before pagination; no implicit entity or relationship creation."""

from core.models.workbench_resource_status import RAW_RESOURCE_STATUSES, SPECIAL_INACTIVE_REASONS

from .base_repo import BaseRepository
from .workbench_resource_dependencies import DEPENDENCIES
from .workbench_resource_state_repo import RESOURCE_KEYS

_TABLES = {**RESOURCE_KEYS, "supplier": ("Suppliers", "supplier_id")}


def _public_status(kind):
    """Project the shared status vocabulary inside a SQL filtering scope."""
    if kind == "op_type":
        return "NULL"
    if kind in SPECIAL_INACTIVE_REASONS:
        special = SPECIAL_INACTIVE_REASONS[kind]
        return ("CASE WHEN source.status='active' THEN 'active' WHEN source.status='inactive' AND profile.inactive_reason='" + special
                + "' THEN '" + special + "' WHEN source.status='inactive' AND profile.inactive_reason='disabled' THEN 'inactive' ELSE 'unknown' END")
    options = ",".join("'" + status + "'" for status in RAW_RESOURCE_STATUSES.get(kind, ("active", "inactive")))
    return f"CASE WHEN source.status IN ({options}) THEN source.status ELSE 'unknown' END"


class WorkbenchResourceQueryRepository(BaseRepository):
    def toolbar_keys(self, query):
        key, source, where, params = self._scope(query)
        return [row["business_code"] for row in self.fetchall("SELECT source." + key + " AS business_code" + source + where + " ORDER BY source." + key, params)]

    def _scope(self, query):
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
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        return key, source, where, params

    def page(self, query):
        key, source, where, params = self._scope(query)
        total = int(self.fetchvalue("SELECT COUNT(*)" + source + where, params, default=0))
        join = " LEFT JOIN WorkbenchEntityRefs AS refs ON refs.kind=? AND refs.active=1 AND refs.entity_key=source." + key
        sort = {"business_code": "source." + key, "label": "source.name", "status": _public_status(query.kind), "default_days": "source.default_days"}[query.sort]
        order = sort + " " + query.direction.upper() + (", source." + key + " ASC" if query.sort != "business_code" else "")
        rows = self.fetchall("SELECT source." + key + " AS business_code, refs.ref, refs.revision" + source + join + where
                             + " ORDER BY " + order + " LIMIT ? OFFSET ?", [query.kind] + params + [query.size, (query.number - 1) * query.size])
        return rows, total

    def scope_state(self, kind):
        counts = {table + "." + key: self.fetchall(f"SELECT {key} AS resource_key,COUNT(*) AS amount FROM {table} "
                                                 f"WHERE {key} IS NOT NULL GROUP BY {key} ORDER BY {key}")
                  for table, key in DEPENDENCIES.get(kind, ())}
        return {"dependencies": counts}

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
            result["shift_pattern"] = self.fetchall("""SELECT d.*,p.periods_json FROM WorkbenchShiftPatternDays d
                LEFT JOIN WorkbenchShiftDayPeriods p ON p.profile_id=d.profile_id AND p.day_offset=d.day_offset
                ORDER BY d.profile_id,d.day_offset""")
        return result

    def summary(self):
        result = {kind: int(self.fetchvalue(f"SELECT COUNT(*) FROM {table}", default=0)) for kind, (table, _) in _TABLES.items()}
        result["part"] = int(self.fetchvalue("SELECT COUNT(*) FROM Parts", default=0))
        result["material"] = int(self.fetchvalue("SELECT COUNT(*) FROM Materials", default=0))
        result["internal_op_types"] = int(self.fetchvalue("SELECT COUNT(*) FROM OpTypes WHERE category IN ('internal','both')", default=0))
        result["external_op_types"] = int(self.fetchvalue("SELECT COUNT(*) FROM OpTypes WHERE category IN ('external','both')", default=0))
        return result
