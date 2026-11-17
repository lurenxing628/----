"""Shared fixed dependency catalog for single and bulk resource deletion."""

import json
from typing import NamedTuple


class Dependency(NamedTuple):
    """删除前要数的一类引用：``name`` 是公开计数名（详情里 ``relationships.counts`` 的键），``table.column`` 指向这条资源。"""

    name: str
    table: str
    column: str

    @property
    def source(self) -> str:
        """引用证据（``references_many``）里这一类的键。"""
        return self.table + "." + self.column


DEPENDENCIES = {
    "op_type": (Dependency("machine_capabilities", "MachineOpTypes", "op_type_id"),
                Dependency("skills", "OperatorSkill", "op_type_id"),
                Dependency("supplier_capabilities", "WorkbenchSupplierOpTypes", "op_type_id"),
                Dependency("part_operations", "PartOperations", "op_type_id"),
                Dependency("batch_operations", "BatchOperations", "op_type_id")),
    "machine": (Dependency("batch_operations", "BatchOperations", "machine_id"),
                Dependency("schedule", "Schedule", "machine_id"),
                Dependency("OperatorMachine.machine_id", "OperatorMachine", "machine_id"),
                Dependency("MachineDowntimes.machine_id", "MachineDowntimes", "machine_id"),
                Dependency("WorkbenchProductionReportRevisions.actual_machine_ref",
                           "WorkbenchProductionReportRevisions", "actual_machine_ref")),
    "operator": (Dependency("batch_operations", "BatchOperations", "operator_id"),
                 Dependency("schedule", "Schedule", "operator_id"),
                 Dependency("OperatorMachine.operator_id", "OperatorMachine", "operator_id"),
                 Dependency("OperatorCalendar.operator_id", "OperatorCalendar", "operator_id"),
                 Dependency("WorkbenchProductionReportRevisions.actual_operator_ref",
                            "WorkbenchProductionReportRevisions", "actual_operator_ref")),
    "supplier": (Dependency("part_operations", "PartOperations", "supplier_id"),
                 Dependency("batch_operations", "BatchOperations", "supplier_id"),
                 Dependency("external_groups", "ExternalGroups", "supplier_id")),
}


def counted_references(kind, references):
    """一条资源已读出的引用证据（``references_many`` 的一项）按公开计数名数条数，与 ``assigned_counts`` 同形。"""
    return {dependency.name: len(references[dependency.source]) for dependency in DEPENDENCIES[kind]}


def report_reference_counts(conn, kind, key, codes_json):
    rows = conn.execute(
        f"""SELECT e.entity_key AS code, COUNT(*) AS amount
            FROM WorkbenchEntityRefs e
            JOIN WorkbenchProductionReports p
              ON p.voided = 0 AND p.{key} IS NOT NULL AND p.{key} = e.ref
            WHERE e.active = 1 AND e.kind = ?
              AND e.entity_key IN (SELECT value FROM json_each(?))
            GROUP BY e.entity_key""",
        (kind, codes_json),
    ).fetchall()
    return {row["code"]: row["amount"] for row in rows}


def report_revision_rows(conn, kind, key, codes_json):
    """有报工引用的资源编号到报工头行；没有引用的编号不出现。"""
    grouped = {}
    ref_rows = conn.execute(
        """SELECT ref, entity_key FROM WorkbenchEntityRefs
           WHERE active = 1 AND kind = ? AND entity_key IN (SELECT value FROM json_each(?))
           ORDER BY entity_key, ref""",
        (kind, codes_json),
    ).fetchall()
    ref_to_code = {row["ref"]: row["entity_key"] for row in ref_rows}
    if not ref_to_code:
        return grouped
    reports = conn.execute(
        f"""SELECT report_ref, current_revision_ref AS revision_ref, revision_count,
                   operation_ref, {key}
            FROM WorkbenchProductionReports
            WHERE voided = 0 AND {key} IS NOT NULL
              AND {key} IN (SELECT value FROM json_each(?))
            ORDER BY report_ref""",
        (json.dumps(list(ref_to_code)),),
    ).fetchall()
    for row in reports:
        grouped.setdefault(ref_to_code[row[key]], []).append(dict(row))
    return grouped
