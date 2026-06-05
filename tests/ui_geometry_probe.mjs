import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { createCdpClientClass } from "./ui_geometry_cdp_client.mjs";
import { WAIT_FOR_PAGE_STABLE_EXPRESSION, buildPageInspectionExpression } from "./ui_geometry_probe_page_eval.mjs";

const chromePath = process.argv[2];
const baseUrl = process.argv[3];
const paths = JSON.parse(process.argv[4]);
const expectedByPath = JSON.parse(process.argv[5]);
const errorPageKeywords = JSON.parse(process.argv[6]);
const profileBaseDir = process.argv[7];
const runtimeContext = JSON.parse(process.argv[8] || "{}");
await fs.mkdir(profileBaseDir, { recursive: true });
const userDataDir = await fs.mkdtemp(path.join(profileBaseDir, "aps-ui-chrome-"));
const chromeArgs = [
  "--headless=new",
  "--disable-gpu",
  "--disable-dev-shm-usage",
  "--no-first-run",
  "--no-default-browser-check",
  "--remote-debugging-port=0",
  `--user-data-dir=${userDataDir}`,
  "about:blank",
];

const chrome = spawn(chromePath, chromeArgs, { stdio: ["ignore", "ignore", "pipe"] });

const active = [];
let chromeStderrTail = "";
let chromeExited = false;
let chromeExitCode = null;
let chromeExitSignal = null;
let chromeSpawnError = null;

function appendChromeStderr(chunk) {
  chromeStderrTail += String(chunk || "");
  if (chromeStderrTail.length > 32768) {
    chromeStderrTail = chromeStderrTail.slice(-32768);
  }
}

if (chrome.stderr) {
  chrome.stderr.on("data", appendChromeStderr);
}
chrome.on("exit", (code, signal) => {
  chromeExited = true;
  chromeExitCode = code;
  chromeExitSignal = signal;
});
chrome.on("error", (error) => {
  chromeSpawnError = error;
});

class ProbeFailure extends Error {
  constructor(kind, details = {}) {
    super(kind);
    this.kind = kind;
    this.details = details;
  }
}

function failurePayload(kind, details = {}) {
  return {
    failure_kind: kind,
    stage: details.stage || "",
    message: details.message || kind,
    chromePath,
    chromeArgs,
    chromeExitCode,
    chromeExitSignal,
    chromeStderrTail,
    userDataDir,
    nodeVersion: process.version,
    baseUrl,
    runtime_context: runtimeContext,
    ...details,
  };
}

function fail(kind, details = {}) {
  throw new ProbeFailure(kind, failurePayload(kind, details));
}

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForChromeExit(timeoutMs) {
  if (chromeExited) {
    return { exited: true, code: chromeExitCode, signal: chromeExitSignal };
  }
  return await new Promise((resolve) => {
    const timer = setTimeout(() => resolve({ exited: false, timeoutMs }), timeoutMs);
    chrome.once("exit", (code, signal) => {
      clearTimeout(timer);
      resolve({ exited: true, code, signal });
    });
  });
}

async function readDebugPort() {
  const activePort = path.join(userDataDir, "DevToolsActivePort");
  const started = Date.now();
  for (let i = 0; i < 100; i += 1) {
    if (chromeSpawnError) {
      fail("chrome_spawn_failed", {
        stage: "readDebugPort",
        message: String(chromeSpawnError && chromeSpawnError.stack ? chromeSpawnError.stack : chromeSpawnError),
        activePort,
        waitedMs: Date.now() - started,
      });
    }
    if (chromeExited) {
      fail("chrome_exited_before_devtools", {
        stage: "readDebugPort",
        activePort,
        waitedMs: Date.now() - started,
      });
    }
    try {
      const content = await fs.readFile(activePort, "utf8");
      const firstLine = content.trim().split(/\r?\n/)[0] || "";
      const port = Number(firstLine);
      if (!Number.isInteger(port) || port < 1 || port > 65535) {
        fail("chrome_devtools_port_invalid", {
          stage: "readDebugPort",
          activePort,
          rawContent: content.slice(0, 2048),
          waitedMs: Date.now() - started,
        });
      }
      return String(port);
    } catch (error) {
      if (error instanceof ProbeFailure) {
        throw error;
      }
      await sleep(100);
    }
  }
  fail("chrome_devtools_port_timeout", {
    stage: "readDebugPort",
    activePort,
    waitedMs: Date.now() - started,
  });
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 5000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function withTimeout(promise, timeoutMs, message) {
  let timer;
  try {
    return await new Promise((resolve, reject) => {
      timer = setTimeout(() => reject(new Error(message)), timeoutMs);
      Promise.resolve(promise).then(resolve, reject);
    });
  } finally {
    clearTimeout(timer);
  }
}

async function writeLine(stream, text) {
  await new Promise((resolve, reject) => {
    stream.write(`${text}\n`, (error) => {
      if (error) reject(error);
      else resolve(undefined);
    });
  });
}

async function preflightDevTools(port) {
  const url = `http://127.0.0.1:${port}/json/version`;
  let response;
  let body = "";
  try {
    response = await fetchWithTimeout(url, {}, 5000);
    body = await withTimeout(response.text(), 5000, "DevTools /json/version body timeout");
  } catch (error) {
    fail("chrome_devtools_version_unreachable", {
      stage: "preflightDevTools",
      port,
      status: 0,
      responseBody: String(error && error.stack ? error.stack : error).slice(0, 4096),
    });
  }
  if (!response.ok) {
    fail("chrome_devtools_version_unreachable", {
      stage: "preflightDevTools",
      port,
      status: response.status,
      responseBody: body.slice(0, 4096),
    });
  }
  let payload;
  try {
    payload = JSON.parse(body);
  } catch (error) {
    fail("chrome_devtools_version_unreachable", {
      stage: "preflightDevTools",
      port,
      status: response.status,
      responseBody: body.slice(0, 4096),
      message: "DevTools /json/version did not return JSON",
    });
  }
  if (!payload.webSocketDebuggerUrl && !payload.Browser) {
    fail("chrome_devtools_version_unreachable", {
      stage: "preflightDevTools",
      port,
      status: response.status,
      responseBody: body.slice(0, 4096),
      message: "DevTools /json/version missing Browser/webSocketDebuggerUrl",
    });
  }
  return payload;
}

const CdpClient = createCdpClientClass({ ProbeFailure, failurePayload });

async function responseTextWithTimeout(response, timeoutMs, stage) {
  try {
    return await withTimeout(response.text(), timeoutMs, `${stage} body timeout`);
  } catch (error) {
    fail("cdp_websocket_failed", {
      stage,
      status: response && response.status,
      message: String(error && error.stack ? error.stack : error),
    });
  }
}

async function newPage(port) {
  const response = await fetchWithTimeout(`http://127.0.0.1:${port}/json/new`, { method: "PUT" }, 5000);
  const body = await responseTextWithTimeout(response, 5000, "newPage");
  if (!response.ok) {
    fail("cdp_websocket_failed", {
      stage: "newPage",
      status: response.status,
      responseBody: body.slice(0, 4096),
    });
  }
  let page;
  try {
    page = JSON.parse(body);
  } catch (error) {
    fail("cdp_websocket_failed", {
      stage: "newPage",
      status: response.status,
      responseBody: body.slice(0, 4096),
      message: String(error && error.stack ? error.stack : error),
    });
  }
  if (!page.webSocketDebuggerUrl) {
    fail("cdp_websocket_failed", { stage: "newPage", page });
  }
  return page;
}

async function waitForPageStable(client, url, viewport) {
  const expression = WAIT_FOR_PAGE_STABLE_EXPRESSION;
  const evaluated = await client.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  }, 10000);
  if (evaluated.exceptionDetails) {
    fail("page_stabilization_timeout", {
      stage: "waitForPageStable",
      url,
      viewport,
      details: evaluated.exceptionDetails,
    });
  }
  return evaluated.result ? evaluated.result.value : {};
}

async function inspectPage(port, url, expected, httpStatus) {
  const page = await newPage(port);
  const client = new CdpClient(page.webSocketDebuggerUrl);
  try {
    await client.open();
    active.push(client);
    await client.send("Page.enable");
    await client.send("Runtime.enable");
    const results = [];
    let pageLoaded = false;
    for (const width of [1024, 768]) {
      await client.send("Emulation.setDeviceMetricsOverride", {
        width,
        height: 900,
        deviceScaleFactor: 1,
        mobile: false,
      });
      client.context = { url, viewport: { width, height: 900 } };
      if (!pageLoaded) {
        const loaded = client.waitEvent("Page.loadEventFired");
        const navigateResult = await client.send("Page.navigate", { url });
        if (navigateResult.errorText) {
          fail("page_http_status_failed", {
            stage: "Page.navigate",
            url,
            viewport: { width, height: 900 },
            message: navigateResult.errorText,
          });
        }
        await loaded;
        pageLoaded = true;
      }
      await waitForPageStable(client, url, { width, height: 900 });
      const expression = buildPageInspectionExpression(httpStatus);
      await client.send("Runtime.evaluate", {
        expression: `window.__APS_EXPECTED_SIGNALS__ = ${JSON.stringify(expected || {})};`,
        returnByValue: true,
      });
      await client.send("Runtime.evaluate", {
        expression: `window.__APS_ERROR_PAGE_KEYWORDS__ = ${JSON.stringify(errorPageKeywords || [])};`,
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
      results.push(JSON.parse(evaluated.result.value));
    }
    return results;
  } finally {
    await client.close();
    const index = active.indexOf(client);
    if (index >= 0) active.splice(index, 1);
  }
}

try {
  const port = await readDebugPort();
  await preflightDevTools(port);
  const results = [];
  for (const pagePath of paths) {
    const url = `${baseUrl}${pagePath}`;
    const httpResponse = await fetchWithTimeout(url, { redirect: "manual" }, 5000);
    const httpStatus = httpResponse.status;
    results.push(...await inspectPage(port, url, expectedByPath[pagePath] || {}, httpStatus));
  }
  await writeLine(process.stdout, JSON.stringify(results));
} catch (error) {
  if (error instanceof ProbeFailure) {
    await writeLine(process.stderr, JSON.stringify(error.details, null, 2));
  } else {
    await writeLine(process.stderr, JSON.stringify(failurePayload("cdp_websocket_failed", {
      stage: "top-level",
      message: String(error && error.stack ? error.stack : error),
    }), null, 2));
  }
  process.exitCode = 1;
} finally {
  for (const client of [...active]) await client.close();
  try { chrome.kill("SIGTERM"); } catch {}
  const chromeExitWait = await waitForChromeExit(3000);
  if (!chromeExitWait.exited) {
    try { chrome.kill("SIGKILL"); } catch {}
  }
  try { await fs.rm(userDataDir, { recursive: true, force: true }); } catch (error) {
    await writeLine(process.stderr, JSON.stringify({
      warning_kind: "chrome_profile_cleanup_warning",
      userDataDir,
      chromeExitWait,
      message: String(error && error.stack ? error.stack : error),
    }, null, 2));
  }
  process.exit(process.exitCode || 0);
}
