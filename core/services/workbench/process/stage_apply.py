"""Complete per-operation choices and narrowly scoped hours persistence."""

from __future__ import annotations

from core.models.resource_capabilities import supports_source
from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories.external_group_repo import ExternalGroupRepository
from data.repositories.part_operation_repo import PartOperationRepository
from data.repositories.supplier_repo import SupplierRepository
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository

from .quota_protection import ProcessQuotaProtection
from .zero_hours import require_zero_confirmation


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
        raise WorkbenchCommandRejected("invalid_relation", "所选工种或供应商记录不存在、已失效，或者选错了类型。请刷新后重新选择。", 422)
    return current.entity_key


def source_catalog(conn, logger=None):
    repo = WorkbenchProcessQueryRepository(conn, logger)
    types = {row["op_type_id"]: row for row in repo.op_type_reference_rows()}
    suppliers = {row["supplier_id"]: row for row in repo.supplier_status_rows()}
    for row in repo.supplier_reference_rows():
        suppliers[row["supplier_id"]]["name"] = row["name"]
    capabilities = {(row["supplier_id"], row["op_type_id"]) for row in
                    SupplierRepository(conn, logger).list_capabilities(status="active") if not row["missing_supplier"]}
    return types, suppliers, capabilities


def require_supplier(conn, operation, supplier_key, type_key, catalog=None):
    types, suppliers, capabilities = source_catalog(conn) if catalog is None else catalog
    supplier = suppliers.get(supplier_key)
    label = supplier["name"] if supplier else supplier_key
    prefix = "工序 {} 的供应商 {}".format(operation["seq"], label)
    if supplier is None or supplier["status"] != "active" or supplier["inactive_reason"] is not None:
        raise WorkbenchCommandRejected("supplier_unavailable", prefix + "未启用，请重新选择。", 422, operation_refs=[operation["ref"]])
    if type_key not in types or not supports_source(types[type_key]["category"], "external"):
        raise WorkbenchCommandRejected("source_category_mismatch", "工序 {} 请先选定有效外协工种。".format(operation["seq"]), 422,
                                       operation_refs=[operation["ref"]])
    if (supplier_key, type_key) not in capabilities:
        raise WorkbenchCommandRejected("supplier_capability_mismatch", prefix + "不能承接" + types[type_key]["name"] + "，请改选承接此工种的供应商。", 422,
                                       operation_refs=[operation["ref"]])
    return supplier


def _guard_rebound_hours(conn, changes, operations):
    old = {op["id"]: op for op in operations}
    refs = {old[key]["ref"]: None for _source, type_key, _supplier, key in changes
            if old[key]["op_type_id"] != type_key}
    if refs:
        protection = ProcessQuotaProtection(conn)
        if conn.in_transaction:
            protection.require_changes(refs)
        else:
            protection.check_changes(refs)


def prepare_source(conn, logger, payload, operations, identities):
    active = exact_operations(payload, operations)
    catalog = source_catalog(conn, logger)
    types = catalog[0]
    changes, affected, cache = [], set(), {}
    for row in payload["operations"]:
        old = active[row["ref"]]
        type_key = _related(identities, row["op_type_ref"], "op_type", cache)
        if type_key not in types or not supports_source(types[type_key]["category"], row["source"]):
            raise WorkbenchCommandRejected("source_category_mismatch", "所选工种类别必须匹配本序归属，不能通过本序操作修改全局工种类别。", 422)
        supplier_key = None
        if row["source"] == "external":
            supplier_key = _related(identities, row["supplier_ref"], "supplier", cache)
            require_supplier(conn, old, supplier_key, type_key, catalog)
        values = (row["source"], type_key, supplier_key)
        if values != (old["source"], old["op_type_id"], old["supplier_id"]):
            changes.append(values + (old["id"],))
            affected.add(old["seq"])
    _guard_rebound_hours(conn, changes, operations)
    return changes, affected


def apply_source(conn, changes, operations):
    repo = PartOperationRepository(conn)
    old_types = {op["id"]: op["op_type_id"] for op in operations}
    for source, type_key, supplier, key in changes:
        fields = {"source": source, "op_type_id": type_key, "supplier_id": supplier}
        if old_types[key] != type_key:
            fields.update(setup_hours=None, unit_hours=None, ext_days=None)
        repo.update_fields_by_id(key, fields)


def source_group_changes(changes, operations, groups):
    incoming = {row[3]: row[:3] for row in changes}
    changed_ids = set(incoming)
    affected, updates, by_group = [], [], {}
    for row in operations:
        if row["status"] == "active" and row["ext_group_id"] is not None:
            by_group.setdefault(row["ext_group_id"], []).append(row)
    for group in groups:
        members = by_group.get(group["group_id"], [])
        if not any(row["id"] in changed_ids for row in members):
            continue
        values = [incoming.get(row["id"], (row["source"], row["op_type_id"], row["supplier_id"])) for row in members]
        if any(row[0] != "external" for row in values):
            affected.append(group)
        elif len({row[2] for row in values}) != 1:
            raise WorkbenchCommandRejected("group_supplier_mismatch", "外协段 {} 至 {} 的供应商必须一致。请整段更换供应商，或先在工时定额页拆分外协段。".format(group["start_seq"], group["end_seq"]), 422,
                                           operation_refs=[row["ref"] for row in members])
        elif group["supplier_id"] != values[0][2]:
            updates.append((group["group_id"], values[0][2]))
    return affected, updates


def _merged_hours_groups(payload, active, groups):
    active_groups = {row["ext_group_id"] for row in active.values() if row["ext_group_id"] is not None}
    merged = {row["ref"]: row for row in groups if row["group_id"] in active_groups and row["merge_mode"] == "merged"}
    if set(merged) != {row["ref"] for row in payload["groups"]}:
        raise WorkbenchCommandRejected("group_set_mismatch", "必须完整提供当前有效合并外协组的总周期，不能包含逐序组或其他组。")
    return merged


def _hours_fields(row, old, merged_keys):
    expected = {"ref", "setup_hours", "unit_hours"} if old["source"] == "internal" else {"ref", "external_days"}
    if old["source"] not in ("internal", "external") or set(row) != expected:
        raise WorkbenchCommandRejected("hours_source_mismatch", "填的工时项要和这道工序已确认的归属对上。", 422)
    if old["source"] == "external" and old["ext_group_id"] in merged_keys:
        # The effective value is the group total. Preserve the member's prior value
        # as the starting point if the user later dissolves this stage.
        if row["external_days"] is not None and row["external_days"] != old["ext_days"]:
            raise WorkbenchCommandRejected("group_cycle_only", "工序 {} 使用整段外协周期，请修改外协段总周期；逐序旧周期不会参与当前排产。".format(old["seq"]), 422,
                                           operation_refs=[old["ref"]])
        return {}
    if "external_days" in row and row["external_days"] is None and old["ext_group_id"] not in merged_keys:
        raise WorkbenchCommandRejected("external_days_required", "不是合并组的外协工序必须填正数周期，不能留空。", 422)
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
        raise WorkbenchCommandRejected("stale_write", "原模板工序已经变了。请刷新后重新操作。")
    updates = _hours_updates(payload, active, merged)
    require_zero_confirmation(conn, [(active[row["ref"]], row) for row in payload["operations"]],
                              payload["confirm_zero_unit_hours"])
    changed = bool(updates)
    op_repo = PartOperationRepository(conn)
    group_repo = ExternalGroupRepository(conn)
    for key, fields in updates:
        op_repo.update_fields_by_id(key, fields)
    for row in payload["groups"]:
        old = merged[row["ref"]]
        if old["total_days"] != row["total_days"]:
            group_repo.set_total_days(old["group_id"], row["total_days"])
            changed = True
    return changed
