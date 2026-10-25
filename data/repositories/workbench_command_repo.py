"""Immutable command receipts stored in the same transaction as business changes."""

from __future__ import annotations

import json
import math
from typing import Any, Dict, Optional

from core.infrastructure.connection_guards import schema_contract_memo
from core.models.content import content_text, unpacked
from core.models.scheduler_history_parser import parse_result_summary_payload
from core.models.workbench_command import WorkbenchCommandOutcome, canonical_json

from .base_repo import BaseRepository
from .workbench_trial_repo import HISTORY_REFERENCE_FORMAT, WorkbenchTrialRepository


def _finite_json_number(text):
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("已保存的命令回执包含非有限数字。")
    return value


class WorkbenchCommandRepository(BaseRepository):
    def get(self, request_key: str) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT request_key, receipt_ref, action, context_ref, input_hash, input_json, outcome_json FROM WorkbenchCommandReceipts WHERE request_key = ?", (request_key,))

    def insert(self, *, request_key: str, receipt_ref: str, action: str, context_ref: str,
               outcome: WorkbenchCommandOutcome, input_json: Optional[str] = None,
               input_hash: Optional[str] = None) -> Dict[str, Any]:
        payload, history = outcome.payload(), None
        if action == "trial.change":
            # Changes are permanent evidence. Keep this receipt's exact prefix
            # instead of storing every earlier validation body again.
            history = payload["data"]["change_history"]
            data = dict(payload["data"], change_history=WorkbenchTrialRepository(self.conn).history_reference(context_ref))
            payload = dict(payload, data=data)
        outcome_json = canonical_json(payload)
        self.execute("""INSERT INTO WorkbenchCommandReceipts
            (request_key, receipt_ref, action, context_ref, input_hash, input_json, outcome_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", (request_key, receipt_ref, action, context_ref, input_hash,
                                              input_json, outcome_json))
        public = self._public_payload(json.loads(outcome_json), action, history=history)
        return {"ok": True, **public, "receipt_ref": receipt_ref, "replayed": False}

    def _public_payload(self, payload, action, *, history=None):
        if action == "trial.change":
            value = payload["data"]["change_history"]
            if type(value) is dict and value.get("format") == HISTORY_REFERENCE_FORMAT:
                payload["data"]["change_history"] = (history if history is not None else
                    WorkbenchTrialRepository(self.conn).public_history(value["draft_ref"], through_revision=value["through_revision"]))
        return payload

    def input_content(self, row) -> Optional[str]:
        """Use saved intent, or exact original source fields for known old commands."""
        text = row["input_json"]
        if text is not None:
            return content_text(unpacked(json.loads(text)))
        action, key = row["action"], row["request_key"]
        if action not in {"scheduling.run", "trial.create", "trial.save", "trial.discard",
                          "scheduling.candidate.adopt", "trial.scenario.adopt"}:
            return None
        if action in ("scheduling.candidate.adopt", "trial.scenario.adopt"):
            return self.adoption_input_contents([row])[key]
        structure = schema_contract_memo(self.conn).structure
        if action == "scheduling.run" and structure.has_table("WorkbenchRunJobs"):
            original = self.fetchone("SELECT input_ref, run_ref FROM WorkbenchRunJobs WHERE request_key=?", (key,))
            if original and original["input_ref"] == row["context_ref"]:
                result = self.public_result(row, replayed=True)
                if result["result"] == "committed" and result["data"] == {"run_ref": original["run_ref"]}:
                    return content_text({"input_ref": original["input_ref"]})
        if action in ("trial.create", "trial.save", "trial.discard") and structure.has_table("WorkbenchTrialDrafts"):
            if action == "trial.create":
                original = self.fetchone("SELECT admission_json FROM WorkbenchTrialDrafts WHERE request_key=?", (key,))
                if original:
                    document = unpacked(json.loads(original["admission_json"]))
                    if not isinstance(document, dict):
                        raise ValueError("已保存的试调受理资料结构不完整。")
                    intent = document.get("input")
                    if type(intent) is dict:
                        return content_text(intent)
            elif action == "trial.save" and structure.has_table("WorkbenchTrialScenarios"):
                original = self.fetchone("SELECT draft_ref, name FROM WorkbenchTrialScenarios WHERE request_key=?", (key,))
                if original and original["draft_ref"] == row["context_ref"]:
                    return content_text({"name": original["name"]})
            elif action == "trial.discard":
                result = self.public_result(row, replayed=True)
                if result["result"] == "committed" and result["data"].get("draft_ref") == row["context_ref"]:
                    return content_text({"confirm": True})
        return None

    def adoption_input_contents(self, rows):
        """Recover a request's legacy adoption intents in one history scan."""
        legacy = {row["request_key"]: row for row in rows}
        contents: Dict[str, Optional[str]] = dict.fromkeys(legacy)
        if not legacy or not schema_contract_memo(self.conn).structure.has_table("ScheduleHistory"):
            return contents
        seen = set()
        for original in self.iter_rows("SELECT result_summary FROM ScheduleHistory"):
            audit = parse_result_summary_payload(original["result_summary"]).payload
            if audit is None:
                continue
            key = audit.get("request_key")
            if type(key) is not str or key not in legacy:
                continue
            row = legacy[key]
            context = "candidate_ref" if row["action"] == "scheduling.candidate.adopt" else "scenario_ref"
            if (audit.get(context) == row["context_ref"]
                    and type(audit.get("reason")) is str and type(audit.get("declared_operator")) is str):
                contents[key] = (None if key in seen else content_text({"confirm": True,
                    "reason": audit["reason"], "declared_operator": audit["declared_operator"]}))
                seen.add(key)
        return contents

    def public_result(self, row: Dict[str, Any], *, replayed: bool) -> Dict[str, Any]:
        data = json.loads(row["outcome_json"], parse_float=_finite_json_number, parse_constant=_finite_json_number)
        if not isinstance(data, dict) or set(data) != {"result", "data", "warnings"}:
            raise ValueError("已保存的命令回执结构不完整。")
        outcome = self._public_payload(WorkbenchCommandOutcome(**data).payload(), row["action"])
        return {"ok": True, **outcome, "receipt_ref": row["receipt_ref"], "replayed": replayed}
