"""Immutable trial scope shared by delivery, operation views and saved archives."""

from collections import defaultdict

from core.models.workbench_command import canonical_json
from core.models.workbench_trial import reject
from core.services.workbench.facts.candidate_facts import GenerationFacts
from core.services.workbench.facts.material_deferral_evidence import archived_deferred_operation_evidence
from core.services.workbench.facts.preflight_dependencies import material_deferred_ids


def delivery_origin(admission, rows, facts=None):
    source = admission["source"]
    if "capture" in source:
        capture = source["capture"]
        facts = facts if facts is not None else GenerationFacts(capture)
        selected = set(capture["input"]["batch_refs"])
        batches = {ref: facts.tables["Batches"][key] for (kind, key), ref in facts.entity_refs.items()
                   if kind == "batch" and ref in selected}
        operations = facts.tables["BatchOperations"].values()
        deferred = material_deferred_ids((source.get("dispositions") or {}).values(), capture["input"])
        deferred_issues = []
    else:
        batches = {row["original"]["batch_ref"]: row["original"]["batch"] for row in rows}
        operations = admission["facts"]["tables"]["BatchOperations"]
        if "deferred_operation_ids" in source:
            deferred, deferred_issues = set(source["deferred_operation_ids"]), source["deferred_operation_issues"]
        else:
            version = source.get("identity", {}).get("version")
            history = [row for row in admission["facts"]["tables"].get("ScheduleHistory", []) if row["version"] == version]
            summary = (history[0]["result_summary"] if len(history) == 1
                       else canonical_json({"material_policy": source.get("material_policy", {})}))
            deferred, deferred_issues = archived_deferred_operation_evidence({"summary": summary})
        selected = {batch["batch_id"] for batch in batches.values()}
        pending = {operation["batch_id"] for operation in operations if operation["id"] in deferred} - selected
        if pending:
            tables = admission["facts"]["tables"]
            batch_rows = {batch["batch_id"]: batch for batch in tables["Batches"]}
            refs = {item["entity_key"]: item["ref"] for item in tables["WorkbenchEntityRefs"]
                    if item["kind"] == "batch" and item["active"] == 1}
            for batch_id in sorted(pending):
                if batch_id not in batch_rows or batch_id not in refs:
                    reject("trial_snapshot_invalid", "保存来源中待料批次的资料或永久编号缺失，请核对保存记录。")
                batches[refs[batch_id]] = batch_rows[batch_id]
    by_batch = defaultdict(list)
    for operation in operations:
        by_batch[operation["batch_id"]].append(dict(operation, op_id=operation["id"]))
    return batches, by_batch, deferred, deferred_issues


def operation_contexts(rows, admission, facts=None, *, origin=None):
    """Bind original arrangements to every operation in this source's batches."""
    source = admission["source"]
    if "capture" in source:
        facts = facts if facts is not None else GenerationFacts(source["capture"])
        operations = facts.tables["BatchOperations"]
        refs = {op_id: ref for ref, op_id in facts.operations.items()}
        execution = facts.execution
    else:
        tables = admission["facts"]["tables"]
        operations = {row["id"]: row for row in tables["BatchOperations"]}
        refs = {int(row["source_key"]): row["ref"] for row in tables["WorkbenchPlanSourceRefs"]
                if row["kind"] == "operation" and row["active"] == 1}
        execution = admission["execution"]
    batches, by_batch, deferred, _issues = delivery_origin(admission, rows, facts) if origin is None else origin
    result = {row["operation_ref"]: {"operation": row["original"]["operation"],
        "execution": row["original"].get("execution") or {}, "batch_ref": row["original"]["batch_ref"],
        "batch": row["original"]["batch"], "row": row, "arranged": True,
        "deferred": row["original"]["operation"]["id"] in deferred} for row in rows}
    for batch_ref, batch in batches.items():
        for item in by_batch[batch["batch_id"]]:
            op = operations[item["id"]]
            ref = refs.get(op["id"])
            if ref is None:
                reject("trial_snapshot_invalid", "保存来源中的工序永久编号缺失，请核对保存记录。")
            if ref not in result:
                result[ref] = {"operation": op, "execution": execution.get(ref, {}),
                    "batch_ref": batch_ref, "batch": batch, "arranged": False,
                    "deferred": op["id"] in deferred}
    for ref, context in result.items():
        disposition = (source.get("dispositions") or {}).get(ref)
        if disposition is not None:
            context["disposition"] = disposition
    return result
