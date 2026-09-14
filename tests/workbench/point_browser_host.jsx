(function () {
  'use strict';
  let mounted;
  function Host({ spec, initial, asOf }) {
    const [data, setData] = React.useState(initial), [theme, setTheme] = React.useState(spec.theme);
    const [selected, setSelected] = React.useState(null), [query, setQuery] = React.useState('');
    const [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null);
    React.useLayoutEffect(() => { document.documentElement.dataset.theme = theme; }, [theme]);
    window.pointHost = { data, selected, query, kind: spec.kind };
    const commands = { busy, blocked: busy, error, execute: async (intent, token) => {
      setBusy(true); setError(null); const key = window.TrialAPI.reserve();
      try {
        const result = await window.TrialAPI.command(intent, token, key);
        window.TrialAPI.clear(key); setData(result.data); window.pointLastReceipt = result; return true;
      } catch (failure) { setError(failure); throw failure; }
      finally { setBusy(false); }
    }};
    const selectPlan = (task, before) => setSelected({task, before});
    let body;
    if (spec.kind === 'plan') body = <div className="plana plan-workspace"><window.PlanLayout /><div className="plan-main"><div>
      <window.PlanGantt data={data} asOf={asOf} selected={selected} onSelect={selectPlan} query={query} onQuery={setQuery} />
      <window.PlanDetailsUI.ProjectionTables data={data} onBatch={setQuery} onResource={setQuery} /></div>
      <window.PlanDetailsUI.TaskDetail data={data} selected={selected} onSelect={selectPlan} /></div></div>;
    if (spec.kind === 'candidate') body = <div className="plana run-candidate-workspace"><window.RunCandidateControls.Styles />
      <div className="rc-heading"><h2>候选排产结果</h2><input type="search" aria-label="搜索候选工序" value={query} onChange={e => setQuery(e.target.value)} /></div>
      <div className="rc-main"><div><window.RunCandidateGantt data={data} selected={selected} onSelect={setSelected} query={query} />
        <window.RunCandidateGantt.TaskList tasks={window.RunCandidateModel.matching(data.tasks, query)} selected={selected} onSelect={setSelected} planned /></div>
        <window.RunCandidateControls.Detail task={selected} onClose={() => setSelected(null)} /></div></div>;
    if (spec.kind === 'trial') body = <div className="plana trial-workspace"><window.TrialStyles /><div className="tt-main"><div>
      <window.TrialGantt data={data} selected={selected} onSelect={setSelected} /></div>
      <window.TrialDetails data={data} selected={selected} onSelect={setSelected} commands={commands} onEditing={() => {}} onRecheck={() => {}} /></div></div>;
    return <><window.WorkbenchControlStyles /><window.WorkbenchControls /><window.WorkbenchNumberControls /><window.WorkbenchGuardHost />
      <AppShell active="gantt" onNav={() => {}} theme={theme} onToggleTheme={() => setTheme(t => t === 'light' ? 'dark' : 'light')}
        operations showCapsule={false} title={spec.kind === 'trial' ? '计划试调' : spec.kind === 'candidate' ? '候选排产结果' : '计划甘特'}>{body}</AppShell></>;
  }
  window.openPoint = async spec => {
    const response = await fetch(spec.path, {cache: 'no-store'}), payload = await response.json();
    if (!response.ok || !payload.ok || payload.meta.source !== 'production') throw new Error('Real point route failed');
    if (spec.kind === 'plan') window.APSPlanContract.workspace(payload, payload.data.plan.plan_ref);
    if (spec.kind === 'trial') window.TrialContract.workspace(window.TrialContract.envelope(payload));
    if (mounted) mounted.unmount();
    mounted = ReactDOM.createRoot(document.getElementById('point-root'));
    mounted.render(<Host spec={spec} initial={payload.data} asOf={payload.meta.as_of} />);
    return payload;
  };
})();
