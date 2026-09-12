(function () {
  'use strict';
  // Sticky table columns cover neighbouring cells. The flags set here let CSS draw a shadow only while
  // something is actually hidden under the column, so a table that fits shows no shadow at all.
  const SELECTOR = '.wb-table-frame', EPSILON = 1;
  function flag(frame, name, on) {
    if (on) { if (!frame.hasAttribute(name)) frame.setAttribute(name, ''); }
    else if (frame.hasAttribute(name)) frame.removeAttribute(name);
  }
  function update(frame) {
    if (!frame || !frame.isConnected) return;
    const hidden = frame.scrollWidth - frame.clientWidth - frame.scrollLeft;
    flag(frame, 'data-overflow-left', frame.scrollLeft > EPSILON);
    flag(frame, 'data-overflow-right', hidden > EPSILON);
  }
  function frames(node) {
    if (!node || node.nodeType !== 1) return [];
    const found = node.matches(SELECTOR) ? [node] : [];
    return found.concat(Array.from(node.querySelectorAll(SELECTOR)));
  }
  function attach(container) {
    if (!container || typeof container.querySelectorAll !== 'function') throw new TypeError('WorkbenchScrollShadows.attach needs a container element');
    const registered = new Map();
    const resize = new ResizeObserver(entries => {
      for (const entry of entries) update(entry.target.matches(SELECTOR) ? entry.target : entry.target.closest(SELECTOR));
    });
    const register = frame => {
      if (registered.has(frame)) return;
      const scroll = () => update(frame);
      frame.addEventListener('scroll', scroll, { passive: true });
      resize.observe(frame);
      const table = frame.querySelector('table');
      if (table) resize.observe(table);
      registered.set(frame, () => {
        frame.removeEventListener('scroll', scroll); resize.unobserve(frame); if (table) resize.unobserve(table);
        frame.removeAttribute('data-overflow-left'); frame.removeAttribute('data-overflow-right');
      });
      update(frame);
    };
    const release = frame => { const dispose = registered.get(frame); if (dispose) { dispose(); registered.delete(frame); } };
    const mutations = new MutationObserver(records => {
      for (const record of records) {
        record.removedNodes.forEach(node => frames(node).forEach(release));
        record.addedNodes.forEach(node => frames(node).forEach(register));
      }
    });
    frames(container).forEach(register);
    mutations.observe(container, { childList: true, subtree: true });
    return () => { mutations.disconnect(); Array.from(registered.keys()).forEach(release); resize.disconnect(); };
  }
  window.WorkbenchScrollShadows = Object.freeze({ attach, update });
})();
