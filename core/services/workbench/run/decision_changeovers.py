"""The shared actual-type events under the decision's fixed next-start window."""

from core.models.workbench_run_candidate import local_time
from core.services.workbench.facts.changeovers import changeover_projection
from core.services.workbench.facts.decision_metrics import (
    COVERAGE_MEMBER_FIELDS,
    metric_definitions,
    metric_delta,
)
from core.services.workbench.facts.decision_read_models import build_changeover_metrics

from .decision_impact import drill_target


class DecisionChangeovers:
    def __init__(self, source):
        self.source = source
        self._seeded = set()
        self._projections, self._metrics = {}, {}

    def _seed_precomputed(self, key):
        comp = self.source.computation_key(key)
        if comp in self._seeded:
            return
        self._seeded.add(comp)
        data = self.source.precomputed_changeovers(comp)
        if data is None:
            return
        self._projections[comp] = data["projection"]
        self._metrics[comp] = data["metrics"]

    def projection(self, key):
        key = self.source.computation_key(key)
        self._seed_precomputed(key)
        if key not in self._projections:
            self._projections[key] = changeover_projection(
                self.source.analysis_tasks(key), start=self.source.scope["range_start"],
                end=self.source.scope["range_end"], work_available=self.source.arrangement_available(key),
                next_operation_refs=self.source.operation_refs, task_intervals=self.source.task_intervals(key),
            )
        return self._projections[key]

    def metrics(self, key):
        key = self.source.computation_key(key)
        self._seed_precomputed(key)
        if key not in self._metrics:
            projected = self.projection(key)
            self._metrics[key] = build_changeover_metrics(
                projected, self.source.analysis_tasks(key), self.source.operation_refs, self.source.task_intervals(key),
            )
        return self._metrics[key]

    def _raw_events(self, key, side, *, machine_ref=None):
        events = self.projection(key)["events"]
        if machine_ref is not None:
            events = [value for value in events if value["machine_ref"] == machine_ref]
        if not events:
            return []
        lookup = {task["row_ref"]: task for task in self.source.analysis_tasks(key)}
        result = []
        for value in events:
            previous, current = lookup[value["previous_row_ref"]], lookup[value["next_row_ref"]]
            result.append({
                "event_ref": side + ":" + value["previous_row_ref"] + ":" + value["next_row_ref"],
                "event_side": side,
                "machine_ref": value["machine_ref"],
                "machine_label": value["machine_label"],
                "next_start": value["next_start"],
                "next_batch_id": current["batch_label"],
                "_value": value,
                "_previous": previous,
                "_next": current,
                "_key": key,
            })
        return result

    def _materialize_event(self, raw_event, *, range_start, window_bounds):
        source = self.source
        value = raw_event["_value"]
        side = raw_event["event_side"]
        key = raw_event["_key"]
        previous, current = raw_event["_previous"], raw_event["_next"]
        intervals = source.task_intervals(key)
        row = {
            **value,
            "event_ref": raw_event["event_ref"],
            "event_side": side,
            "predecessor_outside_window": intervals[value["previous_row_ref"]][0] < range_start,
            "data_gaps": [] if value["state"] == "complete" else [{"code": "arrangement_conflict", "message": "此设备的实际安排存在重叠。"}],
            **{
                name: {
                    "operation_ref": task["operation_ref"],
                    "batch_ref": task["batch_ref"],
                    "batch_label": task["batch_label"],
                    "process_label": task["process_label"],
                    "type_ref": task.get("process_type_ref"),
                    "type_label": task.get("process_type_label"),
                }
                for name, task in (("previous", previous), ("next", current))
            },
            "drill": {
                name: drill_target(
                    source,
                    tasks=[task],
                    batch_ref=task["batch_ref"],
                    operation_ref=task["operation_ref"],
                    before=side == "reference",
                    window_bounds=window_bounds,
                    task_intervals=intervals,
                )
                for name, task in (("previous", previous), ("next", current))
            },
        }
        for drill in row["drill"].values():
            if drill is not None:
                drill.update(
                    resource_ref=value["machine_ref"],
                    resource_kind="machine",
                    resource_view=source.resource_view,
                    comparison_tab="changeovers",
                )
        return row

    def paged_impacts(self, filters, *, offset=0, size=20, all_rows=False):
        side_filter = filters["event_side"]
        machine_ref = filters["machine_ref"]
        raw_rows = []
        if side_filter in ("all", "reference"):
            raw_rows.extend(self._raw_events("reference", "reference", machine_ref=machine_ref))
        if side_filter in ("all", "selected"):
            raw_rows.extend(self._raw_events(self.source.selected_ref, "selected", machine_ref=machine_ref))
        sort_key = filters["sort"]
        ordered, unknown = [], []
        for row in sorted(raw_rows, key=lambda item: item["event_ref"]):
            (unknown if row[sort_key] is None else ordered).append(row)
        ordered.sort(key=lambda item: item[sort_key], reverse=filters["order"] == "desc")
        sorted_rows = ordered + unknown
        total = len(sorted_rows)
        page_rows = sorted_rows if all_rows else sorted_rows[offset:offset + size]
        if not page_rows:
            return [], total
        range_start = local_time(self.source.scope["range_start"])
        window_bounds = (range_start, local_time(self.source.scope["range_end"]))
        items = [self._materialize_event(row, range_start=range_start, window_bounds=window_bounds) for row in page_rows]
        return items, total

    def public_summary(self):
        before, after = (self.metrics(key) for key in ("reference", self.source.selected_ref))
        definitions = {item["key"]: item for item in metric_definitions()}
        deltas = {key: metric_delta(definitions[key], after[key], before[key]) for key in after}
        sides = {}
        for side, key, metrics in (("before", "reference", before), ("after", self.source.selected_ref, after)):
            projected = self.projection(key)
            sides[side] = {
                **{name: {field: value for field, value in item.items() if field not in COVERAGE_MEMBER_FIELDS} for name, item in metrics.items()},
                **{name: projected[name] for name in ("state", "conflict", "conflict_count", "unknown_count", "issues")},
            }
        return {"scope": "fixed_changeover_window", **sides, "deltas": deltas}
