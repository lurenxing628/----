"""Immutable command receipts stored in the same transaction as business changes."""

from __future__ import annotations

import json
import math
from typing import Any, Dict, Optional

from core.models.content import content_text, unpacked
from core.models.scheduler_history_parser import parse_result_summary_payload
from core.models.workbench_command import WorkbenchCommandOutcome, canonical_json

from .base_repo import BaseRepository


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
        outcome_json = canonical_json(outcome.payload())
        self.execute("""INSERT INTO WorkbenchCommandReceipts
            (request_key, receipt_ref, action, context_ref, input_hash, input_json, outcome_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)""", (request_key, receipt_ref, action, context_ref, input_hash,
                                              input_json, outcome_json))
        return {"ok": True, **json.loads(outcome_json), "receipt_ref": receipt_ref, "replayed": False}

    def input_content(self, row) -> Optional[str]:
        """Use saved intent, or exact original source fields for known old commands."""
        text = row.get("input_json")
        if text is not None:
            return content_text(unpacked(json.loads(text)))
        action, key = row["action"], row["request_key"]
        if action not in {"scheduling.run", "trial.create", "trial.save", "trial.discard",
                          "scheduling.candidate.adopt", "trial.scenario.adopt"}:
            return None
        from core.infrastructure.connection_guards import schema_contract_memo

        names = {name for name, value in schema_contract_memo(self.conn).structure.objects.items() if value[0] == "table"}
        if action == "scheduling.run" and "WorkbenchRunJobs" in names:
            original = self.fetchone("SELECT input_ref, run_ref FROM WorkbenchRunJobs WHERE request_key=?", (key,))
            if original and original["input_ref"] == row["context_ref"]:
                result = self.public_result(row, replayed=True)
                if result["result"] == "committed" and result["data"] == {"run_ref": original["run_ref"]}:
                    return content_text({"input_ref": original["input_ref"]})
        if action in ("trial.create", "trial.save", "trial.discard") and "WorkbenchTrialDrafts" in names:
            if action == "trial.create":
                original = self.fetchone("SELECT admission_json FROM WorkbenchTrialDrafts WHERE request_key=?", (key,))
                if original:
                    document = unpacked(json.loads(original["admission_json"]))
                    if not isinstance(document, dict):
                        raise ValueError("已保存的试调受理资料结构不完整。")
                    intent = document.get("input")
                    if type(intent) is dict:
                        return content_text(intent)
            elif action == "trial.save" and "WorkbenchTrialScenarios" in names:
                original = self.fetchone("SELECT draft_ref, name FROM WorkbenchTrialScenarios WHERE request_key=?", (key,))
                if original and original["draft_ref"] == row["context_ref"]:
                    return content_text({"name": original["name"]})
            elif action == "trial.discard":
                result = self.public_result(row, replayed=True)
                if result["result"] == "committed" and result["data"].get("draft_ref") == row["context_ref"]:
                    return content_text({"confirm": True})
        if action in ("scheduling.candidate.adopt", "trial.scenario.adopt") and "ScheduleHistory" in names:
            matches = []
            for original in self.fetchall("SELECT result_summary FROM ScheduleHistory"):
                if original["result_summary"] is None:
                    continue
                audit = parse_result_summary_payload(original["result_summary"]).payload
                context = "candidate_ref" if action == "scheduling.candidate.adopt" else "scenario_ref"
                if (type(audit) is dict and audit.get("request_key") == key
                        and audit.get(context) == row["context_ref"]
                        and type(audit.get("reason")) is str and type(audit.get("declared_operator")) is str):
                    matches.append({"confirm": True, "reason": audit["reason"], "declared_operator": audit["declared_operator"]})
            if len(matches) == 1:
                return content_text(matches[0])
        return None

    @staticmethod
    def public_result(row: Dict[str, Any], *, replayed: bool) -> Dict[str, Any]:
        data = json.loads(row["outcome_json"], parse_float=_finite_json_number, parse_constant=_finite_json_number)
        if not isinstance(data, dict) or set(data) != {"result", "data", "warnings"}:
            raise ValueError("已保存的命令回执结构不完整。")
        outcome = WorkbenchCommandOutcome(**data).payload()
        return {"ok": True, **outcome, "receipt_ref": row["receipt_ref"], "replayed": replayed}
