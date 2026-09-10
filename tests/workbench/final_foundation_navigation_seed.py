"""Opt-in, pre-baseline real trial preparation for foundation URL recovery tests."""

import hashlib
import os
import secrets
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.workbench.final_foundation_live_source_guard import install_from_environment

SOURCE_GUARD = install_from_environment()

from core.infrastructure.workbench_trial_schema import TRIAL_TABLES
from core.models.workbench_plan_scope import PlanCatalogScope, PlanReadScope
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from core.services.workbench.trial import WorkbenchTrialService
from tests.workbench.live_environment import REPO, read_identity, write_json
from tests.workbench.run_live_server_support import database_state
from web.routes.workbench.write_context import issue_write_context, validate_write_context


def _private_database(app, root, owner_pid, nonce):
    root = Path(root).resolve()
    identity = read_identity(root)
    if root == REPO or REPO in root.parents or owner_pid not in (os.getpid(), os.getppid()) or nonce != identity["nonce"]:
        raise ValueError("Navigation preparation requires this process's private fixture")
    db = root / "db/aps-live.db"
    if Path(app.config["DATABASE_PATH"]).resolve() != db or db.is_symlink() or db.stat().st_nlink != 1:
        raise ValueError("Navigation preparation database is not the owned private fixture")
    for name in ("business-before.json", "run-seed.json", "foundation-navigation-seed.json", "server-ready.json", "foundation-navigation-preparation"):
        if (root / name).exists():
            raise ValueError("Navigation preparation must run once before the business baseline: " + name)
    return root, db


def _redacted(value):
    if isinstance(value, dict):
        return {key: {"sha256": hashlib.sha256(item.encode("utf-8")).hexdigest(), "redacted": True}
                if key == "write_token" and item is not None else _redacted(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_redacted(item) for item in value]
    return value


def _prepare(conn, directory):
    plans = WorkbenchPlanQueryService(conn)
    with plans.read_snapshot():
        catalog, _ = plans.catalog_page(PlanCatalogScope())
        official = [row for row in catalog["plans"] if row["is_current_official"]]
        if len(official) != 1:
            raise ValueError("Navigation fixture must have one actual current official plan")
        workspace, _ = plans.workspace(PlanReadScope(official[0]["plan_ref"]))
    if not workspace["tasks_complete"] or not workspace["tasks"]:
        raise ValueError("Navigation draft must be based on complete actual plan tasks")
    scope = {"range_start": workspace["plan_span"]["start"], "range_end": workspace["plan_span"]["end"]}
    intent = {"base": {"plan_ref": workspace["plan"]["plan_ref"]}, "scope": scope}
    service = WorkbenchTrialService(conn, context_factory=issue_write_context, context_validator=validate_write_context)
    preview = service.preview_create(intent)
    request_key = "trial-" + secrets.token_hex(24)
    token = preview["write_context"]["write_token"]
    request = {"request_key": request_key, "input": intent, "write_token_sha256": hashlib.sha256(token.encode()).hexdigest()}
    write_json(directory / "source-workspace.json", workspace)
    write_json(directory / "preview.json", _redacted(preview))
    write_json(directory / "request.json", request)
    receipt = service.create(intent, token, request_key)
    write_json(directory / "receipt.json", _redacted(receipt))
    if receipt["ok"] is not True or receipt["result"] != "committed" or receipt["data"]["status"] != "editing":
        raise ValueError("Real trial service did not commit the preparation draft")
    draft = service.get(receipt["data"]["draft_ref"])
    if draft["base"] != intent["base"] or draft["scope"] != scope or draft["task_count"] != workspace["task_count"]:
        raise ValueError("Prepared draft did not preserve the exact source and full task scope")
    return {"workspace": workspace, "input": intent, "preview": _redacted(preview),
            "request": request,
            "receipt": _redacted(receipt), "draft": _redacted(draft)}


def prepare_navigation_draft(app, root, *, owner_pid, nonce):
    root, db = _private_database(app, root, owner_pid, nonce)
    before = database_state(db)
    if any(before[name] for name in TRIAL_TABLES):
        raise ValueError("Navigation fixture preparation refuses existing trial data")
    directory = root / "foundation-navigation-preparation"
    directory.mkdir()
    write_json(directory / "business-before.json", before)
    with app.app_context(), closing(sqlite3.connect(str(db))) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        prepared = _prepare(conn, directory)
    after = database_state(db)
    changed = [name for name in before if before[name] != after[name]]
    expected = {"WorkbenchTrialDrafts", "WorkbenchTrialRows", "WorkbenchCommandReceipts"}
    if set(before) != set(after) or set(changed) != expected:
        raise ValueError("Preparation changed tables outside its single-draft scope: " + str(changed))
    for name, rows in before.items():
        if after[name][:len(rows)] != rows:
            raise ValueError("Preparation changed an existing business row: " + name)
    if len(after["WorkbenchTrialDrafts"]) != 1 or len(after["WorkbenchTrialRows"]) != prepared["workspace"]["task_count"]:
        raise ValueError("Preparation must add exactly one full draft")
    if len(after["WorkbenchCommandReceipts"]) != len(before["WorkbenchCommandReceipts"]) + 1:
        raise ValueError("Preparation must add exactly one real command receipt")
    write_json(directory / "business-after.json", after)
    evidence = {"kind": "navigation_condition_preparation", "created_before_business_baseline": True,
                "service": "WorkbenchTrialService.preview_create/create/get", "root": str(root),
                "original_rows_preserved": True, "changed_tables": changed, **prepared}
    target = root / "foundation-navigation-seed.json"
    write_json(target, evidence)
    return {"kind": evidence["kind"], "plan_ref": prepared["workspace"]["plan"]["plan_ref"],
            "draft_ref": prepared["draft"]["draft_ref"], "full_scope": prepared["input"]["scope"],
            "request_key": prepared["request"]["request_key"], "evidence": str(target)}


def main():
    from tests.workbench import final_foundation_host as host
    from tests.workbench import run_live_server as live

    root = Path(os.environ["WORKBENCH_FOUNDATION_NAV_ROOT"]).resolve()
    if os.environ.get("WORKBENCH_FOUNDATION_NAV_ENABLED") == "1":
        owner_pid = int(os.environ["WORKBENCH_FOUNDATION_NAV_OWNER_PID"])
        nonce = os.environ["WORKBENCH_FOUNDATION_NAV_NONCE"]
        original = live.seed_run_data

        def seed(app, **kwargs):
            metadata = original(app, **kwargs)
            metadata["foundation_navigation"] = prepare_navigation_draft(app, root, owner_pid=owner_pid, nonce=nonce)
            return metadata

        live.seed_run_data = seed
    try:
        return host.main()
    finally:
        if SOURCE_GUARD is not None:
            write_json(root / ("foundation-source-guard-host-" + str(os.getpid()) + ".json"), SOURCE_GUARD.evidence())


if __name__ == "__main__":
    raise SystemExit(main())
