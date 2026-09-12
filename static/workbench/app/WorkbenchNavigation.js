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
    if (Array.isArray(left) || Array.isArray(right)) return Array.isArray(left) && Array.isArray(right) && left.length === right.length && left.every((value, index) => same(value, right[index]));
    if (!object(left) || !object(right)) return false;
    const keys = Object.keys(left);
    return keys.length === Object.keys(right).length && keys.every(key => own(right, key) && same(left[key], right[key]));
  }
  function validateBoot(boot) {
    const icons = ['box', 'database', 'play', 'home', 'gantt', 'chart', 'users', 'clipboard', 'file', 'grid', 'settings', 'scale'];
    check(object(boot.titles) && Array.isArray(boot.enabled_views) && boot.enabled_views.length > 0 && new Set(boot.enabled_views).size === boot.enabled_views.length && boot.enabled_views.every(id => typeof id === 'string' && typeof boot.titles[id] === 'string') && Object.keys(boot.titles).every(id => boot.enabled_views.includes(id)));
    check(Array.isArray(boot.nav_groups) && boot.nav_groups.length > 0 && object(boot.view_aliases));
    const seen = new Set(),
      groups = new Set();
    boot.nav_groups.forEach(group => {
      check(object(group) && typeof group.title === 'string' && group.title.trim() && !groups.has(group.title) && Array.isArray(group.items) && group.items.length > 0);
      groups.add(group.title);
      const groupIcons = new Set();
      group.items.forEach(item => {
        check(object(item) && boot.enabled_views.includes(item.id) && !seen.has(item.id) && item.label === boot.titles[item.id] && icons.includes(item.icon) && !groupIcons.has(item.icon));
        seen.add(item.id);
        groupIcons.add(item.icon);
      });
    });
    Object.keys(boot.view_aliases).forEach(id => check(boot.enabled_views.includes(id) && !seen.has(id) && seen.has(boot.view_aliases[id])));
    check(boot.enabled_views.every(id => seen.has(id) || own(boot.view_aliases, id)));
    check(typeof boot.help_url === 'string' && boot.help_url.startsWith('/') && !boot.help_url.startsWith('//') && new URL(boot.help_url, location.origin).origin === location.origin);
  }
  function historyView(page) {
    const context = page.context || {};
    return ['analysis', 'gantt', 'delay'].includes(page.view) && context.source === 'run_history' && !own(context, 'run_ref') && !own(context, 'candidate_ref');
  }
  function title(boot, page) {
    if (historyView(page)) return '排产历史';
    return boot.titles[page.view] || '工作区不存在';
  }
  function view(boot) {
    const values = new URL(location.href).searchParams.getAll('view');
    check(values.length <= 1);
    if (location.pathname === boot.trial_url) {
      check(!values.length || values[0] === 'trial');
      return 'trial';
    }
    return values.length ? values[0] : 'dashboard';
  }
  function explicit(boot, current) {
    const values = new URL(location.href).searchParams.getAll('nav');
    check(values.length <= 1);
    if (!values.length) return null;
    let value;
    try {
      value = JSON.parse(values[0]);
    } catch (_) {
      check(false);
    }
    check(object(value) && Object.keys(value).length === 3 && value.version === 1 && value.view === current && own(boot.titles, value.view) && object(value.context));
    check(same(value, boot.navigation));
    return {
      raw: values[0],
      context: boot.navigation.context
    };
  }
  function read(boot) {
    const current = view(boot),
      saved = history.state && history.state.workbench;
    check(own(boot.titles, current));
    const target = explicit(boot, current);
    if (target && (!object(saved) || saved.entry_nav !== target.raw)) return {
      view: current,
      context: target.context,
      key: 0,
      entry_nav: target.raw
    };
    if (!history.state || !own(history.state, 'workbench')) return {
      view: current,
      context: {},
      key: 0
    };
    check(object(saved) && saved.view === current && object(saved.context) && Number.isSafeInteger(saved.key) && saved.key >= 0);
    return saved;
  }
  function href(boot, target) {
    check(own(boot.titles, target));
    if (target === 'trial') return boot.trial_url;
    const url = new URL(boot.entry_url, location.origin);
    url.searchParams.set('view', target);
    return url.pathname + url.search;
  }
  function helpUrl(boot, page) {
    // The manual page renders its "返回" link from src; without it help exits the shell with no way back.
    const url = new URL(boot.help_url, location.origin);
    url.searchParams.set('src', href(boot, page.view));
    return url.pathname + url.search;
  }
  function auxiliary(state) {
    const result = {};
    Object.keys(state || {}).forEach(key => {
      if (!['workbench', 'workbenchPages'].includes(key)) result[key] = state[key];
    });
    return result;
  }
  function remember(boot, page) {
    const current = read(boot);
    check(current.view === page.view && current.key === page.key);
    const main = document.querySelector('.main-content');
    const saved = {
      ...current,
      scroll: {
        windowTop: position(window.scrollY),
        windowLeft: position(window.scrollX),
        mainTop: main ? position(main.scrollTop) : 0,
        mainLeft: main ? position(main.scrollLeft) : 0
      }
    };
    const state = history.state || {};
    check(!own(state, 'workbenchPages') || object(state.workbenchPages));
    const pages = state.workbenchPages || {};
    const nextPages = {
      ...pages,
      [page.view]: {
        ...saved,
        auxiliary: auxiliary(state)
      }
    };
    history.replaceState({
      ...state,
      workbench: saved,
      workbenchPages: nextPages
    }, '', location.href);
    return nextPages;
  }
  function navigate(boot, page, target, supplied, preferSaved = false) {
    check(own(boot.titles, target) && (supplied === undefined || object(supplied)) && typeof preferSaved === 'boolean');
    const pages = remember(boot, page),
      saved = pages[target];
    if (saved !== undefined) check(object(saved) && saved.view === target && object(saved.context));
    const resume = saved && (supplied === undefined || preferSaved);
    // Resuming restores the target's own view state wholesale (scope, topic, table, selection, scroll):
    // every tab keeps its own range and the supplied context only seeds a first visit. Mixing the
    // current tab's scope / topic into the target's saved table produced unreadable combinations.
    const context = resume ? saved.context : supplied || {};
    const scroll = object(context.scroll) ? context.scroll : resume ? saved.scroll : {};
    const next = {
      view: target,
      context,
      key: page.key + 1,
      scroll
    };
    const extra = resume && object(saved.auxiliary) ? saved.auxiliary : {};
    history.pushState({
      ...extra,
      workbench: next,
      workbenchPages: pages
    }, '', href(boot, target));
    return next;
  }
  function replaceContext(boot, page, context) {
    check(object(context));
    const current = read(boot);
    check(current.view === page.view && current.key === page.key);
    history.replaceState({
      ...history.state,
      workbench: {
        ...current,
        context
      }
    }, '', location.href);
  }
  function restore(page, done) {
    const scroll = page.scroll || {},
      started = performance.now();
    let frame = 0,
      stopped = false;
    function cancel() {
      if (stopped) return;
      stopped = true;
      cancelAnimationFrame(frame);
      ['wheel', 'touchstart', 'keydown', 'pointerdown'].forEach(name => window.removeEventListener(name, cancel, true));
      done();
    }
    function apply() {
      if (stopped) return;
      const main = document.querySelector('.main-content');
      const top = position(scroll.windowTop),
        left = position(scroll.windowLeft),
        mainTop = position(scroll.mainTop),
        mainLeft = position(scroll.mainLeft);
      window.scrollTo(left, top);
      if (main) {
        main.scrollTop = mainTop;
        main.scrollLeft = mainLeft;
      }
      const reached = Math.abs(window.scrollY - top) <= 1 && Math.abs(window.scrollX - left) <= 1 && (!main || Math.abs(main.scrollTop - mainTop) <= 1 && Math.abs(main.scrollLeft - mainLeft) <= 1);
      if (reached || performance.now() - started >= 3000) cancel();else frame = requestAnimationFrame(apply);
    }
    ['wheel', 'touchstart', 'keydown', 'pointerdown'].forEach(name => window.addEventListener(name, cancel, true));
    frame = requestAnimationFrame(() => {
      frame = requestAnimationFrame(apply);
    });
    return cancel;
  }
  function guardHistory(boot, {
    hasDirty,
    confirmLeave,
    onRestore,
    onError
  }) {
    let accepted,
      pending = null,
      disposed = false;
    function capture() {
      return {
        page: read(boot),
        state: history.state,
        url: location.href
      };
    }
    function sync() {
      if (!pending) accepted = capture();
    }
    sync();
    function recover(error) {
      pending = null;
      history.replaceState(accepted.state, '', accepted.url);
      onError(error);
    }
    function accept() {
      pending = null;
      accepted = capture();
      onRestore();
    }
    function confirm(entry) {
      entry.phase = 'confirm';
      Promise.resolve().then(confirmLeave).then(allowed => {
        if (disposed || pending !== entry) return;
        if (!allowed) {
          pending = null;
          return;
        }
        entry.phase = 'replay';
        history.go(entry.delta);
      }).catch(error => {
        if (!disposed && pending === entry) recover(error);
      });
    }
    function pop() {
      if (disposed) return;
      try {
        const target = read(boot),
          delta = target.key - accepted.page.key;
        if (pending) {
          if (pending.phase === 'replay' && target.key === pending.target.key && location.href === pending.url) {
            accept();
            return;
          }
          if (target.key === accepted.page.key && location.href === accepted.url) {
            if (pending.phase === 'return') confirm(pending);
            return;
          }
          check(delta !== 0);
          history.go(-delta);
          return;
        }
        if (!hasDirty()) {
          accept();
          return;
        }
        check(delta !== 0);
        pending = {
          phase: 'return',
          delta,
          target,
          url: location.href
        };
        history.go(-delta);
      } catch (error) {
        recover(error);
      }
    }
    window.addEventListener('popstate', pop);
    return {
      sync,
      busy: () => !!pending,
      dispose: () => {
        disposed = true;
        window.removeEventListener('popstate', pop);
      }
    };
  }
  window.WorkbenchNavigation = {
    read,
    href,
    helpUrl,
    remember,
    navigate,
    replaceContext,
    restore,
    validateBoot,
    title,
    historyView,
    guardHistory
  };
})();
