"""One SQLite transaction for guard, disposition, immutable history and receipt.

Only the target item's source closure is read before BEGIN IMMEDIATE; the guard reuses it while unchanged.
"""

import getpass
from contextlib import nullcontext
from datetime import datetime
from typing import Callable

from core.models.enums import DASHBOARD_HANDLING_ACTION_VALUES
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_dashboard import reference
from core.models.workbench_dashboard_input import next_handling, normalize_input
from core.services.workbench.command_prefetch import run_prefetched, write_stamp
from core.services.workbench.commands import WorkbenchCommandService

from .service import WorkbenchDashboardService


class WorkbenchDashboardCommandService:
    def __init__(self, conn, *, clock: Callable[[], datetime], actor_provider=None):
        self.conn = conn
        self.clock = clock
        self.reader = WorkbenchDashboardService(conn)
        self.commands = WorkbenchCommandService(conn)
        self.actor_provider = actor_provider or getpass.getuser

    def _prefetch(self, item_ref, admission):
        """拿写锁前先在读快照里仅读取目标条目的来源闭包并记下库版本；投影在读事务结束后做。"""
        with admission() if admission else nullcontext():
            with self.reader.read_snapshot():
                now = self.clock().replace(microsecond=0)
                captured = self.reader.load_command_item(item_ref, now)
                stamp = write_stamp(self.conn)
            return (now, self.reader.project_command_item(captured)), stamp

    def _recompute(self, item_ref):
        now = self.clock().replace(microsecond=0)
        return now, self.reader.read_command_item(item_ref, now)

    def execute(self, action, item_ref, payload, *, request_key, validate_context, admission=None):
        """admission: optional read-budget slot, held only while prefetching and never under the write lock."""
        if action not in DASHBOARD_HANDLING_ACTION_VALUES:
            raise WorkbenchCommandRejected("invalid_input", "未知处置动作。", 400)
        reference(item_ref)
        normalized = normalize_input(action, payload)
        intent = {
            "request_key": request_key,
            "action": "dashboard." + action,
            "context_ref": item_ref,
            "normalized_input": normalized,
        }
        # 已提交的同一请求直接重放，不为它再读条目来源。
        replayed = self.commands.replay(**intent)
        if replayed is not None:
            return replayed

        def command(prefetched):
            def guard():
                now, item = prefetched.current(lambda: self._recompute(item_ref))
                validate_context(item_ref, action, item["_snapshot"])
                after = next_handling(action, item["_handling"], normalized, now)
                actor = self.actor_provider()
                if type(actor) is not str or not actor.strip():
                    raise RuntimeError("Server local operator is required")
                return item, after, now, actor

            return self.commands.execute(
                **intent,
                guard=guard,
                mutate=self._mutate(action, item_ref, normalized, request_key),
            )

        return run_prefetched(self.conn, lambda: self._prefetch(item_ref, admission), command)

    def _mutate(self, action, item_ref, normalized, request_key):
        def mutate(prepared):
            item, after, now, actor = prepared
            before = item["_handling"]
            changed = before != after
            history_ref = None
            if changed:
                history_ref = self.reader.repo.append(
                    item=item,
                    before=before,
                    after=after,
                    actor=actor,
                    action=action,
                    reason=normalized.get("reason"),
                    request_key=request_key,
                    now=now,
                )
            result = {
                "item_ref": item_ref,
                "handling": after,
                "history_ref": history_ref,
                "risk": item["risk"],
                "source": item["source"],
                "refresh_required": True,
            }
            return WorkbenchCommandOutcome("committed" if changed else "unchanged", result)

        return mutate
