import json
import os
import tempfile
from datetime import date


def find_repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _write_html(
    repo_root: str,
    rel_path: str,
    title: str,
    meta: dict,
    tasks: list,
    calendar_days: list = None,
    critical_chain: dict = None,
):
    out_path = os.path.join(repo_root, rel_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # 该 HTML 设计为“直接双击打开（file://）”即可看到图。
    # 相对路径：evidence/FullE2E/ -> ../../static/...
    meta_json = json.dumps(meta, ensure_ascii=False, indent=2, default=str)
    tasks_json = json.dumps(tasks, ensure_ascii=False, default=str)
    cal_json = json.dumps(calendar_days or [], ensure_ascii=False, default=str)
    cc_json = json.dumps(critical_chain or {}, ensure_ascii=False, default=str)

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{title}</title>
  <link rel="stylesheet" href="../../static/css/frappe-gantt.css"/>
  <link rel="stylesheet" href="../../static/css/aps_gantt.css"/>
  <style>
    body {{ font-family: -apple-system, Segoe UI, Arial, "Microsoft YaHei", sans-serif; margin: 16px; }}
    .meta {{ color: #666; margin: 8px 0 16px; white-space: pre-wrap; }}
    .wrap {{ border: 1px solid #e5e5e5; border-radius: 8px; padding: 12px; }}
    #gantt {{ overflow-x: auto; }}
    .hint {{ color: #999; font-size: 12px; margin-top: 8px; }}
  </style>
</head>
<body>
  <h2>{title}</h2>
  <div class="meta"><b>meta</b>\n{meta_json}</div>
  <div class="wrap">
    <div id="legend" class="aps-gantt-legend"></div>
    <details class="aps-gantt-help" style="margin-top:10px;" open>
      <summary>说明（怎么看）</summary>
      <div class="meta" style="color:#64748b; margin:6px 0 0; line-height:1.7;">
        - 颜色：默认按批次（同批次同色）\n
        - 红边：该批次在该版本中被判定为“超期”\n
        - 关键链：任务条外框高亮（影响全局完工时间）\n
        - 虚线边框：外协任务\n
        - 淡红背景：假期/停工（来自工作日历；未配置则周末默认假期；周末可配置为 workday 作为补班）\n
        - 箭头：工艺依赖（后一工序依赖前一工序）\n
      </div>
    </details>
    <div id="gantt" style="margin-top:10px;"></div>
  </div>
  <div class="hint">提示：这是“复杂案例”生成的 tasks，样式来自仓库内置 Frappe Gantt 0.6.1 资源。</div>

  <script src="../../static/js/frappe-gantt.min.js"></script>
  <script>
    const tasks = {tasks_json};
    const calendarDays = {cal_json};
    const criticalChain = {cc_json};
    const gantt = new Gantt("#gantt", tasks, {{
      view_mode: "Day",
      language: "zh",
      popup_trigger: "click"
    }});

    function norm(v) {{
      return (v === null || typeof v === "undefined") ? "" : String(v).trim();
    }}

    // 按批次稳定配色（同批次同色）
    function hashToHue(s) {{
      const x = norm(s);
      let h = 0;
      for (let i = 0; i < x.length; i++) {{
        h = ((h * 31) + x.charCodeAt(i)) >>> 0;
      }}
      return h % 360;
    }}
    function colorForBatch(batchId) {{
      const b = norm(batchId);
      if (!b) return "#94a3b8";
      const hue = hashToHue(b);
      return `hsl(${{hue}}, 70%, 52%)`;
    }}

    function renderHolidayColumns(gantt, calendarDays) {{
      try {{
        if (!gantt || !gantt.gantt_start || !gantt.options) return;
        const svg = document.querySelector("#gantt svg.gantt");
        if (!svg) return;

        // remove existing
        const old = svg.querySelector("g.aps-holiday-layer");
        if (old && old.parentNode) old.parentNode.removeChild(old);

        const NS = "http://www.w3.org/2000/svg";
        const layer = document.createElementNS(NS, "g");
        layer.setAttribute("class", "aps-holiday-layer");

        // prefer mount inside grid layer
        let mounted = false;
        const gridRow = svg.querySelector(".grid-row");
        if (gridRow) {{
          let gridTop = gridRow;
          while (gridTop && gridTop.parentNode && gridTop.parentNode.tagName) {{
            const tag = String(gridTop.parentNode.tagName || "").toLowerCase();
            if (tag === "svg") break;
            gridTop = gridTop.parentNode;
          }}
          if (gridTop && gridTop !== svg && gridTop.parentNode === svg) {{
            gridTop.appendChild(layer);
            mounted = true;
          }}
        }}
        if (!mounted) svg.appendChild(layer);

        // height in SVG units
        let height = 0;
        try {{
          const bb = svg.getBBox();
          height = bb && bb.height ? bb.height : 0;
        }} catch (_) {{}}
        if (!height) {{
          const hAttr = Number(svg.getAttribute("height") || 0);
          if (hAttr) height = hAttr;
        }}
        if (!height) {{
          const r = svg.getBoundingClientRect();
          if (r && r.height) height = r.height;
        }}

        const step = Number(gantt.options.step) || 24;
        const col = Number(gantt.options.column_width) || 38;
        const start = gantt.gantt_start;

        (Array.isArray(calendarDays) ? calendarDays : []).forEach((d) => {{
          const dateStr = String((d && d.date) || "").trim();
          if (!dateStr) return;
          const isHoliday = d && (d.is_holiday === true || (String(d.day_type || "").trim() && String(d.day_type || "").trim() !== "workday"));
          const isNonworking = d && (d.is_nonworking === true || Number(d.shift_hours || 0) <= 0);
          if (!isHoliday && !isNonworking) return;

          const dt = new Date(dateStr + " 00:00:00");
          if (isNaN(dt.getTime())) return;
          const diffHours = (dt.getTime() - start.getTime()) / 3600000.0;
          const x = (diffHours / step) * col;

          const rect = document.createElementNS(NS, "rect");
          rect.setAttribute("x", String(Math.floor(x)));
          rect.setAttribute("y", "0");
          rect.setAttribute("width", String(col));
          rect.setAttribute("height", String(height || 0));
          rect.setAttribute("class", isNonworking ? "aps-holiday-rect aps-nonworking" : "aps-holiday-rect");
          rect.setAttribute("data-date", dateStr);
          layer.appendChild(rect);
        }});
      }} catch (e) {{
        // ignore
      }}
    }}

    function applyDecorations(tasks, criticalChain) {{
      const byId = new Map();
      (Array.isArray(tasks) ? tasks : []).forEach((t) => {{
        const id = norm(t && t.id);
        if (id) byId.set(id, t);
      }});
      const ccSet = new Set(((criticalChain && criticalChain.ids) || []).map((x) => norm(x)).filter((x) => !!x));

      function upsertCriticalOutlines(wrapper, enabled) {{
        if (!wrapper) return;
        try {{
          wrapper.querySelectorAll(".aps-cc-outline-outer, .aps-cc-outline-inner").forEach((n) => {{
            try {{ n.remove(); }} catch (_) {{}}
          }});
        }} catch (_) {{}}
        if (!enabled) return;
        const bar = wrapper.querySelector(".bar");
        if (!bar) return;
        const x = Number(bar.getAttribute("x") || 0);
        const y = Number(bar.getAttribute("y") || 0);
        const w = Number(bar.getAttribute("width") || 0);
        const h = Number(bar.getAttribute("height") || 0);
        if (!(w > 0 && h > 0)) return;

        let rx0 = Number(bar.getAttribute("rx") || 4);
        let ry0 = Number(bar.getAttribute("ry") || rx0);
        if (!(rx0 >= 0)) rx0 = 4;
        if (!(ry0 >= 0)) ry0 = rx0;
        try {{ bar.setAttribute("rx", String(rx0)); bar.setAttribute("ry", String(ry0)); }} catch (_) {{}}

        const outerPad = 2;
        const innerPad = 1;
        const NS = "http://www.w3.org/2000/svg";

        const outer = document.createElementNS(NS, "rect");
        outer.setAttribute("class", "aps-cc-outline-outer");
        outer.setAttribute("x", String(x - outerPad));
        outer.setAttribute("y", String(y - outerPad));
        outer.setAttribute("width", String(w + outerPad * 2));
        outer.setAttribute("height", String(h + outerPad * 2));
        outer.setAttribute("rx", String(rx0 + outerPad));
        outer.setAttribute("ry", String(ry0 + outerPad));
        outer.setAttribute("vector-effect", "non-scaling-stroke");
        outer.setAttribute("pointer-events", "none");

        const inner = document.createElementNS(NS, "rect");
        inner.setAttribute("class", "aps-cc-outline-inner");
        inner.setAttribute("x", String(x - innerPad));
        inner.setAttribute("y", String(y - innerPad));
        inner.setAttribute("width", String(w + innerPad * 2));
        inner.setAttribute("height", String(h + innerPad * 2));
        inner.setAttribute("rx", String(rx0 + innerPad));
        inner.setAttribute("ry", String(ry0 + innerPad));
        inner.setAttribute("vector-effect", "non-scaling-stroke");
        inner.setAttribute("pointer-events", "none");

        try {{
          // 注意：Frappe Gantt 里 bar 往往不在 wrapper 的直接子级（可能在内部 g 分组里）。
          // 因此必须对 bar 的真实父节点执行 insertBefore，否则会触发 NotFoundError。
          const parent = (bar && bar.parentNode) ? bar.parentNode : wrapper;
          parent.insertBefore(outer, bar);
          parent.insertBefore(inner, bar);
        }} catch (_) {{
          // 兜底：尽量插入（即使顺序不完美也要可见）
          try {{
            const parent = (bar && bar.parentNode) ? bar.parentNode : wrapper;
            parent.appendChild(outer);
            parent.appendChild(inner);
          }} catch (_) {{}}
        }}
      }}

      function upsertCriticalBadge(wrapper, enabled) {{
        if (!wrapper) return;
        try {{
          wrapper.querySelectorAll(".aps-cc-badge").forEach((n) => {{
            try {{ n.remove(); }} catch (_) {{}}
          }});
        }} catch (_) {{}}
        // CC 徽标已弃用：不再插入，仅做清理防止旧 DOM 残留
        return;
      }}

      document.querySelectorAll("#gantt .bar-wrapper").forEach((w) => {{
        const tid = norm(w.getAttribute("data-id"));
        const t = byId.get(tid);
        if (!t) return;
        const meta = (t && t.meta) ? t.meta : {{}};
        const bid = norm(meta.batch_id);
        w.style.setProperty("--aps-bar-color", colorForBatch(bid));
        if (norm(meta.source) === "external") w.classList.add("aps-external");
        if (ccSet.has(tid)) w.classList.add("aps-critical");
        upsertCriticalOutlines(w, ccSet.has(tid));
        // CC 徽标已弃用：这里仅做清理
        upsertCriticalBadge(w, false);
      }});

      // 圆角（SVG rect）
      document.querySelectorAll("#gantt .bar").forEach((rect) => {{
        try {{
          rect.setAttribute("rx", "4");
          rect.setAttribute("ry", "4");
        }} catch (_) {{}}
      }});
    }}

    function renderLegend(tasks, calendarDays, criticalChain) {{
      const el = document.getElementById("legend");
      if (!el) return;
      while (el.firstChild) el.removeChild(el.firstChild);

      function row() {{
        const d = document.createElement("div");
        d.className = "aps-legend-row";
        return d;
      }}
      function title(text) {{
        const s = document.createElement("span");
        s.className = "aps-legend-title";
        s.textContent = text;
        return s;
      }}
      function item(label, chip) {{
        const it = document.createElement("span");
        it.className = "aps-legend-item";
        const c = document.createElement("span");
        c.className = "aps-legend-chip";
        if (chip) {{
          if (chip.background) c.style.background = String(chip.background);
          if (chip.borderColor) c.style.borderColor = String(chip.borderColor);
          if (chip.borderWidth) c.style.borderWidth = String(chip.borderWidth) + "px";
          if (chip.borderStyle) c.style.borderStyle = String(chip.borderStyle);
          if (chip.opacity) c.style.opacity = String(chip.opacity);
        }}
        const tx = document.createElement("span");
        tx.textContent = label;
        it.appendChild(c);
        it.appendChild(tx);
        return it;
      }}

      const ccCount = ((criticalChain && criticalChain.ids) || []).length;
      const makespanEnd = norm(criticalChain && criticalChain.makespan_end) || "-";
      const holidayCount = (Array.isArray(calendarDays) ? calendarDays : []).filter((d) => d && (d.is_holiday || d.is_nonworking)).length;

      const r1 = row();
      const summary = document.createElement("span");
      summary.textContent = `颜色：按批次｜任务：${{(tasks||[]).length}}｜关键链：${{ccCount}}｜完工：${{makespanEnd}}｜假期/停工：${{holidayCount}} 天`;
      r1.appendChild(summary);
      el.appendChild(r1);

      const r2 = row();
      r2.appendChild(title("配色（示例）"));
      const seen = new Set();
      const samples = [];
      (Array.isArray(tasks) ? tasks : []).forEach((t) => {{
        const meta = (t && t.meta) ? t.meta : {{}};
        const bid = norm(meta.batch_id);
        if (!bid || seen.has(bid)) return;
        seen.add(bid);
        samples.push(bid);
      }});
      samples.slice(0, 6).forEach((bid) => {{
        r2.appendChild(item(bid, {{ background: colorForBatch(bid) }}));
      }});
      if (samples.length > 6) {{
        r2.appendChild(item(`…共${{samples.length}}个批次`, {{ background: "#94a3b8" }}));
      }}
      el.appendChild(r2);

      const r3 = row();
      r3.appendChild(title("标记"));
      r3.appendChild(item("假期/停工(背景)", {{ background: "#fee2e2" }}));
      r3.appendChild(item("超期(红边)", {{ background: "#ffffff", borderColor: "#ef4444", borderWidth: 2.5 }}));
      r3.appendChild(item("关键链(外框)", {{ background: "#ffffff", borderColor: "#38bdf8", borderWidth: 2.5 }}));
      r3.appendChild(item("外协(虚线)", {{ background: "#ffffff", borderColor: "#334155", borderWidth: 1.5, borderStyle: "dashed" }}));
      r3.appendChild(item("箭头=工艺依赖", {{ background: "#94a3b8" }}));
      el.appendChild(r3);
    }}

    renderHolidayColumns(gantt, calendarDays);
    applyDecorations(tasks, criticalChain);
    renderLegend(tasks, calendarDays, criticalChain);
  </script>
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def main():
    repo_root = find_repo_root()
    tmpdir = tempfile.mkdtemp(prefix="aps_gantt_complex_")
    test_db = os.path.join(tmpdir, "aps_complex.db")
    test_logs = os.path.join(tmpdir, "logs")
    test_backups = os.path.join(tmpdir, "backups")
    test_templates = os.path.join(tmpdir, "templates_excel")
    os.makedirs(test_logs, exist_ok=True)
    os.makedirs(test_backups, exist_ok=True)
    os.makedirs(test_templates, exist_ok=True)

    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = test_db
    os.environ["APS_LOG_DIR"] = test_logs
    os.environ["APS_BACKUP_DIR"] = test_backups
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = test_templates

    os.sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.logging import OperationLogger
    from core.services.process import ExternalGroupService
    from core.services.scheduler import BatchService, CalendarService, ScheduleService
    from core.services.scheduler.gantt_service import GanttService

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)
    op_logger = OperationLogger(conn, logger=None)

    # -------------------------
    # 1) 基础数据：工种/供应商/人员/设备/人机
    # -------------------------
    # 工种
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN_1", "数铣", "internal"))
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN_2", "钳", "internal"))
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX_1", "标印", "external"))
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX_2", "总检", "external"))

    # 供应商（外协）
    conn.execute(
        "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
        ("S001", "外协-标印厂", "OT_EX_1", 1.5, "active"),
    )
    conn.execute(
        "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
        ("S002", "外协-总检厂", "OT_EX_2", 1.0, "active"),
    )

    # 设备
    conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC001", "CNC-01", "OT_IN_1", "active"))
    conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC002", "CNC-02", "OT_IN_1", "active"))
    conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC003", "钳工台", "OT_IN_2", "active"))

    # 人员
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "张三", "active"))
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP002", "李四", "active"))
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP003", "王五", "active"))

    # 人机关联（制造冲突与错开）
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC001"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC002"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP002", "MC002"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP002", "MC003"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP003", "MC001"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP003", "MC003"))

    # -------------------------
    # 2) 工艺模板（Parts + PartOperations + ExternalGroups）
    # -------------------------
    # P_A：内部 3 道 + 外协连续组 [35-40]
    conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_A", "复杂件A", "yes"))
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 5, "OT_IN_1", "数铣", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 10, "OT_IN_2", "钳", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 20, "OT_IN_1", "数铣", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 35, "OT_EX_1", "标印", "external", "S001", None, "P_A_G1", 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 40, "OT_EX_2", "总检", "external", "S002", None, "P_A_G1", 0.0, 0.0, "active"),
    )
    conn.execute(
        "INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("P_A_G1", "P_A", 35, 40, "separate", None, "S001"),
    )

    # P_B：纯内部两道
    conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_B", "复杂件B", "yes"))
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_B", 5, "OT_IN_2", "钳", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_B", 10, "OT_IN_1", "数铣", "internal", None, None, None, 0.0, 0.0, "active"),
    )

    conn.commit()

    # 将 P_A 的外协连续组改为 merged（整组 3.0 天）
    eg_svc = ExternalGroupService(conn, op_logger=op_logger)
    eg_svc.set_merge_mode(group_id="P_A_G1", merge_mode="merged", total_days=3.0)
    conn.commit()

    # -------------------------
    # 3) 日历（制造跨天/停工效果）
    # -------------------------
    cal = CalendarService(conn, logger=None, op_logger=op_logger)
    # 固定从 2026-01-26（周一）开始，周二短班，周三停工
    cal.upsert("2026-01-26", day_type="workday", shift_hours=8, efficiency=1.0, allow_normal="yes", allow_urgent="yes", remark="正常")
    cal.upsert("2026-01-27", day_type="workday", shift_hours=2, efficiency=1.0, allow_normal="yes", allow_urgent="yes", remark="短班次")
    cal.upsert("2026-01-28", day_type="holiday", shift_hours=0, efficiency=1.0, allow_normal="no", allow_urgent="no", remark="停工")
    conn.commit()

    # -------------------------
    # 4) 创建批次（多批次，制造资源冲突）
    # -------------------------
    batch_svc = BatchService(conn, logger=None, op_logger=op_logger)
    batches = [
        # P_A：含外协 merged 组（会拉长完工）
        ("B001", "P_A", 4, "2026-01-27", "critical", "yes", "复杂A-特急"),
        ("B002", "P_A", 2, "2026-01-29", "urgent", "yes", "复杂A-急件"),
        ("B003", "P_A", 1, "2026-02-05", "normal", "yes", "复杂A-普通"),
        # P_B：纯内部，用于和 P_A 抢资源
        ("B101", "P_B", 6, "2026-01-27", "urgent", "yes", "复杂B-急件"),
        ("B102", "P_B", 3, "2026-01-30", "normal", "yes", "复杂B-普通"),
    ]
    for bid, pn, qty, due, prio, ready, remark in batches:
        batch_svc.create_batch_from_template(
            batch_id=bid,
            part_no=pn,
            quantity=qty,
            due_date=due,
            priority=prio,
            ready_status=ready,
            remark=remark,
            rebuild_ops=True,
        )

    # -------------------------
    # 5) 补齐批次工序：分配设备/人员 + 工时（确保甘特可见且足够复杂）
    # -------------------------
    sch_svc = ScheduleService(conn, logger=None, op_logger=op_logger)

    def assign_internal(op, batch_id: str):
        # 基于工种名决定资源池
        name = (op.op_type_name or "").strip()
        seq = int(op.seq or 0)
        # 数铣 -> MC001/MC002；钳 -> MC003
        if name == "数铣":
            machine = "MC001" if (seq % 2 == 1) else "MC002"
            operator = "OP001" if machine in ("MC001", "MC002") else "OP003"
            # 制造冲突：让部分数铣统一用 OP001
            if batch_id in ("B001", "B002", "B101"):
                operator = "OP001"
        else:
            machine = "MC003"
            operator = "OP002" if batch_id in ("B101", "B102") else "OP003"

        # 工时策略（让时间跨天）
        # setup 固定 0.5h，unit 根据工序类型与序号给不同强度
        setup = 0.5
        if name == "数铣":
            unit = 1.2 if batch_id in ("B001", "B101") else 0.8
        else:
            unit = 0.6 if batch_id in ("B101", "B102") else 0.4

        sch_svc.update_internal_operation(op.id, machine_id=machine, operator_id=operator, setup_hours=setup, unit_hours=unit)

    def assign_external(op):
        # merged 外协组：不传 ext_days（会被服务层设置为 None）
        # 但 supplier_id 可以设置/回显
        sup = op.supplier_id or ("S001" if int(op.seq or 0) == 35 else "S002")
        sch_svc.update_external_operation(op.id, supplier_id=sup, ext_days=None)

    for bid, *_ in batches:
        ops = batch_svc.list_operations(bid)
        for op in ops:
            if (op.source or "").strip() == "internal":
                assign_internal(op, batch_id=bid)
            else:
                assign_external(op)

    # -------------------------
    # 6) 执行排产（固定起点，便于展示）
    # -------------------------
    result = sch_svc.run_schedule(batch_ids=[x[0] for x in batches], start_dt="2026-01-26 08:00:00", created_by="complex_demo")
    version = int(result.get("version") or 1)

    # 以排程起点所在周作为 week_start（保证甘特命中）
    min_start = conn.execute("SELECT MIN(start_time) AS st FROM Schedule WHERE version=?", (version,)).fetchone()["st"]
    week_start = str(min_start)[:10] if min_start else "2026-01-26"

    gantt_svc = GanttService(conn, logger=None, op_logger=op_logger)
    data_machine = gantt_svc.get_gantt_tasks(view="machine", week_start=week_start, offset_weeks=0, version=version)
    data_operator = gantt_svc.get_gantt_tasks(view="operator", week_start=week_start, offset_weeks=0, version=version)

    tasks_machine = data_machine.get("tasks") or []
    tasks_operator = data_operator.get("tasks") or []
    if not tasks_machine:
        raise RuntimeError("复杂案例 machine tasks 为空（不符合预期）")
    if not tasks_operator:
        raise RuntimeError("复杂案例 operator tasks 为空（不符合预期）")

    out_dir = os.path.join(repo_root, "evidence", "FullE2E")
    os.makedirs(out_dir, exist_ok=True)

    tasks_machine_path = os.path.join(out_dir, "gantt_tasks_complex_machine.json")
    with open(tasks_machine_path, "w", encoding="utf-8") as f:
        json.dump(
            {"meta": {"version": version, "week_start": week_start, "view": "machine"}, "tasks": tasks_machine},
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    tasks_operator_path = os.path.join(out_dir, "gantt_tasks_complex_operator.json")
    with open(tasks_operator_path, "w", encoding="utf-8") as f:
        json.dump(
            {"meta": {"version": version, "week_start": week_start, "view": "operator"}, "tasks": tasks_operator},
            f,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    meta = {
        "tmpdir": tmpdir,
        "db": test_db,
        "version": version,
        "week_start": week_start,
        "batch_ids": [x[0] for x in batches],
        "tasks_machine": len(tasks_machine),
        "tasks_operator": len(tasks_operator),
        "note": "包含资源冲突、人机约束、外协 merged 周期、日历短班/停工、不同优先级/交期（含超期标记）",
    }

    html_machine = _write_html(
        repo_root,
        "evidence/FullE2E/gantt_preview_complex_machine.html",
        "甘特图预览（复杂案例 / 设备视图）",
        meta,
        tasks_machine,
        calendar_days=(data_machine.get("calendar_days") or []),
        critical_chain=(data_machine.get("critical_chain") or {}),
    )
    html_operator = _write_html(
        repo_root,
        "evidence/FullE2E/gantt_preview_complex_operator.html",
        "甘特图预览（复杂案例 / 人员视图）",
        meta,
        tasks_operator,
        calendar_days=(data_operator.get("calendar_days") or []),
        critical_chain=(data_operator.get("critical_chain") or {}),
    )

    print("OK")
    print(f"machine_html={html_machine}")
    print(f"operator_html={html_operator}")
    print(f"machine_tasks={tasks_machine_path}")
    print(f"operator_tasks={tasks_operator_path}")


if __name__ == "__main__":
    main()

