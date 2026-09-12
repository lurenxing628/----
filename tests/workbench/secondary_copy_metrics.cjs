'use strict';
const assert = require('node:assert/strict');
const surfaces = ['bg', 'card-bg', 'surface-soft', 'surface-muted'];
const light = 'rgb(71, 85, 105)', dark = 'rgb(148, 163, 184)', original = 'rgb(100, 116, 139)';

async function measure(page, selectors) {
  return page.evaluate(selectors => {
    const rgba = value => { const v = value.match(/[\d.]+/g).map(Number); return v.length === 3 ? v.concat(1) : v; };
    const over = (front, back) => {
      const a = front[3] + back[3] * (1 - front[3]);
      return a ? front.slice(0, 3).map((v, i) => (v * front[3] + back[i] * back[3] * (1 - front[3])) / a).concat(a) : [0, 0, 0, 0];
    };
    const lum = v => v.slice(0, 3).map(c => c / 255).map(c => c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4)
      .reduce((sum, c, i) => sum + c * [.2126, .7152, .0722][i], 0);
    return selectors.flatMap(selector => [...document.querySelectorAll(selector)].flatMap((node, index) => {
      const s = getComputedStyle(node), box = node.getBoundingClientRect();
      if (!box.width || !box.height || s.visibility !== 'visible' || node.closest('[hidden],[aria-hidden="true"]')) return [];
      const text = [...node.childNodes].filter(n => n.nodeType === Node.TEXT_NODE).map(n => n.textContent).join('').trim();
      if (!text) return [];
      let bg = [0, 0, 0, 0], opacity = 1; const effects = [];
      for (let parent = node; parent; parent = parent.parentElement) {
        const p = getComputedStyle(parent); bg = over(bg, rgba(p.backgroundColor)); opacity *= Number(p.opacity);
        if (p.filter !== 'none' || p.backgroundImage !== 'none' || p.mixBlendMode !== 'normal') effects.push(parent.tagName + '.' + parent.className);
      }
      const a = lum(over(rgba(s.color), bg)), b = lum(bg);
      return [{ selector, index, text, color: s.color, background: s.backgroundColor, effectiveBackground: bg,
        ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05), opacity, effects,
        fontSize: s.fontSize, lineHeight: s.lineHeight, fontFamily: s.fontFamily, letterSpacing: s.letterSpacing,
        width: box.width, height: box.height, inViewport: box.bottom > 0 && box.top < innerHeight }];
    }));
  }, selectors);
}

async function tokens(page) {
  return page.evaluate(() => {
    const names = new Set();
    const visit = rules => [...rules].forEach(rule => {
      if (rule.style) [...rule.style].filter(k => /^--(?:ui-|badge-|sidebar-|gantt-|wb-secondary-copy$)/.test(k)).forEach(k => names.add(k));
      if (rule.styleSheet) visit(rule.styleSheet.cssRules);
      if (rule.cssRules) visit(rule.cssRules);
    });
    [...document.styleSheets].forEach(sheet => visit(sheet.cssRules));
    const read = node => {
      const s = getComputedStyle(node);
      return Object.fromEntries([...names].sort().map(k => [k, s.getPropertyValue(k).trim()]));
    };
    return { root: read(document.documentElement), body: read(document.body) };
  });
}

function readable(samples, selectors) {
  for (const selector of selectors) assert(samples.some(row => row.selector === selector), 'Missing readable target: ' + selector);
  for (const row of samples) {
    assert.equal(row.opacity, 1, row.text); assert.deepEqual(row.effects, [], row.text);
    assert.equal(row.effectiveBackground[3], 1, row.text);
    assert(row.ratio >= 4.5, JSON.stringify(row));
  }
}

function compare(before, after, theme) {
  assert.deepEqual(before.tokens.root, after.tokens.root, 'Root/prototype tokens changed');
  const stableTokens = value => Object.fromEntries(Object.entries(value).filter(([k]) => k !== '--ui-muted'));
  assert.deepEqual(stableTokens(before.tokens.body), stableTokens(after.tokens.body), 'Semantic/surface tokens changed');
  if (theme === 'dark') assert.deepEqual(before.tokens, after.tokens, 'Dark tokens changed');
  assert.equal(after.tokens.body['--ui-muted'], theme === 'dark' ? '#94a3b8' : '#475569');
  assert.equal(after.tokens.root['--wb-secondary-copy'], after.tokens.body['--ui-muted']);
  const expectedControls = before.controls.map(row => ({ ...row,
    color: theme !== 'dark' && row.color === original ? light : row.color }));
  assert.deepEqual(expectedControls, after.controls, 'Non-secondary button colors/backgrounds/typography changed');
  assert.equal(before.samples.length, after.samples.length);
  for (let i = 0; i < before.samples.length; i++) {
    const a = before.samples[i], b = after.samples[i];
    for (const key of ['selector', 'index', 'background', 'effectiveBackground', 'fontSize', 'lineHeight', 'fontFamily', 'letterSpacing', 'width', 'height'])
      assert.deepEqual(a[key], b[key], key + ': ' + a.text);
    assert.equal(b.color, theme !== 'dark' && a.color === original ? light : a.color, a.text);
  }
}

async function controls(page) {
  return page.locator('button').evaluateAll(nodes => nodes.filter(n => n.getClientRects().length).map(n => {
    const s = getComputedStyle(n);
    // Unpainted border colors still inherit currentColor; they are not visible control changes.
    const border = ['Top', 'Right', 'Bottom', 'Left'].map(side => {
      const width = s['border' + side + 'Width'], style = s['border' + side + 'Style'];
      return { width, style, color: parseFloat(width) > 0 && !['none', 'hidden'].includes(style) ? s['border' + side + 'Color'] : null };
    });
    return { className: n.className, color: s.color, background: s.backgroundColor, border,
      fontSize: s.fontSize, lineHeight: s.lineHeight, fontFamily: s.fontFamily };
  }));
}
module.exports = { measure, tokens, readable, compare, controls, surfaces, light, dark, original };
