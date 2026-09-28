"""
打包后 exe 冷启动验收脚本（用于 Win7/离线交付验收）。

用法：
  python validate_dist_exe.py "dist\\排产系统\\排产系统.exe"

验证点（最小闭环）：
  - 进程可启动
  - 运行时 host/port 文件可生成并可解析
  - 健康检查接口可访问（GET /system/health）
  - 当前工作台入口、各视图的 HTML 引导与本地脚本/样式引用正确
  - 无条件的旧页面入口保持明确的 410 退役响应
  - static 关键载荷已打进包且可通过 HTTP 取到非空内容
    （static 缺失时运行时只降级警告、页面照常 200，必须在验收层直接断言）

注意：
  - 该脚本会启动 exe 并在验证后结束进程
  - 实际访问地址以 logs/aps_host.txt 与 logs/aps_port.txt 为准
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional, Tuple

from core.infrastructure.safe_files import read_fixed_text, remove_fixed_file

_EXPECTED_CONTRACT_VERSION = 1

# static 验收锚点：新工作台入口从实际 manifest 加载的核心样式与主脚本（B14）。
# tests/app_runtime/test_validate_dist_static_payload.py 对账：锚点必须真实存在于
# 仓库 static/、列入 manifest 且由实际入口模板加载，不能保留已退役的旧资源。
_STATIC_BUNDLE_ANCHORS = (
    "static/workbench/prototype/styles.css",
    "static/workbench/app/theme.js",
    "static/workbench/app/main.js",
)

_WORKBENCH_VIEWS = (
    "dashboard", "process", "batches", "run", "analysis", "gantt", "delay",
    "field", "fieldgantt", "review", "reports", "calib", "basedata", "system", "trial",
)
_RETIRED_PAGE_PATHS = ("/personnel/", "/equipment/", "/process/", "/scheduler/", "/system/backup")


def _is_port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=0.5):
            return True
    except Exception:
        return False


def _http_get(url: str, timeout: float = 2.5) -> int:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(getattr(resp, "status", 200))
    except urllib.error.HTTPError as e:
        return int(getattr(e, "code", 500))


def _http_get_text(url: str, timeout: float = 2.5) -> str:
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8")


def _http_get_bytes(url: str, timeout: float = 2.5) -> bytes:
    """GET 原始字节（css/js 载荷检查用，避免按 utf-8 解码引入无关失败）。"""
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _http_get_page(url: str, timeout: float = 3.0) -> Tuple[int, str, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        response = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return int(response.code), response.read().decode("utf-8"), response.geturl()


class _PageMarkup(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.workbench_body = False
        self.root_count = 0
        self.boot_count = 0
        self.boot_parts = []
        self.in_boot = False
        self.assets = set()
        self.script_assets = set()
        self.style_assets = set()
        self.legacy_response = False
        self.text_parts = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "body" and "aps-workbench" in values.get("class", "").split():
            self.workbench_body = True
        if tag == "div" and values.get("id") == "root":
            self.root_count += 1
        if tag == "script" and values.get("id") == "workbench-boot":
            self.boot_count += 1
            self.in_boot = values.get("type") == "application/json" and not values.get("src")
        if tag == "script" and values.get("src"):
            self.assets.add(values["src"])
            self.script_assets.add(values["src"])
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.assets.add(values["href"])
            self.style_assets.add(values["href"])
        if tag == "main" and values.get("data-workbench-legacy-response") == "true":
            self.legacy_response = True

    def handle_data(self, data):
        self.text_parts.append(data)
        if self.in_boot:
            self.boot_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_boot = False


def _assert_workbench_page(base_url: str, path: str, view: str) -> None:
    status, body, final_url = _http_get_page(base_url + path)
    print(f"[validate] GET {path} -> {status}")
    target, origin = urllib.parse.urlsplit(final_url), urllib.parse.urlsplit(base_url)
    if (status != 200 or (target.scheme, target.netloc) != (origin.scheme, origin.netloc)
            or target.path not in ("/workbench", "/workbench/trial")):
        raise RuntimeError(f"工作台入口响应不正确：{path} -> {status} {final_url}")
    markup = _PageMarkup()
    markup.feed(body)
    markup.close()
    if not markup.workbench_body or markup.root_count != 1 or markup.boot_count != 1:
        raise RuntimeError(f"工作台 HTML 缺少唯一挂载节点或引导配置：{path}")
    try:
        boot = json.loads("".join(markup.boot_parts))
    except ValueError as exc:
        raise RuntimeError(f"工作台引导配置不是有效 JSON：{path}") from exc
    if (not isinstance(boot, dict) or boot.get("schema_version") != 1 or boot.get("view") != view
            or not isinstance(boot.get("enabled_views"), list) or view not in boot["enabled_views"]):
        raise RuntimeError(f"工作台引导配置与请求视图不一致：{path}")
    for asset in markup.assets:
        parts = urllib.parse.urlsplit(asset)
        if parts.scheme or parts.netloc or not parts.path.startswith("/static/workbench/"):
            raise RuntimeError(f"工作台引用了非本机交付资源：{asset}")
    styles = {urllib.parse.urlsplit(asset).path for asset in markup.style_assets}
    scripts = {urllib.parse.urlsplit(asset).path for asset in markup.script_assets}
    missing = ["/" + rel for rel in _STATIC_BUNDLE_ANCHORS
               if "/" + rel not in (styles if rel.endswith(".css") else scripts)]
    if missing:
        raise RuntimeError(f"工作台 HTML 未引用关键脚本或样式：{missing}")


def _assert_retired_page(base_url: str, path: str) -> None:
    status, body, final_url = _http_get_page(base_url + path)
    print(f"[validate] GET {path} -> {status} (expected retired)")
    markup = _PageMarkup()
    markup.feed(body)
    markup.close()
    text = "".join(markup.text_parts)
    if (status != 410 or final_url != base_url + path or not markup.legacy_response
            or "旧入口已退役" not in text or "原业务数据、保存的配置和历史记录仍保留" not in text):
        raise RuntimeError(f"旧入口未返回明确的 410 退役页：{path}")


def _normalize_db_path(path: str) -> str:
    raw = str(path or "").strip()
    if not raw:
        return ""
    return os.path.normcase(os.path.abspath(raw))


def _runtime_contract_paths(log_dir: str) -> Tuple[str, str, str]:
    return (
        os.path.join(log_dir, "aps_host.txt"),
        os.path.join(log_dir, "aps_port.txt"),
        os.path.join(log_dir, "aps_db_path.txt"),
    )


def _read_port_file(path: str) -> int:
    return int(read_fixed_text(path).strip())


def _read_host_file(path: str) -> str:
    return str(read_fixed_text(path).strip())


def _read_db_file(path: str) -> str:
    return _normalize_db_path(read_fixed_text(path).strip())


def _read_runtime_contract(log_dir: str) -> Optional[Tuple[str, int, str]]:
    host_file, port_file, db_file = _runtime_contract_paths(log_dir)
    if not (os.path.lexists(host_file) and os.path.lexists(port_file) and os.path.lexists(db_file)):
        return None

    try:
        host = _read_host_file(host_file)
    except Exception as e:
        raise RuntimeError(f"运行时契约文件解析失败：host 文件无效：{host_file}") from e
    if not host:
        raise RuntimeError(f"运行时契约文件解析失败：host 文件为空：{host_file}")

    try:
        port = _read_port_file(port_file)
    except Exception as e:
        raise RuntimeError(f"运行时契约文件解析失败：port 文件无效：{port_file}") from e
    if port <= 0:
        raise RuntimeError(f"运行时契约文件解析失败：port 必须大于 0：{port_file}")

    try:
        db_path = _read_db_file(db_file)
    except Exception as e:
        raise RuntimeError(f"运行时契约文件解析失败：db_path 文件无效：{db_file}") from e
    if not db_path:
        raise RuntimeError(f"运行时契约文件解析失败：db_path 文件为空：{db_file}")

    return host, port, db_path


def _clear_runtime_contract_files(log_dir: str) -> None:
    paths = _runtime_contract_paths(log_dir)
    failures = []
    for path in paths:
        try:
            remove_fixed_file(path, allow_symlink=False)
        except FileNotFoundError:
            pass
        except OSError as exc:
            failures.append(f"{path}: {exc}")
    if failures:
        raise RuntimeError(f"无法清理旧的运行时契约文件：{failures}")
    remaining = [path for path in paths if os.path.lexists(path)]
    if remaining:
        raise RuntimeError(f"无法清理旧的运行时契约文件：{remaining}")


def _assert_process_running(p: subprocess.Popen, context: str) -> None:
    exit_code = p.poll()
    if exit_code is not None:
        raise RuntimeError(f"进程提前退出（exit_code={exit_code}），{context}")


def _wait_for_runtime_contract(log_dir: str, p: subprocess.Popen, timeout_s: float = 20.0) -> Tuple[str, int, str]:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        _assert_process_running(p, "未生成运行时 host/port/db 契约文件。")
        contract = _read_runtime_contract(log_dir)
        if contract is not None:
            return contract
        time.sleep(0.2)
    raise TimeoutError("超时：未生成运行时 host/port/db 契约文件。")


def _wait_port_open(host: str, port: int, p: subprocess.Popen, timeout_s: float = 20.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        _assert_process_running(p, f"端口未就绪：{host}:{port}")
        if _is_port_open(host, port):
            return
        time.sleep(0.2)
    raise TimeoutError(f"超时：端口未就绪：{host}:{port}")


def _assert_health(base_url: str, timeout: float = 3.0) -> dict:
    text = _http_get_text(base_url + "/system/health", timeout=timeout)
    payload = json.loads(text)
    if payload.get("app") != "aps":
        raise RuntimeError(f"健康检查返回的 app 标识不正确：{payload!r}")
    if payload.get("status") != "ok":
        raise RuntimeError(f"健康检查状态不正确：{payload!r}")
    try:
        contract_version = int(payload.get("contract_version") or 0)
    except Exception:
        contract_version = 0
    if contract_version != _EXPECTED_CONTRACT_VERSION:
        raise RuntimeError(f"健康检查契约版本不正确：{payload!r}")
    if str(payload.get("ui_mode") or "") != "default":
        raise RuntimeError(f"健康检查 ui_mode 不正确：{payload!r}")
    return payload


_NETWORKX_MODULE_ANCHORS = (
    "networkx",
    "networkx.classes.graph",
    "networkx.classes.digraph",
    "networkx.algorithms.dag",
    "networkx.algorithms.cycles",
    "networkx.algorithms.components.weakly_connected",
    "networkx.algorithms.traversal.breadth_first_search",
    "networkx.algorithms.bipartite.matching",
)


def _assert_networkx_bundled(exe_path: str) -> None:
    """校验目标 EXE 内的 NetworkX 字节码，不依赖构建机安装或磁盘源码。

    当前交付锁定 PyInstaller 4.10；默认 onedir 将纯 Python 模块放在
    EXE 内的 PYZ。这里只证明关键载荷可解码，实际图运算另由实机验收覆盖。
    """
    from types import CodeType

    try:
        from PyInstaller.archive.readers import CArchiveReader
        from PyInstaller.loader.pyimod02_archive import ZlibArchiveReader

        archive = CArchiveReader(str(exe_path))
        found = set()
        for offset, _length, _size, compressed, kind, name in archive.toc:
            if kind != "z":
                continue
            if compressed:
                raise RuntimeError(f"不支持压缩的内嵌 PYZ：{name}")
            pyz = ZlibArchiveReader(str(exe_path), offset=archive.pkg_start + offset)
            for module in _NETWORKX_MODULE_ANCHORS:
                entry = pyz.extract(module)
                if entry is None:
                    continue
                expected_kind = 1 if module == "networkx" else 0
                if entry[0] != expected_kind or not isinstance(entry[1], CodeType):
                    raise RuntimeError(f"NetworkX 模块不是有效字节码：{module}")
                found.add(module)
        missing = sorted(set(_NETWORKX_MODULE_ANCHORS) - found)
        if missing:
            raise RuntimeError(f"PYZ 缺少 NetworkX 关键模块：{missing}")
    except Exception as exc:
        raise RuntimeError(
            "离线包 NetworkX 字节码验收失败；请使用锁定的 PyInstaller 4.10 构建环境检查目标 EXE。"
            f"详情：{exc}"
        ) from exc


def _assert_static_bundled(exe_dir: str) -> None:
    """确认离线包内含 static 关键载荷（B14）。

    static 缺失/半缺失时，static_versioning 只会 _warn_once 后回退原始 URL，
    页面照常 200，冷启动/健康检查/页面冒烟全部通过——所以必须在文件层直接断言。
    onedir 打包会把 static 收进 exe 同级目录(PyInstaller 4.10)或 _internal 子目录(6+)。
    """
    root = Path(exe_dir)
    missing = []
    for rel in _STATIC_BUNDLE_ANCHORS:
        rel_parts = rel.split("/")
        found = False
        for base in (root, root / "_internal"):
            candidate = base.joinpath(*rel_parts)
            if candidate.is_file() and candidate.stat().st_size > 0:
                found = True
                break
        if not found:
            missing.append(rel)
    if missing:
        raise RuntimeError(
            f"离线包内 static 关键载荷缺失或为空文件：{missing}；"
            "static 缺失时页面仍会返回 200（静态版本号仅降级警告），必须在验收阶段拦截。"
        )


def _assert_runtime_db_path(db_path: str) -> None:
    normalized = _normalize_db_path(db_path)
    if not normalized:
        raise RuntimeError("运行时 DB 契约文件为空。")
    if not os.path.isabs(normalized):
        raise RuntimeError(f"运行时 DB 路径不是绝对路径：{db_path}")
    if not os.path.exists(normalized):
        raise RuntimeError(f"运行时 DB 文件不存在：{normalized}")


def main() -> int:
    # Runtime path resolution is needed by the CLI only, not its reusable probes.
    from web.bootstrap.launcher_paths import resolve_prelaunch_log_dir, resolve_runtime_db_path

    if len(sys.argv) < 2:
        print("用法：python validate_dist_exe.py \"dist\\\\排产系统\\\\排产系统.exe\"")
        return 2

    exe_path = os.path.abspath(sys.argv[1])
    if not os.path.exists(exe_path):
        print(f"[validate] exe 不存在：{exe_path}")
        return 2

    print(f"[validate] 启动：{exe_path}")
    cwd = os.path.dirname(exe_path)
    log_dir = resolve_prelaunch_log_dir(cwd, frozen=True)

    try:
        _assert_networkx_bundled(exe_path)
        _assert_static_bundled(cwd)
    except Exception as e:
        print(f"[validate] 验收失败：{e}")
        return 7

    try:
        _clear_runtime_contract_files(log_dir)
    except Exception as e:
        print(f"[validate] 验收失败：{e}")
        return 5

    p = subprocess.Popen(
        [exe_path],
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )

    try:
        host, port, db_path = _wait_for_runtime_contract(log_dir, p, timeout_s=20.0)
        _assert_runtime_db_path(db_path)
        expected_db_path = _normalize_db_path(resolve_runtime_db_path(cwd, frozen=True))
        if _normalize_db_path(db_path) != expected_db_path:
            raise RuntimeError(f"运行时数据库偏离交付目录配置：expected={expected_db_path} actual={db_path}")
        _wait_port_open(host, port, p, timeout_s=20.0)
        _assert_process_running(p, f"运行时端口就绪后进程已退出：{host}:{port}")

        base = f"http://{host}:{port}"
        health = _assert_health(base, timeout=3.0)
        _assert_process_running(p, "健康检查通过后进程已退出。")
        print(f"[validate] runtime -> {host}:{port} db={db_path}")
        print(
            "[validate] health -> "
            f"app={health.get('app')} status={health.get('status')} contract={health.get('contract_version')}"
        )

        _assert_workbench_page(base, "/", "dashboard")
        _assert_workbench_page(base, "/workbench", "dashboard")
        for view in _WORKBENCH_VIEWS:
            _assert_workbench_page(base, "/workbench?view=" + view, view)
        _assert_workbench_page(base, "/workbench/trial", "trial")
        for path in _RETIRED_PAGE_PATHS:
            _assert_retired_page(base, path)

        for rel in _STATIC_BUNDLE_ANCHORS:
            static_url = "/" + rel
            try:
                payload = _http_get_bytes(base + static_url, timeout=3.0)
            except urllib.error.HTTPError as e:
                print(f"[validate] GET {static_url} -> {int(getattr(e, 'code', 500))}")
                print("[validate] 验收失败：静态关键载荷不可访问。")
                return 6
            if not payload:
                print(f"[validate] GET {static_url} -> 200 (0 bytes)")
                print("[validate] 验收失败：静态关键载荷返回空内容。")
                return 6
            print(f"[validate] GET {static_url} -> 200 ({len(payload)} bytes)")

        _assert_process_running(p, "页面检查通过后进程已退出。")
        print("[validate] 验收通过：exe 冷启动、运行时契约、工作台 HTML 引导、旧入口退役与 static 关键载荷均正常。")
        return 0
    except Exception as e:
        print(f"[validate] 验收失败：{e}")
        return 5
    finally:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception as e:
            print(f"[validate] 警告：terminate 失败：{e}")
            try:
                p.kill()
                p.wait(timeout=5)
            except Exception as kill_e:
                print(f"[validate] 警告：kill 失败：{kill_e}")


if __name__ == "__main__":
    raise SystemExit(main())
