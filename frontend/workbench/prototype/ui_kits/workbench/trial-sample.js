(function () {
  'use strict';
  const api = window.APSTrialSample, views = window.APSTrialViews;
  const root = document.getElementById('trial-root'), modalRoot = document.getElementById('trial-modal-root');
  const key = 'aps_trial_sample_v1';
  const clone = value => JSON.parse(JSON.stringify(value));
  const initial = () => ({ selected: 'balanced', adopted: clone(api.scenarios.find(s => s.id === 'base')), version: 15,
    taskId: api.scenarios[0].tasks.find(t => !t.locked).id, draft: null, history: [], view: 'resource',
    showBaseline: true, changedOnly: false, search: '', tab: 'impact', theme: document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light', editor: null, expanded: false, notice: '', error: '' });
  let state = initial(), modalKind = null, lastFocus = null, themeError = '';
  const samePlan = (a, b) => a.tasks.length === b.tasks.length && a.tasks.every(t => {
    const other = b.tasks.find(x => x.id === t.id);
    return other && views.sameTask(t, other);
  });
  function selected() {
    const result = state.selected === 'adopted' ? state.adopted
      : state.selected === 'draft' ? state.draft : api.scenarios.find(s => s.id === state.selected);
    if (!result) throw new Error('当前候选方案不存在。');
    return result;
  }
  function viewModel() {
    const scenario = selected(), task = scenario.tasks.find(t => t.id === state.taskId);
    if (!task) throw new Error('选中工序不在当前方案中。');
    const inspection = api.inspect(scenario, api.scenarios.find(s => s.id === 'base'));
    return { scenario, task, report: inspection.report,
      issues: inspection.issues, isAdopted: samePlan(scenario, state.adopted), samePlan };
  }
  function restore() {
    const theme = state.theme;
    try {
      const raw = localStorage.getItem(key);
      if (!raw) return;
      const saved = JSON.parse(raw);
      if (saved.schema !== 1 || !Number.isInteger(saved.version) || saved.version < 15 || !Array.isArray(saved.history)
          || !['resource', 'batch'].includes(saved.view) || !['impact', 'history'].includes(saved.tab)
          || !['light', 'dark'].includes(saved.theme) || typeof saved.search !== 'string'
          || typeof saved.showBaseline !== 'boolean' || typeof saved.changedOnly !== 'boolean'
          || !saved.adopted || api.validate(saved.adopted.tasks).length) throw new Error('保存记录的结构或已采用计划无效。');
      if (saved.draft) api.inspect(saved.draft);
      if (!saved.history.every(r => Number.isInteger(r.version) && typeof r.name === 'string' && typeof r.person === 'string'
          && typeof r.reason === 'string' && typeof r.at === 'string' && typeof r.previous === 'string' && Number.isInteger(r.changed))) throw new Error('采用记录不完整。');
      state = Object.assign(initial(), saved, { theme, editor: null, expanded: false, error: '', notice: '' });
      viewModel();
    } catch (error) {
      state = initial();
      state.error = '本地记录无法恢复：' + error.message + ' 当前显示初始样例，未覆盖原记录；可用“重置样板”清除本样板记录。';
    }
  }
  function persist() {
    try {
      const saved = Object.assign({}, state, { schema: 1 });
      delete saved.editor; delete saved.expanded; delete saved.notice; delete saved.error;
      localStorage.setItem(key, JSON.stringify(saved));
      return true;
    } catch (error) {
      state.error = '本地保存失败：' + error.message + '。本次修改仅在当前页面有效。';
      return false;
    }
  }
  function render() {
    document.documentElement.dataset.theme = state.theme;
    root.innerHTML = views.render(Object.assign({}, state, { error: [state.error, themeError].filter(Boolean).join(' ') }), viewModel());
  }
  function applyTheme(theme) {
    const hadError = !!themeError;
    state.theme = theme === 'dark' ? 'dark' : 'light'; themeError = '';
    document.documentElement.dataset.theme = state.theme;
    if (hadError) render();
    const button = root.querySelector('[data-action="theme"]');
    if (button) button.textContent = '深色：' + (state.theme === 'dark' ? '开' : '关');
  }
  function syncTheme(event) {
    if (event.type === 'storage' && event.key !== 'aps_kit_theme' && event.key !== null) return;
    try { applyTheme(localStorage.getItem('aps_kit_theme')); }
    catch (error) { console.error('读取主题偏好失败：', error); }
  }
  function update(patch, save = true) {
    Object.assign(state, { error: '', notice: '' }, patch);
    if (save) persist();
    render();
  }
  function requireEditorResolved() {
    if (!state.editor) return true;
    state.error = '请先保存试调或取消当前工序编辑，再切换查看对象。';
    render();
    return false;
  }
  function focusAction(action) {
    const target = root.querySelector('[data-action="' + action + '"]');
    if (target) target.focus({ preventScroll: true });
  }
  function openModal(kind) {
    modalKind = kind; lastFocus = document.activeElement;
    modalRoot.innerHTML = views.modal(kind, state, viewModel());
    root.setAttribute('inert', '');
    root.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = 'hidden';
    const target = modalRoot.querySelector('input, textarea') || modalRoot.querySelector('button');
    target.focus();
  }
  function closeModal() {
    modalRoot.innerHTML = ''; modalKind = null;
    root.removeAttribute('inert'); root.removeAttribute('aria-hidden');
    document.body.style.overflow = '';
    if (lastFocus && lastFocus.isConnected) lastFocus.focus({ preventScroll: true });
    else focusAction('adopt');
  }
  function download() {
    let url;
    try {
      const content = api.csv(selected(), api.scenarios.find(s => s.id === 'base'));
      url = URL.createObjectURL(new Blob([content], { type: 'text/csv;charset=utf-8' }));
      const link = document.createElement('a'); link.href = url;
      link.download = '方案试调对比-' + selected().name + '.csv';
      document.body.appendChild(link); link.click(); link.remove();
      update({ notice: '已生成当前预览的 CSV 对比，仅包含示例数据。' }, false);
    } catch (error) { update({ error: '导出失败：' + error.message }, false); }
    finally { if (url) window.setTimeout(() => URL.revokeObjectURL(url), 1000); }
  }
  root.addEventListener('focusin', event => views.revealTask(event.target));
  root.addEventListener('click', event => {
    const link = event.target.closest('a');
    if (link && state.editor) { event.preventDefault(); requireEditorResolved(); return; }
    const target = event.target.closest('button');
    if (!target || target.disabled) return;
    const action = target.dataset.action;
    if (target.dataset.task && requireEditorResolved()) {
      const board = target.closest('.tr-board'), position = { left: board.scrollLeft, top: board.scrollTop };
      update({ taskId: target.dataset.task });
      views.focusTask(root, target.dataset.task, position);
      return;
    }
    if (target.dataset.batch && requireEditorResolved()) {
      const task = selected().tasks.find(t => t.batch === target.dataset.batch);
      update({ taskId: task.id });
      views.focusTask(root, task.id);
      return;
    }
    if (target.dataset.view) return update({ view: target.dataset.view });
    if (target.dataset.tab) return update({ tab: target.dataset.tab });
    if (action === 'theme') {
      const next = state.theme === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem('aps_kit_theme', next); applyTheme(next); }
      catch (error) { themeError = '主题偏好保存失败：' + error.message + '；当前主题未改变。'; render(); focusAction('theme'); }
      return;
    }
    if (action === 'expand') return update({ expanded: !state.expanded }, false);
    if (action === 'export') return download();
    if (action === 'reset' || action === 'discard') return openModal(action);
    if (action === 'adopt') {
      const vm = viewModel();
      if (vm.issues.length || vm.isAdopted || state.editor) return;
      return openModal('adopt');
    }
    if (action === 'edit') {
      const task = viewModel().task;
      if (task.locked) return;
      update({ editor: { taskId: task.id, resource: task.resource, start: task.start } }, false);
      root.querySelector('#tr-edit-form select').focus();
    }
    if (action === 'cancel-edit') { update({ editor: null }, false); focusAction('edit'); }
  });
  window.addEventListener('storage', syncTheme);
  window.addEventListener('pageshow', syncTheme);
  window.addEventListener('focus', syncTheme);
  root.addEventListener('change', event => {
    const t = event.target;
    if (t.name === 'scheme') {
      if (requireEditorResolved()) update({ selected: t.value });
    }
    if (t.name === 'baseline') update({ showBaseline: t.checked });
    if (t.name === 'changed') update({ changedOnly: t.checked });
    if (state.editor && t.closest('#tr-edit-form')) state.editor[t.name] = t.value;
  });
  root.addEventListener('input', event => {
    const t = event.target;
    if (state.editor && t.closest('#tr-edit-form')) state.editor[t.name] = t.value;
    if (t.name !== 'search') return;
    const cursor = t.selectionStart;
    update({ search: t.value });
    const input = root.querySelector('[name="search"]');
    input.focus({ preventScroll: true }); input.setSelectionRange(cursor, cursor);
  });
  root.addEventListener('submit', event => {
    if (event.target.id !== 'tr-edit-form') return;
    event.preventDefault();
    try {
      const fields = Object.fromEntries(new FormData(event.target));
      const draft = api.adjust(selected(), state.editor.taskId, fields);
      draft.name = '手工试调'; draft.recommended = false; draft.changeovers = null;
      draft.summary = '已调整所选工序的时段或资源，批次完工按当前工序安排重新汇总。';
      draft.tradeoff = '前后序不自动移动；采用前需通过资源、工艺、日历和固定工序检查。';
      const issues = api.validate(draft.tasks);
      update({ draft, selected: 'draft', editor: null, notice: issues.length ? '试调草稿已保留；发现 ' + issues.length + ' 项约束冲突，不能采用。' : '试调草稿已保留，当前约束检查通过；正式计划未改变。' });
      focusAction('edit');
    } catch (error) { update({ error: '试调失败：' + error.message }, false); }
  });
  modalRoot.addEventListener('click', event => {
    const t = event.target.closest('[data-action="close-modal"]');
    if (t) closeModal();
  });
  modalRoot.addEventListener('submit', event => {
    event.preventDefault();
    try {
      if (modalKind === 'adopt') {
        const data = Object.fromEntries(new FormData(event.target));
        if (!data.person.trim() || !data.reason.trim()) throw new Error('请填写确认人和采用说明。');
        const vm = viewModel();
        if (vm.issues.length || vm.isAdopted) throw new Error('当前方案状态已变化，请关闭确认窗口重新核对。');
        const delta = api.evaluate(vm.scenario, state.adopted);
        const next = state.version + 1;
        state.history.push({ version: next, name: vm.scenario.name, person: data.person.trim(), reason: data.reason.trim(),
          at: new Date().toLocaleString('zh-CN', { hour12: false }), previous: state.adopted.name, changed: delta.changedOperations });
        update({ version: next, adopted: clone(vm.scenario), tab: 'history', notice: '本地示例已采用 v' + next + ' · ' + vm.scenario.name + '。初始基线与采用记录已保留。' });
      } else if (modalKind === 'reset') {
        const theme = state.theme;
        state = initial(); state.theme = theme;
        update({ notice: '样板已恢复为初始计划 v15。' });
      } else if (modalKind === 'discard') {
        const preset = api.scenarios.find(s => samePlan(s, state.adopted));
        update({ draft: null, selected: preset ? preset.id : 'adopted', editor: null, notice: '试调草稿已放弃；正式采用的计划快照未改变。' });
      }
      closeModal();
    } catch (error) {
      const notice = modalRoot.querySelector('#tr-modal-error');
      notice.hidden = false; notice.textContent = error.message;
    }
  });
  document.addEventListener('keydown', event => {
    if (modalKind) {
      if (event.key === 'Escape') { event.preventDefault(); closeModal(); }
      if (event.key === 'Tab') {
        const items = Array.from(modalRoot.querySelectorAll('button,input,textarea')).filter(e => !e.disabled);
        const first = items[0], last = items[items.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
      return;
    }
    if (event.key === 'Escape' && state.expanded) update({ expanded: false }, false);
    if (event.target.matches('[role="tab"]') && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const tab = event.key === 'Home' ? 'impact' : event.key === 'End' ? 'history' : state.tab === 'impact' ? 'history' : 'impact';
      update({ tab }); root.querySelector('[data-tab="' + tab + '"]').focus();
    }
  });
  window.addEventListener('beforeunload', event => { if (state.editor) { event.preventDefault(); event.returnValue = ''; } });
  window.addEventListener('beforeprint', () => { document.documentElement.dataset.theme = 'light'; });
  window.addEventListener('afterprint', () => { document.documentElement.dataset.theme = state.theme; });
  try { restore(); render(); }
  catch (error) { root.innerHTML = '<p class="tr-error" role="alert">样板加载失败：' + views.esc(error.message) + '</p>'; }
})();
