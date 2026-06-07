"""pytest 共享 fixture 与门禁标注：按 test_debt_registry 把登记的债务节点统一打上 strict xfail；按 tools.test_registry 的门禁必跑清单自动给对应文件的用例打 `required` marker（人用入口：pytest -m required）；并提供 DB/app 共享 fixture（schema_conn/mem_conn/db_path/db_env/app_client）收口回归测试的建库样板。"""

from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

import pytest

# 让 tests 可以直接 import core/data/web（不要求 pip install -e .）
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.infrastructure.database import ensure_schema  # noqa: E402,I001
from tools.full_test_debt_shards import classify_nodeid  # noqa: E402,I001
from tools.test_debt_registry import active_xfail_entries_by_nodeid  # noqa: E402,I001
from tools.test_registry import iter_required_tests  # noqa: E402

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _test_debt_xfail_reason(entry) -> str:
    return f"{entry['debt_id']}: {entry['reason']}"


def _required_test_paths() -> frozenset:
    return frozenset(str(path).replace("\\", "/") for path in iter_required_tests())


def pytest_collection_modifyitems(items):
    entries_by_nodeid = active_xfail_entries_by_nodeid()
    required_paths = _required_test_paths()
    for item in items:
        entry = entries_by_nodeid.get(str(item.nodeid))
        if entry is not None:
            item.add_marker(pytest.mark.xfail(reason=_test_debt_xfail_reason(entry), strict=True))
        nodeid_path = str(item.nodeid).split("::", 1)[0].replace("\\", "/")
        if nodeid_path in required_paths:
            item.add_marker(pytest.mark.required)
        # P4：按 full_test_debt_shards 的单一真相源给需独占进程态的用例打 serial，daily 门禁据此
        # -m "not serial" 走 xdist 并行、-m serial 串行（与上面 required 同一套自动打标机制）。
        if classify_nodeid(str(item.nodeid)) == "serial":
            item.add_marker(pytest.mark.serial)


def pytest_sessionfinish(session, exitstatus):
    """收口 production create_app 同进程化引入的 atexit logging 噪音。

    production(DEBUG=False)下 create_app 会 atexit.register(_run_exit_backup)。main-style 回归
    测试转 pytest 同进程化后，部分用例用 sys.modules.pop("app") 触发 app.py 顶层 create_app 重跑，
    会在不同的 factory 模块状态下注册 atexit。进程退出（check_full_test_debt 分片 shard 子进程、
    pytest capture 流已关闭）时该回调 logging，报 "I/O operation on closed file"，被门禁误判为
    collection_error。逐对象 unregister 在 reimport 后对不上「旧对象」，故双层收口：
      1) 尽力 unregister 当前 factory 对象（覆盖未 reimport 的常规情形）；
      2) 关闭 logging.raiseExceptions——_run_exit_backup 本身 return False、无实际备份副作用，
         唯一危害就是这条写已关闭流的 logging 错误噪音；仅本进程、session 结束后生效，测试期不受影响。
    runtime_lock 系列测试用注入的 fake atexit_register、不依赖真 _run_exit_backup，此处为 no-op。
    """
    try:
        import atexit
        import logging

        from web.bootstrap import factory as _factory

        atexit.unregister(_factory._run_exit_backup)
        logging.raiseExceptions = False
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture(autouse=True)
def _isolate_os_environ():
    """运行时兜底：把每个测试对 os.environ 的改动在结束时还原到测试前快照，杜绝裸写
    os.environ[..]=（未经 monkeypatch）泄漏到后续同进程/同 xdist worker 用例——P4 引入 xdist 的隔离前提。

    P3 main-style→pytest 同进程化后，个别用例与共享 helper（如
    reports_workbench_backlink_helpers._prepare_env：被 9 个用例 import 的 _client 间接触发）
    直接 os.environ[..]= 设 APS_*/SECRET_KEY 且无还原，同进程下污染后续用例（拿到僵尸 APS_DB_PATH）。
    本 autouse 链式保证每个测试 env 隔离，兜住所有裸写泄漏并防未来再漏；monkeypatch.setenv 的
    用例其 teardown 已先还原，此处二次确认、结果一致（双还原幂等）。
    """
    snapshot = dict(os.environ)
    yield
    for key in [k for k in os.environ if k not in snapshot]:
        del os.environ[key]
    for key, value in snapshot.items():
        if os.environ.get(key) != value:
            os.environ[key] = value


@pytest.fixture(autouse=True)
def _isolate_factory_exit_backup_globals():
    """运行时兜底：把每个测试对 web.bootstrap.factory 退出备份注册全局的改动在结束时还原，并注销
    可能新注册的 atexit 退出备份回调——与 _isolate_os_environ 并列，是 P4 xdist 同 worker 串跑的隔离前提。

    根因：production（DEBUG=False）下 create_app 会置 _EXIT_BACKUP_REGISTERED=True 并
    atexit.register(_run_exit_backup)（factory.py:466-468），这是进程级全局、无进程隔离。自研子进程
    分片下每 shard 独立进程天然干净；xdist 同 worker 长生命周期跨文件复用时该标志与 atexit 回调会残留：
    污染后续同 worker 用例对标志的断言起点，并在 worker 退出时让 _run_exit_backup 写已关闭的 capture
    流（报 "I/O operation on closed file"）。此前仅靠个别用例自觉 monkeypatch（tojson_zh_autoescape /
    factory_request_lifecycle 护了、system_health_route 漏护＝不一致），本 autouse 在 conftest 统一钉死，
    覆盖所有 production create_app 用例（含未来新增），与 pytest_sessionfinish 的 session 末兜底互补。
    """
    import atexit

    from web.bootstrap import factory as _factory

    manager = _factory._EXIT_BACKUP_MANAGER
    yield
    # 注销退出备份回调，并把"已注册"标志复位为未注册态——使 flag 与 atexit 状态一致（避免 flag=True 但
    # 回调已注销的瞬态 desync）。_run_exit_backup 测试态 return False 无副作用、注销它正是本 fixture 目的；
    # manager 还原测试前快照（它每次 create_app 重新赋值、残留本身无害，还原仅为干净）。
    atexit.unregister(_factory._run_exit_backup)
    _factory._EXIT_BACKUP_REGISTERED = False
    _factory._EXIT_BACKUP_MANAGER = manager


# ---- 共享 DB/app fixture ----
# 设计依据（最根因路径）：全仓唯一建表入口 ensure_schema（空库→executescript(schema.sql)
# →快进 SchemaVersion=CURRENT，不进迁移、不撞 MigrationContractError，与生产 create_app 同路）；
# 唯一连接工厂 get_connection（FK ON + Row）。app 必须经 importlib 延迟导入，
# 保证 APS_* 环境变量先于 create_app 生效（test_app_factory_runtime_env_refresh 守护的契约）。


@pytest.fixture
def schema_conn():
    """:memory: 连接 + 全量 schema.sql（FK ON + Row，对齐生产连接行为）。"""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def mem_conn():
    """空 :memory: 连接（FK ON + Row），建表交给测试自己（手写最小表场景）。"""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    yield conn
    conn.close()


@pytest.fixture
def db_path(tmp_path):
    """临时文件库路径（str），经生产 ensure_schema 建好全部表并满足迁移契约。"""
    path = tmp_path / "aps_test.db"
    ensure_schema(str(path), logger=None, schema_path=str(SCHEMA_PATH), backup_dir=None)
    return str(path)


@pytest.fixture
def db_env(db_path, tmp_path, monkeypatch):
    """在 db_path 之上设好 APS_* 五件套环境（monkeypatch 自动还原），返回 db_path。"""
    for name, env in (("logs", "APS_LOG_DIR"), ("backups", "APS_BACKUP_DIR"), ("templates_excel", "APS_EXCEL_TEMPLATE_DIR")):
        directory = tmp_path / name
        directory.mkdir()
        monkeypatch.setenv(env, str(directory))
    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", db_path)
    return db_path


@pytest.fixture
def app_client(db_env):
    """create_app().test_client()，环境与库已由 db_env 就位（env 先于 create_app）。"""
    import importlib

    app = importlib.import_module("app").create_app()
    return app.test_client()


@pytest.fixture
def schema_path():
    """schema.sql 的绝对路径（str），供需自建特定版本旧库（迁移测试）而不能用 db_path 的用例。"""
    return str(SCHEMA_PATH)


@pytest.fixture
def repo_root():
    """仓库根 Path，供读取仓库内静态文件（模板等）的用例。"""
    return REPO_ROOT
