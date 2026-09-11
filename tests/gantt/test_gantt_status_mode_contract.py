"""执行事实保留，当前计划风险配色不得从时钟或旧 status 反推实际完成。

旧 Frappe 状态色与依赖开关已退役，当前配色只消费所选计划的交付风险和资源重叠。
"""

from __future__ import annotations

import json
import os
import subprocess

from tests._support.paths import REPO_ROOT_STR


def find_repo_root() -> str:
    return REPO_ROOT_STR


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
    """Current plan risk tones must never reinterpret execution as clock status."""
    from copy import deepcopy
    from types import SimpleNamespace

    from core.services.scheduler.gantt_range import resolve_week_range
    from core.services.scheduler.gantt_tasks import build_tasks
    from tests._support.gantt_current_js import run_current_js

    row = {"schedule_id": 1, "op_id": 123, "op_code": "B1-20", "batch_id": "B1", "piece_id": "piece-a",
           "part_no": "P1", "part_name": "零件1", "seq": 20, "op_type_name": "车削", "source": "internal",
           "op_status": "scheduled", "machine_id": "M1", "machine_name": "一号设备", "operator_id": "O1",
           "operator_name": "张三", "priority": "normal", "lock_status": "locked",
           "start_time": "2026-05-01 08:00:00", "end_time": "2026-05-01 12:00:00", "due_date": "2026-05-30"}
    before = deepcopy(row)
    for status in ("completed", "processing", "paused", "exception"):
        task = build_tasks(view="machine", wr=resolve_week_range(start_date="2026-05-01", end_date="2026-05-01"),
                           rows=[row], overdue_set=set(), execution_facts_by_op_id={123: SimpleNamespace(
                               actual_status=status, actual_start_time="2026-05-01 08:05:00", actual_end_time=None)}).value[0]
        assert task["progress"] == (100 if status == "completed" else 0)
        assert "execution-" + status in task["custom_class"].split()
    assert row == before
    run_current_js(r"""
const data=h.fixture(),task=data.tasks[0],M=h.runtime.PlanGanttModel;
for(const status of ['completed','processing','blocked',null]) {
 task.meta={status};const before=h.clone(task);
 assert.strictEqual(M.tone(task,new Set(),new Map()),'primary');
 assert.strictEqual(M.tone(task,new Set(),new Map([['B1','unknown']])),'primary');
 assert.strictEqual(M.tone(task,new Set(),new Map([['B1','on_time']])),'success');
 assert.strictEqual(M.tone(task,new Set(),new Map([['B1','overdue']])),'critical');
 assert.strictEqual(M.tone(task,new Set([task.task_ref]),new Map([['B1','on_time']])),'critical');h.equal(task,before);
}
assert(!h.text(h.gantt(data).tree).includes('已完成'));assert.strictEqual(h.runtime.Gantt,undefined);
""")
    print("OK")


def test_regression_gantt_status_mode_semantics() -> None:
    main()


if __name__ == "__main__":
    main()
