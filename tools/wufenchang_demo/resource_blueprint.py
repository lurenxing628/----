"""Map selected real equipment and declared workstations to production resources."""

from datetime import timedelta

INTERNAL_TYPES = {
    "TURN": "普车", "TURN_CNC": "数车", "MILL": "普铣", "MILL_CNC": "数铣",
    "DRILL": "钻孔", "GRIND": "磨削", "WIRE": "线切割", "WIRE_MEDIUM": "中走丝",
    "EDM": "电火花", "MARK": "标印", "FIT": "钳", "CLEAN": "清理", "WASH": "清洗",
    "TEST_PIECE": "加工试件", "SHEET": "钣金", "PICK": "领料", "PRINT": "丝网印刷",
    "ASSEMBLY_LOCK": "伞锁装配", "ASSEMBLY_SUPPORT": "综保装配", "ADJUST": "调试",
    "INSPECT": "检验", "INSPECT_FINAL": "成检", "INSPECT_GENERAL": "总检",
    "EXPERIMENT": "试验", "NDT": "无损检测", "SPECIAL_INSPECT": "特检", "AIRTIGHT": "气密性检验",
}
EQUIPMENT_SKILLS = {
    "普车": ["TURN"], "数车": ["TURN_CNC", "TURN"], "普铣": ["MILL"],
    "三轴中心": ["MILL_CNC"], "四轴中心": ["MILL_CNC"], "五轴中心": ["MILL_CNC"],
    "钻床": ["DRILL"], "平磨": ["GRIND"], "外圆磨": ["GRIND"],
    "电火花": ["EDM"], "线切割": ["WIRE", "WIRE_MEDIUM"], "标印": ["MARK"],
}
WORKSTATIONS = (
    ("QG", "钳工工位", 4, ["FIT", "CLEAN", "WASH", "TEST_PIECE", "SHEET", "PICK", "PRINT"]),
    ("SS", "伞锁装配工位", 4, ["ASSEMBLY_LOCK", "ADJUST"]),
    ("ZB", "综保装配工位", 4, ["ASSEMBLY_SUPPORT", "ADJUST"]),
    ("JY", "检验工位", 3, ["INSPECT", "INSPECT_FINAL", "INSPECT_GENERAL", "EXPERIMENT",
                           "NDT", "SPECIAL_INSPECT", "AIRTIGHT"]),
)


def resource_blueprint(evidence, scenario, start, external_types):
    op_types = [{"business_code": code, "label": label,
                 "fields": {"category": "internal", "remark": None}, "relationships": {}}
                for code, label in INTERNAL_TYPES.items()]
    op_types.extend({"business_code": code, "label": row["label"],
                     "fields": {"category": "external", "default_merge_mode": "merged", "remark": None},
                     "relationships": {}} for code, row in external_types.items())
    groups, machines = [], []
    group_codes = {}
    for row in evidence["equipment"]:
        group = row["group"]
        if group not in group_codes:
            code = f"GROUP-{len(group_codes) + 1:02d}"
            group_codes[group] = code
            groups.append({"business_code": code, "label": group,
                           "fields": {"status": "active", "remark": None}, "relationships": {}})
        machines.append({"business_code": row["business_code"], "label": row["label"],
                         "fields": {"status": "active", "category": group, "remark": None},
                         "relationships": {"op_type_codes": EQUIPMENT_SKILLS[group], "group_code": group_codes[group]}})
    for code, label, count, skills in WORKSTATIONS:
        group_code = "GROUP-" + code
        groups.append({"business_code": group_code, "label": label,
                       "fields": {"status": "active", "remark": None}, "relationships": {}})
        for index in range(count):
            machines.append({"business_code": f"ST-{code}-{index + 1:02d}",
                             "label": f"{label}{index + 1:02d}",
                             "fields": {"status": "active", "category": "工位", "remark": None},
                             "relationships": {"op_type_codes": skills, "group_code": group_code}})
    pattern = []
    for offset in range(7):
        rest = (start + timedelta(days=offset)).weekday() >= 5
        pattern.append({"day_offset": offset, "is_rest": rest, "shift_start": "08:00", "shift_end": "17:00",
                        "periods": [] if rest else scenario["shift_periods"]})
    shift = {"business_code": "DAY-01", "label": "日班", "fields": {"status": "active", "remark": None,
             "anchor_date": start.isoformat(), "cycle_days": 7, "pattern": pattern}, "relationships": {}}
    operators = []
    for group in scenario["staffing"]:
        for index in range(group["count"]):
            operators.append({"business_code": "{}-{:02d}".format(group["code"], index + 1),
                              "label": "{}{:02d}岗".format(group["name"], index + 1),
                              "fields": {"status": "active", "remark": None},
                              "relationships": {"skill_codes": group["skills"], "shift_profile_code": "DAY-01"}})
    suppliers = []
    for index, (name, days) in enumerate(scenario["external_days"].items(), 1):
        codes = [code for code, row in external_types.items() if row["supplier"] == name]
        suppliers.append({"business_code": f"SUP-{index:02d}", "label": name,
                          "fields": {"status": "active", "default_days": days, "remark": None},
                          "relationships": {"op_type_codes": codes}})
    return {"op_types": op_types, "machine_groups": groups, "shift_profiles": [shift], "machines": machines,
            "operators": operators, "suppliers": suppliers, "materials": []}


def operator_permissions(resources):
    rows = []
    for operator in resources["operators"]:
        skills = set(operator["relationships"]["skill_codes"])
        rows.append({"operator_code": operator["business_code"],
                     "machine_codes": [machine["business_code"] for machine in resources["machines"]
                                       if skills.intersection(machine["relationships"]["op_type_codes"])]})
    return rows
