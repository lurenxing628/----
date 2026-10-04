"""One SQLite transaction for guard, disposition, immutable history and receipt.

The whole dashboard is computed before BEGIN IMMEDIATE; the guard reuses it while the database is unchanged.
"""

import getpass
from contextlib import nullcontext

from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_dashboard import payload_size, reference
from core.models.workbench_dashboard_input import next_handling, normalize_input
from core.services.workbench.command_prefetch import run_prefetched, write_stamp
from core.services.workbench.commands import WorkbenchCommandService

from .service import WorkbenchDashboardService


class WorkbenchDashboardCommandService:
    def __init__(self, conn, *, clock=None, actor_provider=None):
        self.conn = conn
        self.reader = WorkbenchDashboardService(conn, clock=clock)
        self.commands = WorkbenchCommandService(conn)
        self.actor_provider = actor_provider or getpass.getuser

    def _prefetch(self, admission):
        """拿写锁前先在读快照里读出整份看板并记下库版本；投影在读事务结束后做。"""
        with admission() if admission else nullcontext():
            with self.reader.read_snapshot():
                now = self.reader.clock().replace(microsecond=0)
                sources = self.reader.load(now)
                stamp = write_stamp(self.conn)
            return (now, self.reader.project(sources)), stamp

    def _recompute(self):
        now = self.reader.clock().replace(microsecond=0)
        return now, self.reader.read(now)

    def execute(self, action, item_ref, payload, *, request_key, validate_context, admission=None):
        """admission: optional read-budget slot, held only while prefetching and never under the write lock."""
        if action not in ("transition", "reopen"):
            raise WorkbenchCommandRejected("invalid_input", "未知处置动作。", 400)
        reference(item_ref)
        normalized = normalize_input(action, payload)
        intent = {"request_key": request_key, "action": "dashboard." + action, "context_ref": item_ref, "normalized_input": normalized}
        # 已提交的同一请求直接重放，不为它重算整份看板。
        replayed = self.commands.replay(**intent)
        if replayed is not None:
            return replayed

        def command(prefetched):
            def guard():
                self.reader.require_schema()
                now, data = prefetched.current(self._recompute)
                item = self.reader.detail(data, item_ref)
                validate_context(item_ref, action, item["_snapshot"])
                after = next_handling(action, item["_handling"], normalized, now)
                actor = self.actor_provider()
                if type(actor) is not str or not actor.strip():
                    raise RuntimeError("Server local operator is required")
                return item, after, now, actor

            return self.commands.execute(**intent, guard=guard, mutate=self._mutate(action, item_ref, normalized, request_key))

        return run_prefetched(self.conn, lambda: self._prefetch(admission), command)

    def _mutate(self, action, item_ref, normalized, request_key):
        def mutate(prepared):
            item, after, now, actor = prepared
            before = item["_handling"]
            changed = before != after
            history_ref = None
            if changed:
                history_ref = self.reader.append_handling(item=item, before=before, after=after,
                    facts={"facts": item["_facts"], "guard": item["_snapshot"]}, actor=actor, action=action,
                    reason=normalized.get("reason"), request_key=request_key, now=now)
            result = payload_size({"item_ref": item_ref, "handling": after, "history_ref": history_ref,
                                   "risk": item["risk"], "source": item["source"], "refresh_required": True})
            return WorkbenchCommandOutcome("committed" if changed else "unchanged", result)

        return mutate
