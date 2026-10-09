"""Inject the opt-in isolated complex sample through production HTTP contracts."""

import json
import os
from pathlib import Path

from .sample_data import sample_blueprint
from .sample_http import BASE, SampleClient, SampleProgress

_KINDS = (("op_types", "op_type"), ("machine_groups", "machine_group"),
          ("shift_profiles", "shift_profile"), ("machines", "machine"),
          ("operators", "operator"), ("suppliers", "supplier"), ("materials", "material"))
_RELATIONS = {"op_type_codes": ("op_type_refs", "op_type"), "group_code": ("group_ref", "machine_group"),
              "skill_codes": ("skill_refs", "op_type"), "shift_profile_code": ("shift_profile_ref", "shift_profile")}


class SampleInjector:
    def __init__(self, client, progress, blueprint):
        self.client, self.progress, self.blueprint = client, progress, blueprint
        self.refs = {kind: {} for _, kind in _KINDS}
        self.refs.update(part={}, batch={})
        self.operation_refs = {}

    def resource(self, kind, row):
        payload = {key: row[key] for key in ("business_code", "label", "fields")}
        if "relationships" in row:
            relations = {}
            for key, value in row["relationships"].items():
                field, target = _RELATIONS[key]
                relations[field] = ([self.refs[target][code] for code in value]
                                    if isinstance(value, list) else self.refs[target][value])
            payload["relationships"] = relations
        ref = self.client.create(kind, payload)
        self.refs[kind][row["business_code"]] = ref
        return {"ref": ref, "business_code": row["business_code"]}

    def permissions(self, row):
        ref = self.refs["operator"][row["operator_code"]]
        path = BASE + "/entities/operator/" + ref
        detail = self.client.get(path)
        permissions = [{"machine_ref": self.refs["machine"][code], "skill_level": "normal",
                        "is_primary": "yes" if index == 0 else "no"}
                       for index, code in enumerate(row["machine_codes"])]
        preview = self.client.post(path + "/machine-permissions/preview",
                                   {"write_token": detail["write_context"]["write_token"],
                                    "machine_permissions": permissions})["data"]
        return self.client.command(path + "/machine-permissions/confirm", preview["write_context"],
                                   {"preview_ref": preview["preview_ref"]})["result"]

    def part(self, row):
        collection = BASE + "/entities/part"
        context = self.client.get(collection)["create_context"]
        payload = {key: row[key] for key in ("business_code", "label", "remark")}
        payload["route_raw"] = None
        ref = self.client.command(BASE + "/process/parts/create", context, payload)["data"]["entity_ref"]
        self.refs["part"][row["business_code"]] = ref
        route = {"mode": "rows", "rows": [{"seq": op["seq"], "op_type_name": self._op_name(op["op_type_code"])}
                                          for op in row["operations"]]}
        preview = self.client.post(BASE + "/process/" + ref + "/route-preview", route)["data"]
        self.client.command(BASE + "/process/" + ref + "/route_confirm", preview["write_context"],
                            {"route": route, "discard_group_refs": []})
        detail = self.client.document(collection + "/" + ref)
        operations = {op["sequence"]: op for op in detail["data"]["operations"] if op["status"] == "active"}
        source = {"operations": [{"ref": operations[op["seq"]]["ref"], "source": op["source"],
                                  "op_type_ref": self.refs["op_type"][op["op_type_code"]],
                                  "supplier_ref": self.refs["supplier"][op["supplier_code"]] if op["supplier_code"] else None,
                                  "confirmed": True} for op in row["operations"]], "discard_group_refs": []}
        self._stage(ref, "source_confirm", source, detail)
        detail = self.client.document(collection + "/" + ref)
        groups = {"groups": [{"ref": None, "operation_refs": [operations[seq]["ref"] for seq in group["sequences"]],
                              "supplier_ref": self.refs["supplier"][group["supplier_code"]],
                              "total_days": group["total_days"]} for group in row["groups"]],
                  "discard_group_refs": [group["ref"] for group in detail["data"]["external_groups"]]}
        if groups["groups"]:
            self._stage(ref, "groups_confirm", groups, detail)
        detail = self.client.get(collection + "/" + ref)
        hours = {"operations": [dict(ref=operations[op["seq"]]["ref"], **(
                    {"setup_hours": op["setup_hours"], "unit_hours": op["unit_hours"]} if op["source"] == "internal"
                    else {"external_days": None})) for op in row["operations"]],
                 "groups": [{"ref": group["ref"], "total_days": group["total_days"]}
                            for group in detail["external_groups"]], "confirm_zero_unit_hours": False}
        self.client.command(BASE + "/process/" + ref + "/hours_confirm", detail["write_context"], hours)
        return {"ref": ref, "operation_count": len(operations), "external_group_count": len(hours["groups"])}

    def _op_name(self, code):
        return next(row["label"] for row in self.blueprint["resources"]["op_types"] if row["business_code"] == code)

    def _stage(self, ref, action, value, detail):
        path = BASE + "/process/" + ref
        preview = self.client.post(path + "/stage-preview", {"action": action, "input": value,
                                  "snapshot_ref": detail["meta"]["snapshot_ref"]})["data"]
        return self.client.command(path + "/" + action, preview["write_context"], value)

    def batch(self, row):
        path = BASE + "/entities/batch"
        context = self.client.get(path)["create_context"]
        ref = self.client.command(path + "/create", context, {"business_code": row["business_code"],
                    "part_ref": self.refs["part"][row["part_code"]], "fields": row["fields"]})["data"]["entity_ref"]
        self.refs["batch"][row["business_code"]] = ref
        path += "/" + ref
        detail = self.client.document(path)
        preview = self.client.post(path + "/sync-preview", {"input": {},
                                   "snapshot_ref": detail["meta"]["snapshot_ref"]})["data"]
        result = self.client.command(path + "/sync-confirm", preview["write_context"],
                                     {"preview_ref": preview["preview_ref"]})
        detail = self.client.get(path)
        self.operation_refs[row["business_code"]] = {op["sequence"]: op["ref"] for op in detail["operations"]}
        if row["materials"]:
            rows = [{"row_key": None, "material_ref": self.refs["material"][item["material_code"]],
                     "required_quantity": item["required_quantity"], "available_quantity": item["available_quantity"],
                     "operation_ref": self.operation_refs[row["business_code"]][item["operation_seq"]]
                       if item["operation_seq"] is not None else None,
                     "arrivals": item["arrivals"]} for item in row["materials"]]
            self.client.command(path + "/materials_update", detail["write_context"], {"rows": rows, "removed_keys": []})
        for override in row["operation_overrides"]:
            detail = self.client.get(path)
            fields = {key: value for key, value in override["fields"].items() if not key.endswith("_code")}
            for kind in ("machine", "operator", "supplier"):
                if kind + "_code" in override["fields"]:
                    fields[kind + "_ref"] = self.refs[kind][override["fields"][kind + "_code"]]
            self.client.command(path + "/operation_update", detail["write_context"],
                                {"operation_ref": self.operation_refs[row["business_code"]][override["operation_seq"]], "fields": fields})
        return {"ref": ref, "operation_count": result["data"]["operation_count"], "material_count": len(row["materials"])}

    def calendar(self, row, operator=False):
        date = row["date"]
        if operator:
            path = BASE + "/entities/operator/" + self.refs["operator"][row["operator_code"]] + "/calendar"
        else:
            path = BASE + "/calendar"
        month = self.client.get(path + "/month?year=" + date[:4] + "&month=" + str(int(date[5:7])))
        context = month["write_context"] if operator else next(day["write_context"] for day in month["days"] if day["date"] == date)
        return self.client.command(path + "/upsert", context, {"date": date, "fields": row["fields"]})["result"]

    def downtime(self, row):
        path = BASE + "/entities/machine/" + self.refs["machine"][row["machine_code"]] + "/downtimes"
        context = self.client.get(path)["write_context"]
        return self.client.command(path + "/create", context, row["fields"])["result"]

    def inject(self):
        for plural, kind in _KINDS:
            for row in self.blueprint["resources"][plural]:
                self.progress.step(kind + ":" + row["business_code"], lambda row=row, kind=kind: self.resource(kind, row))
        for row in self.blueprint["operator_machine_permissions"]:
            self.progress.step("permissions:" + row["operator_code"], lambda row=row: self.permissions(row))
        for name, method in (("calendar_days", self.calendar), ("operator_calendar_days", lambda row: self.calendar(row, True)),
                             ("machine_downtimes", self.downtime), ("parts", self.part), ("batches", self.batch)):
            for index, row in enumerate(self.blueprint[name], 1):
                self.progress.step(name + ":" + str(index), lambda row=row, method=method: method(row))
        self.progress.report.update(state="seeded", counts={
            "batches": len(self.refs["batch"]), "operations": sum(len(value) for value in self.operation_refs.values()),
            "parts": len(self.refs["part"]), "resources": {kind: len(self.refs[kind]) for _, kind in _KINDS},
            "calendar_days": len(self.blueprint["calendar_days"]), "downtimes": len(self.blueprint["machine_downtimes"])},
            refs=self.refs, operation_refs=self.operation_refs, schedule_window=self.blueprint["schedule_window"],
            blueprint=self.blueprint,
            exercise_state="not_run")
        self.progress.save()
        return self.progress.report


def inject_sample(base_url, output=None, batch_count=100, operation_count=50, exercise=False):
    client = SampleClient(base_url)
    progress = SampleProgress(output, client)
    blueprint = sample_blueprint(batch_count, operation_count)
    result = SampleInjector(client, progress, blueprint).inject()
    if exercise:
        from .sample_exercise import exercise_sample
        return exercise_sample(base_url, result, output=output)
    return result


def main(runtime_dir):
    runtime_dir = Path(runtime_dir)
    if not (runtime_dir / "aps-complex-sample.txt").is_file():
        raise RuntimeError("请使用启用复杂样例入口，不能向正式数据注入样例。")
    report_path = runtime_dir / "user-data" / "sample-acceptance.json"
    if report_path.exists():
        previous = json.loads(report_path.read_text(encoding="utf-8"))
        if previous.get("state") == "complete":
            return 0
        raise RuntimeError("上次样例注入未完成，已保留数据和记录。请查看 sample-acceptance.json，不会自动重试。")
    contract = json.loads((runtime_dir / "user-data" / "logs" / "aps_runtime.json").read_text(encoding="utf-8"))
    expected_db = runtime_dir / "user-data" / "db" / "aps.db"
    if (os.path.normcase(os.path.abspath(contract["runtime_dir"])) != os.path.normcase(str(runtime_dir.resolve()))
            or os.path.normcase(os.path.abspath(contract["db_path"])) != os.path.normcase(str(expected_db.resolve()))):
        raise RuntimeError("样例启动记录指向其他数据目录，没有注入任何资料。")
    base_url = "http://{}:{}".format(contract["host"], contract["port"])
    health = SampleClient(base_url).document("/system/health")
    if health.get("app") != "aps" or health.get("pid") != contract["pid"]:
        raise RuntimeError("样例后台与本目录启动记录对不上，没有注入任何资料。")
    try:
        inject_sample(base_url, report_path, exercise=True)
    except FileExistsError as exc:
        raise RuntimeError("已有样例准备记录，不会重复注入。请查看 sample-acceptance.json 或用 Start.cmd 打开已有样例。") from exc
    return 0
