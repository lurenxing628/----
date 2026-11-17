"""Persistent draft lifecycle. No publish, actual writes, or latest-base fallback."""

import getpass
from datetime import datetime
from typing import Callable

from core.models.workbench_command import WorkbenchCommandOutcome
from core.models.workbench_trial import (
    ACTIONS,
    CHANGE,
    CREATE,
    DISCARD,
    SAVE,
    change_input,
    create_input,
    discard_input,
    reference,
    reject,
    save_input,
)
from core.models.workbench_trial_scenario_archive import encode_scenario, encode_scenario_resources
from core.services.scheduler.execution.execution_ledger_adapter import ledger_read_snapshot
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.facts.operation_effort_evidence import saved_operation_efforts
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.facts.trial_origin import TrialOrigin, invalid_trial_snapshot
from core.services.workbench.facts.trial_policy import (
    load_draft,
    load_scenario_with_resources,
    public_source_identity,
    require_advanced,
)
from core.services.workbench.facts.trial_scenario_archive import bind_scenario_rows, scenario_issue_refs
from core.shared.refs import new_ref
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository

from .base import prepare_base
from .capacity import trial_capacity
from .constraints import build_archived_trial_intervals
from .facts import live_context, saved_capture
from .preparation import (
    ScenarioLabels,
    apply_changeovers,
    apply_preparation,
    preparation_projection,
    trial_changeovers,
)
from .projection import (
    draft_projection,
    public_scenario_resources,
    scenario_edit_context,
    scenario_resources_snapshot,
    scenario_tasks,
    unplanned_operations,
    write_snapshot,
)
from .validation import TrialValidator


class WorkbenchTrialService:
    def __init__(self, conn, *, context_factory, context_validator, data_context, clock: Callable[[], datetime],
                 actor_provider=None):
        self.conn = conn
        self.repo = WorkbenchTrialRepository(conn)
        self.context_factory, self.context_validator = context_factory, context_validator
        self.clock, self.actor_provider = clock, actor_provider or getpass.getuser
        self.data_context = data_context

    def _now(self):
        return self.clock().isoformat(timespec="seconds")

    def _create_snapshot(self, admission, rows, live):
        return {
            "input": admission["input"],
            "revisions": live["revisions"],
            "data_context_ref": live["data_context_ref"],
            "rows": [(row["source_row_ref"], row["current"]) for row in rows],
        }

    def preview_create(self, value):
        intent = create_input(value)
        with candidate_read_snapshot(self.conn):
            with ledger_read_snapshot(self.conn) as ledger:
                admission, rows, live, resolved_anchors = prepare_base(
                    self.conn, intent, ledger=ledger, data_context=self.data_context
                )
                checked = TrialValidator(
                    admission, rows, live, resolved_anchors=resolved_anchors
                ).evaluate_current()
                context = self.context_factory(
                    next(iter(intent["base"].values())),
                    [CREATE],
                    self._create_snapshot(admission, rows, live),
                )
                return {
                    "base": intent["base"],
                    "base_identity": public_source_identity(admission["source"]),
                    "scope": intent["scope"],
                    "task_count": len(rows),
                    "tasks_complete": True,
                    "validation": checked,
                    "write_context": context,
                }

    def create(self, value, write_token, request_key):
        intent = create_input(value)
        base_ref = next(iter(intent["base"].values()))

        def guard():
            with ledger_read_snapshot(self.conn) as ledger:
                admission, rows, live, resolved_anchors = prepare_base(
                    self.conn, intent, ledger=ledger, data_context=self.data_context
                )
                self.context_validator(write_token, base_ref, CREATE, self._create_snapshot(admission, rows, live))
                validator = TrialValidator(admission, rows, live, resolved_anchors=resolved_anchors)
                checked = validator.evaluate_current()
                origin = live["origin"]
                batch_refs = [ref for ref in origin.batches if ref is not None]
                extra_batch_ids = sorted(
                    {batch["batch_id"] for batch in origin.batches.values()}
                    | {row["original"]["batch"]["batch_id"] for row in rows}
                )
                busy_operation_refs = sorted(
                    op_ref
                    for op_ref, snap in live["execution"].items()
                    if snap.get("execution_state") in ("partial", "started")
                )
                scoped_facts = live["capture"].scoped_archive(
                    batch_refs,
                    baseline_version=admission["baseline"]["version"],
                    extra_batch_ids=extra_batch_ids,
                    busy_operation_refs=busy_operation_refs,
                )
                stored_admission = {**admission, "facts": scoped_facts}
                return stored_admission, rows, live, (checked, validator.protection, validator.trial_intervals)

        def mutate(prepared):
            admission, rows, live, checked = prepared
            head, stored = self.repo.create(admission, rows, checked[0], request_key, self.actor_provider(), self._now())
            return WorkbenchCommandOutcome("committed", self._projection(head, stored, live, checked, changes=[]))

        return WorkbenchCommandService(self.conn).execute(
            request_key=request_key,
            action=CREATE,
            context_ref=base_ref,
            normalized_input=intent,
            guard=guard,
            mutate=mutate,
        )

    def require_draft_header(self, draft_ref):
        header = self.repo.draft_header(reference(draft_ref))
        if header is None:
            reject("entity_not_found", "未找到指定草稿，未改查其他草稿或最新计划。", 404)
        return header

    def require_scenario_header(self, scenario_ref):
        header = self.repo.scenario_header(reference(scenario_ref))
        if header is None:
            reject("entity_not_found", "未找到指定试调场景。", 404)
        return header

    def _loaded(self, ref, *, ledger, header=None):
        head, rows, source = load_draft(self.repo, reference(ref), header=header)
        origin = TrialOrigin.saved(head["admission"], rows, source)
        live = live_context(
            self.conn,
            origin,
            saved_capture(self.conn, head["admission"]),
            ledger=ledger,
            data_context=self.data_context,
        )
        return head, rows, live

    def _projection(self, head, rows, live, checked=None, *, changes=None, scenario_ref=None):
        """checked: (核对结果, 同一次核对得到的 TrialProtection, 同一批行的 trial_intervals)；不给时现核对。"""
        if checked is None:
            validator = TrialValidator(head["admission"], rows, live)
            checked = validator.evaluate_saved(), validator.protection, validator.trial_intervals
        result = draft_projection(
            head,
            rows,
            checked[0],
            live,
            self.context_factory,
            checked[1],
            scenario_ref=scenario_ref,
            trial_intervals=checked[2],
        )
        result["change_history"] = self.repo.public_history(head["draft_ref"]) if changes is None else changes
        return result

    def get(self, draft_ref, *, header=None):
        with candidate_read_snapshot(self.conn):
            with ledger_read_snapshot(self.conn) as ledger:
                return self._projection(*self._loaded(draft_ref, ledger=ledger, header=header))

    def _execute(self, action, ref, intent, token, key, prepare, mutate):
        reference(ref)

        def guard():
            with ledger_read_snapshot(self.conn) as ledger:
                head, rows, live = self._loaded(ref, ledger=ledger)
                self.context_validator(token, ref, action, write_snapshot(head, rows, live))
                if head["status"] != "editing":
                    reject("draft_closed", "草稿已保存或已放弃，不能再改。")
                return prepare(head, rows, live)

        return WorkbenchCommandService(self.conn).execute(
            request_key=key,
            action=action,
            context_ref=ref,
            normalized_input=intent,
            guard=guard,
            mutate=mutate,
        )

    def change(self, draft_ref, value, write_token, request_key):
        intent = change_input(value)

        def prepare(head, rows, live):
            row = next((item for item in rows if item["task_ref"] == intent["task_ref"]), None)
            if row is None:
                reject("task_not_in_draft", "这条工序不属于当前试调草稿，没有调整。请回到本草稿重新选择。", 404)
            validator = TrialValidator(head["admission"], rows, live)
            before = row["current"]
            row["current"] = validator.adjusted(row, intent)
            checked = validator.evaluate_saved()
            return head, rows, live, row, before, (checked, validator.protection, validator.trial_intervals)

        def mutate(prepared):
            head, rows, live, row, before, checked = prepared
            if before == row["current"]:
                return WorkbenchCommandOutcome(
                    "unchanged",
                    self._projection(head, rows, live, checked),
                    history_revision=head["revision"],
                )
            now = self._now()
            revision = head["revision"] + 1
            require_advanced(self.repo.change(head, row, before, checked[0], request_key, self.actor_provider(), now))
            current_head = dict(head, revision=revision, status="editing", validation=checked[0], updated_at=now)
            return WorkbenchCommandOutcome(
                "committed",
                self._projection(current_head, rows, live, checked),
                history_revision=revision,
            )

        return self._execute(CHANGE, draft_ref, intent, write_token, request_key, prepare, mutate)

    def save(self, draft_ref, value, write_token, request_key):
        intent = save_input(value)

        def prepare(head, rows, live):
            scenario_ref = new_ref()
            validator = TrialValidator(head["admission"], rows, live)
            checked = validator.evaluate_saved(), validator.protection, validator.trial_intervals
            snapshot = self._projection(head, rows, live, checked, scenario_ref=scenario_ref)
            # The arrangements this save keeps for the source run's hold window: the validator's held set, the same
            # held_arrangements the run admission and trial adoption use. Saving makes every row read-only below, so
            # the rows' edit_context no longer tells which of them were frozen.
            snapshot["frozen_operation_refs"] = sorted(
                row["operation_ref"] for row in rows if row["original"]["operation"]["id"] in validator.frozen)
            resources_data = scenario_resources_snapshot(live)
            return head, rows, live, scenario_ref, snapshot, validator.trial_intervals, resources_data

        def mutate(prepared):
            head, rows, live, scenario_ref, snapshot, intervals, resources_data = prepared
            snapshot.update(scenario_ref=scenario_ref, name=intent["name"], status="saved", saved_at=self._now())
            for row in snapshot["tasks"]:
                row.update(
                    source_row_ref=row["row_ref"],
                    source_task_ref=row["task_ref"],
                    row_ref=new_ref(),
                    task_ref=new_ref(),
                )
                row["edit_context"] = scenario_edit_context()
            old_to_new = {row["source_task_ref"]: row["task_ref"] for row in snapshot["tasks"]}
            for row in snapshot["tasks"]:
                row["predecessor_refs"] = [old_to_new[ref] for ref in row["predecessor_refs"]]
                row["issues"] = scenario_issue_refs(row["issues"], old_to_new)
            snapshot["validation"]["issues"] = scenario_issue_refs(snapshot["validation"]["issues"], old_to_new)
            row_map = {row["source_row_ref"]: row["row_ref"] for row in snapshot["tasks"]}
            trial_intervals = {
                **intervals,
                "current_by_row": {row_map[key]: val for key, val in intervals["current_by_row"].items()},
                "original_by_row": {row_map[key]: val for key, val in intervals["original_by_row"].items()},
            }
            apply_changeovers(
                snapshot["comparison"],
                trial_changeovers(
                    [dict(row, row_ref=task["row_ref"]) for row, task in zip(rows, snapshot["tasks"])],
                    ScenarioLabels(live["origin"], resources_data),
                    trial_intervals=trial_intervals,
                ),
            )
            snapshot["preview_target"] = "/api/workbench/v1/trial/scenarios/" + snapshot["scenario_ref"]
            resources_json, resources_bytes = encode_scenario_resources(resources_data)
            encoded = encode_scenario(snapshot, resources_bytes=resources_bytes)
            require_advanced(
                self.repo.save(
                    head,
                    snapshot,
                    encoded,
                    resources_json,
                    request_key,
                    self.actor_provider(),
                    snapshot["saved_at"],
                )
            )
            return WorkbenchCommandOutcome("committed", snapshot)

        return self._execute(SAVE, draft_ref, intent, write_token, request_key, prepare, mutate)

    def discard(self, draft_ref, value, write_token, request_key):
        intent = discard_input(value)

        def prepare(head, rows, live):
            checked = TrialValidator(head["admission"], rows, live).evaluate_saved()
            return head, checked

        def mutate(prepared):
            head, checked = prepared
            require_advanced(self.repo.transition(head, "discarded", checked, self._now()))
            return WorkbenchCommandOutcome(
                "committed",
                {"draft_ref": draft_ref, "status": "discarded", "validation": checked, "history_retained": True},
            )

        return self._execute(DISCARD, draft_ref, intent, write_token, request_key, prepare, mutate)

    def scenario(self, scenario_ref, *, header=None):
        with candidate_read_snapshot(self.conn):
            scenario_header, saved, saved_resources = load_scenario_with_resources(
                self.repo, reference(scenario_ref), header=header
            )
            draft_header = self.repo.draft_header(saved["draft_ref"])
            if draft_header is None:
                reject("trial_snapshot_invalid", "试调方案的原草稿缺失，请联系维护人员核对。")
            head, rows, source = load_draft(self.repo, saved["draft_ref"], header=draft_header)
            admission = head["admission"]
            projected = bind_scenario_rows(saved, rows)
            origin = TrialOrigin.saved(admission, projected, source)
            contexts = origin.contexts(projected)
            trial_intervals = build_archived_trial_intervals(
                projected,
                execution={row["operation_ref"]: task["execution"] for task, row in zip(saved["tasks"], projected)},
            )
            # The scenario and its resources were read for this request only; the result is built on them.
            result = saved
            result["tasks"] = scenario_tasks(saved, projected, trial_intervals=trial_intervals)
            result["resources"] = public_scenario_resources(saved_resources)
            pairs, preparation = preparation_projection(
                admission,
                saved_operation_efforts(admission["source"]["operation_effort"], on_corrupt=invalid_trial_snapshot),
                saved_operation_efforts(saved["operation_effort"], on_corrupt=invalid_trial_snapshot),
                current_evidence={"kind": "scenario", "scenario_ref": saved["scenario_ref"]},
                contexts=contexts,
            )
            result["unplanned_operations"] = unplanned_operations(contexts)
            result["scope_complete"] = not result["unplanned_operations"]
            apply_preparation(result["tasks"], result["unplanned_operations"], pairs)
            result["comparison"]["preparation_common"] = preparation
            result["capacity"] = trial_capacity(
                projected,
                origin.calendar_tables,
                source_ref=public_source_identity(admission["source"]),
                trial_intervals=trial_intervals,
            )
            result["change_history"] = self.repo.public_history(
                head["draft_ref"], through_revision=scenario_header["revision"]
            )
            return result

    def lookup(self, request_key):
        with candidate_read_snapshot(self.conn):
            return WorkbenchCommandService(self.conn).lookup(
                request_key,
                action=(CREATE,) + ACTIONS,
                conflict_message="这个操作编号不是试调的操作，请到对应页面查询结果。",
            )
