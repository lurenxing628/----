/* ============================================================
   APS 排产系统 · 日期选择器逻辑（无第三方库）
   - 自动接管页面里所有 <input type="date">（除 [data-aps-skip]），
     以及任何带 [data-aps-date] 的文本输入框。
   - 把原生 type=date 改为 text，挂自定义弹层；value 仍是
     YYYY-MM-DD，选/清后派发 input+change 事件，旧监听照常触发。
   - 读取 min / max / required / disabled / value，越界日期禁用。
   - data-aps-marked="2026-06-19,2026-06-22" 可高亮“已配置”日期。
   - ES6 语法，避免可选链 / 空值合并，兼容旧版 Chrome。
   ============================================================ */
(function () {
  "use strict";
  if (window.APSDatePicker) return;

  var WEEK = ["一", "二", "三", "四", "五", "六", "日"];   // 周一起，与产品口径一致
  var MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];

  var ICON_CAL =
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
    '<rect x="4" y="5" width="16" height="16" rx="2.5"/><path d="M4 10h16M8 3v4M16 3v4"/></svg>';
  var ICON_PREV = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="14 6 8 12 14 18"/></svg>';
  var ICON_NEXT = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><polyline points="10 6 16 12 10 18"/></svg>';

  function pad2(n) { return String(n).padStart(2, "0"); }
  function iso(y, m, d) { return y + "-" + pad2(m + 1) + "-" + pad2(d); }
  function isoOf(dt) { return iso(dt.getFullYear(), dt.getMonth(), dt.getDate()); }
  function parseISO(s) {
    if (!s || typeof s !== "string") return null;
    var m = s.trim().match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (!m) return null;
    var y = +m[1], mo = +m[2], d = +m[3];
    var dt = new Date(y, mo - 1, d);
    if (dt.getFullYear() !== y || dt.getMonth() !== mo - 1 || dt.getDate() !== d) return null;
    return dt;
  }
  function cmp(a, b) { return a < b ? -1 : (a > b ? 1 : 0); }   // ISO 字符串可直接比较

  /* ---------- 单例弹层 ---------- */
  var pop, titleEl, gridEl, weekEl, monthsEl, target = null, view = null, repos = null;

  function buildPop() {
    pop = document.createElement("div");
    pop.className = "apsdp-pop";
    pop.setAttribute("role", "dialog");
    pop.setAttribute("aria-label", "选择日期");
    pop.hidden = true;
    pop.innerHTML =
      '<div class="apsdp-head">' +
        '<button type="button" class="apsdp-nav" data-nav="-1" aria-label="上个月">' + ICON_PREV + '</button>' +
        '<button type="button" class="apsdp-title"><span class="apsdp-title-txt"></span><span class="caret"></span></button>' +
        '<button type="button" class="apsdp-nav" data-nav="1" aria-label="下个月">' + ICON_NEXT + '</button>' +
      '</div>' +
      '<div class="apsdp-week"></div>' +
      '<div class="apsdp-grid"></div>' +
      '<div class="apsdp-months"></div>' +
      '<div class="apsdp-foot">' +
        '<button type="button" class="apsdp-link clear">清除</button>' +
        '<button type="button" class="apsdp-link today">今天</button>' +
      '</div>';
    document.body.appendChild(pop);

    titleEl = pop.querySelector(".apsdp-title-txt");
    gridEl = pop.querySelector(".apsdp-grid");
    weekEl = pop.querySelector(".apsdp-week");
    monthsEl = pop.querySelector(".apsdp-months");

    // 星期表头
    var wh = "";
    for (var i = 0; i < 7; i++) wh += '<div class="apsdp-wd' + (i >= 5 ? " is-weekend" : "") + '">' + WEEK[i] + "</div>";
    weekEl.innerHTML = wh;

    // 月份快选
    var mh = "";
    for (var j = 0; j < 12; j++) mh += '<button type="button" class="apsdp-month" data-m="' + j + '">' + MONTHS[j] + "</button>";
    monthsEl.innerHTML = mh;

    // 事件代理
    pop.addEventListener("mousedown", function (e) { e.preventDefault(); }); // 不抢输入框焦点
    pop.addEventListener("click", onPopClick);
  }

  function onPopClick(e) {
    var t = e.target;
    var nav = t.closest ? t.closest("[data-nav]") : null;
    if (nav) { stepMonth(+nav.getAttribute("data-nav")); return; }
    if (t.closest && t.closest(".apsdp-title")) { pop.classList.toggle("show-months"); return; }
    var mo = t.closest ? t.closest("[data-m]") : null;
    if (mo) { view.m = +mo.getAttribute("data-m"); pop.classList.remove("show-months"); render(); return; }
    var day = t.closest ? t.closest(".apsdp-day") : null;
    if (day && !day.disabled) { pick(day.getAttribute("data-d")); return; }
    if (t.closest && t.closest(".apsdp-link.today")) { onToday(); return; }
    if (t.closest && t.closest(".apsdp-link.clear")) { commit(""); close(); return; }
  }

  function stepMonth(dir) {
    var m = view.m + dir, y = view.y;
    if (m < 0) { m = 11; y--; } else if (m > 11) { m = 0; y++; }
    view.y = y; view.m = m; render();
  }

  function onToday() {
    var now = new Date();
    var s = isoOf(now);
    if (inRange(s)) { commit(s); close(); }
    else { view.y = now.getFullYear(); view.m = now.getMonth(); pop.classList.remove("show-months"); render(); }
  }

  function inRange(s) {
    var min = target.getAttribute("min"), max = target.getAttribute("max");
    if (min && parseISO(min) && cmp(s, min) < 0) return false;
    if (max && parseISO(max) && cmp(s, max) > 0) return false;
    return true;
  }

  // 把日期夹到 [min, max] 内（用于键盘移动，保证总能落在合法日期上）
  function clampISO(s) {
    var min = target.getAttribute("min"), max = target.getAttribute("max");
    if (min && parseISO(min) && cmp(s, min) < 0) return min;
    if (max && parseISO(max) && cmp(s, max) > 0) return max;
    return s;
  }

  function pick(s) { commit(s); close(); }

  function commit(s) {
    if (!target) return;
    target.value = s;
    target.dispatchEvent(new Event("input", { bubbles: true }));
    target.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function markedSet() {
    var raw = target.getAttribute("data-aps-marked");
    var set = {};
    if (raw) raw.split(",").forEach(function (x) { var v = x.trim(); if (v) set[v] = 1; });
    return set;
  }

  function render() {
    titleEl.textContent = view.y + " 年 " + (view.m + 1) + " 月";

    // 月份快选当前态
    var mbs = monthsEl.children;
    for (var k = 0; k < mbs.length; k++) mbs[k].classList.toggle("is-current", +mbs[k].getAttribute("data-m") === view.m);

    var first = new Date(view.y, view.m, 1);
    var offset = (first.getDay() + 6) % 7;            // 周一起
    var start = new Date(view.y, view.m, 1 - offset);
    var selected = parseISO(target.value);
    var selStr = selected ? isoOf(selected) : "";
    var today = isoOf(new Date());
    var marks = markedSet();

    var html = "";
    for (var i = 0; i < 42; i++) {
      var cur = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
      var s = isoOf(cur);
      var out = cur.getMonth() !== view.m;
      var wknd = cur.getDay() === 0 || cur.getDay() === 6;
      var disabled = !inRange(s);
      var cls = "apsdp-day";
      if (out) cls += " is-out";
      if (wknd) cls += " is-weekend";
      if (s === today) cls += " is-today";
      if (s === selStr) cls += " is-selected";
      if (marks[s]) cls += " is-marked";
      html += '<button type="button" class="' + cls + '" data-d="' + s + '"' + (disabled ? " disabled" : "") + ">" + cur.getDate() + "</button>";
    }
    gridEl.innerHTML = html;

    // 6 行 / 5 行自适应：末行整周都在下月则隐藏，避免空跑一行
    if (gridEl.children.length === 42) {
      var lastRowAllOut = true;
      for (var r = 35; r < 42; r++) if (!gridEl.children[r].classList.contains("is-out")) { lastRowAllOut = false; break; }
      for (var rr = 35; rr < 42; rr++) gridEl.children[rr].style.display = lastRowAllOut ? "none" : "";
    }
  }

  function position() {
    var f = target.__apsdpField || target;
    var r = f.getBoundingClientRect();
    var sx = window.pageXOffset, sy = window.pageYOffset;
    var pw = pop.offsetWidth, ph = pop.offsetHeight;
    var vw = document.documentElement.clientWidth, vh = window.innerHeight;
    var left = r.left + sx;
    if (left + pw > sx + vw - 8) left = sx + vw - pw - 8;
    if (left < sx + 8) left = sx + 8;
    var below = r.bottom + 6, above = r.top - 6 - ph;
    var flipUp = (r.bottom + 6 + ph > vh) && (r.top - 6 - ph > 0);
    pop.classList.toggle("flip-up", flipUp);
    pop.style.left = Math.round(left) + "px";
    pop.style.top = Math.round((flipUp ? above : below) + sy) + "px";
  }

  function open(input) {
    target = input;
    var d = parseISO(input.value) || new Date();
    view = { y: d.getFullYear(), m: d.getMonth() };
    pop.classList.remove("show-months");
    pop.hidden = false;
    render();
    position();
    pop.classList.remove("is-anim"); void pop.offsetWidth; pop.classList.add("is-anim");
    if (input.__apsdpField) input.__apsdpField.classList.add("is-open");
    bindDismiss();
  }

  function close() {
    if (pop.hidden) return;
    pop.hidden = true;
    pop.classList.remove("show-months");
    if (target && target.__apsdpField) target.__apsdpField.classList.remove("is-open");
    unbindDismiss();
    target = null;
  }

  function onDocDown(e) {
    if (pop.contains(e.target)) return;
    if (target && target.__apsdpField && target.__apsdpField.contains(e.target)) return;
    close();
  }
  function onKey(e) {
    if (e.key === "Escape") { e.stopPropagation(); close(); return; }
    if (!view) return;
    var step = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[e.key];
    if (step) {
      e.preventDefault();
      var cur = parseISO(target.value);
      var s;
      if (!cur) {
        // 还没选日期：首次按方向键，落在今天（被夹进 min/max 范围内）
        s = clampISO(isoOf(new Date()));
      } else {
        var nx = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + step);
        s = clampISO(isoOf(nx));
      }
      target.value = s;
      var d = parseISO(s);
      view.y = d.getFullYear(); view.m = d.getMonth();
      render();
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (parseISO(target.value)) { commit(target.value); close(); }
    }
  }
  function bindDismiss() {
    document.addEventListener("mousedown", onDocDown, true);
    document.addEventListener("keydown", onKey, true);
    window.addEventListener("resize", reposSoon, true);
    window.addEventListener("scroll", reposSoon, true);
  }
  function unbindDismiss() {
    document.removeEventListener("mousedown", onDocDown, true);
    document.removeEventListener("keydown", onKey, true);
    window.removeEventListener("resize", reposSoon, true);
    window.removeEventListener("scroll", reposSoon, true);
  }
  function reposSoon() {
    if (pop.hidden) return;
    if (repos) return;
    repos = window.requestAnimationFrame(function () { repos = null; if (!pop.hidden) position(); });
  }

  /* ---------- 接管输入框 ---------- */
  function enhance(input) {
    if (!input || input.__apsdp) return;
    input.__apsdp = true;

    var field = document.createElement("span");
    field.className = "apsdp-field";
    input.parentNode.insertBefore(field, input);
    field.appendChild(input);
    input.__apsdpField = field;
    input.classList.add("apsdp-input");
    input.setAttribute("autocomplete", "off");
    try { input.type = "text"; } catch (e) {}   // 关掉原生日历
    if (!input.getAttribute("placeholder")) input.setAttribute("placeholder", "YYYY-MM-DD");

    var trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "apsdp-trigger";
    trigger.setAttribute("aria-label", "打开日历");
    trigger.innerHTML = ICON_CAL;
    field.appendChild(trigger);

    var toggle = function (e) {
      if (input.disabled || input.readOnly) return;
      if (e) e.preventDefault();
      if (!pop.hidden && target === input) { close(); return; }
      open(input);
    };
    trigger.addEventListener("click", toggle);
    // 点击字段任意处（输入框本体或留白）都打开日历，而不仅是图标
    field.addEventListener("click", function (e) {
      if (input.disabled || input.readOnly) return;
      if (e.target.closest && e.target.closest(".apsdp-trigger")) return; // 图标自带开/关
      if (pop.hidden || target !== input) open(input);
    });
    input.addEventListener("focus", function () { if (pop.hidden || target !== input) open(input); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "ArrowDown" && (pop.hidden || target !== input)) { e.preventDefault(); open(input); }
    });
    // 手输合法日期时同步面板
    input.addEventListener("input", function () {
      if (!pop.hidden && target === input) {
        var d = parseISO(input.value);
        if (d) { view.y = d.getFullYear(); view.m = d.getMonth(); render(); }
      }
    });
  }

  function enhanceAll(root) {
    if (!pop) buildPop();
    var scope = root || document;
    var nodes = scope.querySelectorAll('input[type="date"]:not([data-aps-skip]), input[data-aps-date]:not([data-aps-skip])');
    for (var i = 0; i < nodes.length; i++) enhance(nodes[i]);
  }

  window.APSDatePicker = { enhance: enhance, enhanceAll: enhanceAll };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { enhanceAll(); });
  } else {
    enhanceAll();
  }
})();
