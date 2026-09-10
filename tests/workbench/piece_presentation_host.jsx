(function () {
  'use strict';
  let mounted;
  function Host({ spec, data }) {
    const [selected, setSelected] = React.useState(null), [query, setQuery] = React.useState('');
    React.useLayoutEffect(() => { document.documentElement.dataset.theme = spec.theme; }, []);
    window.pieceHost = { data, selected, query, kind: spec.kind };
    const selectPlan = (task, before) => setSelected({ task, before });
    let body;
    if (spec.kind === 'plan' || spec.kind === 'old') body = <div className="plana plan-workspace"><window.PlanLayout /><div className="plan-main"><div>
      <window.PlanGantt data={data} selected={selected} onSelect={selectPlan} query={query} onQuery={setQuery} /></div>
      <window.PlanDetailsUI.TaskDetail data={data} selected={selected} onSelect={selectPlan} /></div></div>;
    if (spec.kind === 'candidate') body = <div className="plana run-candidate-workspace"><window.RunCandidateControls.Styles />
      <div className="rc-heading"><h2>候选排产结果</h2><input type="search" aria-label="搜索候选工序" value={query} onChange={e => setQuery(e.target.value)} /></div>
      <div className="rc-main"><div><window.RunCandidateGantt data={data} selected={selected} onSelect={setSelected} query={query} />
        <window.RunCandidateGantt.TaskList tasks={window.RunCandidateModel.matching(data.tasks, query)} selected={selected} onSelect={setSelected} planned /></div>
        <window.RunCandidateControls.Detail task={selected} onClose={() => setSelected(null)} /></div></div>;
    if (spec.kind === 'trial') body = <div className="plana trial-workspace"><window.TrialStyles /><div className="tt-main"><div>
      <window.TrialGantt data={data} selected={selected} onSelect={setSelected} /></div>
      <window.TrialDetails data={data} selected={selected} onSelect={setSelected} commands={{ busy: false, blocked: true }} onEditing={() => {}} onRecheck={() => {}} /></div></div>;
    return <><window.WorkbenchControlStyles /><window.WorkbenchControls /><window.WorkbenchNumberControls />
      <AppShell active="gantt" onNav={() => {}} theme={spec.theme} onToggleTheme={() => {}} operations showCapsule={false} title="排产安排">{body}</AppShell></>;
  }
  window.openPiece = async spec => {
    const response = await fetch(spec.path, { cache: 'no-store' }), payload = await response.json();
    if (!response.ok || !payload.ok || payload.meta.source !== 'production') throw new Error('Real piece route failed');
    if (spec.kind === 'plan' || spec.kind === 'old') window.APSPlanContract.workspace(payload, payload.data.plan.plan_ref);
    if (spec.kind === 'trial') window.TrialContract.workspace(window.TrialContract.envelope(payload));
    if (spec.kind === 'candidate') window.RunCandidateAPI.workspace(payload, payload.data.candidate.candidate_ref);
    if (mounted) mounted.unmount();
    mounted = ReactDOM.createRoot(document.getElementById('piece-root'));
    mounted.render(<Host spec={spec} data={payload.data} />);
    return payload;
  };
})();
