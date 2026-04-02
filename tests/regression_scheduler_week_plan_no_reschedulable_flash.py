import importlib
import os
import sys
import tempfile


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _prepare_runtime_env(tmpdir: str) -> str:
    test_db = os.path.join(tmpdir, "aps_test.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates
    return test_db


def _build_app(repo_root: str, tmpdir: str):
    from core.infrastructure.database import ensure_schema

    test_db = _prepare_runtime_env(tmpdir)
    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"), backup_dir=None)
    sys.modules.pop("app", None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.schedule_service import ScheduleService

    tmpdir = tempfile.mkdtemp(prefix="aps_regression_schedule_simulate_empty_flash_")
    app = _build_app(repo_root, tmpdir)

    original_run_schedule = getattr(ScheduleService, "run_schedule")

    def _fake_run_schedule(
        self,
        batch_ids,
        start_dt=None,
        end_date=None,
        created_by=None,
        simulate=False,
        enforce_ready=None,
        strict_mode=False,
    ):
        raise ValidationError("所选批次没有可重排工序，本次未执行模拟排产。", field="排产")

    setattr(ScheduleService, "run_schedule", _fake_run_schedule)
    try:
        client_redirect = app.test_client()
        redirect_resp = client_redirect.post(
            "/scheduler/simulate",
            data={"batch_ids": ["B001"], "start_dt": "2026-01-01 08:00:00"},
            follow_redirects=False,
        )
        location = str(redirect_resp.headers.get("Location") or "")
        assert redirect_resp.status_code in (301, 302), f"模拟排产失败后应重定向：{redirect_resp.status_code}"
        assert "/scheduler/gantt" not in location, f"空执行失败后不应跳转到甘特图：{location!r}"

        client = app.test_client()
        resp = client.post(
            "/scheduler/simulate",
            data={"batch_ids": ["B001"], "start_dt": "2026-01-01 08:00:00"},
            follow_redirects=True,
        )
        body = resp.get_data(as_text=True)
        final_path = str(getattr(getattr(resp, "request", None), "path", "") or "")

        assert resp.status_code == 200, f"/scheduler/simulate follow_redirects 后应返回 200：{resp.status_code}"
        assert "所选批次没有可重排工序，本次未执行模拟排产。" in body, "模拟排产页面未展示业务错误提示"
        assert "模拟排产完成：生成版本" not in body, "模拟排产页面不应误报成功"
        if final_path:
            assert final_path.rstrip("/") == "/scheduler", f"空执行失败后应回到批次页：{final_path!r}"
    finally:
        setattr(ScheduleService, "run_schedule", original_run_schedule)

    print("OK")


if __name__ == "__main__":
    main()
