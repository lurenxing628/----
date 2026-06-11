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
  const nav = await client.send("Page.navigate", { url: `${baseUrl}${pagePath}` });
  if (nav && nav.errorText) {
    // 不检查 errorText 时，连不上服务会截到 Chrome 内部错误页且被记成功——基线静默掺假
    throw new Error(`navigate failed: ${nav.errorText}`);
  }
  await client.send("Runtime.evaluate", {
    expression: WAIT_FOR_PAGE_STABLE_EXPRESSION,
    awaitPromise: true,
  });
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

let exitCode = 0;
try {
  const port = await readDebugPort();
  const resp = await fetch(`http://127.0.0.1:${port}/json/new`, { method: "PUT" });
  const page = JSON.parse(await resp.text());
  const client = new CdpClient(page.webSocketDebuggerUrl);
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
  chrome.kill("SIGKILL");
}
process.exit(exitCode);
