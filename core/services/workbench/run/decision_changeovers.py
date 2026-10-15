"""The shared actual-type events under the decision's fixed next-start window."""

from core.models.workbench_run_candidate import local_time
from core.services.workbench.facts.changeovers import changeover_projection, subject_arrangements
from core.services.workbench.facts.decision_metrics import metric_definitions, metric_delta, metric_value

from .decision_impact import _drill


class DecisionChangeovers:
    def __init__(self, source):
        self.source = source
        self._projections, self._metrics = {}, {}

    def available(self, key):
        key = self.source.computation_key(key)
        return self.source.baseline["state"] == "available" if key == "reference" else self.source.result_available(key)

    def tasks(self, key):
        return self.source.analysis_tasks(key)

    def projection(self, key):
        key = self.source.computation_key(key)
        if key not in self._projections:
            self._projections[key] = changeover_projection(self.tasks(key), start=self.source.scope["range_start"],
                end=self.source.scope["range_end"], work_available=self.available(key), next_operation_refs=self.source.operation_refs,
                task_intervals=self.source.task_intervals(key))
        return self._projections[key]

    def metrics(self, key):
        key = self.source.computation_key(key)
        if key not in self._metrics:
            projected = self.projection(key)
            reason = {"code": "changeover_sequence_incomplete", "message": "部分实际设备序列缺少工种身份、时间或存在重叠，切换统计保留已知小计。"} if projected["state"] != "complete" else None
            arrangements = subject_arrangements(self.tasks(key), self.source.operation_refs,
                task_intervals=self.source.task_intervals(key))
            covered = sorted({task["operation_ref"] for task in arrangements})
            values = {}
            for name, value, subtotal in (("type_changeover_count", projected["count"], projected["known_count"]),
                                          ("changed_machine_count", projected["changed_machine_count"], projected["known_changed_machine_count"])):
                unknown = projected["unknown_count"]
                item = metric_value(value, total=max(len(arrangements), unknown), unknown=unknown, subtotal=subtotal,
                                    state=projected["state"], scope="fixed_changeover_window", reason=reason)
                item["covered_operation_refs"] = covered
                values[name] = item
            self._metrics[key] = values
        return self._metrics[key]

    def _events(self, key, side):
        source = self.source
        lookup = {task["row_ref"]: task for task in self.tasks(key)}
        intervals = self.source.task_intervals(key)
        range_start = local_time(source.scope["range_start"])
        result = []
        for value in self.projection(key)["events"]:
            previous, current = (lookup[value[name + "_row_ref"]] for name in ("previous", "next"))
            row = {**value, "event_ref": side + ":" + value["previous_row_ref"] + ":" + value["next_row_ref"],
                   "event_side": side, "predecessor_outside_window": intervals[value["previous_row_ref"]][0] < range_start,
                   "data_gaps": [] if value["state"] == "complete" else [{"code": "arrangement_conflict", "message": "此设备的实际安排存在重叠。"}],
                   **{name: {"operation_ref": task["operation_ref"], "batch_ref": task["batch_ref"], "batch_label": task["batch_label"],
                             "process_label": task["process_label"], "type_ref": task.get("process_type_ref"), "type_label": task.get("process_type_label")}
                      for name, task in (("previous", previous), ("next", current))},
                   "drill": {name: _drill(source, tasks=[task], batch_ref=task["batch_ref"], operation_ref=task["operation_ref"], before=side == "reference")
                             for name, task in (("previous", previous), ("next", current))}}
            for drill in row["drill"].values():
                if drill is not None:
                    drill.update(resource_ref=value["machine_ref"], resource_kind="machine", resource_view=source.resource_view,
                                 comparison_tab="changeovers")
            result.append(row)
        return result

    def impacts(self):
        return self._events("reference", "reference") + self._events(self.source.selected_ref, "selected")

    def public_summary(self):
        before, after = (self.metrics(key) for key in ("reference", self.source.selected_ref))
        definitions = {item["key"]: item for item in metric_definitions()}
        deltas = {key: metric_delta(definitions[key], after[key], before[key]) for key in after}
        sides = {}
        for side, key, metrics in (("before", "reference", before), ("after", self.source.selected_ref, after)):
            projected = self.projection(key)
            sides[side] = {**{name: {field: value for field, value in item.items() if field != "covered_operation_refs"} for name, item in metrics.items()},
                           **{name: projected[name] for name in ("state", "conflict", "conflict_count", "unknown_count", "issues")}}
        return {"scope": "fixed_changeover_window", **sides, "deltas": deltas}
