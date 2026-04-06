(function () {
  var ns = window.__APS_GANTT__;
  if (!ns) return;
  if (!ns._inited) ns._inited = {};
  if (ns._inited.color) return;
  ns._inited.color = true;

  var norm = ns.norm;
  if (typeof norm !== "function") return;

  function hashToHue(s) {
    const x = norm(s);
    let h = 0;
    for (let i = 0; i < x.length; i++) {
      h = ((h * 31) + x.charCodeAt(i)) >>> 0;
    }
    return h % 360;
  }

  function colorForBatch(batchId) {
    const b = norm(batchId);
    if (!b) return "#94a3b8";
    const hue = hashToHue(b);
    return `hsl(${hue}, 70%, 52%)`;
  }

  function colorForPriority(priority) {
    const p = norm(priority) || "normal";
    if (p === "critical") return "#ef4444";
    if (p === "urgent") return "#f59e0b";
    return "#94a3b8";
  }

  function colorForSource(source) {
    const s = norm(source) || "internal";
    if (s === "external") return "#a855f7";
    return "#0ea5e9";
  }

  function parseLocalDateTime(s) {
    const x = norm(s);
    // 期望格式：YYYY-MM-DD HH:MM[:SS]
    const m = /^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?/.exec(x);
    if (!m) return null;
    const yy = Number(m[1]);
    const mm = Number(m[2]) - 1;
    const dd = Number(m[3]);
    const hh = Number(m[4]);
    const mi = Number(m[5]);
    const ss = Number(m[6] || "0");
    const dt = new Date(yy, mm, dd, hh, mi, ss, 0);
    if (isNaN(dt.getTime())) return null;
    // 严格校验：避免 new Date() 自动进位把非法日期/时间当作有效值
    if (
      dt.getFullYear() !== yy
      || dt.getMonth() !== mm
      || dt.getDate() !== dd
      || dt.getHours() !== hh
      || dt.getMinutes() !== mi
      || dt.getSeconds() !== ss
    ) {
      return null;
    }
    return dt;
  }

  function statusKeyForTask(task) {
    const t = task || {};
    const meta = t.meta || {};
    const raw = norm(meta.status).toLowerCase();
    // 优先后端状态：历史版本/模拟场景更符合业务语义
    if (raw) {
      if (raw === "done" || raw === "finished" || raw === "complete" || raw === "completed" || raw === "closed") return "done";
      if (raw === "in_progress" || raw === "running" || raw === "processing" || raw === "started") return "in_progress";
      if (raw === "blocked" || raw === "failed" || raw === "cancelled" || raw === "skipped") return "blocked";
      if (raw === "pending" || raw === "scheduled" || raw === "queued" || raw === "waiting" || raw === "planned") return "pending";
    }
    // 兜底：仅当后端无明确状态时再按时间推断
    const st = parseLocalDateTime(t.start);
    const et = parseLocalDateTime(t.end);
    const now = Date.now();
    if (st && et) {
      if (et.getTime() <= now) return "done";
      if (st.getTime() <= now && now < et.getTime()) return "in_progress";
    }
    return "pending";
  }

  function colorForStatusKey(key) {
    const s = norm(key) || "pending";
    if (s === "done") return "#22c55e";
    if (s === "in_progress") return "#0ea5e9";
    if (s === "blocked") return "#ef4444";
    return "#94a3b8"; // pending
  }

  function getColor(task, mode) {
    const t = task || {};
    const meta = t.meta || {};
    const m = norm(mode) || "batch";
    if (m === "priority") return colorForPriority(meta.priority);
    if (m === "source") return colorForSource(meta.source);
    if (m === "status") return colorForStatusKey(statusKeyForTask(t));
    return colorForBatch(meta.batch_id);
  }

  ns.hashToHue = hashToHue;
  ns.colorForBatch = colorForBatch;
  ns.colorForPriority = colorForPriority;
  ns.colorForSource = colorForSource;
  ns.parseLocalDateTime = parseLocalDateTime;
  ns.statusKeyForTask = statusKeyForTask;
  ns.colorForStatusKey = colorForStatusKey;
  ns.getColor = getColor;
})();

