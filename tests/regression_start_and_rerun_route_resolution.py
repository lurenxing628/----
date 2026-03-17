"""
回归测试：run_start_and_rerun_route 只复用当前仓库 runtime contract 对应的实例。

验证点：
1) 仅当当前仓库 runtime files 能解析到健康 endpoint 时才允许复用。
2) `start-only` / `rerun` 输出的 `host` / `port` / `url` 来自实际 endpoint。
3) fresh-start 会把统一目标 DB 传给子服务环境。
4) DB 错配或 runtime endpoint 身份不可证实时必须拒绝复用。
5) `.cursor` 与 `.windsurf` 两份 runner 行为保持一致。
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import tempfile
from pathlib import Path


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _load_module(path: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载模块：{path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_main(mod, argv: list[str]) -> tuple[int, dict]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = int(mod.main(argv))
    payload = json.loads(buf.getvalue().strip())
    return rc, payload


def _normalize_path(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


def _runner_paths(repo_root: str) -> list[Path]:
    base = Path(repo_root)
    return [
        base / ".cursor" / "skills" / "aps-start-and-rerun-route" / "scripts" / "run_start_and_rerun_route.py",
        base / ".windsurf" / "skills" / "aps-start-and-rerun-route" / "scripts" / "run_start_and_rerun_route.py",
    ]


def _exercise_runner(runner_path: Path, label: str) -> None:
    temp_repo = Path(tempfile.mkdtemp(prefix=f"aps_runner_resolution_{label}_"))
    matched_db = _normalize_path(str(temp_repo / "matched.db"))

    start_only_mod = _load_module(str(runner_path), f"aps_runner_start_only_{label}")
    start_only_mod._find_repo_root = lambda: temp_repo
    reuse_resolve_calls: list[dict] = []

    def _reuse_resolve(self, runtime_dir, preferred_host=None, preferred_port=None, timeout=2.0):
        reuse_resolve_calls.append(
            {
                "runtime_dir": runtime_dir,
                "preferred_host": preferred_host,
                "preferred_port": preferred_port,
                "timeout": float(timeout),
            }
        )
        return {
            "host": "127.0.0.1",
            "port": 5714,
            "base_url": "http://127.0.0.1:5714",
            "source": "runtime_files",
            "health": {"app": "aps", "status": "ok", "contract_version": 1},
        }

    start_only_mod._runtime_probe = lambda repo_root: type(
        "Probe",
        (),
        {
            "resolve_healthy_endpoint": _reuse_resolve,
            "read_runtime_host_port": lambda self, runtime_dir: ("127.0.0.1", 5714),
            "read_runtime_db_path": lambda self, runtime_dir: matched_db,
            "build_base_url": lambda self, host, port: f"http://127.0.0.1:{int(port)}",
        },
    )()
    opened_urls: list[str] = []
    start_only_mod._open_url = lambda url: opened_urls.append(url)

    rc, payload = _run_main(start_only_mod, ["start-only", "--db-path", matched_db, "--no-open"])
    _assert(rc == 0, f"{label}: start-only 应返回 0")
    _assert(payload["host"] == "127.0.0.1", f"{label}: start-only host 不正确")
    _assert(int(payload["port"]) == 5714, f"{label}: start-only port 未使用实际 endpoint")
    _assert(payload["url"] == "http://127.0.0.1:5714/", f"{label}: start-only url 未使用实际 endpoint")
    _assert(payload["server_started_now"] is False, f"{label}: start-only server_started_now 不正确")
    _assert(not opened_urls, f"{label}: 传入 --no-open 时不应打开浏览器")
    _assert(len(reuse_resolve_calls) == 1, f"{label}: 复用路径应只解析一次 runtime endpoint")
    _assert(reuse_resolve_calls[0]["preferred_host"] is None, f"{label}: 不应按 preferred host 直接复用实例")
    _assert(reuse_resolve_calls[0]["preferred_port"] is None, f"{label}: 不应按 preferred port 直接复用实例")

    rerun_mod = _load_module(str(runner_path), f"aps_runner_rerun_{label}")
    rerun_mod._find_repo_root = lambda: temp_repo
    rerun_db = _normalize_path(str(temp_repo / "rerun.db"))
    fresh_resolve_calls: list[dict] = []
    delete_stale_calls: list[str] = []

    def _fresh_resolve(self, runtime_dir, preferred_host=None, preferred_port=None, timeout=2.0):
        fresh_resolve_calls.append(
            {
                "runtime_dir": runtime_dir,
                "preferred_host": preferred_host,
                "preferred_port": preferred_port,
                "timeout": float(timeout),
            }
        )
        if preferred_host is not None or preferred_port is not None:
            return {
                "host": "127.0.0.1",
                "port": 5799,
                "base_url": "http://127.0.0.1:5799",
                "source": "preferred",
                "health": {"app": "aps", "status": "ok", "contract_version": 1},
            }
        return None

    rerun_mod._runtime_probe = lambda repo_root: type(
        "Probe",
        (),
        {
            "resolve_healthy_endpoint": _fresh_resolve,
            "delete_stale_runtime_files": lambda self, runtime_dir: delete_stale_calls.append(str(runtime_dir)),
            "wait_for_healthy_runtime_endpoint": lambda self, runtime_dir, timeout_s, interval_s=0.5: {
                "host": "127.0.0.1",
                "port": 5715,
                "base_url": "http://127.0.0.1:5715",
                "source": "runtime_files",
                "health": {"app": "aps", "status": "ok", "contract_version": 1},
            },
            "read_runtime_host_port": lambda self, runtime_dir: ("127.0.0.1", 5715),
            "read_runtime_db_path": lambda self, runtime_dir: rerun_db,
            "build_base_url": lambda self, host, port: f"http://127.0.0.1:{int(port)}",
        },
    )()
    popen_env: dict = {}

    class _DummyProc:
        pass

    def _fake_popen(*args, **kwargs):
        popen_env.clear()
        popen_env.update(dict(kwargs.get("env") or {}))
        return _DummyProc()

    rerun_mod.subprocess.Popen = _fake_popen
    seeded_db: list[str] = []

    def _fake_seed(repo_root, db_path, view):
        seeded_db.append(str(db_path))
        return {
            "version": 7,
            "week_start": "2026-03-16",
            "task_count": 11,
        }

    rerun_mod._seed_and_schedule = _fake_seed
    verify_calls: list[dict] = []

    def _fake_verify_route(host: str, port: int, view: str, week_start: str, version: int) -> int:
        verify_calls.append(
            {
                "host": host,
                "port": int(port),
                "view": view,
                "week_start": week_start,
                "version": int(version),
            }
        )
        return 11

    rerun_mod._verify_route = _fake_verify_route
    rerun_opened: list[str] = []
    rerun_mod._open_url = lambda url: rerun_opened.append(url)

    rc, payload = _run_main(rerun_mod, ["rerun", "--view", "operator", "--db-path", rerun_db, "--no-open"])
    _assert(rc == 0, f"{label}: rerun 应返回 0")
    _assert(payload["host"] == "127.0.0.1", f"{label}: rerun host 不正确")
    _assert(int(payload["port"]) == 5715, f"{label}: rerun port 未使用实际 endpoint")
    _assert(
        payload["url"] == "http://127.0.0.1:5715/scheduler/gantt?view=operator&week_start=2026-03-16&version=7",
        f"{label}: rerun url 未使用实际 endpoint",
    )
    _assert(payload["server_started_now"] is True, f"{label}: rerun server_started_now 不正确")
    _assert(len(verify_calls) == 1, f"{label}: _verify_route 应被调用一次")
    _assert(verify_calls[0]["host"] == "127.0.0.1", f"{label}: _verify_route 未收到实际 host")
    _assert(verify_calls[0]["port"] == 5715, f"{label}: _verify_route 未收到实际 port")
    _assert(verify_calls[0]["view"] == "operator", f"{label}: _verify_route view 不正确")
    _assert(not rerun_opened, f"{label}: 传入 --no-open 时不应打开浏览器")
    _assert(len(fresh_resolve_calls) == 1, f"{label}: fresh-start 前应只检查一次 repo runtime contract")
    _assert(fresh_resolve_calls[0]["preferred_host"] is None, f"{label}: fresh-start 前不应按 preferred host 探测外部实例")
    _assert(fresh_resolve_calls[0]["preferred_port"] is None, f"{label}: fresh-start 前不应按 preferred port 探测外部实例")
    _assert(delete_stale_calls == [str(temp_repo)], f"{label}: fresh-start 前应清理当前 repo runtime 文件")
    _assert(popen_env.get("APS_DB_PATH") == rerun_db, f"{label}: fresh-start 未把目标 DB 传给子服务环境")
    _assert(len(seeded_db) == 1 and _normalize_path(seeded_db[0]) == rerun_db, f"{label}: _seed_and_schedule 未收到统一目标 DB")

    mismatch_db_mod = _load_module(str(runner_path), f"aps_runner_mismatch_db_{label}")
    mismatch_db_mod._find_repo_root = lambda: temp_repo
    mismatch_db_mod._runtime_probe = lambda repo_root: type(
        "Probe",
        (),
        {
            "resolve_healthy_endpoint": lambda self, runtime_dir, preferred_host=None, preferred_port=None, timeout=2.0: {
                "host": "127.0.0.1",
                "port": 5716,
                "base_url": "http://127.0.0.1:5716",
                "source": "runtime_files",
                "health": {"app": "aps", "status": "ok", "contract_version": 1},
            },
            "read_runtime_host_port": lambda self, runtime_dir: ("127.0.0.1", 5716),
            "read_runtime_db_path": lambda self, runtime_dir: _normalize_path(str(temp_repo / "other.db")),
            "build_base_url": lambda self, host, port: f"http://127.0.0.1:{int(port)}",
        },
    )()
    try:
        mismatch_db_mod.main(["start-only", "--db-path", matched_db, "--no-open"])
        raise RuntimeError(f"{label}: DB 不一致时应拒绝复用")
    except RuntimeError as e:
        _assert("runner target DB" in str(e), f"{label}: DB 不一致时错误信息不正确")

    foreign_endpoint_mod = _load_module(str(runner_path), f"aps_runner_foreign_endpoint_{label}")
    foreign_endpoint_mod._find_repo_root = lambda: temp_repo
    foreign_endpoint_mod._runtime_probe = lambda repo_root: type(
        "Probe",
        (),
        {
            "resolve_healthy_endpoint": lambda self, runtime_dir, preferred_host=None, preferred_port=None, timeout=2.0: {
                "host": "127.0.0.1",
                "port": 5717,
                "base_url": "http://127.0.0.1:5717",
                "source": "runtime_files",
                "health": {"app": "aps", "status": "ok", "contract_version": 1},
            },
            "read_runtime_host_port": lambda self, runtime_dir: ("127.0.0.1", 5718),
            "read_runtime_db_path": lambda self, runtime_dir: matched_db,
            "build_base_url": lambda self, host, port: f"http://127.0.0.1:{int(port)}",
        },
    )()
    try:
        foreign_endpoint_mod.main(["start-only", "--db-path", matched_db, "--no-open"])
        raise RuntimeError(f"{label}: 实例身份不可证实时应拒绝复用")
    except RuntimeError as e:
        _assert("cannot be proven to belong to this repo" in str(e), f"{label}: 实例身份错误信息不正确")


def main() -> None:
    repo_root = find_repo_root()
    for runner_path in _runner_paths(repo_root):
        runner_label = runner_path.relative_to(repo_root).parts[0].lstrip(".")
        _exercise_runner(runner_path, runner_label)
    print("OK")


if __name__ == "__main__":
    main()
