(function () {
 "use strict";
window.APSFieldReports.mountCalendars=function(form,onChange){
const portalRoot=document.createElement('div');
portalRoot.className='r-calendar-portals';
form.closest('.r-editor,.r-inline-editor').appendChild(portalRoot);
function ReportIcon({name}) {
  return React.createElement('svg',{className:'lucide',viewBox:'0 0 24 24',width:16,height:16,fill:'none',stroke:'currentColor',strokeWidth:2,strokeLinecap:'round',strokeLinejoin:'round','aria-hidden':true},
    ...window.APSFieldReports.iconNodes[name].map(([tag,attrs],i)=>React.createElement(tag,{...attrs,key:i})));
}
const FR_WEEK = ["一", "二", "三", "四", "五", "六", "日"];
const FR_MONTHS = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"];
const frPad2 = (n) => String(n).padStart(2, "0");
function frParseDT(s) {
  const m = /^(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2}))?$/.exec(s || "");
  if (!m) return { y:null, mo:null, d:null, hh:null, mm:null };
  return { y:+m[1], mo:+m[2], d:+m[3], hh:m[4] == null ? null : +m[4], mm:m[5] == null ? null : +m[5] };
}
function frFmtDT(mo, d, hh, mm, year = 2026) {
  if (mo == null || d == null) return "";
  let s = year + "-" + frPad2(mo) + "-" + frPad2(d);
  if (hh != null && mm != null) s += "T" + frPad2(hh) + ":" + frPad2(mm);
  return s;
}
const FR_ICON_CAL = <ReportIcon name="calendar-days" />;
const FR_ICON_PREV = <ReportIcon name="chevron-left" />;
const FR_ICON_NEXT = <ReportIcon name="chevron-right" />;

// 自定义时间选择器（小时 / 分钟两列）。原生 <input type=time> 的下拉用浏览器
// 自带样式（亮蓝方块），与全站日历不一致且无法用 CSS 接管，故改为令牌化两列选择。
const FR_ICON_CLOCK = <ReportIcon name="clock-3" />;
function FRTimePicker({ value, onChange }) {
  const { useState, useRef, useEffect, useLayoutEffect } = React;
  const wrapRef = useRef(null);
  const hRef = useRef(null);
  const mRef = useRef(null);
  const [open, setOpen] = useState(false);
  const tm = /^(\d{1,2}):(\d{2})$/.exec(value || "");
  const hh = tm ? +tm[1] : null;
  const mm = tm ? +tm[2] : null;

  useEffect(() => {
    if (!open) return;
    const onDown = (e) => { if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", onDown, true);
    return () => document.removeEventListener("mousedown", onDown, true);
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    const center = (col, idx) => {
      if (!col) return;
      const el = col.children[idx];
      if (el) col.scrollTop = el.offsetTop - col.clientHeight / 2 + el.clientHeight / 2;
    };
    center(hRef.current, hh == null ? 8 : hh);
    center(mRef.current, mm == null ? 0 : mm);
  }, [open]);

  const pick = (nh, nm) => onChange(frPad2(nh) + ":" + frPad2(nm));
  const hours = Array.from({ length: 24 }, (_, i) => i);
  const mins = Array.from({ length: 60 }, (_, i) => i);

  return (
    <span ref={wrapRef} className="fr-tp">
      <button type="button" className={"fr-tp-btn" + (open ? " is-open" : "")}
        onClick={() => setOpen((o) => !o)}>
        <span className={"fr-tp-val" + (value ? "" : " is-empty")}>{value || "选择时间"}</span>
        <span className="fr-tp-ic">{FR_ICON_CLOCK}</span>
      </button>
      {open ? (
        <div className="fr-tp-pop" role="dialog" aria-label="选择时间">
          <div className="fr-tp-col" ref={hRef}>
            {hours.map((h) => (
              <button key={h} type="button" className={"fr-tp-opt" + (h === hh ? " is-on" : "")}
                onClick={() => pick(h, mm == null ? 0 : mm)}>{frPad2(h)}</button>
            ))}
          </div>
          <div className="fr-tp-col" ref={mRef}>
            {mins.map((m) => (
              <button key={m} type="button" className={"fr-tp-opt" + (m === mm ? " is-on" : "")}
                onClick={() => pick(hh == null ? 8 : hh, m)}>{frPad2(m)}</button>
            ))}
          </div>
        </div>
      ) : null}
    </span>
  );
}

function FRDateTimeField({ value, onChange, need, label }) {
  const { useState, useRef, useEffect, useLayoutEffect } = React;
  const fieldRef = useRef(null);
  const popRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [showMonths, setShowMonths] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0, flipUp: false });

  const today = new Date(2026, 8, 7);
  const parsed = frParseDT(value);
  const REF_YEAR = parsed.y || today.getFullYear();
  const [view, setView] = useState(() => ({ y: REF_YEAR, m: parsed.mo != null ? parsed.mo - 1 : today.getMonth() }));

  useEffect(() => {
    if (!open) return;
    const p = frParseDT(value);
    setView({ y: p.y || today.getFullYear(), m: p.mo != null ? p.mo - 1 : today.getMonth() });
    setShowMonths(false);
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return;
    const f = fieldRef.current;
    if (f) {
      const r = f.getBoundingClientRect();
      const pw = 268, ph = 374;
      const left = Math.max(8, Math.min(r.left, window.innerWidth - pw - 8));
      const flipUp = r.bottom + ph + 6 > window.innerHeight && r.top > ph + 8;
      setPos({ top: Math.max(8, Math.min(flipUp ? r.top - ph - 6 : r.bottom + 6, window.innerHeight - ph - 8)), left, flipUp });
    }
    const onScroll = (e) => {
      // 时间选择器在列内滚动（含程序化 scrollTop 居中）会冒泡到此捕获监听，
      // 不能因此把整个日历关掉——仅当滚动发生在弹层之外时才收起。
      if (e && e.target && e.target.nodeType && popRef.current && popRef.current.contains(e.target)) return;
      setOpen(false);
    };
    const onDown = (e) => {
      if (fieldRef.current && fieldRef.current.contains(e.target)) return;
      if (popRef.current && popRef.current.contains(e.target)) return;
      setOpen(false);
    };
    window.addEventListener("scroll", onScroll, true);
    window.addEventListener("resize", onScroll, true);
    document.addEventListener("mousedown", onDown, true);
    return () => {
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onScroll, true);
      document.removeEventListener("mousedown", onDown, true);
    };
  }, [open]);

  const step = (dir) => setView((v) => { let m = v.m + dir, y = v.y; if (m < 0) { m = 11; y--; } else if (m > 11) { m = 0; y++; } return { y, m }; });
  const pickDay = (mo, d, y = view.y) => { const p = frParseDT(value); onChange(frFmtDT(mo, d, p.hh != null ? p.hh : 8, p.mm != null ? p.mm : 0, y)); };
  const setTime = (t) => {
    const tm = /^(\d{1,2}):(\d{2})$/.exec(t || "");
    const p = frParseDT(value);
    let mo = p.mo, d = p.d;
    if (mo == null) { mo = today.getMonth() + 1; d = today.getDate(); }
    onChange(tm ? frFmtDT(mo, d, +tm[1], +tm[2], p.y || view.y) : frFmtDT(mo, d, null, null, p.y || view.y));
  };
  const clear = () => { onChange(""); setOpen(false); };
  const pickToday = () => pickDay(today.getMonth() + 1, today.getDate(), today.getFullYear());

  // 42 格日历（周一起），末行整周在下月则裁掉
  const first = new Date(view.y, view.m, 1);
  const offset = (first.getDay() + 6) % 7;
  const start = new Date(view.y, view.m, 1 - offset);
  const tY = today.getFullYear(), tMo = today.getMonth() + 1, tD = today.getDate();
  let allCells = [];
  for (let i = 0; i < 42; i++) {
    const cur = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    const out = cur.getMonth() !== view.m;
    allCells.push({
      y: cur.getFullYear(), day: cur.getDate(), mo: cur.getMonth() + 1, d: cur.getDate(), out,
      wknd: cur.getDay() === 0 || cur.getDay() === 6,
      isToday: cur.getFullYear() === tY && cur.getMonth() === tMo - 1 && cur.getDate() === tD,
      isSel: !out && view.y === REF_YEAR && parsed.mo === cur.getMonth() + 1 && parsed.d === cur.getDate(),
    });
  }
  const cells = allCells.slice(35).every((c) => c.out) ? allCells.slice(0, 35) : allCells;
  const timeVal = (parsed.hh != null && parsed.mm != null) ? frPad2(parsed.hh) + ":" + frPad2(parsed.mm) : "";


  const popover = (
    <div ref={popRef} className={"apsdp-pop is-anim" + (showMonths ? " show-months" : "") + (pos.flipUp ? " flip-up" : "")}
      role="dialog" aria-label="选择日期与时间"
      onKeyDown={(e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); setOpen(false); } }}
      style={{ position: "fixed", top: pos.top, left: pos.left, width: 268, maxWidth: "calc(100vw - 16px)", maxHeight: "calc(100vh - 16px)", overflowY: "auto" }}>
      <div className="apsdp-head">
        <button type="button" className="apsdp-nav" aria-label="上个月" onClick={() => step(-1)}>{FR_ICON_PREV}</button>
        <button type="button" className="apsdp-title" onClick={() => setShowMonths((s) => !s)}>
          <span className="apsdp-title-txt">{view.y} 年 {view.m + 1} 月</span><span className="caret"></span>
        </button>
        <button type="button" className="apsdp-nav" aria-label="下个月" onClick={() => step(1)}>{FR_ICON_NEXT}</button>
      </div>
      <div className="apsdp-week">
        {FR_WEEK.map((w, i) => <div key={i} className={"apsdp-wd" + (i >= 5 ? " is-weekend" : "")}>{w}</div>)}
      </div>
      <div className="apsdp-grid">
        {cells.map((c, i) => (
          <button key={i} type="button"
            className={"apsdp-day" + (c.out ? " is-out" : "") + (c.wknd ? " is-weekend" : "") + (c.isToday ? " is-today" : "") + (c.isSel ? " is-selected" : "")}
            onClick={() => pickDay(c.mo, c.d, c.y)}>{c.day}</button>
        ))}
      </div>
      <div className="apsdp-months">
        {FR_MONTHS.map((mn, i) => (
          <button key={i} type="button" className={"apsdp-month" + (i === view.m ? " is-current" : "")}
            onClick={() => { setView((v) => ({ ...v, m: i })); setShowMonths(false); }}>{mn}</button>
        ))}
      </div>
      <div className="apsdp-foot">
        <span className="fr-dt-timewrap">
          <span className="fr-dt-timelbl">时间</span>
          <FRTimePicker value={timeVal} onChange={setTime} />
        </span>
        <span style={{ display: "inline-flex", gap: 4, marginLeft: "auto" }}>
          <button type="button" className="apsdp-link clear" onClick={clear}>清除</button>
          <button type="button" className="apsdp-link today" onClick={pickToday}>今天</button>
        </span>
      </div>
    </div>
  );

  return (
    <span ref={fieldRef} className={"apsdp-field" + (need ? " is-need" : "") + (open ? " is-open" : "")} style={{ height: 32 }}>
      <input className="apsdp-input" aria-label={label} style={{ width: "100%" }} value={value.replace("T", " ")} placeholder="YYYY-MM-DD HH:MM"
        autoComplete="off" onChange={(e) => onChange(e.target.value.replace(" ", "T"))} onFocus={() => setOpen(true)}
        onKeyDown={(e) => { if (e.key === "Escape" && open) { e.preventDefault(); e.stopPropagation(); setOpen(false); } }} />
      <button type="button" className="apsdp-trigger" aria-label="打开日历"
        onMouseDown={(e) => e.preventDefault()} onClick={() => setOpen((o) => !o)}>{FR_ICON_CAL}</button>
      {open ? ReactDOM.createPortal(popover, portalRoot) : null}
    </span>
  );
}


function mountReportingCalendars(form, onChange) {
  const mounted = [];
  for (const slot of form.querySelectorAll('[data-calendar]')) {
    const input = form.elements[slot.dataset.calendar];
    function BoundCalendar() {
      const [value, setValue] = React.useState(input.value);
      return <FRDateTimeField value={value} need={!value} label={slot.dataset.label} onChange={next => {
        input.value = next; setValue(next); onChange();
      }} />;
    }
    const instance = ReactDOM.createRoot(slot);
    ReactDOM.flushSync(() => instance.render(<BoundCalendar />));
    mounted.push({instance,slot});
  }
  return () => {
    // Preserve React-owned children until the host's current unmount has finished.
    for (const {slot} of mounted) slot.remove();
    portalRoot.remove();
    Promise.resolve().then(() => { for (const {instance} of mounted) instance.unmount(); });
  };
}

return mountReportingCalendars(form,onChange);
};
})();
