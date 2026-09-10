"""Immutable command receipts stored in the same transaction as business changes."""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from core.models.workbench_command import WorkbenchCommandOutcome, canonical_json

from .base_repo import BaseRepository


class WorkbenchCommandRepository(BaseRepository):
    def get(self, request_key: str) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT request_key, receipt_ref, action, context_ref, input_hash, outcome_json FROM WorkbenchCommandReceipts WHERE request_key = ?", (request_key,))

    def insert(self, *, request_key: str, receipt_ref: str, action: str, context_ref: str,
               input_hash: str, outcome: WorkbenchCommandOutcome) -> None:
        self.execute("""INSERT INTO WorkbenchCommandReceipts
            (request_key, receipt_ref, action, context_ref, input_hash, outcome_json)
            VALUES (?, ?, ?, ?, ?, ?)""", (request_key, receipt_ref, action, context_ref, input_hash, canonical_json(outcome.payload())))

    @staticmethod
    def public_result(row: Dict[str, Any], *, replayed: bool) -> Dict[str, Any]:
        data = json.loads(row["outcome_json"])
        if not isinstance(data, dict) or set(data) != {"result", "data", "warnings"}:
            raise ValueError("已保存的命令回执结构不完整。")
        outcome = WorkbenchCommandOutcome(**data).payload()
        canonical_json(outcome)
        return {"ok": True, **outcome, "receipt_ref": row["receipt_ref"], "replayed": replayed}
