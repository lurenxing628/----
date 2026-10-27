"""Immutable command receipts stored in the same transaction as business changes."""

from __future__ import annotations

import json
from typing import Any, Dict, NoReturn, Optional

from core.models.content import content_text, unpacked
from core.models.workbench_command import WorkbenchCommandOutcome
from core.shared.strict_json import canonical_json, load_strict_json

from .base_repo import BaseRepository
from .workbench_trial_repo import HISTORY_REFERENCE_FORMAT, WorkbenchTrialRepository


def _corrupt_receipt() -> NoReturn:
    raise ValueError("已保存的命令回执结构不完整。")


def _nonfinite_receipt() -> NoReturn:
    raise ValueError("已保存的命令回执包含非有限数字。")


def _corrupt_input() -> NoReturn:
    raise ValueError("已保存的命令原提交内容缺失或无法读取。")


class WorkbenchCommandRepository(BaseRepository):
    def get(self, request_key: str) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT request_key, receipt_ref, action, context_ref, input_json, outcome_json FROM WorkbenchCommandReceipts WHERE request_key = ?", (request_key,))

    def insert(self, *, request_key: str, receipt_ref: str, action: str, context_ref: str,
               input_json: str, outcome: WorkbenchCommandOutcome) -> Dict[str, Any]:
        payload, history = outcome.payload(), None
        if action == "trial.change":
            # Changes are permanent evidence. Keep this receipt's exact prefix
            # instead of storing every earlier validation body again.
            history = payload["data"]["change_history"]
            data = dict(payload["data"], change_history=WorkbenchTrialRepository(self.conn).history_reference(context_ref))
            payload = dict(payload, data=data)
        outcome_json = canonical_json(payload)
        self.execute("""INSERT INTO WorkbenchCommandReceipts
            (request_key, receipt_ref, action, context_ref, input_json, outcome_json)
            VALUES (?, ?, ?, ?, ?, ?)""", (request_key, receipt_ref, action, context_ref, input_json, outcome_json))
        public = self._public_payload(json.loads(outcome_json), action, history=history)
        return {"ok": True, **public, "receipt_ref": receipt_ref, "replayed": False}

    def _public_payload(self, payload, action, *, history=None):
        if action == "trial.change":
            value = payload["data"]["change_history"]
            if type(value) is dict and value.get("format") == HISTORY_REFERENCE_FORMAT:
                payload["data"]["change_history"] = (history if history is not None else
                    WorkbenchTrialRepository(self.conn).public_history(value["draft_ref"], through_revision=value["through_revision"]))
        return payload

    def input_content(self, row) -> str:
        """The receipt's saved original intent; every receipt stores it, so NULL is a damaged archive."""
        return content_text(unpacked(load_strict_json(row["input_json"], on_malformed=_corrupt_input)))

    def public_result(self, row: Dict[str, Any], *, replayed: bool) -> Dict[str, Any]:
        data = load_strict_json(row["outcome_json"], on_malformed=_corrupt_receipt, on_nonfinite=_nonfinite_receipt,
                                expected=dict)
        if set(data) != {"result", "data", "warnings"}:
            _corrupt_receipt()
        outcome = self._public_payload(WorkbenchCommandOutcome(**data).payload(), row["action"])
        return {"ok": True, **outcome, "receipt_ref": row["receipt_ref"], "replayed": replayed}
