"""Complete per-operation choices and narrowly scoped hours persistence."""

from __future__ import annotations

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.process_quota_protection import ProcessQuotaProtection
from data.repositories.base_repo import BaseRepository
from data.repositories.supplier_repo import SupplierRepository


def exact_operations(payload, operations):
    active = {row["ref"]: row for row in operations if row["status"] == "active"}
    if not active or set(active) != {row["ref"] for row in payload["operations"]}:
        raise WorkbenchCommandRejected("operation_set_mismatch", "必须完整提交当前有效工序，不能遗漏、重复或包含其他模板及停用工序。")
    return active


def _related(identities, ref, kind, cache):
    if ref not in cache:
        cache[ref] = identities.get(ref)
    current = cache[ref]
    if current is None or not current.active or current.kind != kind:
        raise WorkbenchCommandRejected("invalid_relation", "所选工种或供应商记录不存在、已失效或引用类型错误。", 422)
    return current.entity_key


def prepare_source(conn, logger, payload, operations, identities):
    active = exact_operations(payload, operations)
    repo = BaseRepository(conn, logger)
    types = {row["op_type_id"]: row for row in repo.fetchall("SELECT op_type_id,category FROM OpTypes")}
    suppliers = {row["supplier_id"]: row for row in repo.fetchall("""SELECT s.supplier_id,s.status,p.inactive_reason
        FROM Suppliers s LEFT JOIN WorkbenchSupplierProfiles p ON p.supplier_id=s.supplier_id""")}
    capabilities = {(row["supplier_id"], row["op_type_id"]) for row in
                    SupplierRepository(conn, logger).list_capabilities(status="active") if not row["missing_supplier"]}
    changes, affected, cache = [], set(), {}
    for row in payload["operations"]:
        old = active[row["ref"]]
        type_key = _related(identities, row["op_type_ref"], "op_type", cache)
        if type_key not in types or types[type_key]["category"] != row["source"]:
            raise WorkbenchCommandRejected("source_category_mismatch", "所选工种类别必须匹配本序归属，不能通过本序操作修改全局工种类别。", 422)
        supplier_key = None
        if row["source"] == "external":
            supplier_key = _related(identities, row["supplier_ref"], "supplier", cache)
            if supplier_key not in suppliers or suppliers[supplier_key]["status"] != "active" or suppliers[supplier_key]["inactive_reason"] is not None:
                raise WorkbenchCommandRejected("supplier_unavailable", "所选供应商不存在或未启用，不能确认外协归属。", 422)
            if (supplier_key, type_key) not in capabilities:
                raise WorkbenchCommandRejected("supplier_capability_mismatch", "供应商没有所选外协工种的有效v21能力关系，不能猜测其能力。", 422)
        values = (row["source"], type_key, supplier_key)
        if values != (old["source"], old["op_type_id"], old["supplier_id"]):
            changes.append(values + (old["id"],))
            affected.add(old["seq"])
    return changes, affected


def apply_source(conn, changes):
    conn.executemany("UPDATE PartOperations SET source=?,op_type_id=?,supplier_id=? WHERE id=?", changes)


def _merged_hours_groups(payload, active, groups):
    active_groups = {row["ext_group_id"] for row in active.values() if row["ext_group_id"] is not None}
    merged = {row["ref"]: row for row in groups if row["group_id"] in active_groups and row["merge_mode"] == "merged"}
    if set(merged) != {row["ref"] for row in payload["groups"]}:
        raise WorkbenchCommandRejected("group_set_mismatch", "必须完整提供当前有效合并外协组的总周期，不能包含逐序组或其他组。")
    return merged


def _hours_fields(row, old, merged_keys):
    expected = {"ref", "setup_hours", "unit_hours"} if old["source"] == "internal" else {"ref", "external_days"}
    if old["source"] not in ("internal", "external") or set(row) != expected:
        raise WorkbenchCommandRejected("hours_source_mismatch", "工时字段必须匹配已确认的本序归属。", 422)
    if "external_days" in row and row["external_days"] is None and old["ext_group_id"] not in merged_keys:
        raise WorkbenchCommandRejected("external_days_required", "非合并外协工序必须提供有限正数周期，不能使用空值。", 422)
    return {("ext_days" if key == "external_days" else key): value for key, value in row.items() if key != "ref"}


def _hours_updates(payload, active, merged):
    merged_keys = {row["group_id"] for row in merged.values()}
    updates = []
    for row in payload["operations"]:
        old = active[row["ref"]]
        fields = _hours_fields(row, old, merged_keys)
        fields = {key: value for key, value in fields.items() if old[key] != value}
        if fields:
            updates.append((old["id"], fields))
    return updates


def apply_hours(conn, payload, operations, groups):
    active = exact_operations(payload, operations)
    merged = _merged_hours_groups(payload, active, groups)
    current = ProcessQuotaProtection(conn).require_changes(
        {row["ref"]: row.get("unit_hours", active[row["ref"]]["unit_hours"]) for row in payload["operations"]})
    if any(current[ref]["id"] != row["id"] or current[ref]["part_no"] != row["part_no"] or
           current[ref]["seq"] != row["seq"] for ref, row in active.items()):
        raise WorkbenchCommandRejected("stale_write", "原模板工序已变化，未更新同号新对象。")
    updates = _hours_updates(payload, active, merged)
    changed = bool(updates)
    for key, fields in updates:
        assignments = ",".join(name + "=?" for name in fields)
        conn.execute("UPDATE PartOperations SET " + assignments + " WHERE id=?", list(fields.values()) + [key])
    for row in payload["groups"]:
        old = merged[row["ref"]]
        if old["total_days"] != row["total_days"]:
            conn.execute("UPDATE ExternalGroups SET total_days=? WHERE group_id=?", (row["total_days"], old["group_id"]))
            changed = True
    return changed
