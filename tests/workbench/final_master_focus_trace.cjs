'use strict';
const assert = require('node:assert/strict');

async function observeFocus(page, probe, target, name) {
  const owner = await target.elementHandle(); assert(owner);
  await page.evaluate(owner => {
    const events = [], text = owner.textContent;
    const describe = node => node && ({tag: node.tagName, class: node.className, role: node.getAttribute('role'),
      label: node.getAttribute('aria-label'), text: node.tagName === 'BODY' ? undefined : node.textContent.slice(0, 150)});
    const snapshot = () => ({owner_connected: owner.isConnected, owner_disabled: owner.disabled,
      same_trigger: [...document.querySelectorAll('[data-batch-workspace] button')].find(node => node.textContent === text) === owner,
      owner_focused: document.activeElement === owner, active: describe(document.activeElement),
      dialogs: [...document.querySelectorAll('[role="dialog"]')].map(node => ({...describe(node), visible: !!node.getClientRects().length,
        contains_focus: node.contains(document.activeElement)}))});
    const initial = snapshot();
    const capture = event => events.push({type: event.type, at: performance.now(), utc: new Date().toISOString(), key: event.key,
      trusted: event.isTrusted, target: describe(event.target), related: describe(event.relatedTarget), snapshot: snapshot()});
    const names = ['pointerdown', 'pointerup', 'focusin', 'focusout', 'keydown'];
    names.forEach(name => document.addEventListener(name, capture, true));
    const observer = new MutationObserver(records => {
      const values = records.filter(row => row.type === 'childList' || row.target === owner);
      if (values.length) events.push({type: 'mutation', at: performance.now(), utc: new Date().toISOString(),
        owner_attributes: values.filter(row => row.target === owner).map(row => row.attributeName), snapshot: snapshot()});
    });
    observer.observe(document.querySelector('[data-batch-workspace]'), {subtree: true, childList: true, attributes: true, attributeFilter: ['disabled']});
    window.finalMasterFocusTrace = () => { names.forEach(name => document.removeEventListener(name, capture, true)); observer.disconnect();
      return {initial, events, final: snapshot()}; };
  }, owner);
  await owner.dispose();
  return async () => {
    const evidence = await page.evaluate(() => window.finalMasterFocusTrace());
    probe.report.focus_restore = (probe.report.focus_restore || []).concat({variant: probe.variant, name, evidence});
  };
}

module.exports = {observeFocus};
