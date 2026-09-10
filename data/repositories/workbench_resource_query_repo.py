"""SQL filtering before pagination; no implicit entity or relationship creation."""

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_table_query import table_query_required

from .base_repo import BaseRepository
from .workbench_resource_state_repo import RESOURCE_KEYS

_TABLES = {**RESOURCE_KEYS, "supplier": ("Suppliers", "supplier_id")}


def _public_status(kind):
    if kind == "op_type":
        return "NULL"
    if kind in ("operator", "supplier"):
        special, label = ("leave", "leave") if kind == "operator" else ("pending_review", "pending_review")
        return ("CASE WHEN source.status='active' THEN 'active' WHEN source.status='inactive' AND profile.inactive_reason='" + special + "' THEN '" + label
                + "' WHEN source.status='inactive' AND profile.inactive_reason='disabled' THEN 'inactive' ELSE 'unknown' END")
    options = "'active','maintain','inactive'" if kind == "machine" else "'active','inactive'"
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
            conditions.append("source.category=?")
            params.append(query.category)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        return key, source, where, params

    def matching_keys(self, query):
        if table_query_required(query):
            raise WorkbenchCommandRejected("invalid_input", "列筛选与业务列排序请使用查询服务的 matching_keys 统一入口。", 400)
        return self.toolbar_keys(query)

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
        refs = self.fetchall("""SELECT kind,COUNT(*) AS instances,coalesce(SUM(revision),0) AS revisions
            FROM WorkbenchEntityRefs WHERE kind IN ('part','material','batch','op_type','machine','operator','supplier','machine_group','shift_profile','resource_team')
            GROUP BY kind ORDER BY kind""")
        dependencies = {"op_type": (("PartOperations", "op_type_id"), ("BatchOperations", "op_type_id")),
                        "machine": (("BatchOperations", "machine_id"), ("Schedule", "machine_id")),
                        "operator": (("BatchOperations", "operator_id"), ("Schedule", "operator_id")),
                        "supplier": (("PartOperations", "supplier_id"), ("BatchOperations", "supplier_id"), ("ExternalGroups", "supplier_id"))}
        counts = {table: self.fetchall(f"SELECT {key} AS resource_key,COUNT(*) AS amount FROM {table} GROUP BY {key} ORDER BY {key}")
                  for table, key in dependencies.get(kind, ())}
        return {"identities": refs, "dependencies": counts}

    def summary(self):
        result = {kind: int(self.fetchvalue(f"SELECT COUNT(*) FROM {table}", default=0)) for kind, (table, _) in _TABLES.items()}
        result["part"] = int(self.fetchvalue("SELECT COUNT(*) FROM Parts", default=0))
        result["material"] = int(self.fetchvalue("SELECT COUNT(*) FROM Materials", default=0))
        result["internal_op_types"] = int(self.fetchvalue("SELECT COUNT(*) FROM OpTypes WHERE category='internal'", default=0))
        result["external_op_types"] = int(self.fetchvalue("SELECT COUNT(*) FROM OpTypes WHERE category='external'", default=0))
        return result
