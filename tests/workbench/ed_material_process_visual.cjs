'use strict';
// Read-only layout measurement. Scrolled content is reported separately from clipping.
async function geometry(page) {
  return page.evaluate(() => {
    const visible = n => n.getClientRects().length && getComputedStyle(n).visibility === 'visible' && !n.closest('[hidden],[aria-hidden="true"]');
    const dialogs = Array.from(document.querySelectorAll('[role="dialog"][aria-modal="true"]')).filter(visible);
    const root = dialogs[dialogs.length - 1];
    if (!root) return {scope: 'no-active-dialog', clipping: [], overlaps: [], controls: [], scrollRegions: []};
    const box = n => { const r = n.getBoundingClientRect(); return {left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.width, height: r.height}; };
    const clipping = [], controls = [], scrollRegions = [], controlContrast = [];
    const text = n => (n.getAttribute('aria-label') || n.textContent || n.value || '').trim().slice(0, 100);
    const rgba = value => { const a = value.match(/[\d.]+/g).map(Number); return [a[0], a[1], a[2], a[3] === undefined ? 1 : a[3]]; };
    const blend = (a, b) => a.slice(0, 3).map((c, i) => c * a[3] + b[i] * (1 - a[3])).concat(1);
    const lum = a => a.slice(0, 3).map(c => c / 255).map(c => c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4).reduce((sum, c, i) => sum + c * [.2126, .7152, .0722][i], 0);
    for (const n of root.querySelectorAll('*')) {
      if (!visible(n)) continue;
      const s = getComputedStyle(n), r = box(n);
      if (/(auto|scroll)/.test(s.overflowX + s.overflowY) && (n.scrollHeight > n.clientHeight + 2 || n.scrollWidth > n.clientWidth + 2))
        scrollRegions.push({tag: n.tagName, class: n.className, width: n.clientWidth, scrollWidth: n.scrollWidth, height: n.clientHeight, scrollHeight: n.scrollHeight});
      if (n.matches('input,select,textarea,button,[role="combobox"]') && r.width > 4 && r.height > 4) {
        controls.push({tag: n.tagName, type: n.type, name: n.name, label: text(n), value: n.value, disabled: n.disabled,
          color: s.color, background: s.backgroundColor, font: s.fontFamily, radius: s.borderRadius, rect: r});
        if (n.matches('input,textarea') && !n.disabled && n.value && !['checkbox', 'radio'].includes(n.type)) {
          const colors = []; for (let parent = n; parent; parent = parent.parentElement) colors.push(rgba(getComputedStyle(parent).backgroundColor));
          const bg = colors.reverse().reduce((bg, fg) => blend(fg, bg), [255, 255, 255, 1]), fg = blend(rgba(s.color), bg);
          const a = lum(bg), b = lum(fg), ratio = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
          controlContrast.push({label: text(n), value: n.value, ratio, passes: ratio >= 4.5});
        }
      }
      if (n.matches('input,select,textarea') || !/(hidden|clip)/.test(s.overflowX + s.overflowY) || s.textOverflow === 'ellipsis') continue;
      // .wb-visually-hidden (1x1, overflow hidden, clip rect(0 0 0 0)) is screen-reader-only text; clipping it is the intent, not a defect.
      if (n.classList.contains('wb-visually-hidden') || s.clip === 'rect(0px, 0px, 0px, 0px)') continue;
      for (const child of n.childNodes) {
        if (child.nodeType !== Node.TEXT_NODE || !child.textContent.trim()) continue;
        const range = document.createRange(); range.selectNodeContents(child);
        for (const t of range.getClientRects()) if (t.left < r.left - 2 || t.right > r.right + 2 || t.top < r.top - 2 || t.bottom > r.bottom + 2)
          clipping.push({text: child.textContent.trim().slice(0, 100), owner: n.className, rect: r, textRect: {left: t.left, top: t.top, right: t.right, bottom: t.bottom}});
      }
    }
    const nodes = Array.from(root.querySelectorAll('button,input,textarea,[role="combobox"]')).filter(n => {
      if (!visible(n)) return false;
      const r = box(n); if (r.width < 4 || r.height < 4 || r.left < 0 || r.right > innerWidth || r.top < 0 || r.bottom > innerHeight) return false;
      const hit = document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2);
      return hit && (hit === n || n.contains(hit));
    });
    const overlaps = [], insetSteppers = [];
    for (let i = 0; i < nodes.length; i++) for (let j = i + 1; j < nodes.length; j++) {
      const a = nodes[i], b = nodes[j]; if (a.contains(b) || b.contains(a)) continue;
      const x = box(a), y = box(b), w = Math.min(x.right, y.right) - Math.max(x.left, y.left), h = Math.min(x.bottom, y.bottom) - Math.max(x.top, y.top);
      if (w <= 2 || h <= 2) continue;
      const input = a.matches('input.wb-number-input') ? a : b.matches('input.wb-number-input') ? b : null;
      const step = a.matches('button.wb-number-step') ? a : b.matches('button.wb-number-step') ? b : null;
      if (input && step) {
        const field = box(input), button = box(step), padding = parseFloat(getComputedStyle(input).paddingRight);
        if (button.left >= field.right - padding && button.right <= field.right + 1 && button.top >= field.top - 1 && button.bottom <= field.bottom + 1) {
          insetSteppers.push({input: text(input), step: text(step), reservedPadding: padding}); continue;
        }
      }
      overlaps.push({a: text(a), b: text(b), width: w, height: h});
    }
    return {scope: root.getAttribute('aria-label') || (root.getAttribute('aria-labelledby') || '').split(' ').map(id => document.getElementById(id)?.textContent || '').join(' '),
      rect: box(root), clipping, overlaps, insetSteppers, controls, controlContrast, scrollRegions,
      dateInputs: root.querySelectorAll('input[type="date"],input[type="month"],input[type="datetime-local"]').length};
  });
}
module.exports = {geometry};
