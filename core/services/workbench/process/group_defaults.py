"""Apply resource defaults only to newly introduced outsourcing operations."""

import math
from uuid import uuid4

from core.models.resource_capabilities import supports_source
from data.repositories.external_group_repo import ExternalGroupRepository
from data.repositories.part_operation_repo import PartOperationRepository
from data.repositories.supplier_repo import SupplierRepository
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository
from data.repositories.workbench_process_workflow_repo import WorkbenchProcessWorkflowRepository


def create_group(conn, part_no, members, supplier_id, total_days):
    group_id = "WB-" + uuid4().hex
    ExternalGroupRepository(conn).create({"group_id": group_id, "part_no": part_no,
        "start_seq": members[0]["seq"], "end_seq": members[-1]["seq"], "merge_mode": "merged",
        "total_days": total_days, "supplier_id": supplier_id})
    repo = PartOperationRepository(conn)
    for row in members:
        repo.update(part_no, row["seq"], {"ext_group_id": group_id})
    return group_id


def _default_suppliers(conn):
    capability_rows = SupplierRepository(conn).list_capabilities(status="active")
    suppliers = {row["supplier_id"]: row for row in capability_rows
                 if not row["missing_supplier"]}
    capabilities = {(row["supplier_id"], row["op_type_id"]) for row in capability_rows if not row["missing_supplier"]}
    available = {row["supplier_id"] for row in WorkbenchProcessQueryRepository(conn).supplier_status_rows()
                 if row["status"] == "active" and row["inactive_reason"] is None}
    return suppliers, capabilities, available


def _uses_merged_default(row, eligible, suppliers, capabilities, available):
    supplier = suppliers.get(row["supplier_id"])
    days = supplier["default_days"] if supplier else None
    return (row["seq"] in eligible and row["source"] == "external" and supports_source(row["category"], "external")
            and row["ext_group_id"] is None and row["default_merge_mode"] == "merged"
            and row["supplier_id"] in available
            and (row["supplier_id"], row["op_type_id"]) in capabilities
            and isinstance(days, (int, float)) and not isinstance(days, bool) and math.isfinite(days) and days > 0)


def apply_default_groups(conn, part_no, operation_sequences):
    """Group only consecutive new eligible rows; one supplier cycle per stage."""
    eligible = set(operation_sequences)
    if not eligible:
        return False
    rows = WorkbenchProcessWorkflowRepository(conn).active_operations(part_no)
    suppliers, capabilities, available = _default_suppliers(conn)
    segments, segment = [], []
    for row in rows:
        usable = _uses_merged_default(row, eligible, suppliers, capabilities, available)
        if segment and (not usable or segment[-1]["supplier_id"] != row["supplier_id"]):
            segments.append(segment)
            segment = []
        if usable:
            segment.append(row)
    if segment:
        segments.append(segment)
    for members in segments:
        supplier_id = members[0]["supplier_id"]
        create_group(conn, part_no, members, supplier_id, suppliers[supplier_id]["default_days"])
    return bool(segments)
