(function () {
  'use strict';

  const KEY = 'trialAdoptionHistory',
    C = window.TrialContract;
  function restore(scenarioRef) {
    const saved = history.state && history.state[KEY];
    if (!saved || saved.scenario_ref !== scenarioRef) return {
      tab: 'delivery',
      status: 'all',
      page: 1,
      size: 20
    };
    C.check(['delivery', 'capacity', 'history', 'adoptions', 'issues', 'tasks', 'unplanned'].includes(saved.tab) && window.TrialAdoptionHistoryAPI.states.includes(saved.status) && Number.isSafeInteger(saved.page) && saved.page > 0 && [10, 20, 50].includes(saved.size) && (!saved.snapshot_ref || /^[A-Za-z0-9_-]{32}$/.test(saved.snapshot_ref)), '采用记录查看状态无法恢复，请明确刷新记录。');
    return saved;
  }
  function remember(scenarioRef, patch) {
    if (!C.ref(scenarioRef)) return;
    const saved = {
      ...restore(scenarioRef),
      ...patch,
      scenario_ref: scenarioRef
    };
    history.replaceState({
      ...history.state,
      [KEY]: saved
    }, '', location.href);
  }
  function initialTab(scenarioRef) {
    try {
      return restore(scenarioRef).tab;
    } catch (_) {
      return 'adoptions';
    }
  }
  function openPlan(scenarioRef, planRef) {
    C.check(C.ref(scenarioRef) && C.ref(planRef));
    const entry = history.state && history.state.workbench;
    const node = document.getElementById('workbench-boot');
    C.check(entry && entry.view === 'trial' && entry.context && entry.context.scenario_ref === scenarioRef && node, '当前工作台导航上下文不可用，未切换到其他方案。');
    const boot = JSON.parse(node.textContent),
      url = new URL(boot.entry_url, location.origin);
    C.check(url.origin === location.origin && Number.isSafeInteger(entry.key), '正式方案导航地址无效。');
    url.searchParams.set('view', 'gantt');
    history.pushState({
      workbench: {
        view: 'gantt',
        context: {
          plan_ref: planRef
        },
        key: entry.key + 1
      }
    }, '', url.pathname + url.search);
    window.dispatchEvent(new PopStateEvent('popstate'));
    // The shell restores scrolling only after its history guard accepts the new entry.
  }
  window.TrialAdoptionHistoryState = {
    restore,
    remember,
    initialTab,
    openPlan
  };
})();
