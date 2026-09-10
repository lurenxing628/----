"""One SQLite transaction for guard, disposition, immutable history and receipt."""

import getpass

from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_dashboard import payload_size, reference
from core.models.workbench_dashboard_input import next_handling, normalize_input
from core.services.workbench.commands import WorkbenchCommandService

from .dashboard import WorkbenchDashboardService


class WorkbenchDashboardCommandService:
    def __init__(self, conn, *, clock=None, actor_provider=None):
        self.reader = WorkbenchDashboardService(conn, clock=clock)
        self.commands = WorkbenchCommandService(conn)
        self.actor_provider = actor_provider or getpass.getuser

    def execute(self, action, item_ref, payload, *, request_key, validate_context):
        if action not in ("transition", "reopen"):
            raise WorkbenchCommandRejected("invalid_input", "未知处置动作。", 400)
        reference(item_ref)
        normalized = normalize_input(action, payload)

        def guard():
            self.reader.repo.require_schema()
            now = self.reader.clock().replace(microsecond=0)
            data = self.reader.read(now)
            item = self.reader.detail(data, item_ref)
            validate_context(item_ref, action, item["_snapshot"])
            after = next_handling(action, item["_handling"], normalized, now)
            actor = self.actor_provider()
            if type(actor) is not str or not actor.strip():
                raise RuntimeError("Server local operator is required")
            return item, after, now, actor

        def mutate(prepared):
            item, after, now, actor = prepared
            before = item["_handling"]
            changed = before != after
            history_ref = None
            if changed:
                history_ref = self.reader.repo.append(item=item, before=before, after=after,
                    facts={"facts": item["_facts"], "guard": item["_snapshot"]}, actor=actor, action=action,
                    reason=normalized.get("reason"), request_key=request_key, now=now)
            result = payload_size({"item_ref": item_ref, "handling": after, "history_ref": history_ref,
                                   "risk": item["risk"], "source": item["source"], "refresh_required": True})
            return WorkbenchCommandOutcome("committed" if changed else "unchanged", result)

        return self.commands.execute(request_key=request_key, action="dashboard." + action, context_ref=item_ref,
                                     normalized_input=normalized, guard=guard, mutate=mutate)
