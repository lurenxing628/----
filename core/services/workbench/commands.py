"""Atomic SQLite intent handling. Callers provide normalized input and domain actions."""

from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, Optional, Tuple

from core.errors import BusinessError, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.content import content_text
from core.models.workbench_command import (
    WorkbenchCommandOutcome,
    WorkbenchCommandRejected,
    WorkbenchCommandUncertain,
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

    def replay(self, *, request_key: str, action: object, context_ref: object, normalized_input: Any) -> Optional[Dict[str, Any]]:
        """Read-only: the committed result of this same intent, or None when none is observed.

        Callers that refuse new work before ``execute`` (for example while a
        scheduling run holds the scheduler lock) check this first, so a retry of
        an already committed request still replays instead of being refused.
        """
        action, context_ref, input_text = self._admit(request_key, action, context_ref, normalized_input)
        try:
            return self._replay(request_key, action, context_ref, input_text)
        except (WorkbenchCommandRejected, BusinessError, ValidationError):
            raise
        except Exception as exc:
            raise WorkbenchCommandUncertain(request_key) from exc

    def execute(self, *, request_key: str, action: object, context_ref: object, normalized_input: Any,
                guard: Callable[[], Any], mutate: Callable[[Any], WorkbenchCommandOutcome]) -> Dict[str, Any]:
        """Own the outer transaction; replay before checking a now-expired edit token.

        ``guard`` re-reads and validates current facts under the acquired write lock.
        ``mutate`` uses this same connection and existing nested domain transactions.
        It must not perform file/remote actions or commit the connection directly.
        A missing lookup means no committed receipt was observed, not that an in-flight
        request cannot still complete. A retry must retain its original request key.
        """
        action, context_ref, input_text = self._admit(request_key, action, context_ref, normalized_input)
        try:
            # Receipts are immutable and committed atomically with their mutation.
            # A completed SELECT is enough to replay one: taking a write lock here
            # needlessly competes with the worker and long-lived DELETE readers.
            result = self._replay(request_key, action, context_ref, input_text)
            if result is not None:
                return result
            with self.tx.transaction(begin_immediate=True):
                # Another connection may have admitted this intent after the
                # read-only lookup. Keep the second lookup under the write lock.
                result = self._replay(request_key, action, context_ref, input_text)
                if result is None:
                    result = self._apply(request_key, action, context_ref, input_text, guard, mutate)
            return result
        except (WorkbenchCommandRejected, BusinessError, ValidationError):
            raise
        except Exception as exc:
            raise WorkbenchCommandUncertain(request_key) from exc

    def _admit(self, request_key: str, action: object, context_ref: object, normalized_input: Any) -> Tuple[str, str, str]:
        # Admission boundary: some routes pass raw request-body values (for example a preview_ref).
        validate_request_key(request_key)
        if not isinstance(action, str) or not action or not isinstance(context_ref, str) or not context_ref:
            raise WorkbenchCommandRejected("invalid_input", "没有指定要操作哪条记录或做什么操作。", 400)
        try:
            input_text = content_text(normalized_input, json_input=True)
        except (TypeError, ValueError, OverflowError) as exc:
            raise WorkbenchCommandRejected("invalid_input", "提交的内容里有存不下来的数据，操作没有完成。", 400) from exc
        if self.conn.in_transaction:
            raise RuntimeError("工作台命令必须拥有最外层事务，不能在调用方未提交的事务中声称已保存。")
        return action, context_ref, input_text

    def _replay(self, request_key: str, action: str, context_ref: str, input_text: str) -> Optional[Dict[str, Any]]:
        row = self.repo.get(request_key)
        if not row:
            return None
        self._check_replay(row, action, context_ref, input_text)
        return self.repo.public_result(row, replayed=True)

    def _check_replay(self, row, action: str, context_ref: str, input_text: str) -> None:
        if (row["action"], row["context_ref"]) != (action, context_ref):
            raise WorkbenchCommandRejected("request_key_conflict", "这个操作编号对应的内容和上次提交的不一样，请先核对上次的结果。")
        original = self.repo.input_content(row)
        if original is None:
            raise WorkbenchCommandRejected("command_original_input_missing", "此操作已有保存结果，原提交内容未保存。请先读取该操作的回执结果。")
        if original != input_text:
            raise WorkbenchCommandRejected("request_key_conflict", "这个操作编号对应的内容和上次提交的不一样，请先核对上次的结果。")

    def _apply(self, request_key, action, context_ref, input_text, guard, mutate):
        checked = guard()
        outcome = mutate(checked)
        if not isinstance(outcome, WorkbenchCommandOutcome):
            raise TypeError("领域动作必须返回明确的数据库命令结果。")
        receipt_ref = uuid.uuid4().hex
        return self.repo.insert(request_key=request_key, receipt_ref=receipt_ref, action=action,
                                context_ref=context_ref, input_json=input_text, outcome=outcome)
