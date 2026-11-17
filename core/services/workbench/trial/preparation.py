"""Trial projections read the same saved requirement and changeover facts."""

from core.services.workbench.facts.changeovers import changeover_projection
from core.services.workbench.facts.operation_effort_evidence import archived_standard_effort
from core.services.workbench.facts.preparation_projection import (
    PREPARATION_METRIC_VERSION,
    operation_allocation,
    preparation_delta,
    preparation_summary,
    project_operation_effort,
    public_preparation_metrics,
    public_preparation_roles,
)
from core.services.workbench.facts.trial_origin import CandidateTrialSource, invalid_trial_snapshot
from core.services.workbench.facts.trial_policy import public_source_identity

from .arrangements import same_arrangement
from .effort import retained_role


def _side_effort(name, ref, context, records, evidence, admission, *, standard=None):
    op, execution = context["operation"], context["execution"]
    standard = archived_standard_effort(op, execution) if standard is None else standard
    current_execution = admission["execution"][ref]
    runtime = records.get(ref)
    if runtime is not None and runtime["op_id"] != op["id"]:
        invalid_trial_snapshot()
    value = project_operation_effort(runtime, standard,
        allocation_state=operation_allocation(runtime, arranged=context["arranged"], source=op["source"],
                                              deferred=context["deferred"], available=True),
        source=op["source"], execution=current_execution, evidence_source=evidence)
    if name == "after" and runtime is None and context["arranged"]:
        row = context["row"]
        held = row["original"].get("execution_anchor") is not None or same_arrangement(row["current"], row["original"]["arrangement"])
        role = retained_role(row, current_execution) if held else "new_schedule"
        value.update(requirement_role=role, allocation_state="external" if op["source"] == "external" else role)
    return value


def after_preparation_rows(admission, after, *, current_evidence, contexts):
    """The current side's rows from ``after``, the current requirement ledger already admitted by operation."""
    return [dict(_side_effort("after", ref, context, after, current_evidence, admission),
                 operation_ref=ref, arranged=context["arranged"])
            for ref, context in contexts.items()]


def preparation_projection(admission, before, after, *, current_evidence, contexts):
    """The immutable source and the explicit current ledger remain distinct: ``before`` is the source's requirement
    ledger and ``after`` the current one, each already admitted by operation."""
    pairs, summary_rows = {}, {"before": [], "after": []}
    origin = public_source_identity(admission["source"])
    for ref, context in contexts.items():
        op, execution = context["operation"], context["execution"]
        standard = archived_standard_effort(op, execution)
        pair = {}
        for name, records, evidence in (("before", before, origin), ("after", after, current_evidence)):
            value = _side_effort(name, ref, context, records, evidence, admission, standard=standard)
            pair[name] = value
            summary_rows[name].append(dict(value, operation_ref=ref, arranged=context["arranged"]))
        pairs[ref] = pair
    summaries = {name: preparation_summary(values) for name, values in summary_rows.items()}
    return pairs, {"metric_version": PREPARATION_METRIC_VERSION, "scope": "full_admission",
        "before": public_preparation_metrics(summaries["before"]["metrics"]),
        "after": public_preparation_metrics(summaries["after"]["metrics"]),
        "deltas": {key: preparation_delta(summaries["after"]["metrics"][key], value)
                   for key, value in summaries["before"]["metrics"].items()},
        "role_totals": {name: public_preparation_roles(summary["role_totals"]) for name, summary in summaries.items()},
        "coverage": {name: summary["coverage"] for name, summary in summaries.items()}}


def new_slot(row):
    """Whether the trial moved this row to a new slot: only such a row carries that slot's own requirement
    (``TrialValidator.adjusted``), so its current arrangement holds the operation's own type."""
    return "operation_effort" in row["current"]


class DraftLabels:
    """The labels a draft's arrangements show, all from its source: the type each side holds (a new slot holds its
    operation's own type, ``trial_operation_types``; every other arrangement the type the source recorded) and the
    source's machine names."""

    def __init__(self, origin):
        source = origin.source
        self._recorded = source.document["operation_types"]
        self._slot_types = source.document["trial_operation_types"]
        machines = (source.facts.tables["Machines"].values() if isinstance(source, CandidateTrialSource)
                    else origin.tables["Machines"])
        self._machines = {item["machine_id"]: item["name"] for item in machines}

    def operation_type(self, row, *, current):
        """The ``(ref, label)`` of the type one side of ``row`` holds."""
        if current and new_slot(row):
            kind = self._slot_types[row["operation_ref"]]
            return kind["ref"], self._slot_type_label(kind)
        kind = self._recorded[row["operation_ref"]]
        return kind["ref"], kind["label"]

    def machine_label(self, row, machine_id, *, current):
        """The name of the machine one side of ``row`` is arranged on; None without a machine or a name."""
        if current and new_slot(row):
            return self._slot_machine_label(machine_id)
        return self._machines.get(machine_id)

    def _slot_type_label(self, kind):
        return kind["label"]

    def _slot_machine_label(self, machine_id):
        return self._machines.get(machine_id)


class ScenarioLabels(DraftLabels):
    """A saved scenario's labels: a new slot shows the labels saved with the scenario (``scenario_resources_snapshot``),
    and none for a machine or type that snapshot does not hold; every other arrangement shows its draft's."""

    def __init__(self, origin, resources):
        super().__init__(origin)
        self._saved_machines = {item["business_code"]: item["label"] for item in resources["machines"]}
        self._saved_types = {item["ref"]: item["name"] for item in resources["op_types"] if item["ref"] is not None}

    def _slot_type_label(self, kind):
        return self._saved_types.get(kind["ref"])

    def _slot_machine_label(self, machine_id):
        return self._saved_machines.get(machine_id)


def trial_changeovers(
    rows,
    labels: DraftLabels,
    *,
    start=None,
    end=None,
    next_operation_refs=None,
    after_only=False,
    trial_intervals,
):
    projected = {}
    sides = ("current",) if after_only else ("original", "current")
    for side in sides:
        tasks = []
        current = side == "current"
        side_intervals = trial_intervals["current_by_row"] if current else trial_intervals["original_by_source_row"]
        for row in rows:
            original = row["original"]
            arrangement = row["current"] if current else original["arrangement"]
            type_ref, type_label = labels.operation_type(row, current=current)
            machine_label = labels.machine_label(row, arrangement["machine_id"], current=current)
            task = {
                "row_ref": row["source_row_ref"] if side == "original" else row["row_ref"],
                "operation_ref": row["operation_ref"],
                "source": original["operation"]["source"],
                "start": arrangement["start"],
                "end": arrangement["end"],
                "machine": {"ref": arrangement["machine_ref"], "label": machine_label},
                "process_type_ref": type_ref,
                "process_type_label": type_label,
            }
            tasks.append(task)
        projected["before" if side == "original" else "after"] = changeover_projection(
            tasks, start=start, end=end, next_operation_refs=next_operation_refs, task_intervals=side_intervals
        )
    windowed = start is not None or end is not None
    return {
        "scope": "fixed_changeover_window" if windowed else "complete_trial",
        "metric_version": PREPARATION_METRIC_VERSION if windowed else "type_changeover_v1",
        **projected,
    }


def apply_preparation(tasks, unplanned, pairs):
    for task in tasks + unplanned:
        task["operation_effort"] = pairs[task["operation_ref"]]


def apply_changeovers(comparison, common):
    comparison["changeover_common"] = common
    comparison["changeovers"] = common["after"]["count"]
    comparison["changeover_reason"] = "；".join(item["message"] for item in common["after"]["issues"]) or None
