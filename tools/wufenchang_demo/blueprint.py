"""Prepare a dated, unscheduled workload from the reviewed source fixture."""

import json
from datetime import date, timedelta
from pathlib import Path

from .resource_blueprint import INTERNAL_TYPES, operator_permissions, resource_blueprint

DATA = Path(__file__).with_name("data")
_LOCK_FAMILIES = {"HSS2", "HZK1", "SZM1", "SZS2A"}
_THERMAL = {"喷漆", "热处理", "表面处理", "吹砂", "涂漆", "涂油", "油漆", "酸洗", "喷塑"}
_SPECIAL_PROCESS = {"焊接", "钨极氩弧焊", "冲压", "激光切割"}


def read_fixture(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def workday(start, offset):
    day = start
    while offset:
        day += timedelta(days=1)
        if day.weekday() < 5:
            offset -= 1
    return day


def _supplier(operation):
    if operation["operation"] in _THERMAL:
        return "热表处理中心"
    if operation["operation"] in _SPECIAL_PROCESS:
        return "机加中心"
    department = operation["department"]
    return department if department in {"电子产品装配分厂", "二分厂", "一分厂"} else None


def _parts(source, scenario):
    external_types, parts, adoptions = {}, [], []
    internal_codes = {label: code for code, label in INTERNAL_TYPES.items()}
    supplier_codes = {name: f"SUP-{index:02d}" for index, name in enumerate(scenario["external_days"], 1)}
    for part in source["parts"]:
        operations, groups = [], []
        for row in part["operations"]:
            supplier = _supplier(row)
            if supplier is not None:
                code = "EXT-{:02d}".format(list(scenario["external_days"]).index(supplier) + 1) + "-" + row["operation"]
                external_types[code] = {"label": row["operation"], "supplier": supplier}
                # External type names are unique across suppliers in this selected fixture.
                operation = {"seq": row["sequence"], "op_type_code": code, "source": "external",
                             "supplier_code": supplier_codes[supplier], "setup_hours": None, "unit_hours": None,
                             "external_days": None}
                if operations and operations[-1]["source"] == "external" and operations[-1]["supplier_code"] == operation["supplier_code"]:
                    groups[-1]["sequences"].append(row["sequence"])
                else:
                    groups.append({"sequences": [row["sequence"]], "supplier_code": supplier_codes[supplier],
                                   "total_days": scenario["external_days"][supplier]})
            else:
                if row["operation"] == "装配":
                    code = "ASSEMBLY_LOCK" if part["family"] in _LOCK_FAMILIES else "ASSEMBLY_SUPPORT"
                else:
                    code = internal_codes[row["operation"]]
                minutes = row["unit_minutes"]
                if minutes == 0:
                    minutes = scenario["zero_unit_minutes"][row["operation"]]
                    adoptions.append({"drawing": part["drawing"], "sequence": row["sequence"], "raw_minutes": 0,
                                      "unit_minutes": minutes, "basis": "zero_unit_minutes"})
                operation = {"seq": row["sequence"], "op_type_code": code, "source": "internal", "supplier_code": None,
                             "setup_hours": row["setup_minutes"] / 60.0, "unit_hours": minutes / 60.0, "external_days": None}
            operations.append(operation)
        parts.append({"business_code": part["drawing"], "label": part["name"], "remark": None,
                      "operations": operations, "groups": groups})
    return parts, external_types, adoptions


def _batches(parts, resources, scenario, start):
    batches = []
    for part_index, part in enumerate(parts):
        material = f"M-{part_index + 1:03d}"
        delayed = part_index % 4 == 0
        resources["materials"].append({"business_code": material, "label": part["label"] + "配套料",
            "fields": {"status": "active", "spec": part["business_code"], "unit": "套",
                       "stock_qty": 8 if delayed else 12, "remark": None}})
        for batch_index, quantity in enumerate(scenario["batch_quantities"]):
            arrival_rows = []
            available = quantity
            if delayed and batch_index == 2:
                available = 2
                arrival_rows = [{"arrival_date": workday(start, offset).isoformat(), "quantity": 2} for offset in (2, 4)]
            index = part_index * 3 + batch_index
            priority = "critical" if index % 17 == 0 else "urgent" if index % 5 == 0 else "normal"
            batches.append({"business_code": "D{}{:02d}-{}".format(start.strftime("%y%m"), part_index + 1, batch_index + 1),
                "part_code": part["business_code"], "fields": {"quantity": quantity,
                    "due_date": workday(start, 10 + batch_index * 8 + part_index % 9).isoformat(),
                    "priority": priority, "ready_status": "partial" if arrival_rows else "yes",
                    "ready_date": workday(start, batch_index).isoformat(), "remark": None},
                "materials": [{"material_code": material, "required_quantity": quantity, "available_quantity": available,
                               "operation_seq": part["operations"][0]["seq"], "arrivals": arrival_rows}],
                "operation_overrides": []})
    return batches


def _calendar(scenario, start):
    days = []
    for offset in range(scenario["calendar_days"]):
        day = start + timedelta(days=offset)
        rest = day.weekday() >= 5
        days.append({"date": day.isoformat(), "fields": {"type": "rest" if rest else "work", "hours": 0 if rest else 8,
            "eff": 100, "allowNormal": "no" if rest else "yes", "allowUrgent": "no" if rest else "yes",
            "periods": [] if rest else scenario["shift_periods"], "shiftStart": "00:00" if rest else "08:00",
            "shiftEnd": "00:00" if rest else "17:00", "note": None}})
    return days


def demo_blueprint(start_date=None):
    start = date.fromisoformat(start_date) if start_date else date.today()
    while start.weekday() >= 5:
        start += timedelta(days=1)
    source, scenario, equipment = read_fixture("routes.json"), read_fixture("scenario.json"), read_fixture("resources.json")
    parts, external_types, adoptions = _parts(source, scenario)
    resources = resource_blueprint(equipment, scenario, start, external_types)
    batches = _batches(parts, resources, scenario, start)
    downtime = []
    for index, machine in enumerate(("3140073", "2140027", "3102089", "2701017")):
        day = workday(start, index + 1).isoformat()
        downtime.append({"machine_code": machine, "fields": {"start_time": day + " 09:00:00", "end_time": day + " 11:00:00",
                         "reason_code": "maintenance", "reason_detail": "例行保养"}})
    leave = []
    for index, operator in enumerate(("QG-01", "XG-01", "SS-01")):
        leave.append({"operator_code": operator, "date": workday(start, 6 + index).isoformat(),
                      "fields": {"type": "rest", "eff": 100, "allowNormal": "no", "allowUrgent": "no",
                                 "periods": [], "shiftStart": "08:00", "note": "技能培训"}})
    return {"parts": parts, "batches": batches, "resources": resources,
            "calendar_days": _calendar(scenario, start), "operator_calendar_days": leave,
            "machine_downtimes": downtime, "operator_machine_permissions": operator_permissions(resources),
            "schedule_window": {"start_date": start.isoformat(), "end_date": (start + timedelta(days=55)).isoformat(),
                                "ready_check": True, "material_strategy": "strict", "missing_resource_policy": "auto_assign",
                                "completed_policy": "preserve_actuals", "hold_window": None},
            "config_patch": scenario["schedule_config"],
            "source_adoptions": adoptions}
