(function () {
  'use strict';
  const DAY = 86400000, weekdays = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];
  function axis({ start, end, width, left = 0, viewport = width }) {
    if (start === null) return { bands: [], ticks: [] };
    const span = end > start ? end - start : 1;
    const scale = width / span, low = start + left / scale, high = Math.min(end, start + (left + viewport) / scale);
    const unit = DAY * scale >= 54 ? 'day' : DAY * 30 * scale >= 70 ? 'month' : 'year';
    const date = new Date(low), year = date.getUTCFullYear(), month = date.getUTCMonth();
    let at = Date.UTC(year, unit === 'year' ? 0 : month, unit === 'day' ? date.getUTCDate() : 1);
    const bands = [], crossYear = new Date(start).getUTCFullYear() !== new Date(end).getUTCFullYear();
    while (at < high) {
      const d = new Date(at), wire = d.toISOString(), y = d.getUTCFullYear(), m = d.getUTCMonth();
      const next = unit === 'day' ? at + DAY : unit === 'month' ? Date.UTC(y, m + 1, 1) : Date.UTC(y + 1, 0, 1);
      const label = unit === 'day' ? wire.slice(crossYear ? 0 : 5, 10) + ' ' + weekdays[d.getUTCDay()] : unit === 'month' ? y + '年' + (m + 1) + '月' : y + '年';
      const begin = Math.max(start, low, at), finish = Math.min(end, high, next);
      bands.push({ at, x: (begin - start) * scale, width: (finish - begin) * scale, label });
      at = next;
    }
    const ticks = window.PlanGanttModel.ticks(start, end, width, left, viewport);
    const step = window.PlanGanttModel.tickStep(start, end, width);
    if (left === 0 && (!ticks.length || ticks[0].x > 75)) ticks.unshift({ at: start, x: 0, label: window.PlanGanttModel.wire(start) });
    return { bands, ticks: ticks.map(tick => ({ ...tick, label: step >= DAY * 28 ? tick.label.slice(0, 7) : step >= DAY ? tick.label.slice(5, 10) : step < 60000 ? tick.label.slice(11, 19) : tick.label.slice(11, 16) })) };
  }
  function taskLines({ sequence, process, batch, piece, resource }, mode, width) {
    if (width < 28) return { primary: '', secondary: '' };
    return { primary: width < 75 ? process : [sequence, process].filter(value => value !== null && value !== undefined && value !== '').join(' '),
      secondary: width < 75 ? '' : [mode === 'batch' ? resource : batch, piece].filter(Boolean).join(' · ') };
  }
  function palette(node) {
    const style = getComputedStyle(node), value = key => style.getPropertyValue(key).trim(), colors = {};
    for (const tone of ['primary', 'critical', 'success', 'plan', 'overlap']) colors[tone] = {
      fill: value('--wb-gantt-' + tone + '-fill'), edge: value('--wb-gantt-' + tone + '-edge'), ink: value('--wb-gantt-' + tone + '-ink') };
    return { ...colors, gold: value('--wb-gantt-gold'), text: value('--ui-text'), font: value('--wb-gantt-font') };
  }
  function useCanvasPaint(ref, paint, colors, deps, printing = false) {
    const current = React.useRef(paint), printState = React.useRef(printing), request = React.useRef(null); current.current = paint; printState.current = printing;
    React.useLayoutEffect(() => {
      let frame = null, live = true;
      function draw() {
        if (frame !== null) cancelAnimationFrame(frame); frame = null;
        const node = ref.current; if (!live || !node) return;
        // Layout dimensions remain in the same CSS coordinates as the marks when paginated print scales the visual rectangle.
        const width = node.clientWidth, height = node.clientHeight, dpr = window.devicePixelRatio || 1;
        const bufferWidth = Math.max(1, Math.round(width * dpr)), bufferHeight = Math.max(1, Math.round(height * dpr));
        if (node.width !== bufferWidth) node.width = bufferWidth;
        if (node.height !== bufferHeight) node.height = bufferHeight;
        const ctx = node.getContext('2d'); ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, width, height);
        current.current(ctx, width, height, colors(node));
      }
      function schedule() {
        if (!live) return;
        if (printState.current) { draw(); return; }
        if (frame !== null) return;
        frame = -1;
        const id = requestAnimationFrame(draw); if (frame === -1) frame = id;
      }
      request.current = schedule;
      const theme = new MutationObserver(schedule), resize = new ResizeObserver(schedule);
      theme.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'class'] }); resize.observe(ref.current);
      const media = typeof window.matchMedia === 'function' ? window.matchMedia('print') : null;
      if (media) media.addEventListener('change', schedule);
      window.addEventListener('beforeprint', draw); window.addEventListener('afterprint', schedule); window.addEventListener('resize', schedule);
      return () => {
        live = false; request.current = null; if (frame !== null) cancelAnimationFrame(frame);
        theme.disconnect(); resize.disconnect(); window.removeEventListener('beforeprint', draw); window.removeEventListener('afterprint', schedule); window.removeEventListener('resize', schedule);
        if (media) media.removeEventListener('change', schedule);
      };
    }, []);
    React.useLayoutEffect(() => { if (request.current) request.current(); }, [printing, ...deps]);
  }
  function rounded(ctx, x, y, width, height) {
    const radius = Math.min(4, width / 2, height / 2);
    ctx.beginPath(); ctx.moveTo(x + radius, y); ctx.lineTo(x + width - radius, y); ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius); ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height); ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius); ctx.quadraticCurveTo(x, y, x + radius, y); ctx.closePath();
  }
  function fitText(ctx, text, width) {
    if (ctx.measureText(text).width <= width) return text;
    if (ctx.measureText('…').width > width) return '';
    let low = 0, high = text.length;
    while (low < high) { const mid = Math.ceil((low + high) / 2); if (ctx.measureText(text.slice(0, mid) + '…').width <= width) low = mid; else high = mid - 1; }
    return text.slice(0, low) + '…';
  }
  function paintBar(ctx, { x, y, width, height, fill, edge, lineWidth = 1, dashed = false, texture = null, textureColor = edge, textColor, font, lines, viewport, onTime = false, locked = false, statusColor, critical = false, criticalColor = edge, muted = false }) {
    if (width <= 0) return;
    ctx.save(); if (muted) ctx.globalAlpha = .66; rounded(ctx, x, y, width, height); ctx.fillStyle = fill; ctx.fill();
    if (texture) {
      ctx.save(); ctx.clip(); ctx.strokeStyle = textureColor; ctx.lineWidth = 1; ctx.globalAlpha = .25;
      const spacing = texture === 'external' ? 10 : 6;
      for (let stripe = Math.floor((Math.max(0, -x) - height) / spacing) * spacing; stripe < Math.min(width, viewport - x); stripe += spacing) {
        ctx.beginPath(); ctx.moveTo(x + stripe, texture === 'external' ? y : y + height); ctx.lineTo(x + stripe + height, texture === 'external' ? y + height : y); ctx.stroke();
      }
      ctx.restore();
    }
    ctx.strokeStyle = edge; ctx.lineWidth = Math.min(lineWidth, width); ctx.setLineDash(dashed ? [4, 3] : []);
    rounded(ctx, x + ctx.lineWidth / 2, y + ctx.lineWidth / 2, width - ctx.lineWidth, height - ctx.lineWidth); ctx.stroke();
    if (critical) {
      ctx.save(); rounded(ctx, x, y, width, height); ctx.clip(); ctx.fillStyle = criticalColor; ctx.fillRect(x, y, width, 3); ctx.restore();
    }
    if (lines && lines.primary) {
      const textX = Math.max(0, x) + 4, room = Math.min(viewport, x + width) - textX - 4;
      ctx.font = font; ctx.fillStyle = textColor;
      ctx.fillText(fitText(ctx, lines.primary, room), textX, y + (lines.secondary ? 16 : height / 2 + 4));
      if (lines.secondary) ctx.fillText(fitText(ctx, lines.secondary, room), textX, y + 31);
    }
    if (width >= 28 && (onTime || locked)) {
      ctx.fillStyle = statusColor;
      if (locked) ctx.fillRect(x + width - 8, y + 3, 4, 4);
      if (onTime) { ctx.beginPath(); ctx.arc(x + width - 6, y + height - 5, 2, 0, Math.PI * 2); ctx.fill(); }
    }
    ctx.restore();
  }
  window.GanttPresentation = { axis, taskLines, palette, paintBar, useCanvasPaint };
})();
