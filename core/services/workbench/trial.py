"""Persistent draft lifecycle. No publish, actual writes, or latest-base fallback."""

import getpass
from copy import deepcopy
from datetime import datetime

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
from core.models.workbench_trial_codec import fingerprint
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.run_input_readonly import candidate_read_snapshot
from data.repositories.workbench_trial_repo import WorkbenchTrialRepository, new_ref

from .trial_base import prepare_base
from .trial_facts import live_context
from .trial_projection import draft_projection, write_snapshot
from .trial_validation import TrialValidator


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
        return {"input": admission["input"], "facts_hash": admission["facts_hash"],
                "source_hash": fingerprint(admission["source"]),
                "rows_hash": fingerprint([(row["source_row_ref"], row["original"]) for row in rows])}

    def preview_create(self, value):
        intent = create_input(value)
        with candidate_read_snapshot(self.conn):
            self.repo.require_schema()
            admission, rows, live = prepare_base(self.conn, intent)
            checked = TrialValidator(self.conn, admission, rows, live).evaluate()
            context = self.context_factory(next(iter(intent["base"].values())), [CREATE], self._create_snapshot(admission, rows))
            return {"base": intent["base"], "scope": intent["scope"], "task_count": len(rows),
                    "tasks_complete": True, "validation": checked, "write_context": context}

    def create(self, value, write_token, request_key):
        intent = create_input(value)
        base_ref = next(iter(intent["base"].values()))

        def guard():
            self.repo.require_schema()
            admission, rows, live = prepare_base(self.conn, intent)
            self.context_validator(write_token, base_ref, CREATE, self._create_snapshot(admission, rows))
            return admission, rows, live

        def mutate(prepared):
            admission, rows, live = prepared
            checked = TrialValidator(self.conn, admission, rows, live).evaluate()
            ref = self.repo.create(admission, rows, checked, request_key, self.actor_provider(), self._now())
            head, stored = self.repo.get(ref)
            return WorkbenchCommandOutcome("committed", self._projection(head, stored, live, checked))

        return WorkbenchCommandService(self.conn).execute(request_key=request_key, action=CREATE,
            context_ref=base_ref, normalized_input=intent, guard=guard, mutate=mutate)

    def _loaded(self, ref):
        head, rows = self.repo.get(reference(ref))
        live = live_context(self.conn, [row["operation_ref"] for row in rows])
        return head, rows, live

    def _projection(self, head, rows, live, checked=None):
        if checked is None:
            checked = TrialValidator(self.conn, head["admission"], rows, live).evaluate()
        result = draft_projection(head, rows, checked, live, self.context_factory)
        changes = self.repo.changes(head["draft_ref"])
        for item in changes:
            for side in ("before", "after"):
                item[side] = {key: item[side][key] for key in ("machine_ref", "operator_ref", "start", "end")}
        result["change_history"] = changes
        return result

    def get(self, draft_ref):
        with candidate_read_snapshot(self.conn):
            return self._projection(*self._loaded(draft_ref))

    def _execute(self, action, ref, intent, token, key, mutate):
        reference(ref)

        def guard():
            head, rows, live = self._loaded(ref)
            self.context_validator(token, ref, action, write_snapshot(head, rows, live))
            if head["status"] != "editing":
                reject("draft_closed", "草稿已保存或已放弃，不能再改。")
            return head, rows, live

        return WorkbenchCommandService(self.conn).execute(request_key=key, action=action, context_ref=ref,
                                                          normalized_input=intent, guard=guard, mutate=mutate)

    def change(self, draft_ref, value, write_token, request_key):
        intent = change_input(value)

        def mutate(prepared):
            head, rows, live = prepared
            row = next((item for item in rows if item["task_ref"] == intent["task_ref"]), None)
            if row is None:
                reject("task_not_in_draft", "这条工序不属于当前试调草稿，没有调整。请回到本草稿重新选择。", 404)
            validator = TrialValidator(self.conn, head["admission"], rows, live)
            before = row["current"]
            row["current"] = validator.adjusted(row, intent)
            checked = validator.evaluate()
            if before == row["current"]:
                return WorkbenchCommandOutcome("unchanged", self._projection(head, rows, live, checked))
            self.repo.change(head, row, before, checked, request_key, self.actor_provider(), self._now())
            current_head, current_rows = self.repo.get(draft_ref)
            return WorkbenchCommandOutcome("committed", self._projection(current_head, current_rows, live, checked))

        return self._execute(CHANGE, draft_ref, intent, write_token, request_key, mutate)

    def save(self, draft_ref, value, write_token, request_key):
        intent = save_input(value)

        def mutate(prepared):
            head, rows, live = prepared
            snapshot = deepcopy(self._projection(head, rows, live))
            snapshot.update(scenario_ref=new_ref(), name=intent["name"], status="saved", saved_at=self._now())
            snapshot.pop("write_context")
            for row in snapshot["tasks"]:
                row.update(source_row_ref=row["row_ref"], source_task_ref=row["task_ref"],
                           row_ref=new_ref(), task_ref=new_ref())
                row["edit_context"] = {"can_change": False, "blocked_reasons": [{"code": "scenario_readonly", "message": "试调方案已保存，只能查看不能改。"}]}
            old_to_new = {row["source_task_ref"]: row["task_ref"] for row in snapshot["tasks"]}
            for row in snapshot["tasks"]:
                row["predecessor_refs"] = [old_to_new[ref] for ref in row["predecessor_refs"]]
                _scenario_issue_refs(row["issues"], old_to_new)
            _scenario_issue_refs(snapshot["validation"]["issues"], old_to_new)
            snapshot["preview_target"] = "/api/workbench/v1/trial/scenarios/" + snapshot["scenario_ref"]
            self.repo.save(head, snapshot, request_key, self.actor_provider(), snapshot["saved_at"])
            return WorkbenchCommandOutcome("committed", snapshot)

        return self._execute(SAVE, draft_ref, intent, write_token, request_key, mutate)

    def discard(self, draft_ref, value, write_token, request_key):
        intent = discard_input(value)

        def mutate(prepared):
            head, rows, live = prepared
            checked = TrialValidator(self.conn, head["admission"], rows, live).evaluate()
            self.repo.transition(head, "discarded", checked, self._now())
            return WorkbenchCommandOutcome("committed", {"draft_ref": draft_ref, "status": "discarded",
                                                         "validation": checked, "history_retained": True})

        return self._execute(DISCARD, draft_ref, intent, write_token, request_key, mutate)

    def scenario(self, scenario_ref):
        with candidate_read_snapshot(self.conn):
            return self.repo.scenario(reference(scenario_ref))

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
    for row in issues:
        for key in ("task_ref", "related_task_ref"):
            if row.get(key) in mapping:
                row[key] = mapping[row[key]]
