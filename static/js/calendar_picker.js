(() => {
  const cfg = window.__APS_WORKCALENDAR__ || {};
  const rows = Array.isArray(cfg.rows) ? cfg.rows : [];
  const holidayDefaultEfficiencyRaw = cfg.holidayDefaultEfficiency;
  const holidayDefaultEfficiency =
    Number.isFinite(Number(holidayDefaultEfficiencyRaw)) && Number(holidayDefaultEfficiencyRaw) > 0
      ? Number(holidayDefaultEfficiencyRaw)
      : 0.8;

  /** @type {Map<string, any>} */
  const rowMap = new Map();
  for (const r of rows) {
    if (r && typeof r.date === "string" && r.date.trim()) {
      rowMap.set(r.date.trim(), r);
    }
  }

  const elDate = document.querySelector('input[name="date"]');
  const elType = document.querySelector('select[name="day_type"]');
  const elShiftStart = document.querySelector('input[name="shift_start"]');
  const elShiftEnd = document.querySelector('input[name="shift_end"]');
  const elShiftHours = document.querySelector('input[name="shift_hours"]');
  const elEff = document.querySelector('input[name="efficiency"]');
  const elAllowNormal = document.querySelector('select[name="allow_normal"]');
  const elAllowUrgent = document.querySelector('select[name="allow_urgent"]');
  const elRemark = document.querySelector('input[name="remark"]');

  const btnOpen = document.getElementById("wcDatePickBtn");
  const panel = document.getElementById("wcCalendarPanel");
  const titleEl = panel ? panel.querySelector(".wc-cal-title") : null;
  const gridEl = panel ? panel.querySelector(".wc-cal-grid") : null;
  const btnPrev = panel ? panel.querySelector('[data-action="prev"]') : null;
  const btnNext = panel ? panel.querySelector('[data-action="next"]') : null;
  const hintEl = document.getElementById("wcDateHint");

  if (!elDate || !btnOpen || !panel || !titleEl || !gridEl) return;

  const weekNames = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  const weekLabels = ["一", "二", "三", "四", "五", "六", "日"];

  function pad2(n) {
    return String(n).padStart(2, "0");
  }

  function fmtISO(d) {
    const y = d.getFullYear();
    const m = pad2(d.getMonth() + 1);
    const dd = pad2(d.getDate());
    return `${y}-${m}-${dd}`;
  }

  function parseISO(s) {
    if (!s || typeof s !== "string") return null;
    const m = s.trim().match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (!m) return null;
    const y = Number(m[1]);
    const mo = Number(m[2]);
    const d = Number(m[3]);
    if (!Number.isFinite(y) || !Number.isFinite(mo) || !Number.isFinite(d)) return null;
    const dt = new Date(y, mo - 1, d);
    // 防御：避免 2026-02-31 这种溢出
    if (dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d) return null;
    return dt;
  }

  function isWeekend(d) {
    const w = d.getDay();
    return w === 0 || w === 6;
  }

  function normalizeDayType(v) {
    const s = String(v || "").trim().toLowerCase();
    if (s === "weekend") return "holiday";
    if (s === "holiday") return "holiday";
    return "workday";
  }

  function dayTypeZh(v) {
    return normalizeDayType(v) === "workday" ? "工作日" : "假期";
  }

  function safeNumber(v) {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function numClose(a, b, eps = 1e-9) {
    const x = safeNumber(a);
    const y = safeNumber(b);
    if (x === null || y === null) return false;
    return Math.abs(x - y) <= eps;
  }

  function updateHint(dateStr) {
    if (!hintEl) return;
    const d = parseISO(dateStr);
    if (!d) {
      hintEl.textContent = "";
      return;
    }
    const w = weekNames[d.getDay()];
    const weekend = isWeekend(d);
    const suffix = weekend ? "（周末）" : "";
    hintEl.textContent = `${dateStr} ${w}${suffix}`;
  }

  function resetFormForNewDate(dayType) {
    const t = normalizeDayType(dayType);
    if (elType) elType.value = t;
    if (elShiftStart) elShiftStart.value = "08:00";
    if (elShiftEnd) elShiftEnd.value = "";
    if (elShiftHours) elShiftHours.value = t === "workday" ? "8" : "0";
    if (elEff) elEff.value = t === "workday" ? "1.0" : String(holidayDefaultEfficiency);
    if (elAllowNormal) elAllowNormal.value = "yes";
    if (elAllowUrgent) elAllowUrgent.value = "yes";
    if (elRemark) elRemark.value = "";
  }

  function applyTypeDefaultsOnChange(dayType) {
    const t = normalizeDayType(dayType);
    const shVal = elShiftHours ? String(elShiftHours.value || "").trim() : "";
    const effVal = elEff ? String(elEff.value || "").trim() : "";

    // 规则：
    // - 默认假期不工作：从 workday 切到 holiday 时，若工时仍是默认 8，则自动置 0
    // - 默认效率：workday=1.0；holiday=holidayDefaultEfficiency（仅在空值或“看起来还是默认值”时替换）
    if (t === "holiday") {
      if (elShiftHours && (shVal === "" || numClose(shVal, 8))) elShiftHours.value = "0";
      if (elEff && (effVal === "" || numClose(effVal, 1))) elEff.value = String(holidayDefaultEfficiency);
      return;
    }

    // workday
    if (elShiftHours && (shVal === "" || numClose(shVal, 0))) elShiftHours.value = "8";
    if (elEff && (effVal === "" || numClose(effVal, holidayDefaultEfficiency))) elEff.value = "1.0";
  }

  function fillFormFromRow(r) {
    if (!r) return;
    if (elType) elType.value = normalizeDayType(r.day_type);
    if (elShiftStart) elShiftStart.value = r.shift_start || "08:00";
    if (elShiftEnd) elShiftEnd.value = r.shift_end || "";
    if (elShiftHours) {
      const sh = safeNumber(r.shift_hours);
      elShiftHours.value = sh === null ? "" : String(sh);
    }
    if (elEff) {
      const eff = safeNumber(r.efficiency);
      elEff.value = eff === null ? "" : String(eff);
    }
    if (elAllowNormal && r.allow_normal) elAllowNormal.value = String(r.allow_normal);
    if (elAllowUrgent && r.allow_urgent) elAllowUrgent.value = String(r.allow_urgent);
    if (elRemark) elRemark.value = r.remark || "";
  }

  function tooltipForRow(r) {
    if (!r) return "";
    const lines = [];
    lines.push(`类型：${r.day_type_zh || dayTypeZh(r.day_type)}`);
    if (typeof r.shift_hours !== "undefined" && r.shift_hours !== null) lines.push(`可用工时：${r.shift_hours}`);
    if (typeof r.efficiency !== "undefined" && r.efficiency !== null) lines.push(`效率：${r.efficiency}`);
    if (r.allow_normal) lines.push(`允许普通件：${r.allow_normal === "yes" ? "是" : "否"}`);
    if (r.allow_urgent) lines.push(`允许急件：${r.allow_urgent === "yes" ? "是" : "否"}`);
    if (r.remark) lines.push(`说明：${r.remark}`);
    return lines.join("\n");
  }

  function showPanel() {
    panel.style.display = "block";
  }

  function hidePanel() {
    panel.style.display = "none";
  }

  function isPanelVisible() {
    return panel.style.display !== "none";
  }

  // 以“当前输入日期”作为默认月视图
  let viewMonth = (() => {
    const d = parseISO(elDate.value);
    const base = d || new Date();
    return new Date(base.getFullYear(), base.getMonth(), 1);
  })();

  function setViewMonth(y, m) {
    viewMonth = new Date(y, m, 1);
  }

  function renderWeekHeader() {
    const header = panel.querySelector(".wc-cal-week");
    if (!header) return;
    header.innerHTML = "";
    for (const t of weekLabels) {
      const div = document.createElement("div");
      div.className = "wc-cal-weekday";
      div.textContent = t;
      header.appendChild(div);
    }
  }

  function renderGrid() {
    titleEl.textContent = `${viewMonth.getFullYear()}年${viewMonth.getMonth() + 1}月`;
    gridEl.innerHTML = "";

    const first = new Date(viewMonth.getFullYear(), viewMonth.getMonth(), 1);
    // Monday-first：把 Sun(0) 映射到 6
    const offset = (first.getDay() + 6) % 7;
    const start = new Date(first);
    start.setDate(first.getDate() - offset);

    const selected = parseISO(elDate.value);
    const selectedStr = selected ? fmtISO(selected) : "";

    for (let i = 0; i < 42; i += 1) {
      const cur = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
      const dateStr = fmtISO(cur);
      const inMonth = cur.getMonth() === viewMonth.getMonth();
      const weekend = isWeekend(cur);

      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "wc-cal-day";
      if (!inMonth) btn.classList.add("wc-cal-day--muted");
      if (weekend) btn.classList.add("wc-cal-day--weekend");
      if (dateStr === selectedStr) btn.classList.add("wc-cal-day--selected");

      const row = rowMap.get(dateStr);
      if (row) {
        btn.classList.add("wc-cal-day--configured");
        btn.title = tooltipForRow(row);
      }

      btn.dataset.date = dateStr;
      btn.textContent = String(cur.getDate());
      btn.addEventListener("click", () => {
        elDate.value = dateStr;
        updateHint(dateStr);

        const r = rowMap.get(dateStr);
        if (r) {
          fillFormFromRow(r);
        } else {
          // 新日期：默认类型按周末/工作日推断（假期包含周末）
          const defaultType = weekend ? "holiday" : "workday";
          resetFormForNewDate(defaultType);
        }

        // 若选到其它月份，自动切换视图
        setViewMonth(cur.getFullYear(), cur.getMonth());
        renderGrid();
        hidePanel();
      });
      gridEl.appendChild(btn);
    }
  }

  function render() {
    renderWeekHeader();
    renderGrid();
  }

  // ---- interactions ----
  btnOpen.addEventListener("click", (e) => {
    e.preventDefault();
    if (isPanelVisible()) {
      hidePanel();
      return;
    }
    // 打开时尽量对齐到当前输入月份
    const d = parseISO(elDate.value) || new Date();
    setViewMonth(d.getFullYear(), d.getMonth());
    render();
    showPanel();
  });

  if (btnPrev) {
    btnPrev.addEventListener("click", (e) => {
      e.preventDefault();
      setViewMonth(viewMonth.getFullYear(), viewMonth.getMonth() - 1);
      renderGrid();
    });
  }
  if (btnNext) {
    btnNext.addEventListener("click", (e) => {
      e.preventDefault();
      setViewMonth(viewMonth.getFullYear(), viewMonth.getMonth() + 1);
      renderGrid();
    });
  }

  // 输入框手工修改时，同步 hint 与默认填充
  elDate.addEventListener("change", () => {
    const d = parseISO(elDate.value);
    updateHint(elDate.value);
    if (!d) return;
    const dateStr = fmtISO(d);
    const r = rowMap.get(dateStr);
    if (r) {
      fillFormFromRow(r);
    } else {
      const defaultType = isWeekend(d) ? "holiday" : "workday";
      resetFormForNewDate(defaultType);
    }
  });

  if (elType) {
    elType.addEventListener("change", () => {
      applyTypeDefaultsOnChange(elType.value);
    });
  }

  // 点击外部关闭面板
  document.addEventListener("click", (e) => {
    if (!isPanelVisible()) return;
    const target = /** @type {HTMLElement} */ (e.target);
    if (!target) return;
    if (panel.contains(target) || btnOpen.contains(target)) return;
    hidePanel();
  });

  // 初始 hint
  updateHint(elDate.value);
})();

