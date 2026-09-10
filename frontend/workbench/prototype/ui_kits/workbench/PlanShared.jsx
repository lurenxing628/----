const PLAN_UI = { view: 'resource', search: '', showBaseline: true, changedOnly: false, tab: 'impact', expanded: false };
function usePlanWorkspace() {
  const [, refresh] = React.useReducer(n => n + 1, 0), [error, setError] = React.useState('');
  React.useEffect(() => {
    const update = () => refresh();
    window.addEventListener('aps-plan-change', update); window.addEventListener('storage', update);
    return () => { window.removeEventListener('aps-plan-change', update); window.removeEventListener('storage', update); };
  }, []);
  const api = window.APSPlanWorkbench, saved = api.read(window.localStorage);
  const mutate = action => { try { action(); setError(''); window.dispatchEvent(new Event('aps-plan-change')); return true; } catch (e) { setError('操作未保存：' + e.message); return false; } };
  const save = patch => mutate(() => api.save(window.localStorage, patch));
  const state = Object.assign({}, saved, PLAN_UI), vm = api.viewModel(saved);
  const setUI = patch => { Object.assign(PLAN_UI, patch); refresh(); };
  return { saved, state, vm, error: error || saved.error, save, mutate, setUI };
}
function PlanContextBar({ plan, onNav, detail = false }) {
  const { saved, vm, save } = plan, { ControlButton: Button } = window.APSWorkbenchUI;
  const choices = window.APSTrialSample.scenarios.concat(saved.draft ? [saved.draft] : []);
  if (!choices.some(s => window.APSPlanWorkbench.same(s, saved.adopted))) choices.push({ ...saved.adopted, id: 'adopted' });
  return <div className="pw-context">
    <label>查看方案 <select aria-label="查看方案" value={saved.selected} onChange={e => save({ selected: e.target.value })}>{choices.map(s => <option key={s.id} value={s.id}>{s.name}{window.APSPlanWorkbench.same(s, saved.adopted) ? ' · 已采用' : ''}</option>)}</select></label>
    <span className="tr-status">{vm.isAdopted ? '正式采用 v' + saved.version : '候选预览 · 未采用'}</span><span className="muted">09-08 至 09-09 · 4 批 / 8 道工序</span>
    <div className="pw-actions">{detail && <Button size="sm" onClick={() => onNav('analysis')}>返回方案对比</Button>}<a className="tr-button" href="trial-sample.html">方案试调</a></div>
  </div>;
}
function PlanError({ error }) { return error ? <div className="tr-error" role="alert">{error}</div> : null; }
function PlanTimeline({ plan }) {
  const { state, vm, save, setUI } = plan;
  const root = React.useRef(null), selection = React.useRef(null);
  const html = window.APSTrialViews.timeline({ ...state, allowPerson: true }, vm);
  React.useLayoutEffect(() => {
    const pending = selection.current; selection.current = null;
    if (pending) window.APSTrialViews.focusTask(root.current, pending.id, pending.position);
  });
  return <div ref={root} className="pw-timeline" onFocus={event => window.APSTrialViews.revealTask(event.target)} onClick={event => {
    if (event.target.name === 'baseline') { setUI({ showBaseline: event.target.checked }); return; }
    if (event.target.name === 'changed') { setUI({ changedOnly: event.target.checked }); return; }
    const button = event.target.closest('button'); if (!button) return;
    if (button.dataset.task) {
      const board = button.closest('.tr-board');
      selection.current = { id: button.dataset.task, position: { left: board.scrollLeft, top: board.scrollTop } };
      if (!save({ taskId: button.dataset.task })) selection.current = null;
    }
    if (button.dataset.view) setUI({ view: button.dataset.view });
    if (button.dataset.action === 'expand') setUI({ expanded: !state.expanded });
  }} onInput={event => {
    if (event.target.name !== 'search') return;
    const value = event.target.value, cursor = event.target.selectionStart;
    setUI({ search: value });
    requestAnimationFrame(() => { const input = document.querySelector('.pw-timeline [name="search"]'); if (input) { input.focus({ preventScroll: true }); input.setSelectionRange(cursor, cursor); } });
  }} dangerouslySetInnerHTML={{ __html: html }} />;
}
function PlanAdopt({ plan }) {
  const dialog = React.useRef(null), opener = React.useRef(null), [message, setMessage] = React.useState('');
  const { ControlButton: Button } = window.APSWorkbenchUI, { vm, saved, mutate } = plan;
  const close = () => { dialog.current.close(); if (opener.current) opener.current.focus(); };
  return <><Button variant="primary" disabled={!!plan.error || vm.isAdopted || vm.issues.length > 0} onClick={e => { opener.current = e.currentTarget; setMessage(''); dialog.current.showModal(); }}>采用此方案</Button>
    <dialog ref={dialog} className="pw-dialog" onCancel={() => { if (opener.current) opener.current.focus(); }} aria-labelledby="pw-adopt-title"><form onSubmit={e => {
      e.preventDefault(); const values = new FormData(e.currentTarget);
      if (mutate(() => window.APSPlanWorkbench.adopt(window.localStorage, values.get('person'), values.get('reason')))) { setMessage('本地示例已采用，记录已保留。'); e.currentTarget.reset(); close(); }
    }}><h3 id="pw-adopt-title">采用 {vm.scenario.name}</h3><p>将本地正式示例更新为 v{saved.version + 1}，保留原始基线及采用历史。不写入生产计划。</p>
      <label>确认人<input name="person" required maxLength={40} /></label><label>采用说明<textarea name="reason" required maxLength={300} /></label><PlanError error={plan.error} />
      <div className="pw-actions"><Button onClick={close}>取消</Button><button className="tr-button primary" type="submit">确认采用</button></div>
    </form></dialog>{message && <span role="status">{message}</span>}</>;
}
function planDownload(plan) {
  plan.mutate(() => {
    const url = URL.createObjectURL(new Blob([window.APSTrialSample.csv(plan.vm.scenario)], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = '排产方案-' + plan.vm.scenario.name + '.csv'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
}
