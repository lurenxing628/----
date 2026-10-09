"""Deterministic data for the isolated complex scheduling sample.

This module does not open a database or write a plan.  The injector resolves
business codes to the real references returned by the normal workbench APIs.
Only a successful scheduler run supplies planned times and resource choices.
Report requests below select operations; they are not invented execution facts.
"""

from datetime import date, timedelta

_INTERNAL_NAMES = ("车削", "铣削", "钻孔", "磨削", "镗孔", "线切割", "装配", "精整")
_EXTERNAL_NAMES = ("热处理", "电镀", "检验")
_GROUP_SKILLS = ((0, 4), (1, 2), (3, 7), (4, 2), (5, 3), (6, 7))
_GROUP_NAMES = ("车镗", "铣钻", "磨整", "镗钻", "线磨", "装配精整")
_DAY_PERIODS = (("08:00", "12:00", 0), ("13:00", "17:00", 0))
_NIGHT_PERIODS = (("20:00", "00:00", 0), ("00:30", "04:30", 1))


def _periods(rows):
    return [{"start": start, "end": end, "day_offset": offset}
            for start, end, offset in rows]


def _op_code(index):
    return f"CS-OP-{index + 1:02d}"


def _calendar_fields(kind="work", *, urgent_only=False, efficiency=100):
    if kind == "rest":
        return {"type": "rest", "hours": 0, "eff": efficiency,
                "allowNormal": "no", "allowUrgent": "no", "periods": [],
                "shiftStart": "00:00", "shiftEnd": "00:00", "note": "复杂样例休息日"}
    return {"type": "work", "hours": 16, "eff": efficiency,
            "allowNormal": "no" if urgent_only else "yes", "allowUrgent": "yes",
            "periods": _periods(_DAY_PERIODS + _NIGHT_PERIODS),
            "shiftStart": "08:00", "shiftEnd": "04:30", "note": "复杂样例两班制"}


def _shift_profile(code, label, periods, anchor):
    pattern = []
    for offset in range(7):
        rest = (anchor.weekday() + offset) % 7 >= 5
        pattern.append({"day_offset": offset, "is_rest": rest,
                        "shift_start": periods[0][0], "shift_end": periods[-1][1],
                        "periods": [] if rest else _periods(periods)})
    return {"business_code": code, "label": label,
            "fields": {"status": "active", "remark": "复杂样例周一至周五轮班",
                       "anchor_date": anchor.isoformat(), "cycle_days": 7, "pattern": pattern},
            "relationships": {}}


def _resources(anchor):
    op_types = []
    for index, name in enumerate(_INTERNAL_NAMES + _EXTERNAL_NAMES):
        external = index >= len(_INTERNAL_NAMES)
        op_types.append({"business_code": _op_code(index), "label": name,
                         "fields": {"category": "external" if external else "internal",
                                    "default_merge_mode": "merged" if external else None,
                                    "remark": "复杂样例工种"}, "relationships": {}})
    groups, machines = [], []
    for group_index, (name, skills) in enumerate(zip(_GROUP_NAMES, _GROUP_SKILLS)):
        group_code = f"CS-GROUP-{group_index + 1:02d}"
        groups.append({"business_code": group_code, "label": "样例" + name + "组",
                       "fields": {"status": "active", "remark": "复杂样例可替代设备组"},
                       "relationships": {}})
        for member_index, suffix in enumerate("甲乙丙丁"):
            machine_number = group_index * 4 + member_index + 1
            machines.append({"business_code": f"CS-MACHINE-{machine_number:02d}",
                             "label": "样例" + name + "设备" + suffix,
                             "fields": {"status": "active", "category": name,
                                        "remark": "复杂样例多工种设备；真实停机影响可用时段"},
                             "relationships": {"op_type_codes": [_op_code(skill) for skill in skills],
                                               "group_code": group_code}})
    operators = []
    for index in range(16):
        base = index % 8
        operators.append({"business_code": f"CS-PERSON-{index + 1:02d}",
                          "label": "样例人员" + "甲乙丙丁戊己庚辛壬癸子丑寅卯辰巳"[index],
                          "fields": {"status": "active", "remark": "复杂样例跨设备共享人员"},
                          "relationships": {"skill_codes": [_op_code(skill) for skill in
                                                            (base, (base + 1) % 8, (base + 3) % 8)],
                                            "shift_profile_code": "CS-SHIFT-DAY" if index < 8 else "CS-SHIFT-NIGHT"}})
    suppliers = []
    for index, suffix in enumerate("甲乙丙"):
        suppliers.append({"business_code": f"CS-SUPPLIER-{index + 1:02d}",
                          "label": "样例综合外协" + suffix,
                          "fields": {"status": "active", "default_days": 1.0 + index * 0.5,
                                     "remark": "复杂样例热处理、电镀、检验多能力供应商"},
                          "relationships": {"op_type_codes": [_op_code(skill) for skill in (8, 9, 10)]}})
    materials = [{"business_code": f"CS-MATERIAL-{index + 1:02d}",
                  "label": "样例原料" + name,
                  "fields": {"status": "active", "spec": spec, "unit": "件",
                             "stock_qty": 240 + index * 60, "remark": "复杂样例物料，包含分次到料"}}
                 for index, (name, spec) in enumerate((("合金钢", "钢棒"), ("铝材", "板材"),
                                                      ("铜材", "铜棒"), ("铸件", "毛坯"), ("紧固件", "组件")))]
    return {"op_types": op_types, "machine_groups": groups,
            "shift_profiles": [_shift_profile("CS-SHIFT-DAY", "样例白班", _DAY_PERIODS, anchor),
                               _shift_profile("CS-SHIFT-NIGHT", "样例跨午夜夜班", _NIGHT_PERIODS, anchor)],
            "machines": machines, "operators": operators, "suppliers": suppliers, "materials": materials}


def _parts(part_count, operation_count):
    first = operation_count // 3
    second = operation_count * 2 // 3
    names = ("阶梯轴", "异形板", "精密套", "法兰盘", "连接座", "导向块", "齿轮坯", "模具芯", "阀体", "装配框")
    parts = []
    for part_index in range(part_count):
        operations, groups = [], []
        external = {}
        for stage_index, start in enumerate((first, second)):
            supplier = f"CS-SUPPLIER-{(part_index + stage_index) % 3 + 1:02d}"
            sequences = [start, start + 1]
            groups.append({"sequences": sequences, "supplier_code": supplier,
                           "merge_mode": "merged", "total_days": 1.0 + ((part_index + stage_index) % 4) * 0.5})
            for member_index, seq in enumerate(sequences):
                external[seq] = (8 + (part_index + stage_index + member_index) % 3, supplier)
        for seq in range(1, operation_count + 1):
            if seq in external:
                op_index, supplier = external[seq]
                operation = {"seq": seq, "op_type_code": _op_code(op_index), "source": "external",
                             "supplier_code": supplier, "setup_hours": None, "unit_hours": None,
                             "external_days": None}
            else:
                op_index = (seq - 1 + part_index * 3) % 8
                operation = {"seq": seq, "op_type_code": _op_code(op_index), "source": "internal",
                             "supplier_code": None, "setup_hours": round(0.08 + ((seq + part_index) % 5) * 0.05, 3),
                             "unit_hours": round(0.018 + ((seq * 3 + part_index) % 7) * 0.004, 3),
                             "external_days": None}
            operations.append(operation)
        parts.append({"business_code": f"CS-PART-{part_index + 1:02d}",
                      "label": "复杂样例" + names[part_index],
                      "remark": "独立复杂样例：顺序依赖、装夹工时、两段连续合并外协",
                      "route_raw": "；".join("{}: {}".format(row["seq"],
                                          (_INTERNAL_NAMES + _EXTERNAL_NAMES)[int(row["op_type_code"][-2:]) - 1])
                                          for row in operations),
                      "operations": operations, "groups": groups})
    return parts


def _batches(batch_count, parts, start):
    batches = []
    material_count = min(20, batch_count)
    for index in range(batch_count):
        quantity = 8 + (index * 7) % 23
        release_offset = (index % 7) * 2
        material_rows = []
        if index < material_count:
            required = quantity * (1 + index % 2)
            available = required if index % 4 == 0 else required // 3
            remaining = required - available
            arrivals = []
            if remaining:
                first_quantity = max(1, remaining // 2)
                arrivals.append({"arrival_date": (start + timedelta(days=release_offset + 2)).isoformat(),
                                 "quantity": first_quantity})
                if remaining > first_quantity:
                    arrivals.append({"arrival_date": (start + timedelta(days=release_offset + 5)).isoformat(),
                                     "quantity": remaining - first_quantity})
            material_rows.append({"material_code": f"CS-MATERIAL-{index % 5 + 1:02d}",
                                  "required_quantity": required, "available_quantity": available,
                                  "operation_seq": 1 if index % 2 == 0 else min(7, len(parts[index % len(parts)]["operations"])),
                                  "arrivals": arrivals})
        partial = bool(material_rows and material_rows[0]["available_quantity"] < material_rows[0]["required_quantity"])
        ready_offset = release_offset + (5 if partial else 0)
        priority = "critical" if index % 17 == 0 else "urgent" if index % 7 == 0 else "normal"
        batches.append({"business_code": f"CS-BATCH-{index + 1:03d}",
                        "part_code": parts[index % len(parts)]["business_code"],
                        "fields": {"quantity": quantity,
                                   "due_date": (start + timedelta(days=32 + index % 40)).isoformat(),
                                   "priority": priority, "ready_status": "partial" if partial else "yes",
                                   "ready_date": (start + timedelta(days=ready_offset)).isoformat(),
                                   "remark": "[复杂样例] 独立数据；含交期、加急、齐套及分次到料"},
                        "materials": material_rows, "operation_overrides": []})
    return batches


def _calendars(start, end):
    holidays = {(start + timedelta(days=offset)).isoformat() for offset in (14, 30, 45, 74)}
    overtime_day = start + timedelta(days=(5 - start.weekday()) % 7)
    days = []
    for offset in range((end - start).days + 1):
        day = start + timedelta(days=offset)
        fields = _calendar_fields("rest" if day.weekday() >= 5 or day.isoformat() in holidays else "work")
        if day == overtime_day:
            fields = _calendar_fields(urgent_only=True, efficiency=80)
            fields["note"] = "复杂样例周六仅急件；个人日历安排部分人员加班"
        days.append({"date": day.isoformat(), "fields": fields})
    personal = []
    for index in range(16):
        leave_day = start + timedelta(days=7 + index % 5 + (index // 8) * 7)
        while leave_day.weekday() >= 5:
            leave_day += timedelta(days=1)
        personal.append({"operator_code": f"CS-PERSON-{index + 1:02d}",
                         "date": leave_day.isoformat(),
                         "fields": {"type": "rest", "eff": 100, "allowNormal": "no", "allowUrgent": "no",
                                    "periods": [], "shiftStart": "08:00", "note": "复杂样例人员请假"}})
    for index in (0, 3, 8, 11):
        periods = _DAY_PERIODS if index < 8 else _NIGHT_PERIODS
        personal.append({"operator_code": f"CS-PERSON-{index + 1:02d}", "date": overtime_day.isoformat(),
                         "fields": {"type": "work", "eff": 90, "allowNormal": "no", "allowUrgent": "yes",
                                    "shiftStart": periods[0][0], "shiftEnd": periods[-1][1],
                                    "periods": _periods(periods), "note": "复杂样例周六急件加班"}})
    return days, personal


def _downtimes(resources, start):
    rows = []
    for index, machine in enumerate(resources["machines"]):
        day = start + timedelta(days=1 + index % 4)
        night = index % 3 == 0
        rows.append({"machine_code": machine["business_code"],
                     "fields": {"start_time": day.isoformat() + (" 22:00:00" if night else " 09:00:00"),
                                "end_time": (day + timedelta(days=1)).isoformat() + " 02:00:00" if night else day.isoformat() + " 11:00:00",
                                "reason_code": "maintenance" if index % 2 == 0 else "tooling",
                                "reason_detail": "复杂样例计划维护与工装更换"}})
    return rows


def _permissions(resources):
    result = []
    for operator in resources["operators"]:
        skills = set(operator["relationships"]["skill_codes"])
        machines = [machine["business_code"] for machine in resources["machines"]
                    if skills.intersection(machine["relationships"]["op_type_codes"])]
        result.append({"operator_code": operator["business_code"], "machine_codes": machines})
    return result


def sample_blueprint(batch_count=100, operation_count=50, start_date=None):
    """Return fresh JSON-shaped data; supported sample sizes have at least 8 ops.

    ``(2, 12)`` is the small real-API acceptance fixture. The default contains
    100 batches / 5000 operations, 4600 internal operations and 400 external
    operations in 200 merged stages. Parts are reused by successive batches.
    The default anchor starts fourteen days before creation (weekends move to
    Monday), so real adopted past tasks can receive synthetic actual reports.
    Conflict scenarios are explicit optional changes, never silently injected
    into the base data. Actual report requests must use a real adopted plan.
    """
    created_date = date.today()
    start = date.fromisoformat(start_date) if start_date is not None else created_date - timedelta(days=14)
    while start.weekday() >= 5:
        start += timedelta(days=1)
    end = start + timedelta(days=80)
    resources = _resources(start)
    parts = _parts(min(10, batch_count), operation_count)
    batches = _batches(batch_count, parts, start)
    calendar_days, personal_days = _calendars(start, end)
    report_requests = [{"batch_code": batch["business_code"], "operation_seq": 1,
                        "quantity": max(1, batch["fields"]["quantity"] // 3)}
                       for batch in batches[:6]]
    return {"metadata": {"id": "complex-scheduling", "label": "复杂排产样例",
                         "anchor_date": start.isoformat(),
                         "created_date": created_date.isoformat(), "synthetic_business_data": True,
                         "date_basis": "首回日期前14天起，周末顺延；过去报工与未来计划均为独立样例合成数据。",
                         "batch_count": batch_count, "operations_per_batch": operation_count,
                         "operation_count": batch_count * operation_count,
                         "internal_operation_count": batch_count * (operation_count - 4),
                         "external_operation_count": batch_count * 4, "merged_stage_count": batch_count * 2,
                         "material_batch_count": min(20, batch_count),
                         "internal_continuous_groups_supported": False},
            "schedule_window": {"start_date": start.isoformat(), "end_date": end.isoformat(),
                                "ready_check": True, "missing_resource_policy": "auto_assign",
                                "completed_policy": "preserve_actuals", "material_strategy": "stage"},
            "config_patch": {"auto_assign_enabled": "yes"}, "resources": resources,
            "parts": parts, "batches": batches, "calendar_days": calendar_days,
            "operator_calendar_days": personal_days, "machine_downtimes": _downtimes(resources, start),
            "operator_machine_permissions": _permissions(resources), "actual_report_requests": report_requests,
            "conflict_scenarios": [
                {"code": "arrival-after-window", "batch_code": batches[0]["business_code"],
                 "fields": {"ready_status": "no", "ready_date": (start + timedelta(days=83)).isoformat(),
                            "due_date": (start + timedelta(days=2)).isoformat()},
                 "expectation": "齐套时间超出排产范围，不能伪造窗口内开工或准时交付"},
                {"code": "due-before-release", "batch_code": batches[-1]["business_code"],
                 "fields": {"ready_date": (start + timedelta(days=77)).isoformat(),
                            "due_date": (start + timedelta(days=1)).isoformat()},
                 "expectation": "依赖顺序及外协周期不变，交付风险必须保留"}]}
