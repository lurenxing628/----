"""Persistent draft lifecycle. No publish, actual writes, or latest-base fallback."""

import getpass
from datetime import datetime

from core.infrastructure.read_evidence import read_evidence_scope
from core.models.workbench_command import WorkbenchCommandOutcome, validate_request_key
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
from core.models.workbench_trial_scenario_archive import encode_scenario
from core.services.scheduler.execution.execution_ledger_adapter import ledger_read_snapshot
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.facts.trial_policy import (
    load_draft,
    load_scenario,
    require_advanced,
    require_trial_schema,
)
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository, new_ref

from .base import prepare_base
from .capacity import trial_capacity
from .facts import live_context
from .preparation import apply_changeovers, apply_preparation, preparation_projection, trial_changeovers
from .projection import (
    draft_projection,
    scenario_rows,
    source_projection,
    unplanned_operations,
    write_snapshot,
)
from .validation import TrialValidator


class WorkbenchTrialService:
    def __init__(self, conn, *, context_factory, context_validator, clock=None, actor_provider=None):
        self.conn = conn
        self.repo = WorkbenchTrialRepository(conn)
        self.context_factory, self.context_validator = context_factory, context_validator
        self.clock, self.actor_provider = clock or datetime.now, actor_provider or getpass.getuser

    def _now(self):
        return self.clock().isoformat(timespec="seconds")

    @staticmethod
    def _create_snapshot(admission, rows):
        return {"input": admission["input"], "facts": admission["facts"],
                "execution": admission["execution"], "baseline": admission["baseline"],
                "source": admission["source"],
                "rows": [(row["source_row_ref"], row["original"]) for row in rows]}

    def preview_create(self, value):
        intent = create_input(value)
        with candidate_read_snapshot(self.conn):
            with read_evidence_scope(self.conn), ledger_read_snapshot(self.conn) as execution_service:
                require_trial_schema(self.repo)
                admission, rows, live = prepare_base(self.conn, intent, execution_service=execution_service)
                checked = TrialValidator(self.conn, admission, rows, live).evaluate_current()
                context = self.context_factory(next(iter(intent["base"].values())), [CREATE], self._create_snapshot(admission, rows))
                return {"base": intent["base"], "base_identity": admission["source"]["identity"],
                        "scope": intent["scope"], "task_count": len(rows),
                        "tasks_complete": True, "validation": checked, "write_context": context}

    def create(self, value, write_token, request_key):
        intent = create_input(value)
        base_ref = next(iter(intent["base"].values()))

        def guard():
            with read_evidence_scope(self.conn), ledger_read_snapshot(self.conn) as execution_service:
                require_trial_schema(self.repo)
                admission, rows, live = prepare_base(self.conn, intent, execution_service=execution_service)
                self.context_validator(write_token, base_ref, CREATE, self._create_snapshot(admission, rows))
                validator = TrialValidator(self.conn, admission, rows, live)
                checked = validator.evaluate_current()
                return admission, rows, live, checked, validator.protection

        def mutate(prepared):
            admission, rows, live, checked, protection = prepared
            head, stored = self.repo.create(admission, rows, checked, request_key, self.actor_provider(), self._now())
            return WorkbenchCommandOutcome("committed", self._projection(head, stored, live,
                                                                         (checked, protection), changes=[]))

        return WorkbenchCommandService(self.conn).execute(request_key=request_key, action=CREATE,
            context_ref=base_ref, normalized_input=intent, guard=guard, mutate=mutate)

    def _loaded(self, ref, *, execution_service):
        head, rows = load_draft(self.repo, reference(ref))
        live = live_context(self.conn, rows, head["admission"], execution_service=execution_service)
        return head, rows, live

    def _projection(self, head, rows, live, checked=None, *, changes=None, source_prepared=None, scenario_ref=None):
        """checked: (核对结果, 同一次核对得到的 TrialProtection)，与这些行同一次核对；不给时现核对。"""
        if checked is None:
            validator = TrialValidator(self.conn, head["admission"], rows, live)
            checked = validator.evaluate_saved(), validator.protection
        result = draft_projection(head, rows, checked[0], live, self.context_factory, checked[1],
                                  source_prepared=source_prepared, scenario_ref=scenario_ref)
        result["change_history"] = self.repo.public_history(head["draft_ref"]) if changes is None else changes
        return result

    def get(self, draft_ref):
        with candidate_read_snapshot(self.conn):
            with read_evidence_scope(self.conn), ledger_read_snapshot(self.conn) as execution_service:
                return self._projection(*self._loaded(draft_ref, execution_service=execution_service))

    def _execute(self, action, ref, intent, token, key, prepare, mutate):
        reference(ref)

        def guard():
            with read_evidence_scope(self.conn), ledger_read_snapshot(self.conn) as execution_service:
                head, rows, live = self._loaded(ref, execution_service=execution_service)
                self.context_validator(token, ref, action, write_snapshot(head, rows, live))
                if head["status"] != "editing":
                    reject("draft_closed", "草稿已保存或已放弃，不能再改。")
                return prepare(head, rows, live)

        return WorkbenchCommandService(self.conn).execute(request_key=key, action=action, context_ref=ref,
                                                          normalized_input=intent, guard=guard, mutate=mutate)

    def change(self, draft_ref, value, write_token, request_key):
        intent = change_input(value)

        def prepare(head, rows, live):
            row = next((item for item in rows if item["task_ref"] == intent["task_ref"]), None)
            if row is None:
                reject("task_not_in_draft", "这条工序不属于当前试调草稿，没有调整。请回到本草稿重新选择。", 404)
            validator = TrialValidator(self.conn, head["admission"], rows, live)
            before = row["current"]
            row["current"] = validator.adjusted(row, intent)
            checked = validator.evaluate_saved()
            return head, rows, live, row, before, checked, validator.protection

        def mutate(prepared):
            head, rows, live, row, before, checked, protection = prepared
            if before == row["current"]:
                return WorkbenchCommandOutcome("unchanged", self._projection(head, rows, live, (checked, protection)))
            now = self._now()
            require_advanced(self.repo.change(head, row, before, checked, request_key, self.actor_provider(), now))
            current_head = dict(head, revision=head["revision"] + 1, status="editing", validation=checked, updated_at=now)
            return WorkbenchCommandOutcome("committed", self._projection(current_head, rows, live, (checked, protection)))

        return self._execute(CHANGE, draft_ref, intent, write_token, request_key, prepare, mutate)

    def save(self, draft_ref, value, write_token, request_key):
        intent = save_input(value)

        def prepare(head, rows, live):
            scenario_ref = new_ref()
            source_prepared = source_projection(rows, head["admission"], facts=live["source_facts"])
            snapshot = self._projection(head, rows, live, source_prepared=source_prepared, scenario_ref=scenario_ref)
            return head, rows, source_prepared, scenario_ref, snapshot

        def mutate(prepared):
            head, rows, source_prepared, scenario_ref, snapshot = prepared
            snapshot.update(scenario_ref=scenario_ref, name=intent["name"], status="saved", saved_at=self._now())
            for row in snapshot["tasks"]:
                row.update(source_row_ref=row["row_ref"], source_task_ref=row["task_ref"],
                           row_ref=new_ref(), task_ref=new_ref())
                row["edit_context"] = {"can_change": False, "blocked_reasons": [{"code": "scenario_readonly", "message": "试调方案已保存，只能查看不能改。"}]}
            old_to_new = {row["source_task_ref"]: row["task_ref"] for row in snapshot["tasks"]}
            for row in snapshot["tasks"]:
                row["predecessor_refs"] = [old_to_new[ref] for ref in row["predecessor_refs"]]
                row["issues"] = _scenario_issue_refs(row["issues"], old_to_new)
            snapshot["validation"]["issues"] = _scenario_issue_refs(snapshot["validation"]["issues"], old_to_new)
            apply_changeovers(snapshot["comparison"], trial_changeovers(
                [dict(row, row_ref=task["row_ref"]) for row, task in zip(rows, snapshot["tasks"])],
                head["admission"], facts=source_prepared[0]))
            snapshot["preview_target"] = "/api/workbench/v1/trial/scenarios/" + snapshot["scenario_ref"]
            encoded = encode_scenario(snapshot)
            require_advanced(self.repo.save(head, snapshot, encoded, request_key, self.actor_provider(), snapshot["saved_at"]))
            return WorkbenchCommandOutcome("committed", snapshot)

        return self._execute(SAVE, draft_ref, intent, write_token, request_key, prepare, mutate)

    def discard(self, draft_ref, value, write_token, request_key):
        intent = discard_input(value)

        def prepare(head, rows, live):
            checked = TrialValidator(self.conn, head["admission"], rows, live).evaluate_saved()
            return head, checked

        def mutate(prepared):
            head, checked = prepared
            require_advanced(self.repo.transition(head, "discarded", checked, self._now()))
            return WorkbenchCommandOutcome("committed", {"draft_ref": draft_ref, "status": "discarded",
                                                         "validation": checked, "history_retained": True})

        return self._execute(DISCARD, draft_ref, intent, write_token, request_key, prepare, mutate)

    def scenario(self, scenario_ref):
        with candidate_read_snapshot(self.conn):
            with read_evidence_scope(self.conn):
                saved = load_scenario(self.repo, reference(scenario_ref))
                header = self.repo.draft_header(saved["draft_ref"])
                if header is None:
                    # Trial drafts are permanent; every saved scenario keeps its draft.
                    reject("trial_snapshot_invalid", "试调方案的原草稿缺失，请联系维护人员核对。")
                head, rows = load_draft(self.repo, saved["draft_ref"], header=header)
                admission = head["admission"]
                projected = scenario_rows(saved, rows)
                _, archive, _, contexts = source_projection(projected, admission)
                # A saved comparison already holds its delivery summary and changeovers.
                result = {**saved, "tasks": [dict(task) for task in saved["tasks"]],
                          "comparison": dict(saved["comparison"]),
                          "capacity": trial_capacity(projected, archive, source_ref=admission["source"]["identity"])}
                pairs, preparation = preparation_projection(projected, admission, saved.get("operation_effort"),
                    current_evidence={"kind": "scenario", "scenario_ref": saved["scenario_ref"]}, contexts=contexts)
                result["unplanned_operations"] = unplanned_operations(contexts)
                result["scope_complete"] = not result["unplanned_operations"]
                apply_preparation(result["tasks"], result["unplanned_operations"], pairs)
                result["comparison"]["preparation_common"] = preparation
                return result

    def lookup(self, request_key):
        validate_request_key(request_key)
        with candidate_read_snapshot(self.conn):
            commands = WorkbenchCommandService(self.conn)
            row = commands.repo.get(request_key)
            if row is None:
                return None
            if row["action"] not in (CREATE,) + ACTIONS:
                reject("request_key_conflict", "这个操作编号不是试调的操作，请到对应页面查询结果。")
            return commands.repo.public_result(row, replayed=True)


def _scenario_issue_refs(issues, mapping):
    """Issue rows are shared with the draft admission and per-task lists; remapping builds new rows."""
    return [dict(row, **{key: mapping[row[key]] for key in ("task_ref", "related_task_ref") if row.get(key) in mapping})
            for row in issues]
