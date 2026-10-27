"""Shared fixed dependency catalog for single and bulk resource deletion."""

from collections import defaultdict

from .workbench_execution_repo import stored_report_values

DEPENDENCIES = {
    "op_type": (("Machines", "op_type_id"), ("MachineOpTypes", "op_type_id"), ("OperatorSkill", "op_type_id"),
                ("WorkbenchSupplierOpTypes", "op_type_id"), ("PartOperations", "op_type_id"), ("BatchOperations", "op_type_id")),
    "machine": (("BatchOperations", "machine_id"), ("Schedule", "machine_id"), ("OperatorMachine", "machine_id"),
                ("MachineDowntimes", "machine_id"), ("WorkbenchProductionReportRevisions", "actual_machine_ref")),
    "operator": (("BatchOperations", "operator_id"), ("Schedule", "operator_id"), ("OperatorMachine", "operator_id"),
                 ("OperatorCalendar", "operator_id"), ("WorkbenchProductionReportRevisions", "actual_operator_ref")),
    "supplier": (("PartOperations", "supplier_id"), ("BatchOperations", "supplier_id"), ("ExternalGroups", "supplier_id")),
}


def report_revision_rows(conn, kind, key, codes=None, *, identities=None):
    base_where = """WHERE NOT EXISTS (
            SELECT 1 FROM WorkbenchProductionReportRevisions later
            WHERE later.report_ref = v.report_ref AND later.sequence > v.sequence
        )
        AND NOT EXISTS (
            SELECT 1 FROM WorkbenchProductionReportVoids void
            WHERE void.report_ref = v.report_ref
        )"""
    if codes is None:
        revisions = conn.execute(
            f"""SELECT v.* FROM WorkbenchProductionReportRevisions v
            {base_where}
            AND instr(v.values_json, ?) > 0 AND instr(v.values_json, ?) = 0
            ORDER BY v.report_ref, v.sequence""",
            (f'"{key}"', f'"{key}":null'),
        ).fetchall()
        if not revisions:
            return {}
        if identities is not None:
            ref_to_code = {row["ref"]: row["entity_key"] for row in identities if row["kind"] == kind and row["active"]}
        else:
            ref_rows = conn.execute(
                "SELECT ref, entity_key FROM WorkbenchEntityRefs WHERE active=1 AND kind=? ORDER BY entity_key, ref",
                (kind,),
            ).fetchall()
            ref_to_code = {row["ref"]: row["entity_key"] for row in ref_rows}
        grouped = defaultdict(list)
        for row in revisions:
            ref = stored_report_values(row["values_json"]).get(key)
            if ref in ref_to_code:
                grouped[ref_to_code[ref]].append(dict(row))
        return dict(grouped)
    unique_codes = sorted(set(codes))
    grouped = {code: [] for code in codes}
    if not unique_codes:
        return dict(grouped)
    ref_rows = []
    for start in range(0, len(unique_codes), 400):
        chunk = unique_codes[start : start + 400]
        marks = ",".join("?" for _ in chunk)
        ref_rows.extend(
            conn.execute(
                f"SELECT ref, entity_key FROM WorkbenchEntityRefs WHERE active=1 AND kind=? AND entity_key IN ({marks}) ORDER BY entity_key, ref",
                [kind] + chunk,
            ).fetchall()
        )
    ref_to_code = {row["ref"]: row["entity_key"] for row in ref_rows}
    if not ref_to_code:
        return dict(grouped)
    refs = sorted(ref_to_code)
    for start in range(0, len(refs), 200):
        ref_chunk = refs[start : start + 200]
        chunk_set = set(ref_chunk)
        ref_filter = " OR ".join("instr(v.values_json, ?) > 0" for _ in ref_chunk)
        revisions = conn.execute(
            f"""SELECT v.* FROM WorkbenchProductionReportRevisions v
            {base_where}
            AND ({ref_filter})
            ORDER BY v.report_ref, v.sequence""",
            ref_chunk,
        ).fetchall()
        for row in revisions:
            ref = stored_report_values(row["values_json"]).get(key)
            if ref in chunk_set:
                grouped[ref_to_code[ref]].append(dict(row))
    return dict(grouped)
