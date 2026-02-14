"""
冒烟测试：app_new_ui create_app 基础可用性

验证点：
1) from app_new_ui import create_app 可用，且 create_app() 返回 Flask app。
2) 保留导入副作用契约：模块级 app = create_app() 可访问。
3) 基础端点可用（/ 与 /excel-demo/）。
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _prepare_env(tmpdir: str) -> None:
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(Path(tmpdir) / "aps_test.db")
    os.environ["APS_LOG_DIR"] = str(Path(tmpdir) / "logs")
    os.environ["APS_BACKUP_DIR"] = str(Path(tmpdir) / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(Path(tmpdir) / "templates_excel")
    # 该冒烟不验证密钥生成策略，仅保证 create_app 可执行
    os.environ["SECRET_KEY"] = "aps-smoke-app-new-ui-key"


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    tmpdir = tempfile.mkdtemp(prefix="aps_smoke_new_ui_")
    _prepare_env(tmpdir)

    # 保证每次基于当前环境重新导入
    sys.modules.pop("app_new_ui", None)
    mod = importlib.import_module("app_new_ui")

    app = mod.create_app()
    if app is None:
        raise RuntimeError("app_new_ui.create_app() 返回 None")
    if not hasattr(mod, "app"):
        raise RuntimeError("app_new_ui 未导出模块级 app")
    if mod.app is None:
        raise RuntimeError("app_new_ui 模块级 app 为 None")

    client = app.test_client()
    r1 = client.get("/")
    if r1.status_code != 200:
        raise RuntimeError(f"GET / 返回非 200：{r1.status_code}")

    r2 = client.get("/excel-demo/")
    if r2.status_code != 200:
        raise RuntimeError(f"GET /excel-demo/ 返回非 200：{r2.status_code}")

    print("OK")


if __name__ == "__main__":
    main()
