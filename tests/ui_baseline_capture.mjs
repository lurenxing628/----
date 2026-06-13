// UI 截图基线采集（fusion-anchor-baseline-prep，手跑工具——由
// tests/_scripts_e2e/capture_ui_baseline.py 调起，不进 gate/registry）。
// 用法：node ui_baseline_capture.mjs <chromePath> <baseUrl> <pathsJson> <profileBaseDir> <outputDir>
// 对每个 path：CDP navigate → 等页面稳定 → 截亮色 → set data-theme=dark + 两帧 rAF → 截暗色。
// 单页失败不中断（继续余页），结果按行输出 JSON（py 侧汇总并定退出码）。
import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { createCdpClientClass } from "./ui_geometry_cdp_client.mjs";
import { WAIT_FOR_PAGE_STABLE_EXPRESSION } from "./ui_geometry_probe_page_eval.mjs";

const chromePath = process.argv[2];
const baseUrl = process.argv[3];
const pagePaths = JSON.parse(process.argv[4]);
const profileBaseDir = process.argv[5];
const outputDir = process.argv[6];

await fs.mkdir(profileBaseDir, { recursive: true });
await fs.mkdir(outputDir, { recursive: true });
const userDataDir = await fs.mkdtemp(path.join(profileBaseDir, "aps-baseline-chrome-"));

class ProbeFailure extends Error {
  constructor(kind, details = {}) {
    super(kind);
    this.kind = kind;
    this.details = details;
  }
}
const failurePayload = (kind, details) => ({ kind, ...details });
const CdpClient = createCdpClientClass({ ProbeFailure, failurePayload });

const chrome = spawn(chromePath, [
  "--headless=new",
  "--disable-gpu",
  "--disable-dev-shm-usage",
  "--no-first-run",
  "--no-default-browser-check",
  "--remote-debugging-port=0",
  "--window-size=1440,1200",
  `--user-data-dir=${userDataDir}`,
  "about:blank",
], { stdio: ["ignore", "ignore", "ignore"] });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function readDebugPort() {
  const activePort = path.join(userDataDir, "DevToolsActivePort");
  for (let i = 0; i < 100; i += 1) {
    try {
      const content = await fs.readFile(activePort, "utf8");
      const port = Number(content.trim().split(/\r?\n/)[0]);
      if (Number.isInteger(port) && port > 0) return String(port);
    } catch {
      await sleep(100);
    }
  }
  throw new Error("DevToolsActivePort timeout");
}

// 暗色切换照探针先例（page_eval.mjs:54）；必须等两帧 rAF——
// common_theme.js 的真实切换用双 requestAnimationFrame 延迟应用样式
const SET_DARK_AND_SETTLE = `
  new Promise((resolve) => {
    document.documentElement.setAttribute("data-theme", "dark");
    requestAnimationFrame(() => requestAnimationFrame(() => resolve("dark-ready")));
  })
`;

function safeName(pagePath) {
  return pagePath.replace(/^\//, "").replace(/[\/?&=]+/g, "_").replace(/_+$/, "") || "root";
}

async function captureOne(client, pagePath) {
  const targetUrl = `${baseUrl}${pagePath}`;
  // HTTP 状态校验：CDP Page.navigate 的 errorText 只接网络层失败，接不住服务端 500——
  // errorhandler(500) 原地渲染错误页、URL 不变，会被截图记成功进基线（验收证据掺假）。
  // 先用一次带超时的 manual-redirect fetch 拿真实状态码，非 200 即暴露。探针 probe.mjs:348
  // 同样在导航前 fetch 拿状态码（其用 AbortController 实现超时，此处用等价的 AbortSignal.timeout）。
  const httpResp = await fetch(targetUrl, { redirect: "manual", signal: AbortSignal.timeout(5000) });
  if (httpResp.status !== 200) {
    throw new Error(`HTTP ${httpResp.status}（非 200，疑似错误页/重定向），不进基线`);
  }
  // 照探针先例（probe.mjs:296-309）：先挂 loadEventFired 再 navigate 再等 load——
  // 否则稳定等待表达式可能跑在旧 document 上，截到旧页/空白页还记成功
  const loaded = client.waitEvent("Page.loadEventFired", 30000);
  const nav = await client.send("Page.navigate", { url: targetUrl });
  if (nav && nav.errorText) {
    // 不检查 errorText 时，连不上服务会截到 Chrome 内部错误页且被记成功——基线静默掺假
    throw new Error(`navigate failed: ${nav.errorText}`);
  }
  await loaded;
  await client.send("Runtime.evaluate", {
    expression: WAIT_FOR_PAGE_STABLE_EXPRESSION,
    awaitPromise: true,
  });
  // 校验真的落在目标页（重定向到错误页/登录页要暴露，不进基线）
  const href = await client.send("Runtime.evaluate", {
    expression: "location.pathname + location.search",
    returnByValue: true,
  });
  const actual = href && href.result ? String(href.result.value) : "";
  if (actual !== pagePath) {
    throw new Error(`landed on ${actual}, expected ${pagePath}`);
  }
  // 关键 DOM 信号：契约页都继承 base.html 的应用外壳——顶栏 + 侧栏导航 + 主题切换按钮三者
  // 在 base.html 无条件输出。要求三者俱全（非任一），状态 200 但渲染异常/错误页/残页（缺其中
  // 任一）会被这道挡住，不让进基线。
  const shell = await client.send("Runtime.evaluate", {
    expression:
      "Boolean(document.querySelector('header.top-header')) && Boolean(document.querySelector('nav.sidebar-nav')) && Boolean(document.getElementById('apsThemeToggle'))",
    returnByValue: true,
  });
  if (!(shell && shell.result && shell.result.value === true)) {
    throw new Error("缺应用外壳（顶栏/侧栏导航/主题切换按钮三者之一缺失），疑似错误页或残页，不进基线");
  }
  const files = [];
  for (const theme of ["light", "dark"]) {
    if (theme === "dark") {
      await client.send("Runtime.evaluate", { expression: SET_DARK_AND_SETTLE, awaitPromise: true });
    }
    const shot = await client.send("Page.captureScreenshot", { format: "png" });
    const fileName = `${safeName(pagePath)}__${theme}.png`;
    await fs.writeFile(path.join(outputDir, fileName), Buffer.from(shot.data, "base64"));
    files.push(fileName);
  }
  return files;
}

function waitForChromeExit(timeoutMs) {
  return new Promise((resolve) => {
    // signal 结束的进程 exitCode 为 null、signalCode 才有值——两个都要看
    if (chrome.exitCode !== null || chrome.signalCode !== null) return resolve(true);
    const timer = setTimeout(() => resolve(false), timeoutMs);
    chrome.once("exit", () => {
      clearTimeout(timer);
      resolve(true);
    });
  });
}

let exitCode = 0;
let client = null;
try {
  const port = await readDebugPort();
  const resp = await fetch(`http://127.0.0.1:${port}/json/new`, { method: "PUT" });
  const page = JSON.parse(await resp.text());
  client = new CdpClient(page.webSocketDebuggerUrl);
  await client.open();
  await client.send("Page.enable", {});
  await client.send("Runtime.enable", {});

  for (const pagePath of pagePaths) {
    try {
      const files = await captureOne(client, pagePath);
      console.log(JSON.stringify({ path: pagePath, ok: true, files }));
    } catch (error) {
      exitCode = 1; // 单页失败不中断：余页继续，最终非 0 退出
      console.log(JSON.stringify({ path: pagePath, ok: false, error: String(error && error.message || error) }));
    }
  }
} finally {
  // 清理照探针先例（probe.mjs:363-378）：关 client → SIGTERM → 等 3s → SIGKILL 兜底 → 删 profile。
  // Windows 下 Chrome 未退出就删 profile 会撞文件锁，顺序不能省。
  if (client) {
    try { await client.close(); } catch {}
  }
  try { chrome.kill("SIGTERM"); } catch {}
  if (!(await waitForChromeExit(3000))) {
    try { chrome.kill("SIGKILL"); } catch {}
    await waitForChromeExit(2000);
  }
  try {
    await fs.rm(userDataDir, { recursive: true, force: true });
  } catch (error) {
    console.error(JSON.stringify({ warning: "profile_cleanup_failed", userDataDir, message: String(error && error.message || error) }));
  }
}
process.exit(exitCode);
