from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest
from werkzeug.serving import make_server

REPO_ROOT = Path(__file__).resolve().parents[1]

SMOKE_PATHS = (
    "/scheduler/?status=pending",
    "/scheduler/config",
    "/scheduler/batches",
    "/scheduler/excel/batches",
    "/system/backup",
    "/system/logs",
    "/system/history",
    "/process/",
    "/material/batches",
)

EXPECTED_PAGE_SIGNALS = {
    "/scheduler/?status=pending": {
        "path": "/scheduler/?status=pending",
        "texts": ["排产调度", "批次列表", "排产操作"],
        "ids": ["jsRunScheduleForm", "runEnforceReady", "runStrictMode"],
    },
    "/scheduler/config": {
        "path": "/scheduler/config",
        "texts": ["排产高级设置", "保存当前设置"],
        "ids": ["freezeWindowEnabled", "preferPrimarySkill", "enforceReadyDefault", "autoAssignEnabled", "orToolsEnabled"],
    },
    "/scheduler/batches": {
        "path": "/scheduler/batches",
        "texts": ["批次管理", "批次列表"],
        "ids": ["batchManageStrictMode", "batchesManageTable"],
    },
    "/scheduler/excel/batches": {
        "path": "/scheduler/excel/batches",
        "texts": ["批量维护批次"],
        "ids": ["batchImportAutoOps", "batchImportStrictMode"],
    },
    "/system/backup": {
        "path": "/system/backup",
        "texts": ["系统管理 - 备份/恢复", "扩展功能状态"],
        "ids": ["backupAutoBackupEnabled", "backupAutoCleanupEnabled", "pluginStatusTable"],
    },
    "/system/logs": {
        "path": "/system/logs",
        "texts": ["系统管理 - 操作日志", "筛选日志"],
        "ids": ["systemLogsTable"],
    },
    "/system/history": {
        "path": "/system/history",
        "texts": ["系统管理 - 排产历史", "最近排产记录"],
        "ids": ["systemHistoryTable"],
    },
    "/process/": {
        "path": "/process/",
        "texts": ["零件工艺模板"],
        "ids": ["processCreateStrictMode", "partsTable"],
    },
    "/material/batches": {
        "path": "/material/batches",
        "texts": ["批次物料需求"],
        "ids": ["batchMaterialBatchSelect"],
    },
}


def _find_chrome() -> str:
    candidates = (
        os.environ.get("APS_CHROME_PATH"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    )
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    message = "没有找到可用于 UI 几何 smoke 的 Chrome/Chromium；CI 需要设置 APS_CHROME_PATH 或安装 Chrome。"
    if os.environ.get("CI"):
        pytest.fail(message)
    pytest.skip(message)


def _find_node_with_browser_runtime() -> str:
    node = shutil.which("node")
    message = "UI 浏览器几何 smoke 需要 Node.js，并且全局 fetch/WebSocket 必须可用。"
    if not node:
        if os.environ.get("CI"):
            pytest.fail(message)
        pytest.skip(message)
    completed = subprocess.run(
        [
            node,
            "-e",
            "if (typeof fetch !== 'function' || typeof WebSocket !== 'function') process.exit(1)",
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=10,
    )
    if completed.returncode != 0:
        runtime_message = f"{message} 当前 Node 版本缺少 fetch 或 WebSocket，请使用 Node 24 或更新版本。"
        if os.environ.get("CI"):
            pytest.fail(runtime_message)
        pytest.skip(runtime_message)
    return node


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _build_app(tmp_path, monkeypatch):
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("APS_DB_PATH", str(tmp_path / "aps_ui_geometry.db"))
    monkeypatch.setenv("APS_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("APS_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("APS_EXCEL_TEMPLATE_DIR", str(tmp_path / "templates_excel"))
    (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
    (tmp_path / "backups").mkdir(parents=True, exist_ok=True)
    (tmp_path / "templates_excel").mkdir(parents=True, exist_ok=True)

    from core.infrastructure.database import ensure_schema

    ensure_schema(
        str(tmp_path / "aps_ui_geometry.db"),
        logger=None,
        schema_path=str(REPO_ROOT / "schema.sql"),
        backup_dir=None,
    )
    conn = sqlite3.connect(str(tmp_path / "aps_ui_geometry.db"))
    try:
        conn.execute(
            "INSERT INTO Parts (part_no, part_name, route_raw, route_parsed) VALUES (?, ?, ?, ?)",
            ("P_UI_GEOMETRY", "浏览器几何测试零件", "", "no"),
        )
        conn.execute(
            """
            INSERT INTO Batches (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("B_UI_GEOMETRY", "P_UI_GEOMETRY", "浏览器几何测试零件", 1, "2026-05-20", "normal", "yes", "pending"),
        )
        conn.execute(
            """
            INSERT INTO ScheduleHistory
                (schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-05-06 09:00:00",
                1,
                "priority_first",
                1,
                1,
                "success",
                json.dumps(
                    {
                        "algo": {
                            "mode": "improve",
                            "objective": "min_overdue",
                            "metrics": {
                                "total_tardiness_hours": 0,
                                "weighted_tardiness_hours": 0,
                                "makespan_hours": 1,
                                "changeover_count": 0,
                                "machine_util_avg": 0.5,
                            },
                        },
                        "warnings": [],
                        "errors": [],
                    },
                    ensure_ascii=False,
                ),
                "ui-smoke",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    for name in list(sys.modules):
        if name == "app" or name.startswith("web.bootstrap.entrypoint") or name.startswith("web.bootstrap.factory"):
            sys.modules.pop(name, None)

    import app as app_mod

    app = app_mod.create_app()
    app.config["PLUGIN_STATUS"] = {
        "loaded_at": "2026-05-06 09:00:00",
        "config_source": "config",
        "telemetry_persisted": True,
        "degraded": False,
        "registry": {"capabilities": ("ui-smoke-capability",)},
        "degradation_events": (),
        "conflicted_capabilities": (),
        "statuses": (
            {
                "plugin_id": "ui-smoke-plugin",
                "name": "浏览器几何测试扩展",
                "version": "1.0",
                "enabled": "yes",
                "loaded": "yes",
                "enabled_source": "config",
                "error": "",
                "capabilities": ("ui-smoke-capability",),
            },
        ),
    }
    return app


def _serve_app(app):
    server = make_server("127.0.0.1", _free_port(), app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def _run_chrome_geometry_probe(*, chrome_path: str, node_path: str, base_url: str, tmp_path: Path) -> list[dict]:
    script = tmp_path / "ui_geometry_probe.mjs"
    script.write_text(
        textwrap.dedent(
            r"""
            import fs from "node:fs/promises";
            import os from "node:os";
            import path from "node:path";
            import { spawn } from "node:child_process";

            const chromePath = process.argv[2];
            const baseUrl = process.argv[3];
            const paths = JSON.parse(process.argv[4]);
            const expectedByPath = JSON.parse(process.argv[5]);
            const userDataDir = await fs.mkdtemp(path.join(os.tmpdir(), "aps-ui-chrome-"));

            const chrome = spawn(chromePath, [
              "--headless=new",
              "--disable-gpu",
              "--disable-dev-shm-usage",
              "--no-first-run",
              "--no-default-browser-check",
              "--remote-debugging-port=0",
              `--user-data-dir=${userDataDir}`,
              "about:blank",
            ], { stdio: ["ignore", "ignore", "pipe"] });

            const active = [];
            function fail(message) {
              try { chrome.kill("SIGKILL"); } catch {}
              console.error(message);
              process.exit(1);
            }

            async function sleep(ms) {
              await new Promise((resolve) => setTimeout(resolve, ms));
            }

            async function readDebugPort() {
              const activePort = path.join(userDataDir, "DevToolsActivePort");
              for (let i = 0; i < 100; i += 1) {
                try {
                  const content = await fs.readFile(activePort, "utf8");
                  return content.trim().split(/\r?\n/)[0];
                } catch {
                  await sleep(100);
                }
              }
              fail("Chrome 没有打开调试端口。");
            }

            class CdpClient {
              constructor(wsUrl) {
                this.nextId = 1;
                this.pending = new Map();
                this.waiters = new Map();
                this.ws = new WebSocket(wsUrl);
              }

              async open() {
                await new Promise((resolve, reject) => {
                  this.ws.onopen = resolve;
                  this.ws.onerror = reject;
                  this.ws.onmessage = (event) => this.onMessage(event);
                });
              }

              onMessage(event) {
                const payload = JSON.parse(event.data);
                if (payload.id && this.pending.has(payload.id)) {
                  const { resolve, reject } = this.pending.get(payload.id);
                  this.pending.delete(payload.id);
                  if (payload.error) {
                    reject(new Error(JSON.stringify(payload.error)));
                  } else {
                    resolve(payload.result || {});
                  }
                  return;
                }
                const waiters = this.waiters.get(payload.method) || [];
                const waiter = waiters.shift();
                if (waiter) {
                  waiter.resolve(payload.params || {});
                }
              }

              send(method, params = {}) {
                const id = this.nextId;
                this.nextId += 1;
                this.ws.send(JSON.stringify({ id, method, params }));
                return new Promise((resolve, reject) => {
                  this.pending.set(id, { resolve, reject });
                });
              }

              waitEvent(method, timeoutMs = 10000) {
                return new Promise((resolve, reject) => {
                  const timer = setTimeout(() => reject(new Error(`等待 ${method} 超时`)), timeoutMs);
                  const waiters = this.waiters.get(method) || [];
                  waiters.push({
                    resolve: (value) => {
                      clearTimeout(timer);
                      resolve(value);
                    },
                  });
                  this.waiters.set(method, waiters);
                });
              }

              close() {
                this.ws.close();
              }
            }

            async function newPage(port) {
              const response = await fetch(`http://127.0.0.1:${port}/json/new`, { method: "PUT" });
              if (!response.ok) {
                throw new Error(`创建 Chrome 标签失败：${response.status}`);
              }
              return await response.json();
            }

            async function inspectPage(port, url, width, expected) {
              const httpResponse = await fetch(url, { redirect: "manual" });
              const httpStatus = httpResponse.status;
              const page = await newPage(port);
              const client = new CdpClient(page.webSocketDebuggerUrl);
              await client.open();
              active.push(client);
              await client.send("Page.enable");
              await client.send("Runtime.enable");
              await client.send("Emulation.setDeviceMetricsOverride", {
                width,
                height: 900,
                deviceScaleFactor: 1,
                mobile: false,
              });
              const loaded = client.waitEvent("Page.loadEventFired");
              await client.send("Page.navigate", { url });
              await loaded;
              const expression = `
                (() => {
                  const maxScrollWidth = Math.max(
                    document.body ? document.body.scrollWidth : 0,
                    document.documentElement ? document.documentElement.scrollWidth : 0
                  );
                  const bodyOverflow = maxScrollWidth > window.innerWidth + 1;
                  const toggleRows = [...document.querySelectorAll('.aps-toggle-row')];
                  const toggleOverlapCount = toggleRows.filter((row) => {
                    const track = row.querySelector('.aps-toggle-track');
                    const title = row.querySelector('.aps-toggle-title');
                    if (!track || !title) return false;
                    const a = track.getBoundingClientRect();
                    const b = title.getBoundingClientRect();
                    return !(a.right <= b.left || b.right <= a.left || a.bottom <= b.top || b.bottom <= a.top);
                  }).length;
                  const visibleNotices = [...document.querySelectorAll('.aps-notice,.aps-summary-item')]
                    .filter((el) => {
                      const rect = el.getBoundingClientRect();
                      return rect.width > 0 && rect.height > 0;
                    }).length;
                  document.documentElement.setAttribute('data-theme', 'dark');
                  const darkSummaryBadCount = [...document.querySelectorAll('.aps-summary-item')]
                    .filter((el) => {
                      const style = getComputedStyle(el);
                      return style.backgroundColor.includes('255, 255, 255') || style.color === style.backgroundColor;
                    }).length;
                  const logsTable = document.querySelector('#systemLogsTable');
                  const bodyText = document.body ? document.body.innerText || "" : "";
                  const hasAppShell = Boolean(document.querySelector('meta[name="aps-ui-template-env"]'))
                    && Boolean(document.querySelector('header nav, header.top-header, nav.sidebar-nav'))
                    && Boolean(document.getElementById('apsThemeToggle'));
                  const pageLooksError = /Traceback|Internal Server Error|Werkzeug|500 Internal|服务器内部错误|错误详情|Unhandled|Exception/i
                    .test(bodyText);
                  const expectedTexts = window.__APS_EXPECTED_SIGNALS__?.texts || [];
                  const expectedIds = window.__APS_EXPECTED_SIGNALS__?.ids || [];
                  const expectedPath = window.__APS_EXPECTED_SIGNALS__?.path || "";
                  const finalPath = location.pathname + location.search;
                  const missingExpectedTexts = expectedTexts.filter((text) => !bodyText.includes(text));
                  const missingExpectedIds = expectedIds.filter((id) => !document.getElementById(id));
                  const pathMismatch = Boolean(expectedPath && finalPath !== expectedPath);
                  function parseRgb(value) {
                    const text = String(value || "");
                    const start = text.indexOf("(");
                    const end = text.indexOf(")");
                    if (start < 0 || end <= start) return null;
                    const parts = text.slice(start + 1, end).split(",");
                    const alpha = parts.length >= 4 ? Number(String(parts[3] || "").trim()) : 1;
                    if (Number.isFinite(alpha) && alpha === 0) return null;
                    const channels = parts.slice(0, 3)
                      .map((part) => Number(String(part || "").trim()));
                    return channels.every((item) => Number.isFinite(item)) ? channels : null;
                  }
                  function channelToLinear(value) {
                    const normalized = value / 255;
                    return normalized <= 0.03928
                      ? normalized / 12.92
                      : Math.pow((normalized + 0.055) / 1.055, 2.4);
                  }
                  function luminance(rgb) {
                    return 0.2126 * channelToLinear(rgb[0])
                      + 0.7152 * channelToLinear(rgb[1])
                      + 0.0722 * channelToLinear(rgb[2]);
                  }
                  function contrastRatio(a, b) {
                    const high = Math.max(luminance(a), luminance(b));
                    const low = Math.min(luminance(a), luminance(b));
                    return (high + 0.05) / (low + 0.05);
                  }
                  function isVisible(el) {
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                  }
                  function nearestBackground(el) {
                    let node = el;
                    while (node && node !== document.documentElement) {
                      const bg = parseRgb(getComputedStyle(node).backgroundColor);
                      if (bg) {
                        return bg;
                      }
                      node = node.parentElement;
                    }
                    return parseRgb(getComputedStyle(document.body || document.documentElement).backgroundColor);
                  }
                  function lowContrastTextCount(selectors) {
                    return selectors.flatMap((selector) => [...document.querySelectorAll(selector)])
                      .filter((el) => isVisible(el))
                      .filter((el) => {
                        const fg = parseRgb(getComputedStyle(el).color);
                        const bg = nearestBackground(el);
                        return fg && bg && contrastRatio(fg, bg) < 3;
                      }).length;
                  }
                  function multilineTableComputedOk(selector) {
                    const table = document.querySelector(selector);
                    if (!table) {
                      return true;
                    }
                    if (!table.classList.contains('aps-table--multiline')) {
                      return false;
                    }
                    const cells = [...table.querySelectorAll('thead th, tbody td')].filter((cell) => isVisible(cell));
                    if (!cells.length) {
                      return false;
                    }
                    return cells.slice(0, 12).every((cell) => {
                      const style = getComputedStyle(cell);
                      const wrapOk = style.overflowWrap === 'anywhere' || style.wordBreak !== 'normal';
                      return (
                        style.whiteSpace === 'normal'
                        && style.textOverflow !== 'ellipsis'
                        && style.overflow !== 'hidden'
                        && wrapOk
                      );
                    });
                  }
                  const requiredToggleByPath = {
                    "/scheduler/": ["runEnforceReady", "runStrictMode"],
                    "/scheduler/batches": ["batchManageStrictMode"],
                    "/scheduler/excel/batches": ["batchImportAutoOps", "batchImportStrictMode"],
                    "/process/": ["processCreateStrictMode"],
                  };
                  const requiredToggleIds = requiredToggleByPath[location.pathname] || [];
                  const missingRequiredToggleIds = requiredToggleIds
                    .filter((id) => !document.getElementById(id));
                  const darkLowContrastSummaryCount = [...document.querySelectorAll('.aps-summary-item')]
                    .filter((el) => {
                      const style = getComputedStyle(el);
                      const fg = parseRgb(style.color);
                      const bg = parseRgb(style.backgroundColor);
                      return fg && bg && contrastRatio(fg, bg) < 3;
                    }).length;
                  const darkLowContrastTextCount = lowContrastTextCount([
                    '.aps-summary-label',
                    '.aps-summary-value',
                    '.aps-summary-desc',
                    '.aps-notice-title',
                    '.aps-notice-body',
                    '.aps-toggle-title',
                    '.aps-toggle-desc',
                  ]);
                  const darkNoticeBadCount = [...document.querySelectorAll('.aps-notice')]
                    .filter((el) => {
                      const style = getComputedStyle(el);
                      return style.backgroundColor.includes('255, 255, 255');
                    }).length;
                  const multilineTableChecks = {
                    systemLogsTable: multilineTableComputedOk('#systemLogsTable'),
                    pluginStatusTable: multilineTableComputedOk('#pluginStatusTable'),
                    systemHistoryTable: multilineTableComputedOk('#systemHistoryTable'),
                  };
                  return JSON.stringify({
                    path: finalPath,
                    expectedPath,
                    pathMismatch,
                    httpStatus: ${httpStatus},
                    title: document.title || "",
                    hasAppShell,
                    pageLooksError,
                    missingExpectedTexts,
                    missingExpectedIds,
                    width: window.innerWidth,
                    bodyOverflow,
                    maxScrollWidth,
                    toggleCount: toggleRows.length,
                    toggleOverlapCount,
                    visibleNotices,
                    darkSummaryBadCount,
                    darkLowContrastSummaryCount,
                    darkLowContrastTextCount,
                    darkNoticeBadCount,
                    multilineTableChecks,
                    logsTableMultiline: multilineTableChecks.systemLogsTable,
                    requiredToggleIds,
                    missingRequiredToggleIds,
                  });
                })()
              `;
              await client.send("Runtime.evaluate", {
                expression: `window.__APS_EXPECTED_SIGNALS__ = ${JSON.stringify(expected || {})};`,
                returnByValue: true,
              });
              const evaluated = await client.send("Runtime.evaluate", {
                expression,
                returnByValue: true,
                awaitPromise: true,
              });
              if (evaluated.exceptionDetails) {
                throw new Error(`页面检查脚本执行失败：${JSON.stringify(evaluated.exceptionDetails)}`);
              }
              if (!evaluated.result || typeof evaluated.result.value !== "string") {
                throw new Error(`页面检查脚本没有返回 JSON 字符串：${JSON.stringify(evaluated.result || {})}`);
              }
              client.close();
              return JSON.parse(evaluated.result.value);
            }

            try {
              const port = await readDebugPort();
              const results = [];
              for (const pagePath of paths) {
                for (const width of [1024, 768]) {
                  results.push(await inspectPage(port, `${baseUrl}${pagePath}`, width, expectedByPath[pagePath] || {}));
                }
              }
              console.log(JSON.stringify(results));
              for (const client of active) client.close();
              chrome.kill("SIGKILL");
            } catch (error) {
              fail(error && error.stack ? error.stack : String(error));
            }
            """
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            node_path,
            str(script),
            chrome_path,
            base_url,
            json.dumps(SMOKE_PATHS, ensure_ascii=False),
            json.dumps(EXPECTED_PAGE_SIGNALS, ensure_ascii=False),
        ],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return json.loads(completed.stdout)


def test_ui_pages_do_not_create_body_level_overflow_in_real_browser(tmp_path, monkeypatch) -> None:
    chrome_path = _find_chrome()
    node_path = _find_node_with_browser_runtime()
    app = _build_app(tmp_path, monkeypatch)
    server, base_url = _serve_app(app)
    try:
        results = _run_chrome_geometry_probe(
            chrome_path=chrome_path,
            node_path=node_path,
            base_url=base_url,
            tmp_path=tmp_path,
        )
    finally:
        server.shutdown()

    overflowing = [item for item in results if item["bodyOverflow"]]
    overlapping_toggles = [item for item in results if item["toggleOverlapCount"]]
    bad_dark_summary = [item for item in results if item["darkSummaryBadCount"]]
    bad_dark_summary_contrast = [item for item in results if item["darkLowContrastSummaryCount"]]
    bad_dark_text_contrast = [item for item in results if item["darkLowContrastTextCount"]]
    bad_dark_notice = [item for item in results if item["darkNoticeBadCount"]]
    bad_logs_table = [item for item in results if not item["logsTableMultiline"]]
    bad_multiline_tables = [
        item
        for item in results
        if any(not ok for ok in dict(item["multilineTableChecks"]).values())
    ]
    missing_required_toggles = [item for item in results if item["missingRequiredToggleIds"]]
    bad_http_status = [item for item in results if item["httpStatus"] != 200]
    bad_shell = [item for item in results if not item["hasAppShell"]]
    error_pages = [item for item in results if item["pageLooksError"]]
    wrong_paths = [item for item in results if item["pathMismatch"]]
    missing_expected_texts = [item for item in results if item["missingExpectedTexts"]]
    missing_expected_ids = [item for item in results if item["missingExpectedIds"]]

    assert bad_http_status == []
    assert bad_shell == []
    assert error_pages == []
    assert wrong_paths == []
    assert missing_expected_texts == []
    assert missing_expected_ids == []
    assert overflowing == []
    assert overlapping_toggles == []
    assert bad_dark_summary == []
    assert bad_dark_summary_contrast == []
    assert bad_dark_text_contrast == []
    assert bad_dark_notice == []
    assert bad_logs_table == []
    assert bad_multiline_tables == []
    assert missing_required_toggles == []
    assert any(item["toggleCount"] > 0 for item in results)
    assert any(item["visibleNotices"] > 0 for item in results)


def test_ui_browser_geometry_smoke_covers_scheduler_run_page() -> None:
    assert "/scheduler/?status=pending" in SMOKE_PATHS
    assert "/scheduler/batches?status=pending" not in SMOKE_PATHS
    assert "/system/history" in SMOKE_PATHS
    assert EXPECTED_PAGE_SIGNALS["/scheduler/?status=pending"]["ids"] == [
        "jsRunScheduleForm",
        "runEnforceReady",
        "runStrictMode",
    ]
    assert "pluginStatusTable" in EXPECTED_PAGE_SIGNALS["/system/backup"]["ids"]
    assert EXPECTED_PAGE_SIGNALS["/system/history"]["ids"] == ["systemHistoryTable"]
    script_source = Path(__file__).read_text(encoding="utf-8")
    assert '"/scheduler/": ["runEnforceReady", "runStrictMode"]' in script_source
    assert "multilineTableComputedOk('#systemLogsTable')" in script_source
    assert "multilineTableComputedOk('#pluginStatusTable')" in script_source
    assert "multilineTableComputedOk('#systemHistoryTable')" in script_source
