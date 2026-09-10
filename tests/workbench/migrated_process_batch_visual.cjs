'use strict';
// DOM/CSS readback only. Does not style or mutate the application.
async function contrast(page) {
  return page.evaluate(() => {
    const rgba = value => { const n = value.match(/[\d.]+/g)?.map(Number); return n && n.length >= 3 ? [n[0], n[1], n[2], n[3] ?? 1] : [0, 0, 0, 0]; };
    const blend = (fg, bg) => [0, 1, 2].map(i => fg[i] * fg[3] + bg[i] * (1 - fg[3])).concat(1);
    const luminance = rgb => rgb.slice(0, 3).map(x => x / 255).map(x => x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4).reduce((v, x, i) => v + x * [.2126, .7152, .0722][i], 0);
    const result = [], walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      const text = node.textContent.trim(), owner = node.parentElement;
      if (!text || !owner || owner.closest('style,script,[aria-hidden="true"],[hidden],button:disabled,select:disabled,input:disabled')) continue;
      const style = getComputedStyle(owner), rect = owner.getBoundingClientRect();
      if (style.visibility !== 'visible' || !owner.getClientRects().length || rect.bottom < 0 || rect.top > innerHeight || rect.right < 0 || rect.left > innerWidth) continue;
      const range = document.createRange(); range.selectNodeContents(node);
      const textRect = Array.from(range.getClientRects()).find(r => r.width && r.height && r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight);
      if (!textRect) continue;
      const hit = document.elementFromPoint(textRect.x + textRect.width / 2, textRect.y + textRect.height / 2);
      if (!hit || !(owner === hit || owner.contains(hit))) continue;
      let layers = [], opacity = 1;
      for (let n = owner; n; n = n.parentElement) { const s = getComputedStyle(n); layers.push(rgba(s.backgroundColor)); opacity *= Number(s.opacity); }
      if (opacity < .99) continue;
      let bg = [255, 255, 255, 1]; for (const color of layers.reverse()) bg = blend(color, bg);
      const color = blend(rgba(style.color), bg), a = luminance(color), b = luminance(bg), ratio = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
      const large = parseFloat(style.fontSize) >= 24 || parseFloat(style.fontSize) >= 18.66 && Number(style.fontWeight) >= 700;
      result.push({text: text.slice(0, 160), tag: owner.tagName, className: owner.className, color: style.color, background: bg, font: style.fontSize,
        ratio: Math.round(ratio * 1000) / 1000, threshold: large ? 3 : 4.5, passes: ratio >= (large ? 3 : 4.5)});
    }
    return {checked: result.length, minimum: Math.min(...result.map(r => r.ratio)), failures: result.filter(r => !r.passes), rows: result};
  });
}
module.exports = {contrast};
