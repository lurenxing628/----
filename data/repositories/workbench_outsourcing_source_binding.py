"""Resolve current batch relations without manufacturing historical birth records."""

from core.models.workbench_outsourcing import reject


def resolve_source_binding(conn, operation_ref, origin, batch_ref):
    confirmation = conn.execute(
        "SELECT * FROM WorkbenchOutsourcingSourceConfirmations WHERE operation_ref=?", (operation_ref,)).fetchone()
    if confirmation is not None:
        valid = conn.execute("""SELECT 1 FROM WorkbenchOutsourcingMembers m
            JOIN WorkbenchOutsourcingReceipts r ON r.outsourcing_ref=m.outsourcing_ref
            JOIN WorkbenchOutsourcingFacts f ON f.outsourcing_ref=r.outsourcing_ref
            WHERE m.operation_ref=? AND r.batch_ref=? AND f.fact_ref=? AND f.sequence=1""",
            (operation_ref, confirmation["batch_ref"], confirmation["fact_ref"])).fetchone()
        if origin["batch_ref"] is not None or valid is None:
            reject("工序的来源确认与原外协登记不一致，请核对原登记。", "identity_drift", 409)
    if origin["batch_ref"] is not None:
        resolved_ref, basis = origin["batch_ref"], "birth_record"
    elif confirmation is not None:
        resolved_ref, basis = confirmation["batch_ref"], "registration_confirmation"
    else:
        if conn.execute("SELECT 1 FROM WorkbenchOutsourcingMembers WHERE operation_ref=?", (operation_ref,)).fetchone():
            reject("已有外协登记缺少原批次的确认记录，请先核对原登记。", "identity_missing", 409)
        resolved_ref, basis = batch_ref, "current_relation"
    if resolved_ref != batch_ref:
        reject("工序所属批次实例已变化，请核对批次与工序关联。", "identity_drift", 409)
    return {"batch_ref": resolved_ref, "confirmation": dict(confirmation) if confirmation is not None else None,
            "source_resolution": {"basis": basis, "confirmation_ref": confirmation["fact_ref"] if confirmation is not None else None}}


def source_resolution(operations):
    resolutions = [op["binding"]["source_resolution"] for op in operations]
    basis = ("current_relation" if any(item["basis"] == "current_relation" for item in resolutions)
             else "registration_confirmation" if any(item["basis"] == "registration_confirmation" for item in resolutions)
             else "birth_record")
    refs = {item["confirmation_ref"] for item in resolutions if item["confirmation_ref"] is not None}
    if len(refs) > 1:
        reject("所选工序已分别登记，不能合成另一条登记。", "constraint_conflict", 409)
    return {"basis": basis, "confirmation_ref": next(iter(refs)) if refs else None}
