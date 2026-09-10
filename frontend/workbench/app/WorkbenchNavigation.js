(function () {
  'use strict';
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const own = (value, key) => Object.prototype.hasOwnProperty.call(value, key);
  const position = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : 0;
  function check(value) {
    if (!value) throw new Error('页面定位信息无效，未自动切换对象或扩大范围。请从侧栏重新打开工作区。');
  }
  function same(left, right) {
    if (left === right) return true;
    if (Array.isArray(left) || Array.isArray(right)) return Array.isArray(left) && Array.isArray(right)
      && left.length === right.length && left.every((value, index) => same(value, right[index]));
    if (!object(left) || !object(right)) return false;
    const keys = Object.keys(left);
    return keys.length === Object.keys(right).length && keys.every(key => own(right, key) && same(left[key], right[key]));
  }
  function view(boot) {
    const values = new URL(location.href).searchParams.getAll('view'); check(values.length <= 1);
    if (location.pathname === boot.trial_url) { check(!values.length || values[0] === 'trial'); return 'trial'; }
    return values.length ? values[0] : 'dashboard';
  }
  function explicit(boot, current) {
    const values = new URL(location.href).searchParams.getAll('nav'); check(values.length <= 1);
    if (!values.length) return null;
    let value;
    try { value = JSON.parse(values[0]); } catch (_) { check(false); }
    check(object(value) && Object.keys(value).length === 3 && value.version === 1 && value.view === current
      && own(boot.titles, value.view) && object(value.context));
    check(same(value, boot.navigation));
    return { raw: values[0], context: boot.navigation.context };
  }
  function read(boot) {
    const current = view(boot), saved = history.state && history.state.workbench;
    check(own(boot.titles, current));
    const target = explicit(boot, current);
    if (target && (!object(saved) || saved.entry_nav !== target.raw)) return { view: current, context: target.context, key: 0, entry_nav: target.raw };
    if (!history.state || !own(history.state, 'workbench')) return { view: current, context: {}, key: 0 };
    check(object(saved) && saved.view === current && object(saved.context)
      && Number.isSafeInteger(saved.key) && saved.key >= 0);
    return saved;
  }
  function href(boot, target) {
    check(own(boot.titles, target));
    if (target === 'trial') return boot.trial_url;
    const url = new URL(boot.entry_url, location.origin); url.searchParams.set('view', target);
    return url.pathname + url.search;
  }
  function auxiliary(state) {
    const result = {};
    Object.keys(state || {}).forEach(key => { if (!['workbench', 'workbenchPages'].includes(key)) result[key] = state[key]; });
    return result;
  }
  function remember(boot, page) {
    const current = read(boot);
    check(current.view === page.view && current.key === page.key);
    const main = document.querySelector('.main-content');
    const saved = { ...current, scroll: { windowTop: position(window.scrollY), windowLeft: position(window.scrollX),
      mainTop: main ? position(main.scrollTop) : 0, mainLeft: main ? position(main.scrollLeft) : 0 } };
    const state = history.state || {};
    check(!own(state, 'workbenchPages') || object(state.workbenchPages));
    const pages = state.workbenchPages || {};
    const nextPages = { ...pages, [page.view]: { ...saved, auxiliary: auxiliary(state) } };
    history.replaceState({ ...state, workbench: saved, workbenchPages: nextPages }, '', location.href);
    return nextPages;
  }
  function navigate(boot, page, target, supplied) {
    check(own(boot.titles, target) && (supplied === undefined || object(supplied)));
    const pages = remember(boot, page), saved = pages[target];
    if (saved !== undefined) check(object(saved) && saved.view === target && object(saved.context));
    const context = supplied === undefined && saved ? saved.context : supplied || {};
    const scroll = object(context.scroll) ? context.scroll : supplied === undefined && saved ? saved.scroll : {};
    const next = { view: target, context, key: page.key + 1, scroll };
    const extra = supplied === undefined && saved && object(saved.auxiliary) ? saved.auxiliary : {};
    history.pushState({ ...extra, workbench: next, workbenchPages: pages }, '', href(boot, target));
    return next;
  }
  function replaceContext(boot, page, context) {
    check(object(context));
    const current = read(boot); check(current.view === page.view && current.key === page.key);
    history.replaceState({ ...history.state, workbench: { ...current, context } }, '', location.href);
  }
  function restore(page, done) {
    const scroll = page.scroll || {}, started = performance.now();
    let frame = 0, stopped = false;
    function cancel() {
      if (stopped) return;
      stopped = true; cancelAnimationFrame(frame);
      ['wheel', 'touchstart', 'keydown', 'pointerdown'].forEach(name => window.removeEventListener(name, cancel, true));
      done();
    }
    function apply() {
      if (stopped) return;
      const main = document.querySelector('.main-content');
      const top = position(scroll.windowTop), left = position(scroll.windowLeft), mainTop = position(scroll.mainTop), mainLeft = position(scroll.mainLeft);
      window.scrollTo(left, top);
      if (main) { main.scrollTop = mainTop; main.scrollLeft = mainLeft; }
      const reached = Math.abs(window.scrollY - top) <= 1 && Math.abs(window.scrollX - left) <= 1
        && (!main || Math.abs(main.scrollTop - mainTop) <= 1 && Math.abs(main.scrollLeft - mainLeft) <= 1);
      if (reached || performance.now() - started >= 3000) cancel();
      else frame = requestAnimationFrame(apply);
    }
    ['wheel', 'touchstart', 'keydown', 'pointerdown'].forEach(name => window.addEventListener(name, cancel, true));
    frame = requestAnimationFrame(() => { frame = requestAnimationFrame(apply); });
    return cancel;
  }
  window.WorkbenchNavigation = { read, href, remember, navigate, replaceContext, restore };
})();
