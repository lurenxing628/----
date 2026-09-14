"""Readonly scenario adoption directory; every page binds live identity state."""

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from core.models.workbench_plan_reference import WorkbenchPlanLocator, WorkbenchPlanReferenceError
from core.models.workbench_trial import reference, reject
from core.services.scheduler.workbench_plan_page import _PagePlanQueryService
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from data.repositories.workbench_trial_adoption_history import MAX_DIRECTORY_BYTES, TrialAdoptionHistoryRepository

from .plan_queries import WorkbenchPlanQueryService
from .run_input_readonly import candidate_read_snapshot
from .trial_adoption_history_evidence import audit_fields, gap, invalid, receipt_plan, scenario_evidence


def history_scope(scenario_ref, status="all", size=20):
    reference(scenario_ref)
    if status not in ("all", "current", "historical", "unavailable") or type(size) is not int or not 1 <= size <= 50:
        reject("invalid_input", "采用记录的状态筛选或每页条数不对，请重新选择。", 400)
    return {"source": "production", "kind": "trial_adoption_history", "scenario_ref": scenario_ref, "status": status, "size": size}


class WorkbenchTrialAdoptionHistoryService:
    def __init__(self, conn):
        self.conn = conn

    def read(self, scenario_ref, *, status="all", page=1, size=20):
        scope = history_scope(scenario_ref, status, size)
        if type(page) is not int or not 1 <= page <= 100000:
            reject("invalid_input", "页码必须是 1 至 100000 的整数。", 400)
        with candidate_read_snapshot(self.conn):
            try:
                return self._read(scope, page)
            except WorkbenchCommandRejected:
                raise
            except (KeyError, TypeError, ValueError, OverflowError):
                invalid()

    def _read(self, scope, page):
        saved, header, draft = scenario_evidence(self.conn, scope["scenario_ref"])
        repo = TrialAdoptionHistoryRepository(self.conn)
        refs = WorkbenchPlanIdentityRepository(self.conn)
        revision = refs.read_revision()
        catalog = WorkbenchPlanCatalogRepository(self.conn)
        # This is current-state evidence only. It never chooses the requested scene.
        current_version = catalog.latest_version()
        query = _PagePlanQueryService(catalog, current_version)
        reader = WorkbenchPlanQueryService(self.conn)
        rows, all_items, seen = repo.receipts(scope["scenario_ref"]), [], set()
        for row in rows:
            plan = receipt_plan(row, saved)
            if plan["plan_ref"] in seen:
                invalid()
            seen.add(plan["plan_ref"])
            audit, audit_gaps = audit_fields(repo, row, plan, saved, header, draft)
            identity, issues = self._identity(refs, reader, query, plan)
            state = "unavailable" if identity is None or not identity["capabilities"]["view"] else (
                "current" if identity["is_current_official"] else "historical")
            all_items.append({"receipt_ref": row["receipt_ref"], "request_key": row["request_key"],
                "scenario_ref": saved["scenario_ref"], "draft_ref": saved["draft_ref"],
                "committed_at_utc": row["committed_at_utc"], "committed_plan": plan,
                "official_plan": identity, "current_state": state, "adoption": audit,
                "evidence_gaps": issues + audit_gaps,
                "field_sources": {"commit": "WorkbenchCommandReceipts", "intent": "receipt_input_hash+ScheduleHistory",
                                  "actor_and_local_time": "ScheduleHistory", "current_state": "live_plan_identity"}})
        items = [item for item in all_items if scope["status"] == "all" or item["current_state"] == scope["status"]]
        pages = (len(items) + scope["size"] - 1) // scope["size"]
        if page > max(1, pages):
            reject("invalid_input", "翻页位置已失效，请回到第 1 页重新查询。", 400)
        source = {"base": saved["base"], "base_identity": saved["base_identity"], "baseline": saved["baseline"],
                  "name": saved["name"], "saved_at": header["saved_at"], "saved_by": header["local_operator"],
                  "save_request_key": header["request_key"], "draft_ref": saved["draft_ref"], "scenario_ref": saved["scenario_ref"]}
        repo.bound(len(canonical_json({"source": source, "items": all_items}).encode("utf-8")), MAX_DIRECTORY_BYTES)
        digest = input_fingerprint({"scope": scope, "source": source, "items": all_items,
                                    "identity_revision": revision, "current_version": current_version})
        offset = (page - 1) * scope["size"]
        return {"scope": scope, "source": source, "items": items[offset:offset + scope["size"]],
                "page": {"number": page, "size": scope["size"], "total": len(items), "pages": pages},
                "total_adoptions": len(all_items), "state": "available" if items else "empty"}, digest

    @staticmethod
    def _identity(refs, reader, query, plan):
        try:
            locator = refs.resolve_plan(plan["plan_ref"])
            if locator != WorkbenchPlanLocator(plan["version"], "adopted"):
                raise ValueError("Receipt plan identity mismatch")
            history = query.repo.get_history_identity_row(plan["version"])
            options = query.repo.list_plan_role_options(plan["version"])
            option = next((row for row in options if row["role"] == "adopted"), None)
            identity = reader._catalog_role(query, history, "adopted", option)
            if identity["plan_ref"] != plan["plan_ref"]:
                raise ValueError("Receipt plan ref mismatch")
            return identity, identity["blocked_reasons"]
        except WorkbenchPlanReferenceError:
            return None, [gap("official_identity_unavailable", "这次采用的结果还在，但它生成的正式计划编号已失效，不能打开，也不能当成当前正式计划。")]
