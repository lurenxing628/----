"""Atomic SQLite intent handling. Callers provide normalized input and domain actions."""

from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, Optional

from core.errors import BusinessError, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import (
    WorkbenchCommandOutcome,
    WorkbenchCommandRejected,
    WorkbenchCommandUncertain,
    input_fingerprint,
    validate_request_key,
)
from data.repositories.workbench_command_repo import WorkbenchCommandRepository


class WorkbenchCommandService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.repo = WorkbenchCommandRepository(conn, logger=logger)
        self.tx = TransactionManager(conn)

    def lookup(self, request_key: str) -> Optional[Dict[str, Any]]:
        row = self.repo.get(validate_request_key(request_key))
        return self.repo.public_result(row, replayed=True) if row else None

    def execute(self, *, request_key: str, action: str, context_ref: str, normalized_input: Any,
                guard: Callable[[], Any], mutate: Callable[[Any], WorkbenchCommandOutcome]) -> Dict[str, Any]:
        """Own the outer transaction; replay before checking a now-expired edit token.

        ``guard`` re-reads and validates current facts under the acquired write lock.
        ``mutate`` uses this same connection and existing nested domain transactions.
        It must not perform file/remote actions or commit the connection directly.
        A missing lookup means no committed receipt was observed, not that an in-flight
        request cannot still complete. A retry must retain its original request key.
        """
        validate_request_key(request_key)
        if not isinstance(action, str) or not action or not isinstance(context_ref, str) or not context_ref:
            raise WorkbenchCommandRejected("invalid_input", "未提供要操作的对象或操作类型。", 400)
        try:
            fingerprint = input_fingerprint(normalized_input)
        except (TypeError, ValueError, OverflowError) as exc:
            raise WorkbenchCommandRejected("invalid_input", "操作内容包含不能保存的数据。", 400) from exc
        if self.conn.in_transaction:
            raise RuntimeError("工作台命令必须拥有最外层事务，不能在调用方未提交的事务中声称已保存。")
        try:
            with self.tx.transaction(begin_immediate=True):
                row = self.repo.get(request_key)
                if row:
                    self._check_replay(row, action, context_ref, fingerprint)
                    result = self.repo.public_result(row, replayed=True)
                else:
                    result = self._apply(request_key, action, context_ref, fingerprint, guard, mutate)
            return result
        except (WorkbenchCommandRejected, BusinessError, ValidationError):
            raise
        except Exception as exc:
            raise WorkbenchCommandUncertain(request_key) from exc

    @staticmethod
    def _check_replay(row, action: str, context_ref: str, fingerprint: str) -> None:
        if (row["action"], row["context_ref"], row["input_hash"]) != (action, context_ref, fingerprint):
            raise WorkbenchCommandRejected("request_key_conflict", "同一请求标识对应的操作内容发生变化，请核对已有结果。")

    def _apply(self, request_key, action, context_ref, fingerprint, guard, mutate):
        checked = guard()
        outcome = mutate(checked)
        if not isinstance(outcome, WorkbenchCommandOutcome):
            raise TypeError("领域动作必须返回明确的数据库命令结果。")
        receipt_ref = uuid.uuid4().hex
        self.repo.insert(request_key=request_key, receipt_ref=receipt_ref, action=action,
                         context_ref=context_ref, input_hash=fingerprint, outcome=outcome)
        row = self.repo.get(request_key)
        if row is None:
            raise RuntimeError("命令回执写入后无法读回。")
        return self.repo.public_result(row, replayed=False)
