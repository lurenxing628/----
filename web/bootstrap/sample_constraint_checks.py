"""Independent checks of the sample's complete public candidate rows.

The product's adoption preview remains the authority for real calendar,
efficiency, downtime and execution constraints. These checks compare the
returned HTTP rows with the injected business inputs; they never write a plan.
"""

from collections import Counter, defaultdict
from datetime import datetime, timedelta


def require(value, message):
    if not value:
        raise RuntimeError(message)


def _resource_ref(task, kind):
    resource = task[kind]
    return resource["ref"] if resource is not None else None


def _candidate_inputs(workspace, seed, preflight):
    blueprint = seed["blueprint"]
    tasks = workspace["tasks"]
    expected = {ref for operations in seed["operation_refs"].values() for ref in operations.values()}
    by_ref = {row["operation_ref"]: row for row in tasks}
    require(workspace["tasks_complete"] is True, "候选没有返回完整工序范围。")
    require(len(tasks) == len(by_ref) == len(expected) and set(by_ref) == expected,
            "候选工序与样例注入范围不一致，不能把部分排完写成完整验收。")
    require(workspace["unplanned_operation_count"] == 0, "可行样例仍有未排工序。")
    require(workspace["candidate"]["completeness"] == "complete", "候选完整性未确认。")
    parts = {row["business_code"]: row for row in blueprint["parts"]}
    machines = {seed["refs"]["machine"][row["business_code"]]: row
                for row in blueprint["resources"]["machines"]}
    operators = {seed["refs"]["operator"][row["business_code"]]: row
                 for row in blueprint["resources"]["operators"]}
    permissions = {(seed["refs"]["operator"][row["operator_code"]], seed["refs"]["machine"][machine])
                   for row in blueprint["operator_machine_permissions"] for machine in row["machine_codes"]}
    input_tasks = {row["operation_ref"]: row for row in preflight["tasks"]}
    window = blueprint["schedule_window"]
    low = datetime.fromisoformat(window["start_date"])
    high = datetime.fromisoformat(window["end_date"]) + timedelta(days=1)
    return tasks, by_ref, parts, machines, operators, permissions, input_tasks, (low, high)


def _check_task_identity_and_release(task, operation, fields, batch_ref, bounds, input_tasks):
    start, end = datetime.fromisoformat(task["start"]), datetime.fromisoformat(task["end"])
    low, high = bounds
    require(low <= start < end <= high, "候选有工序时间超出样例窗口或时长不成立。")
    require(task["batch_ref"] == batch_ref and task["sequence"] == operation["seq"]
            and task["quantity"] == fields["quantity"], "候选批次、工序顺序或数量与真实注入资料不一致。")
    require(task["source"] == operation["source"], "候选工序归属与真实工艺不一致。")
    require(task["due_date"] == fields["due_date"], "候选交期没有保留原批次交期。")
    material_checks = 0
    captured = input_tasks[task["operation_ref"]]
    release = captured.get("material_ready_date")
    if release:
        require(start >= datetime.fromisoformat(release), "候选安排早于预检确认的物料放行日期。")
        material_checks = 1
    if fields.get("ready_date"):
        require(start >= datetime.fromisoformat(fields["ready_date"]), "候选安排早于批次齐套日期。")
    return start, end, material_checks


def _check_predecessor(task, start, sequence, previous, group_by_seq):
    if previous is None:
        return 0
    prior_seq, prior_task = previous
    same_group = sequence in group_by_seq and group_by_seq.get(prior_seq) == group_by_seq[sequence]
    if same_group:
        require((task["start"], task["end"]) == (prior_task["start"], prior_task["end"]),
                "合并外协成员没有使用同一真实周期。")
    else:
        require(start >= datetime.fromisoformat(prior_task["end"]), "候选后道早于前道完工。")
    return 1


def _check_resources(task, operation, seed, machines, operators, permissions, occupied, start, end):
    machine, operator = _resource_ref(task, "machine"), _resource_ref(task, "operator")
    if operation["source"] == "internal":
        require(machine in machines and operator in operators, "自制工序没有真实设备或人员。")
        op_type = operation["op_type_code"]
        require(op_type in machines[machine]["relationships"]["op_type_codes"], "设备工种不匹配。")
        require(op_type in operators[operator]["relationships"]["skill_codes"], "人员技能不匹配。")
        require((operator, machine) in permissions, "人员没有对应设备操作关系。")
        for kind, ref in (("machine", machine), ("operator", operator)):
            occupied[kind, ref].append((start, end, task["operation_ref"]))
        return 1
    require(machine is None and operator is None, "外协工序占用了内部设备或人员。")
    require(_resource_ref(task, "supplier") == seed["refs"]["supplier"][operation["supplier_code"]],
            "外协供应商没有保留实际工艺来源。")
    return 0


def _check_resource_nonoverlap(occupied):
    overlap_checks = 0
    for (kind, ref), spans in occupied.items():
        spans.sort()
        for first, second in zip(spans, spans[1:]):
            require(first[1] <= second[0], f"{kind}资源{ref}发生工序重叠：{first[2]} / {second[2]}。")
            overlap_checks += 1
    return overlap_checks


def check_candidate(workspace, seed, preflight):
    blueprint = seed["blueprint"]
    tasks, by_ref, parts, machines, operators, permissions, input_tasks, bounds = _candidate_inputs(workspace, seed, preflight)
    occupied = defaultdict(list)
    merges, material_checks, chain_checks, qualifications = 0, 0, 0, 0
    priorities = Counter()
    for batch in blueprint["batches"]:
        code, fields = batch["business_code"], batch["fields"]
        sequence_refs = {int(sequence): ref for sequence, ref in seed["operation_refs"][code].items()}
        part = parts[batch["part_code"]]
        group_by_seq = {sequence: index for index, group in enumerate(part["groups"])
                        for sequence in group["sequences"]}
        priorities[fields["priority"]] += 1
        previous = None
        for operation in part["operations"]:
            sequence = operation["seq"]
            task = by_ref[sequence_refs[sequence]]
            start, end, release_checks = _check_task_identity_and_release(
                task, operation, fields, seed["refs"]["batch"][code], bounds, input_tasks)
            material_checks += release_checks
            chain_checks += _check_predecessor(task, start, sequence, previous, group_by_seq)
            previous = sequence, task
            qualifications += _check_resources(task, operation, seed, machines, operators, permissions, occupied, start, end)
        for group in part["groups"]:
            members = [by_ref[sequence_refs[seq]] for seq in group["sequences"]]
            require(len({(row["start"], row["end"]) for row in members}) == 1, "外协连续组被拆开。")
            merges += 1
    overlap_checks = _check_resource_nonoverlap(occupied)
    return {"scope_complete": True, "operation_count": len(tasks), "batch_count": len(blueprint["batches"]),
            "source_counts": dict(Counter(row["source"] for row in tasks)),
            "qualified_internal_tasks": qualifications, "precedence_checks": chain_checks,
            "merged_external_cycles": merges, "material_release_checks": material_checks,
            "resource_nonoverlap_checks": overlap_checks, "machine_count": len({key[1] for key in occupied if key[0] == "machine"}),
            "operator_count": len({key[1] for key in occupied if key[0] == "operator"}), "priority_counts": dict(priorities),
            "calendar_days": len(blueprint["calendar_days"]),
            "personal_calendar_days": len(blueprint["operator_calendar_days"]),
            "machine_downtimes": len(blueprint["machine_downtimes"]),
            "calendar_downtime_duration_authority": "complete production candidate adopt-preview, not an approximate second calendar"}
