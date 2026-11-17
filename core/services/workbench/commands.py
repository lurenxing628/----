"""Atomic SQLite intent handling. Callers provide normalized input and domain actions."""

from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, Optional, Tuple, Type, Union

from core.errors import BusinessError, ValidationError
from core.infrastructure.transaction import TransactionManager
from core.models.content import StoredJsonCorrupt, content_text
from core.models.workbench_command import (
    WorkbenchCommandOutcome,
    WorkbenchCommandRejected,
    WorkbenchCommandUncertain,
    validate_request_key,
)
from data.repositories.workbench_command_repo import WorkbenchCommandRepository

_DEFAULT_CONFLICT_MESSAGE = "这个操作编号对应的内容和上次提交的不一样，请先核对上次的结果。"


def command_lookup_payload(
    receipt: Optional[Dict[str, Any]],
    *,
    may_be_in_flight: bool = True,
    **extra: Any,
) -> Dict[str, Any]:
    if receipt is not None:
        return {"state": "recorded", "receipt": receipt, "may_be_in_flight": False, "resolution": "recorded", **extra}
    return {
        "state": "not_observed",
        "receipt": None,
        "may_be_in_flight": may_be_in_flight,
        "resolution": "unresolved" if may_be_in_flight else "context_replaced",
        **extra,
    }


class WorkbenchCommandService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.repo = WorkbenchCommandRepository(conn, logger=logger)
        self.tx = TransactionManager(conn)

    def lookup(
        self,
        request_key: str,
        *,
        action: Any = None,
        context_ref: Optional[str] = None,
        conflict_message: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        row = self.repo.get(validate_request_key(request_key))
        if row is None:
            return None
        message = conflict_message or _DEFAULT_CONFLICT_MESSAGE
        if action is not None:
            allowed = (action,) if isinstance(action, str) else tuple(action)
            if row["action"] not in allowed:
                raise WorkbenchCommandRejected("request_key_conflict", message)
        if context_ref is not None and row["context_ref"] != context_ref:
            raise WorkbenchCommandRejected("request_key_conflict", message)
        return self.repo.public_result(row, replayed=True)

    def has_receipt(self, request_key: str) -> bool:
        return self.repo.exists(validate_request_key(request_key))

    def replay(self, *, request_key: str, action: object, context_ref: object, normalized_input: Any) -> Optional[Dict[str, Any]]:
        """Read-only: the committed result of this same intent, or None when none is observed.

        Callers that refuse new work before ``execute`` (for example while a
        scheduling run holds the scheduler lock) check this first, so a retry of
        an already committed request still replays instead of being refused.
        """
        action, context_ref, input_text, input_shape = self._admit(request_key, action, context_ref, normalized_input)
        try:
            return self._replay(request_key, action, context_ref, input_text, input_shape)
        except (WorkbenchCommandRejected, WorkbenchCommandUncertain, BusinessError, ValidationError):
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
        action, context_ref, input_text, input_shape = self._admit(request_key, action, context_ref, normalized_input)
        try:
            # Receipts are immutable and committed atomically with their mutation.
            # A completed SELECT is enough to replay one: taking a write lock here
            # needlessly competes with the worker and long-lived DELETE readers.
            result = self._replay(request_key, action, context_ref, input_text, input_shape)
            if result is not None:
                return result
            with self.tx.transaction(begin_immediate=True):
                # Another connection may have admitted this intent after the
                # read-only lookup. Keep the second lookup under the write lock.
                result = self._replay(request_key, action, context_ref, input_text, input_shape)
                if result is None:
                    result = self._apply(request_key, action, context_ref, input_text, guard, mutate)
            return result
        except (WorkbenchCommandRejected, WorkbenchCommandUncertain, BusinessError, ValidationError):
            raise
        except Exception as exc:
            raise WorkbenchCommandUncertain(request_key) from exc

    def _admit(self, request_key: str, action: object, context_ref: object,
               normalized_input: Any) -> Tuple[str, str, str, Union[Type[dict], Type[list]]]:
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
        # 同一命令的输入形状固定：报工逐行提交是行列表，其余命令是对象；重放按这个形状读回执里存的原提交。
        input_shape = dict if type(normalized_input) is dict else list
        return action, context_ref, input_text, input_shape

    def _replay(self, request_key: str, action: str, context_ref: str, input_text: str,
                input_shape: Union[Type[dict], Type[list]]) -> Optional[Dict[str, Any]]:
        row = self.repo.get(request_key)
        if not row:
            return None
        try:
            self._check_replay(row, action, context_ref, input_text, input_shape)
            return self.repo.public_result(row, replayed=True)
        except StoredJsonCorrupt as exc:
            # 回执在，这个编号就有一次提交已经生效；回执读不出来就核不了是不是同一次提交，只能报结果未知，不能说没提交。
            raise WorkbenchCommandUncertain(request_key) from exc

    def _check_replay(self, row, action: str, context_ref: str, input_text: str,
                      input_shape: Union[Type[dict], Type[list]]) -> None:
        if (row["action"], row["context_ref"]) != (action, context_ref):
            raise WorkbenchCommandRejected("request_key_conflict", "这个操作编号对应的内容和上次提交的不一样，请先核对上次的结果。")
        if self.repo.input_content(row, input_shape) != input_text:
            raise WorkbenchCommandRejected("request_key_conflict", "这个操作编号对应的内容和上次提交的不一样，请先核对上次的结果。")

    def _apply(self, request_key, action, context_ref, input_text, guard, mutate):
        checked = guard()
        outcome = mutate(checked)
        if not isinstance(outcome, WorkbenchCommandOutcome):
            raise TypeError("领域动作必须返回明确的数据库命令结果。")
        receipt_ref = uuid.uuid4().hex
        return self.repo.insert(request_key=request_key, receipt_ref=receipt_ref, action=action,
                                context_ref=context_ref, input_json=input_text, outcome=outcome)
