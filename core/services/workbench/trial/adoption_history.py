"""Readonly scenario adoption directory; every page binds live identity state."""

from core.models.workbench_trial import reference, reject
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from data.repositories.workbench_trial_adoption_history import TrialAdoptionHistoryRepository

from .adoption_history_evidence import (
    audit_fields,
    gap,
    read_bounded_scenario,
    receipt_plan,
    scenario_headers,
)
from .adoption_history_policy import adoption_receipts


def history_scope(scenario_ref, status, size):
    reference(scenario_ref)
    if status not in ("all", "current", "historical", "unavailable") or type(size) is not int or not 1 <= size <= 50:
        reject("invalid_input", "采用记录的状态筛选或每页条数不对，请重新选择。", 400)
    return {"source": "production", "kind": "trial_adoption_history", "scenario_ref": scenario_ref, "status": status, "size": size}


class WorkbenchTrialAdoptionHistoryService:
    def __init__(self, conn):
        self.conn = conn

    def read(self, scenario_ref, *, status="all", page=1, size=20, bind_snapshot):
        scope = history_scope(scenario_ref, status, size)
        if type(page) is not int or not 1 <= page <= 100000:
            reject("invalid_input", "页码必须是 1 至 100000 的整数。", 400)
        reader = WorkbenchPlanQueryService(self.conn)
        with candidate_read_snapshot(self.conn):
            with reader.read_snapshot() as context:
                return self._read(scope, page, context, reader, bind_snapshot=bind_snapshot)

    def _read(self, scope, page, context, reader, *, bind_snapshot):
        repo = TrialAdoptionHistoryRepository(self.conn)
        trial_repo, header, draft = scenario_headers(self.conn, scope["scenario_ref"])
        revision = context.plan_revision
        catalog = context.repo
        current_version = catalog.latest_version()
        rows = adoption_receipts(repo, scope["scenario_ref"])
        plans = [receipt_plan(row) for row in rows]
        all_items = []
        versions = [plan["version"] for plan in plans]
        catalog.prefetch_history_rows(versions)
        histories = [catalog.get_history_row(version) for version in versions]
        for row, plan, history in zip(rows, plans, histories):
            audit, audit_gaps = audit_fields(history=history)
            identity, issues = self._identity(context, reader, history)
            state = (
                "unavailable"
                if identity is None or not identity["capabilities"]["view"]
                else ("current" if identity["is_current_official"] else "historical")
            )
            all_items.append(
                {
                    "receipt_ref": row["receipt_ref"],
                    "request_key": row["request_key"],
                    "scenario_ref": header["scenario_ref"],
                    "draft_ref": header["draft_ref"],
                    "committed_at_utc": row["committed_at_utc"],
                    "committed_plan": plan,
                    "official_plan": identity,
                    "current_state": state,
                    "adoption": audit,
                    "evidence_gaps": issues + audit_gaps,
                    "field_sources": {
                        "commit": "WorkbenchCommandReceipts",
                        "intent": "ScheduleHistory",
                        "actor_and_local_time": "ScheduleHistory",
                        "current_state": "live_plan_identity",
                    },
                }
            )
        content = {
            "scenario_ref": header["scenario_ref"],
            "draft_ref": header["draft_ref"],
            "scenario_revision": header["revision"],
            "draft_revision": draft["revision"],
            "save_request_key": header["request_key"],
            "adoptions": [
                {
                    "receipt_ref": item["receipt_ref"],
                    "request_key": item["request_key"],
                    "plan_ref": item["committed_plan"]["plan_ref"],
                    "version": item["committed_plan"]["version"],
                    "current_state": item["current_state"],
                    "source_issue": item["evidence_gaps"],
                }
                for item in all_items
            ],
            "identity_revision": revision,
            "current_version": current_version,
        }
        snapshot = bind_snapshot(scope, content)
        saved = read_bounded_scenario(trial_repo, scope["scenario_ref"], header=header)
        items = [item for item in all_items if scope["status"] == "all" or item["current_state"] == scope["status"]]
        pages = (len(items) + scope["size"] - 1) // scope["size"]
        if page > max(1, pages):
            reject("invalid_input", "翻页位置已失效，请回到第 1 页重新查询。", 400)
        source = {
            "base": saved["base"],
            "base_identity": saved["base_identity"],
            "baseline": saved["baseline"],
            "name": saved["name"],
            "saved_at": header["saved_at"],
            "saved_by": header["local_operator"],
            "save_request_key": header["request_key"],
            "draft_ref": saved["draft_ref"],
            "scenario_ref": saved["scenario_ref"],
        }
        offset = (page - 1) * scope["size"]
        return (
            {
                "scope": scope,
                "source": source,
                "items": items[offset : offset + scope["size"]],
                "page": {"number": page, "size": scope["size"], "total": len(items), "pages": pages},
                "total_adoptions": len(all_items),
                "state": "available" if items else "empty",
            },
            snapshot,
        )

    @staticmethod
    def _identity(context, reader, history):
        if history is None:
            return None, [gap("official_identity_unavailable", "此次采用生成的正式计划编号已失效，暂无法打开。")]
        identity = reader.catalog_role(context, history)
        return identity, identity["blocked_reasons"]
