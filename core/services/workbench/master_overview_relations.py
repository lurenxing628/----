"""Batch requirements are explicit cross-page facts, never stock reservations."""

from .master_overview_graph import number, text

READY_TEXT = {"yes": "已齐套", "no": "未齐套"}


def batch_relations(graph):
    facts = graph.facts
    if not facts.available("Batches", "BatchMaterials"):
        for entity in graph.entities:
            if entity["domain"] in ("part", "material"):
                graph.unknown(entity, "批次物料关系", "Batches / BatchMaterials", relation=True)
        return
    batches = {}
    for row in facts.rows("Batches"):
        ref = facts.ref("batch", row["batch_id"])
        batches[row["batch_id"]] = {"key": "batch:" + ref, "ref": ref, "domain": "batch",
            "business_code": row["batch_id"], "label": row["part_name"] or "名称未填写", "relations": [],
            "target": {"view": "batches", "context": {"entity_ref": ref}}}
        part = graph.by_key.get(("part", row["part_no"]))
        if part:
            graph.link(part, batches[row["batch_id"]], "本零件的批次", "Batches.part_no")
    raw_batches = facts.index("Batches", "batch_id")
    for row in facts.rows("BatchMaterials"):
        material = graph.by_key.get(("material", row["material_id"]))
        batch = batches.get(row["batch_id"])
        if material is None or batch is None:
            if material:
                graph.issue(material, "batch_material.orphan", "物料需求批次不存在", "关联批次已不存在，请核对这条物料需求。")
                material["relations_complete"] = False
            else:
                facts.gaps.append({"code": "material_requirement_orphan", "source": "BatchMaterials.material_id",
                                   "message": "有物料需求关联的物料无法读取，请核对物料资料。"})
            continue
        graph.link(material, batch, "需求批次", "BatchMaterials.batch_id")
        part = graph.by_key.get(("part", raw_batches[row["batch_id"]]["part_no"]))
        graph.link(material, part, "需求批次对应零件", "BatchMaterials -> Batches.part_no", "批次需求物料")
        _requirement_fields(graph, material, row, batch)


def _requirement_fields(graph, entity, row, batch):
    code = batch["business_code"]
    evidence_key = batch["ref"] + ":" + str(row["id"])
    for key, label, positive in (("required_qty", "需求数量", True), ("available_qty", "到料数量", False)):
        value = row[key]
        graph.field(entity, code + " " + label, value, "BatchMaterials." + key, valid=number(value, positive))
        if not number(value, positive):
            item = graph.issue(entity, "batch_material." + key, "批次" + label + "待核对",
                               "批次 " + code + " 的" + label + "填的是" + text(value) + "。", action="核对批次物料需求", related_ref=evidence_key)
            item["target"] = batch["target"]
    graph.field(entity, code + " 齐套状态", READY_TEXT.get(row["ready_status"], row["ready_status"]), "BatchMaterials.ready_status", required=False)
    if number(row["required_qty"], True) and number(row["available_qty"]) and row["available_qty"] < row["required_qty"]:
        item = graph.issue(entity, "batch_material.pending", "批次到料记录不足",
                           "批次 " + code + " 需求 " + text(row["required_qty"]) + "，已到料 " + text(row["available_qty"]) + "；库存不算预留也不算到料。",
                           action="核对批次物料需求", related_ref=evidence_key)
        item["target"] = batch["target"]


def resource_profile_fields(graph):
    facts = graph.facts
    groups = facts.index("WorkbenchMachineGroups", "group_id")
    members = facts.index("WorkbenchMachineGroupMembers", "machine_id")
    for row in facts.rows("Machines"):
        entity = graph.by_key[("equipment", row["machine_id"])]
        if not facts.available("WorkbenchMachineGroups", "WorkbenchMachineGroupMembers"):
            graph.unknown(entity, "设备组", "WorkbenchMachineGroups / WorkbenchMachineGroupMembers")
            continue
        member = members.get(row["machine_id"])
        group = groups.get(member["group_id"]) if member else None
        graph.field(entity, "设备组", group["name"] if group else None,
                    "WorkbenchMachineGroupMembers -> WorkbenchMachineGroups.name", required=False)
        if member and group is None:
            graph.issue(entity, "machine.group_missing", "设备组记录缺失", "设备组已不存在，请重新选择。")
