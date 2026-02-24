from __future__ import annotations

import json
import os
import subprocess


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _run_node_status_check(gantt_js_path: str) -> dict:
    node_code = r"""
const fs = require("fs");
const codePath = process.env.APS_GANTT_JS;
if (!codePath) {
  console.error("APS_GANTT_JS missing");
  process.exit(2);
}
const code = fs.readFileSync(codePath, "utf8");

function escapeRe(s) {
  return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function extractNamedFunction(fnName) {
  const re = new RegExp("function\\s+" + escapeRe(fnName) + "\\s*\\([^)]*\\)\\s*\\{", "m");
  const m = re.exec(code);
  if (!m) throw new Error("cannot find function " + fnName);
  const start = m.index;
  const braceStart = code.indexOf("{", start);
  if (braceStart < 0) throw new Error("cannot find opening brace " + fnName);

  let depth = 0;
  let inS = false, inD = false, inT = false, inLine = false, inBlock = false, esc = false;
  for (let i = braceStart; i < code.length; i++) {
    const ch = code[i];
    const nx = code[i + 1];
    if (inLine) {
      if (ch === "\n") inLine = false;
      continue;
    }
    if (inBlock) {
      if (ch === "*" && nx === "/") { inBlock = false; i++; }
      continue;
    }
    if (inS) {
      if (esc) { esc = false; continue; }
      if (ch === "\\") { esc = true; continue; }
      if (ch === "'") { inS = false; continue; }
      continue;
    }
    if (inD) {
      if (esc) { esc = false; continue; }
      if (ch === "\\") { esc = true; continue; }
      if (ch === "\"") { inD = false; continue; }
      continue;
    }
    if (inT) {
      if (esc) { esc = false; continue; }
      if (ch === "\\") { esc = true; continue; }
      if (ch === "`") { inT = false; continue; }
      continue;
    }

    if (ch === "/" && nx === "/") { inLine = true; i++; continue; }
    if (ch === "/" && nx === "*") { inBlock = true; i++; continue; }
    if (ch === "'") { inS = true; continue; }
    if (ch === "\"") { inD = true; continue; }
    if (ch === "`") { inT = true; continue; }

    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) {
        return code.slice(start, i + 1);
      }
    }
  }
  throw new Error("cannot extract full body " + fnName);
}

function str(v) {
  return v === null || typeof v === "undefined" ? "" : String(v);
}
function norm(v) {
  return str(v).trim();
}
function parseLocalDateTime(s) {
  const x = norm(s);
  const m = /^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?/.exec(x);
  if (!m) return null;
  const yy = Number(m[1]);
  const mm = Number(m[2]) - 1;
  const dd = Number(m[3]);
  const hh = Number(m[4]);
  const mi = Number(m[5]);
  const ss = Number(m[6] || "0");
  const dt = new Date(yy, mm, dd, hh, mi, ss, 0);
  return isNaN(dt.getTime()) ? null : dt;
}
eval(extractNamedFunction("statusKeyForTask"));

const now = new Date();
const y = now.getFullYear();
const m = String(now.getMonth() + 1).padStart(2, "0");
const d = String(now.getDate()).padStart(2, "0");
const date = `${y}-${m}-${d}`;

const cases = [
  { name: "backend_completed_first", task: { start: date + " 23:00:00", end: date + " 23:30:00", meta: { status: "completed" } }, expected: "done" },
  { name: "backend_processing_first", task: { start: date + " 23:00:00", end: date + " 23:30:00", meta: { status: "processing" } }, expected: "in_progress" },
  { name: "backend_blocked", task: { start: date + " 23:00:00", end: date + " 23:30:00", meta: { status: "blocked" } }, expected: "blocked" },
  { name: "time_fallback_done", task: { start: date + " 00:00:00", end: date + " 00:01:00", meta: {} }, expected: "done" },
];

const out = cases.map((c) => ({
  name: c.name,
  got: statusKeyForTask(c.task),
  expected: c.expected,
}));

process.stdout.write(JSON.stringify({ out }));
"""
    env = dict(os.environ)
    env["APS_GANTT_JS"] = gantt_js_path
    p = subprocess.run(
        ["node", "-"],
        input=node_code,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    if p.returncode != 0:
        raise RuntimeError(f"node 执行失败：rc={p.returncode} stderr={p.stderr[:500]!r}")
    return json.loads(p.stdout or "{}")


def main() -> None:
    repo_root = find_repo_root()
    gantt_js_path = os.path.join(repo_root, "static", "js", "gantt.js")
    if not os.path.exists(gantt_js_path):
        raise RuntimeError(f"缺少文件：{gantt_js_path}")

    with open(gantt_js_path, "r", encoding="utf-8") as f:
        src = f.read()
    # 依赖模式应统一为 depsMode，不再保留旧双复选框语义
    if "depsMode" not in src:
        raise RuntimeError("gantt.js 缺少 depsMode 语义字段")
    if "showProcessDeps" in src or "onlyCCDeps" in src:
        raise RuntimeError("gantt.js 仍包含旧依赖开关字段（showProcessDeps/onlyCCDeps）")

    ret = _run_node_status_check(gantt_js_path)
    rows = ret.get("out") or []
    if not rows:
        raise RuntimeError("status 语义检查无输出")
    bad = [x for x in rows if str(x.get("got")) != str(x.get("expected"))]
    if bad:
        raise RuntimeError(f"status 语义不符合预期：{bad}")

    print("OK")


if __name__ == "__main__":
    main()

