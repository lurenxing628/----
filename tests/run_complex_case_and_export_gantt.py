import json
import os
import sys
import tempfile
import textwrap
from typing import Any, Dict, List, Optional


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("repo root not found: expected app.py and schema.sql")


def build_preview_client_bootstrap(
    tasks_expr: str = "tasks",
    calendar_days_expr: str = "calendarDays",
    critical_chain_expr: str = "criticalChain",
    degradation_events_expr: str = '(typeof degradationEvents === "undefined" ? [] : degradationEvents)',
    degradation_counters_expr: str = '(typeof degradationCounters === "undefined" ? {} : degradationCounters)',
    empty_reason_expr: str = '(typeof emptyReason === "undefined" ? "" : emptyReason)',
    overdue_markers_degraded_expr: str = '(typeof overdueMarkersDegraded === "undefined" ? false : overdueMarkersDegraded)',
    overdue_markers_partial_expr: str = '(typeof overdueMarkersPartial === "undefined" ? false : overdueMarkersPartial)',
    overdue_markers_message_expr: str = '(typeof overdueMarkersMessage === "undefined" ? "" : overdueMarkersMessage)',
) -> str:
    return textwrap.dedent(
        f"""
        (function () {{
          const taskList = {tasks_expr};
          const dayList = {calendar_days_expr};
          const chainData = {critical_chain_expr};
          const previewDegradationEvents = {degradation_events_expr};
          const previewDegradationCounters = {degradation_counters_expr};
          const previewEmptyReason = {empty_reason_expr};
          const previewOverdueMarkersDegraded = {overdue_markers_degraded_expr};
          const previewOverdueMarkersPartial = {overdue_markers_partial_expr};
          const previewOverdueMarkersMessage = {overdue_markers_message_expr};
          const previewCalendarPayload = {{
            degradationEvents: previewDegradationEvents,
            degradationCounters: previewDegradationCounters,
            emptyReason: previewEmptyReason
          }};
          const ganttNs = window.__APS_GANTT__ || {{}};
          const outlineApi = ganttNs.outline;
          const contractApi = ganttNs.contract;
          if (!outlineApi || typeof outlineApi.setCriticalOutlineEnabled !== "function" || typeof outlineApi.installCriticalOutlineSyncAdapter !== "function") {{
            throw new Error("APS critical outline helper missing");
          }}
          if (!contractApi || typeof contractApi.normalizeCriticalChain !== "function" || typeof contractApi.buildRenderTasks !== "function") {{
            throw new Error("APS gantt contract helper missing");
          }}

          const critical = contractApi.normalizeCriticalChain(chainData);
          const renderTasks = contractApi.buildRenderTasks(taskList, "critical", critical);

          const gantt = new Gantt("#gantt", renderTasks, {{
            view_mode: "Day",
            language: "zh",
            popup_trigger: "click",
            custom_popup_html(task) {{
              const meta = task && task.meta ? task.meta : {{}};
              const criticalInfo = contractApi.getCriticalTooltip(task, critical);
              function escapeHtml(value) {{
                const text = value === null || typeof value === "undefined" ? "" : String(value);
                if (!/[&<>"']/.test(text)) return text;
                return text
                  .replace(/&/g, "&amp;")
                  .replace(/</g, "&lt;")
                  .replace(/>/g, "&gt;")
                  .replace(/"/g, "&quot;")
                  .replace(/'/g, "&#39;");
              }}

              const lines = [
                `<div class="title">${{escapeHtml(meta._raw_name || task.name || "")}}</div>`,
                `<div class="subtitle">时间：${{escapeHtml(task.start || "-")}} ～ ${{escapeHtml(task.end || "-")}}</div>`,
                `<div class="subtitle">批次：${{escapeHtml(meta.batch_id || "-")}}</div>`,
                `<div class="subtitle">件：${{escapeHtml(meta.piece_id || "-")}}</div>`,
                `<div class="subtitle">图号：${{escapeHtml(meta.part_no || "-")}}</div>`,
                `<div class="subtitle">工序：${{escapeHtml(meta.seq || "-")}}（${{escapeHtml(meta.op_type_name || "-")}}）</div>`,
                `<div class="subtitle">设备：${{escapeHtml(meta.machine || "-")}}</div>`,
                `<div class="subtitle">人员：${{escapeHtml(meta.operator || "-")}}</div>`,
                `<div class="subtitle">来源：${{escapeHtml(meta.source || "-")}}</div>`,
                `<div class="subtitle">关键链：${{escapeHtml(criticalInfo.statusLabel)}}｜超期：${{meta.is_overdue ? "是" : "否"}}</div>`,
                `<div class="subtitle">关键链前驱：${{escapeHtml(criticalInfo.predecessorText)}}｜类型：${{escapeHtml(criticalInfo.edgeTypeText)}}｜间隔(分)：${{escapeHtml(criticalInfo.gapText)}}</div>`,
                `<div class="subtitle">关键链依据：${{escapeHtml(criticalInfo.reasonText)}}</div>`,
              ];
              if (criticalInfo.unavailableMessage) {{
                lines.push(`<div class="subtitle">关键链降级：${{escapeHtml(criticalInfo.unavailableMessage)}}</div>`);
              }}
              return lines.join("");
            }}
          }});
          outlineApi.installCriticalOutlineSyncAdapter(gantt);

          function norm(value) {{
            return value === null || typeof value === "undefined" ? "" : String(value).trim();
          }}

          function hashToHue(value) {{
            const text = norm(value);
            let hue = 0;
            for (let i = 0; i < text.length; i++) {{
              hue = ((hue * 31) + text.charCodeAt(i)) >>> 0;
            }}
            return hue % 360;
          }}

          function colorForBatch(batchId) {{
            const value = norm(batchId);
            if (!value) return "#94a3b8";
            return `hsl(${{hashToHue(value)}}, 70%, 52%)`;
          }}

          function renderHolidayColumns(currentGantt, days) {{
            try {{
              if (!currentGantt || !currentGantt.gantt_start || !currentGantt.options) return;
              const svg = document.querySelector("#gantt svg.gantt");
              if (!svg) return;

              const oldLayer = svg.querySelector("g.aps-holiday-layer");
              if (oldLayer && oldLayer.parentNode) {{
                oldLayer.parentNode.removeChild(oldLayer);
              }}

              const NS = "http://www.w3.org/2000/svg";
              const layer = document.createElementNS(NS, "g");
              layer.setAttribute("class", "aps-holiday-layer");

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

              let height = 0;
              try {{
                const box = svg.getBBox();
                height = box && box.height ? box.height : 0;
              }} catch (_) {{
                height = 0;
              }}
              if (!height) {{
                const attrHeight = Number(svg.getAttribute("height") || 0);
                if (attrHeight) height = attrHeight;
              }}
              if (!height) {{
                const rect = svg.getBoundingClientRect();
                if (rect && rect.height) height = rect.height;
              }}

              const step = Number(currentGantt.options.step) || 24;
              const width = Number(currentGantt.options.column_width) || 38;
              const start = currentGantt.gantt_start;
              (Array.isArray(days) ? days : []).forEach((day) => {{
                const dateStr = norm(day && day.date);
                if (!dateStr) return;
                const isHoliday = day && (
                  day.is_holiday === true
                  || (norm(day.day_type) && norm(day.day_type) !== "workday")
                );
                const isNonworking = day && (
                  day.is_nonworking === true
                  || Number(day.shift_hours || 0) <= 0
                );
                if (!isHoliday && !isNonworking) return;

                const date = new Date(dateStr + " 00:00:00");
                if (isNaN(date.getTime())) return;
                const diffHours = (date.getTime() - start.getTime()) / 3600000.0;
                const x = (diffHours / step) * width;

                const rect = document.createElementNS(NS, "rect");
                rect.setAttribute("x", String(Math.floor(x)));
                rect.setAttribute("y", "0");
                rect.setAttribute("width", String(width));
                rect.setAttribute("height", String(height || 0));
                rect.setAttribute("class", isNonworking ? "aps-holiday-rect aps-nonworking" : "aps-holiday-rect");
                rect.setAttribute("data-date", dateStr);
                layer.appendChild(rect);
              }});
            }} catch (_) {{
              // ignore preview-only decoration failures
            }}
          }}

          function applyDegradationWarning(chain) {{
            const warning = document.getElementById("ganttDegradationWarning");
            if (!warning) return;
            const message = contractApi.buildDegradationMessages({{
              degradationEvents: previewDegradationEvents,
              degradationCounters: previewDegradationCounters,
              emptyReason: previewEmptyReason
            }}, chain).join(" ");
            warning.textContent = message;
            warning.style.display = message ? "block" : "none";
          }}

          function applyOverdueWarning() {{
            const warning = document.getElementById("ganttOverdueWarning");
            if (!warning) return;
            const message = contractApi.getOverdueWarningMessage({{
              overdueMarkersDegraded: previewOverdueMarkersDegraded,
              overdueMarkersPartial: previewOverdueMarkersPartial,
              overdueMarkersMessage: previewOverdueMarkersMessage
            }});
            warning.textContent = message;
            warning.style.display = message ? "block" : "none";
          }}

          function applyDecorations(renderList, chain) {{
            const byId = new Map();
            (Array.isArray(renderList) ? renderList : []).forEach((task) => {{
              const id = norm(task && task.id);
              if (id) byId.set(id, task);
            }});
            const ccSet = chain && chain.idSet ? chain.idSet : new Set();

            document.querySelectorAll("#gantt .bar-wrapper").forEach((wrapper) => {{
              const taskId = norm(wrapper.getAttribute("data-id"));
              const task = byId.get(taskId);
              if (!task) return;
              const meta = task.meta || {{}};
              const isCritical = ccSet.has(taskId);
              wrapper.style.setProperty("--aps-bar-color", colorForBatch(meta.batch_id));
              wrapper.classList.toggle("aps-external", norm(meta.source) === "external");
              wrapper.classList.toggle("aps-critical", isCritical);
              outlineApi.setCriticalOutlineEnabled(wrapper, isCritical);
              wrapper.querySelectorAll(".aps-cc-badge").forEach((node) => {{
                try {{
                  node.remove();
                }} catch (_) {{
                  // ignore
                }}
              }});
            }});

            document.querySelectorAll("#gantt .bar").forEach((rect) => {{
              try {{
                rect.setAttribute("rx", "4");
                rect.setAttribute("ry", "4");
              }} catch (_) {{
                // ignore
              }}
            }});
          }}

          function renderLegend(renderList, days, chain) {{
            const legend = document.getElementById("legend");
            if (!legend) return;
            while (legend.firstChild) {{
              legend.removeChild(legend.firstChild);
            }}

            function row() {{
              const node = document.createElement("div");
              node.className = "aps-legend-row";
              return node;
            }}

            function title(text) {{
              const node = document.createElement("span");
              node.className = "aps-legend-title";
              node.textContent = text;
              return node;
            }}

            function item(label, chip) {{
              const itemNode = document.createElement("span");
              itemNode.className = "aps-legend-item";
              const chipNode = document.createElement("span");
              chipNode.className = "aps-legend-chip";
              if (chip) {{
                if (chip.background) chipNode.style.background = String(chip.background);
                if (chip.borderColor) chipNode.style.borderColor = String(chip.borderColor);
                if (chip.borderWidth) chipNode.style.borderWidth = String(chip.borderWidth) + "px";
                if (chip.borderStyle) chipNode.style.borderStyle = String(chip.borderStyle);
                if (chip.opacity) chipNode.style.opacity = String(chip.opacity);
              }}
              const labelNode = document.createElement("span");
              labelNode.textContent = label;
              itemNode.appendChild(chipNode);
              itemNode.appendChild(labelNode);
              return itemNode;
            }}

            const normalizedChain = contractApi.normalizeCriticalChain(chain);
            const ccCount = normalizedChain && normalizedChain.idSet ? normalizedChain.idSet.size : 0;
            const makespanEnd = norm(chain && chain.makespan_end) || "-";
            const calendarDayList = Array.isArray(days) ? days : [];
            const holidayCount = calendarDayList.filter((day) => day && (day.is_holiday || day.is_nonworking)).length;
            const calendarBackgroundDisabled = calendarDayList.length === 0
              && !contractApi.shouldUseFallbackCalendarDays(previewCalendarPayload);

            const summaryRow = row();
            const summary = document.createElement("span");
            summary.textContent = `任务 ${{(renderList || []).length}} · 关键链 ${{ccCount}} · 完工 ${{makespanEnd}} · 假期/停工 ${{holidayCount}} · 箭头 ${{contractApi.getArrowModeLabel("critical", chain)}} · ${{contractApi.getCriticalStatusLabel(chain)}}`;
            summaryRow.appendChild(summary);
            legend.appendChild(summaryRow);

            const warningText = contractApi.getCriticalChainUnavailableMessage(chain);
            if (warningText) {{
              const warnRow = row();
              const warn = document.createElement("span");
              warn.textContent = warningText;
              warnRow.appendChild(warn);
              legend.appendChild(warnRow);
            }}

            const colorRow = row();
            colorRow.appendChild(title("配色"));
            const seen = new Set();
            (Array.isArray(renderList) ? renderList : []).forEach((task) => {{
              const batchId = norm(task && task.meta && task.meta.batch_id);
              if (!batchId || seen.has(batchId) || seen.size >= 6) return;
              seen.add(batchId);
              colorRow.appendChild(item(batchId, {{ background: colorForBatch(batchId) }}));
            }});
            legend.appendChild(colorRow);

            const markRow = row();
            markRow.appendChild(title("标记"));
            markRow.appendChild(calendarBackgroundDisabled
              ? item("假期/停工(停用)", {{ background: "#ffffff", borderColor: "#94a3b8", borderWidth: 1.5 }})
              : item("假期/停工(背景)", {{ background: "#fee2e2" }}));
            markRow.appendChild(item("超期", {{ background: "#ffffff", borderColor: "#ef4444", borderWidth: 2.5 }}));
            const criticalMarkerDisabled = normalizedChain && normalizedChain.available === false;
            markRow.appendChild(item(
              criticalMarkerDisabled ? "关键链(停用)" : "关键链",
              {{ background: "#ffffff", borderColor: criticalMarkerDisabled ? "#94a3b8" : "#38bdf8", borderWidth: 2.5 }}
            ));
            markRow.appendChild(item("外协", {{ background: "#ffffff", borderColor: "#334155", borderWidth: 1.5, borderStyle: "dashed" }}));
            legend.appendChild(markRow);
          }}

            const originalChangeViewMode = typeof gantt.change_view_mode === "function"
            ? gantt.change_view_mode
            : null;
          if (originalChangeViewMode) {{
            gantt.change_view_mode = function (mode) {{
              const result = originalChangeViewMode.call(this, mode);
              outlineApi.installCriticalOutlineSyncAdapter(this);
              renderHolidayColumns(this, dayList);
              applyDecorations(renderTasks, critical);
              renderLegend(renderTasks, dayList, critical);
              applyDegradationWarning(critical);
              applyOverdueWarning();
              contractApi.renderHelpList(document.getElementById("ganttHelpList"), critical, previewCalendarPayload);
              return result;
            }};
          }}

          renderHolidayColumns(gantt, dayList);
          applyDecorations(renderTasks, critical);
          renderLegend(renderTasks, dayList, critical);
          applyDegradationWarning(critical);
          applyOverdueWarning();
          contractApi.renderHelpList(document.getElementById("ganttHelpList"), critical, previewCalendarPayload);
          window.__APS_GANTT_PREVIEW__ = {{
            gantt: gantt,
            critical: critical,
            renderTasks: renderTasks,
            renderHolidayColumns: renderHolidayColumns,
            applyDecorations: applyDecorations,
            renderLegend: renderLegend
          }};
        }})();
        """
    ).strip()


def _write_html(
    repo_root: str,
    rel_path: str,
    title: str,
    meta: Dict[str, Any],
    tasks: List[Dict[str, Any]],
    calendar_days: Optional[List[Dict[str, Any]]] = None,
    critical_chain: Optional[Dict[str, Any]] = None,
    degradation_events: Optional[List[Dict[str, Any]]] = None,
    degradation_counters: Optional[Dict[str, Any]] = None,
    empty_reason: str = "",
    overdue_markers_degraded: bool = False,
    overdue_markers_partial: bool = False,
    overdue_markers_message: str = "",
) -> str:
    out_path = os.path.join(repo_root, rel_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    meta_json = json.dumps(meta, ensure_ascii=False, indent=2, default=str)
    tasks_json = json.dumps(tasks, ensure_ascii=False, default=str)
    cal_json = json.dumps(calendar_days or [], ensure_ascii=False, default=str)
    cc_json = json.dumps(critical_chain or {}, ensure_ascii=False, default=str)
    degradation_events_json = json.dumps(degradation_events or [], ensure_ascii=False, default=str)
    degradation_counters_json = json.dumps(degradation_counters or {}, ensure_ascii=False, default=str)
    empty_reason_json = json.dumps(empty_reason or "", ensure_ascii=False)
    overdue_markers_message_json = json.dumps(overdue_markers_message or "", ensure_ascii=False)
    overdue_markers_degraded_json = "true" if overdue_markers_degraded else "false"
    overdue_markers_partial_json = "true" if overdue_markers_partial else "false"
    bootstrap_js = build_preview_client_bootstrap(
        "tasks",
        "calendarDays",
        "criticalChain",
        "degradationEvents",
        "degradationCounters",
        "emptyReason",
        "overdueMarkersDegraded",
        "overdueMarkersPartial",
        "overdueMarkersMessage",
    )

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
    <div id="ganttOverdueWarning" class="aps-gantt-help" style="display:none; margin-bottom:10px;"></div>
    <div id="ganttDegradationWarning" class="aps-gantt-help" style="display:none; margin-bottom:10px;"></div>
    <div id="legend" class="aps-gantt-legend"></div>
    <details class="aps-gantt-help" style="margin-top:10px;" open>
      <summary>说明（怎么看）</summary>
      <ul id="ganttHelpList" class="meta" style="color:#64748b; margin:6px 0 0; line-height:1.7;"></ul>
    </details>
    <div id="gantt" style="margin-top:10px;"></div>
  </div>
  <div class="hint">提示：这是“复杂案例”生成的 tasks，样式来自仓库内置 Frappe Gantt 0.6.1 资源。</div>

  <script src="../../static/js/frappe-gantt.min.js"></script>
  <script src="../../static/js/gantt_outline.js"></script>
  <script src="../../static/js/gantt_contract.js"></script>
  <script>
    const tasks = {tasks_json};
    const calendarDays = {cal_json};
    const criticalChain = {cc_json};
    const degradationEvents = {degradation_events_json};
    const degradationCounters = {degradation_counters_json};
    const emptyReason = {empty_reason_json};
    const overdueMarkersDegraded = {overdue_markers_degraded_json};
    const overdueMarkersPartial = {overdue_markers_partial_json};
    const overdueMarkersMessage = {overdue_markers_message_json};
    {bootstrap_js}
  </script>
</body>
</html>
"""
    with open(out_path, "w", encoding="utf-8") as handle:
        handle.write(html)
    return out_path


def main() -> None:
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

    sys.path.insert(0, repo_root)

    from core.infrastructure.database import ensure_schema, get_connection
    from core.infrastructure.logging import OperationLogger
    from core.services.process import ExternalGroupService
    from core.services.scheduler import BatchService, CalendarService, ScheduleService
    from core.services.scheduler.gantt_service import GanttService

    ensure_schema(test_db, logger=None, schema_path=os.path.join(repo_root, "schema.sql"))
    conn = get_connection(test_db)
    op_logger = OperationLogger(conn, logger=None)

    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN_1", "Machining", "internal"))
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_IN_2", "Grinding", "internal"))
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX_1", "Coating", "external"))
    conn.execute("INSERT INTO OpTypes (op_type_id, name, category) VALUES (?, ?, ?)", ("OT_EX_2", "FinalInspect", "external"))

    conn.execute(
        "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
        ("S001", "Vendor-Coating", "OT_EX_1", 1.5, "active"),
    )
    conn.execute(
        "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status) VALUES (?, ?, ?, ?, ?)",
        ("S002", "Vendor-Inspect", "OT_EX_2", 1.0, "active"),
    )

    conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC001", "CNC-01", "OT_IN_1", "active"))
    conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC002", "CNC-02", "OT_IN_1", "active"))
    conn.execute("INSERT INTO Machines (machine_id, name, op_type_id, status) VALUES (?, ?, ?, ?)", ("MC003", "GRD-01", "OT_IN_2", "active"))

    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP001", "Alice", "active"))
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP002", "Bob", "active"))
    conn.execute("INSERT INTO Operators (operator_id, name, status) VALUES (?, ?, ?)", ("OP003", "Carol", "active"))

    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC001"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP001", "MC002"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP002", "MC002"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP002", "MC003"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP003", "MC001"))
    conn.execute("INSERT INTO OperatorMachine (operator_id, machine_id) VALUES (?, ?)", ("OP003", "MC003"))

    conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_A", "ComplexPartA", "yes"))
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 5, "OT_IN_1", "Machining", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 10, "OT_IN_2", "Grinding", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 20, "OT_IN_1", "Machining", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 35, "OT_EX_1", "Coating", "external", "S001", None, "P_A_G1", 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_A", 40, "OT_EX_2", "FinalInspect", "external", "S002", None, "P_A_G1", 0.0, 0.0, "active"),
    )
    conn.execute(
        "INSERT INTO ExternalGroups (group_id, part_no, start_seq, end_seq, merge_mode, total_days, supplier_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("P_A_G1", "P_A", 35, 40, "separate", None, "S001"),
    )

    conn.execute("INSERT INTO Parts (part_no, part_name, route_parsed) VALUES (?, ?, ?)", ("P_B", "ComplexPartB", "yes"))
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_B", 5, "OT_IN_2", "Grinding", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P_B", 10, "OT_IN_1", "Machining", "internal", None, None, None, 0.0, 0.0, "active"),
    )
    conn.commit()

    eg_svc = ExternalGroupService(conn, op_logger=op_logger)
    eg_svc.set_merge_mode(group_id="P_A_G1", merge_mode="merged", total_days=3.0)
    conn.commit()

    cal = CalendarService(conn, logger=None, op_logger=op_logger)
    cal.upsert("2026-01-26", day_type="workday", shift_hours=8, efficiency=1.0, allow_normal="yes", allow_urgent="yes", remark="normal")
    cal.upsert("2026-01-27", day_type="workday", shift_hours=2, efficiency=1.0, allow_normal="yes", allow_urgent="yes", remark="short shift")
    cal.upsert("2026-01-28", day_type="holiday", shift_hours=0, efficiency=1.0, allow_normal="no", allow_urgent="no", remark="shutdown")
    conn.commit()

    batch_svc = BatchService(conn, logger=None, op_logger=op_logger)
    batches = [
        ("B001", "P_A", 4, "2026-01-27", "critical", "yes", "Complex A critical"),
        ("B002", "P_A", 2, "2026-01-29", "urgent", "yes", "Complex A urgent"),
        ("B003", "P_A", 1, "2026-02-05", "normal", "yes", "Complex A normal"),
        ("B101", "P_B", 6, "2026-01-27", "urgent", "yes", "Complex B urgent"),
        ("B102", "P_B", 3, "2026-01-30", "normal", "yes", "Complex B normal"),
    ]
    for batch_id, part_no, quantity, due_date, priority, ready_status, remark in batches:
        batch_svc.create_batch_from_template(
            batch_id=batch_id,
            part_no=part_no,
            quantity=quantity,
            due_date=due_date,
            priority=priority,
            ready_status=ready_status,
            remark=remark,
            rebuild_ops=True,
        )

    sch_svc = ScheduleService(conn, logger=None, op_logger=op_logger)

    def assign_internal(op, batch_id: str) -> None:
        name = (op.op_type_name or "").strip()
        seq = int(op.seq or 0)
        if name == "Machining":
            machine = "MC001" if (seq % 2 == 1) else "MC002"
            operator = "OP001"
        else:
            machine = "MC003"
            operator = "OP002" if batch_id in ("B101", "B102") else "OP003"

        setup = 0.5
        if name == "Machining":
            unit = 1.2 if batch_id in ("B001", "B101") else 0.8
        else:
            unit = 0.6 if batch_id in ("B101", "B102") else 0.4

        sch_svc.update_internal_operation(
            op.id,
            machine_id=machine,
            operator_id=operator,
            setup_hours=setup,
            unit_hours=unit,
        )

    def assign_external(op) -> None:
        supplier_id = op.supplier_id or ("S001" if int(op.seq or 0) == 35 else "S002")
        sch_svc.update_external_operation(op.id, supplier_id=supplier_id, ext_days=None)

    for batch_id, *_rest in batches:
        for op in batch_svc.list_operations(batch_id):
            if (op.source or "").strip() == "internal":
                assign_internal(op, batch_id=batch_id)
            else:
                assign_external(op)

    result = sch_svc.run_schedule(
        batch_ids=[batch_id for batch_id, *_rest in batches],
        start_dt="2026-01-26 08:00:00",
        created_by="complex_demo",
    )
    version = int(result.get("version") or 1)

    min_start = conn.execute("SELECT MIN(start_time) AS st FROM Schedule WHERE version=?", (version,)).fetchone()["st"]
    week_start = str(min_start)[:10] if min_start else "2026-01-26"

    gantt_svc = GanttService(conn, logger=None, op_logger=op_logger)
    data_machine = gantt_svc.get_gantt_tasks(view="machine", week_start=week_start, offset_weeks=0, version=version)
    data_operator = gantt_svc.get_gantt_tasks(view="operator", week_start=week_start, offset_weeks=0, version=version)

    tasks_machine = data_machine.get("tasks") or []
    tasks_operator = data_operator.get("tasks") or []
    if not tasks_machine:
        raise RuntimeError("complex machine gantt tasks unexpectedly empty")
    if not tasks_operator:
        raise RuntimeError("complex operator gantt tasks unexpectedly empty")

    out_dir = os.path.join(repo_root, "evidence", "FullE2E")
    os.makedirs(out_dir, exist_ok=True)

    machine_tasks_path = os.path.join(out_dir, "gantt_tasks_complex_machine.json")
    with open(machine_tasks_path, "w", encoding="utf-8") as handle:
        json.dump(
            {"meta": {"version": version, "week_start": week_start, "view": "machine"}, "tasks": tasks_machine},
            handle,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    operator_tasks_path = os.path.join(out_dir, "gantt_tasks_complex_operator.json")
    with open(operator_tasks_path, "w", encoding="utf-8") as handle:
        json.dump(
            {"meta": {"version": version, "week_start": week_start, "view": "operator"}, "tasks": tasks_operator},
            handle,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    meta = {
        "tmpdir": tmpdir,
        "db": test_db,
        "version": version,
        "week_start": week_start,
        "batch_ids": [batch_id for batch_id, *_rest in batches],
        "tasks_machine": len(tasks_machine),
        "tasks_operator": len(tasks_operator),
        "note": "contains resource conflicts, external merged span, short shift, holiday, and mixed priorities",
    }

    machine_html = _write_html(
        repo_root,
        "evidence/FullE2E/gantt_preview_complex_machine.html",
        "甘特图预览（复杂案例 / 设备视图）",
        meta,
        tasks_machine,
        calendar_days=(data_machine.get("calendar_days") or []),
        critical_chain=(data_machine.get("critical_chain") or {}),
        degradation_events=(data_machine.get("degradation_events") or []),
        degradation_counters=(data_machine.get("degradation_counters") or {}),
        empty_reason=str(data_machine.get("empty_reason") or ""),
        overdue_markers_degraded=bool(data_machine.get("overdue_markers_degraded")),
        overdue_markers_partial=bool(data_machine.get("overdue_markers_partial")),
        overdue_markers_message=str(data_machine.get("overdue_markers_message") or ""),
    )
    operator_html = _write_html(
        repo_root,
        "evidence/FullE2E/gantt_preview_complex_operator.html",
        "甘特图预览（复杂案例 / 人员视图）",
        meta,
        tasks_operator,
        calendar_days=(data_operator.get("calendar_days") or []),
        critical_chain=(data_operator.get("critical_chain") or {}),
        degradation_events=(data_operator.get("degradation_events") or []),
        degradation_counters=(data_operator.get("degradation_counters") or {}),
        empty_reason=str(data_operator.get("empty_reason") or ""),
        overdue_markers_degraded=bool(data_operator.get("overdue_markers_degraded")),
        overdue_markers_partial=bool(data_operator.get("overdue_markers_partial")),
        overdue_markers_message=str(data_operator.get("overdue_markers_message") or ""),
    )

    print("OK")
    print(f"machine_html={machine_html}")
    print(f"operator_html={operator_html}")
    print(f"machine_tasks={machine_tasks_path}")
    print(f"operator_tasks={operator_tasks_path}")


if __name__ == "__main__":
    main()
