(function () {
  'use strict';
  const A = window.TrialAPI, C = window.TrialContract, U = window.TrialControls, S = window.TrialSession;
  function Finish({ data, kind, commands, onClose, onRecheck }) {
    const [name, setName] = React.useState(''), [confirm, setConfirm] = React.useState(false);
    React.useEffect(() => { setConfirm(false); }, [data]);
    const save = kind === 'save';
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({ dirty: save && !!name, locked: commands.busy || !!commands.key,
      message: save ? '试调方案名称或保存确认还没提交。' : '放弃草稿的确认还没提交。' });
    async function close(detail) {
      if (detail && detail.guardConfirmed === true && detail.guardOwner === guardOwner || await window.WorkbenchGuards.confirmLeave({ owner: guardOwner })) onClose();
    }
    return <U.Modal title={save ? '保存试调方案' : '确认放弃草稿'} icon={save ? 'check' : 'x'} locked={commands.busy || !!commands.key} guardOwner={guardOwner} onClose={close}
      footer={<><U.Button icon="x" disabled={commands.busy || !!commands.key} onClick={close}>取消</U.Button>
        <U.Button icon="refresh-cw" disabled={commands.busy || !!commands.key} onClick={() => { setConfirm(false); onRecheck(); }}>刷新草稿</U.Button>
        {commands.key && <U.Button icon="refresh-cw" busy={commands.busy} onClick={commands.lookup}>{window.WorkbenchTerms.actions.query_result}</U.Button>}<U.Button className="btn primary" icon={save ? 'check' : 'x'}
        disabled={!confirm || save && !name.trim() || commands.blocked || !data.write_context || data.write_context.capabilities['trial.' + kind] !== true}
        onClick={() => commands.execute({ action: kind, draft_ref: data.draft_ref, input: save ? { name } : { confirm: true } }, data.write_context.write_token)}>
        {save ? '确认保存试调方案' : '确认放弃'}</U.Button></>}><div className="trial-modal-body">
        <p>{save ? '保存后草稿关闭，可继续查看试调方案和调整记录。' : '放弃后草稿不可继续调整，可查看历史记录。'}</p>
        <p>已安排 {data.task_count} 道工序{data.unplanned_operations.length > 0 && '；' + data.unplanned_operations.length + ' 道工序未安排'} · 约束检查{U.statusLabel(data.validation.constraints_status)}</p>
        {save && <label className="tt-naming">试调方案名称<input aria-label="试调方案名称" maxLength={120} value={name} onChange={e => { setName(e.target.value); setConfirm(false); }} autoComplete="off" /></label>}
        <label className="tt-check"><input type="checkbox" checked={confirm} onChange={e => setConfirm(e.target.checked)} />{save ? '确认保存试调方案，冲突和未安排工序一并保留' : '确认放弃当前草稿'}</label>
        <U.ErrorBox error={commands.error} />
        {commands.key && <section className="tt-notice" aria-label="待确认的试调提交"><p>{commands.note || '上次提交结果尚未确认。'}</p><window.WorkbenchReference value={commands.key} /></section>}
      </div></U.Modal>;
  }
  function Session({ initialTarget, onNavigate, renderAdoption, onTargetChange }) {
    const guardOwner = React.useId(), [editorRevision, resetEditor] = React.useReducer(value => value + 1, 0);
    React.useEffect(() => {
      let original, printing = false;
      function beforePrint() {
        if (printing) return;
        original = document.documentElement.getAttribute('data-theme'); printing = true;
        document.documentElement.setAttribute('data-theme', 'light');
      }
      function afterPrint() {
        if (!printing) return;
        if (original === null) document.documentElement.removeAttribute('data-theme');
        else document.documentElement.setAttribute('data-theme', original);
        printing = false;
      }
      window.addEventListener('beforeprint', beforePrint); window.addEventListener('afterprint', afterPrint);
      return () => { window.removeEventListener('beforeprint', beforePrint); window.removeEventListener('afterprint', afterPrint); afterPrint(); };
    }, []);
    const [target, setTarget] = React.useState(initialTarget.base ? {} : initialTarget), [base, setBase] = React.useState(initialTarget.base || null);
    const [modal, setModal] = React.useState(initialTarget.base ? 'create' : null), [revision, refresh] = React.useReducer(n => n + 1, 0);
    const stored = React.useRef(null), [selected, setSelected] = React.useState(null), [editing, setEditing] = React.useState(false);
    const [detailsOpen, setDetailsOpen] = React.useState(false);
    const inspectFocus = React.useRef(null);
    const [error, setError] = React.useState(null), [notice, setNotice] = React.useState(''), [directory, setDirectory] = React.useState(!initialTarget.draft_ref && !initialTarget.scenario_ref);
    const [origin, setOrigin] = React.useState(initialTarget.task_origin || null), locatedOrigin = React.useRef(null);
    function notifyTarget(next) {
      const failed = () => setError(new Error('试调记录已定位，但页面地址更新失败。可从试调列表重新打开。'));
      try { Promise.resolve(onTargetChange({ ...next, ...(initialTarget.return_decision_history_context ? { return_decision_history_context: initialTarget.return_decision_history_context } : {}), ...(origin && next.draft_ref ? { task_origin: origin } : {}) })).catch(failed); } catch (_) { failed(); }
    }
    const key = target.scenario_ref || target.draft_ref || '', isScenario = !!target.scenario_ref;
    const read = S.useRead(async signal => {
      const v = await A.read('/trial/' + (isScenario ? 'scenarios/' : 'drafts/') + key, {}, signal); C.workspace(v.data, target); return v;
    }, [key, isScenario, revision], !!key);
    if (read.result) stored.current = { key, result: read.result };
    React.useEffect(() => { if (read.result) setBase(read.result.data.base); }, [read.result]);
    const result = read.result || stored.current && stored.current.key === key && stored.current.result, data = result && result.data;
    const originalTask = React.useMemo(() => {
      if (!origin || !read.result) return { task: null, error: null };
      try { return { task: C.originTask(read.result.data, origin), error: null }; }
      catch (error) { return { task: null, error }; }
    }, [origin, read.result]);
    React.useEffect(() => {
      if (originalTask.task && locatedOrigin.current !== key) { setSelected(originalTask.task.task_ref); setDetailsOpen(true); locatedOrigin.current = key; }
    }, [originalTask.task, key]);
    window.WorkbenchCaption.useCaption(data && read.result && !read.busy && !read.error ? {
      reference: data.scenario_ref || data.draft_ref, label: data.scenario_ref ? '当前试调方案' : '当前试调草稿',
      name: data.name || U.sourceLabel(data.base_identity),
      status: data.scenario_ref ? '已保存的试调方案' : '试调草稿 · ' + U.statusLabel(data.status),
      ...(data.baseline.version !== null ? { version: '建草稿时的正式计划 第 ' + data.baseline.version + ' 版' } : {}),
    } : null);
    const commands = S.useCommands(receipt => {
      const d = receipt.data, next = d.scenario_ref ? { scenario_ref: d.scenario_ref } : { draft_ref: d.draft_ref };
      setModal(null); setEditing(false); resetEditor(); setTarget(next); setDirectory(false); if (d.scenario_ref) { setSelected(null); setOrigin(null); } refresh();
      setNotice(d.scenario_ref ? '试调方案已保存。' : d.status === 'discarded' ? '草稿已放弃。' : '试调已保存。');
      notifyTarget(next);
    });
    const actions = { ...commands, blocked: commands.blocked || !!key && (!read.result || !!read.error || read.busy || !!origin && !originalTask.task) };
    window.WorkbenchGuards.useDirtyGuard({ owner: guardOwner, dirty: false, locked: commands.busy || !!commands.key,
      message: '上次提交的结果还没查到，请先留在这个页面。' });
    async function guard() {
      if (!await window.WorkbenchGuards.confirmLeave({ owner: guardOwner })) return false;
      setError(null); if (editing) { commands.clearError(); setEditing(false); resetEditor(); } return true;
    }
    async function select(ref) { if (ref !== selected && !await guard()) return false; setSelected(ref); return true; }
    async function inspectTask(ref) {
      if (!await select(ref)) return;
      setDetailsOpen(true); if (inspectFocus.current) inspectFocus.current();
    }
    async function toggleDetails() {
      if (!detailsOpen) setDetailsOpen(true);
      else if (await guard()) setDetailsOpen(false);
    }
    async function open(next) {
      if (!await guard()) return;
      try {
        C.check(!origin || !!next.draft_ref, '原任务定位只能打开试调草稿，不能把已保存的试调方案当成草稿。');
        C.target(next); const canonical = next.scenario_ref ? { scenario_ref: next.scenario_ref } : { draft_ref: next.draft_ref };
        commands.clearError();
        setTarget(canonical); stored.current = null; setSelected(null); setDetailsOpen(false); locatedOrigin.current = null; setNotice(''); setDirectory(false); refresh(); notifyTarget(canonical);
      }
      catch (error) { setError(error); }
    }
    function reload() { commands.restore(); refresh(); }
    // An actually rendered dialog owns the command feedback; the page below does not repeat it.
    const finishing = !!data && ['save', 'discard'].includes(modal), dialog = modal === 'create' || finishing;
    return <div className="plana trial-workspace" data-trial-workspace data-open-ref={key} data-open-kind={isScenario ? 'scenario' : 'draft'}>
      <h2 className="wb-page-title">试调排产方案</h2><header className="tt-tools">
        <U.Button icon="chevron-left" onClick={() => onNavigate('analysis', base || {})}>返回方案</U.Button>
        {initialTarget.return_decision_history_context && <U.Button icon="history" onClick={() => onNavigate('analysis', window.DecisionHistoryAPI.historyContext(initialTarget))}>返回历史走势</U.Button>}
        <U.Button icon="folder-open" onClick={() => setDirectory(!directory)} aria-expanded={directory}>草稿 / 试调方案列表</U.Button>
        <U.Button icon="plus" className="btn primary" disabled={commands.blocked} onClick={async () => { if (await guard()) setModal('create'); }}>新增试调</U.Button>
        {key && <U.Button icon="refresh-cw" aria-label="刷新当前试调" busy={read.busy} disabled={commands.busy || !!commands.key} onClick={reload}>刷新</U.Button>}
        {data && <><U.Download data={data} /><details className="tt-refs wb-ref"><summary title={window.WorkbenchFormat.dateTime(data.time_scope.start, { seconds: true, fractions: true }) + ' 至 ' + window.WorkbenchFormat.dateTime(data.time_scope.end, { seconds: true, fractions: true })}>{window.WorkbenchFormat.compactRange(data.time_scope.start, data.time_scope.end)}</summary>
          <div className="tt-source-body"><dl className="tt-source-facts">
            <div><dt>原安排</dt><dd>{U.sourceLabel(data.base_identity)} · 创建草稿时保存</dd></div><div><dt>试调安排</dt><dd>{data.scenario_ref ? '已保存的调整结果' : '当前调整结果'}</dd></div>
            {data.baseline.version !== null && <div><dt>建草稿时的正式计划</dt><dd>第 {data.baseline.version} 版</dd></div>}
            <div><dt>开始</dt><dd>{window.WorkbenchFormat.dateTime(data.time_scope.start, { seconds: true, fractions: true })}</dd></div><div><dt>结束</dt><dd>{window.WorkbenchFormat.dateTime(data.time_scope.end, { seconds: true, fractions: true })}</dd></div>
            {result && <div><dt>本次刷新时间</dt><dd>{window.WorkbenchFormat.dateTime(result.meta.as_of, { seconds: true, fractions: true })}</dd></div>}
          </dl><div className="tt-source-wide">交期数据：{window.WorkbenchTerms.delivery_coverage(data.comparison.delivery_summary)}</div>
            <window.WorkbenchReference entries={{ '草稿编号': data.draft_ref, ...(data.scenario_ref ? { '试调方案编号': data.scenario_ref } : {}), '来源编号': Object.values(data.base)[0] }} />
          </div>
        </details></>}
      </header>
      <U.ErrorBox error={error} />{!dialog && !editing && <U.ErrorBox error={commands.error} />}<U.ErrorBox error={originalTask.error} />
      {!commands.key && commands.note && <p role="status">{commands.note}</p>}
      {commands.error && !commands.key && <U.Button icon="refresh-cw" onClick={reload} disabled={commands.busy}>刷新试调内容和操作记录</U.Button>}
      {!dialog && commands.key && <section className="tt-notice" aria-label="待确认的试调提交"><strong>上次试调提交待确认</strong><p>{commands.note || '上次提交结果尚未确认。'}</p>
        <div className="tt-tools"><U.Button icon="refresh-cw" onClick={commands.lookup} busy={commands.busy}>查询结果</U.Button><window.WorkbenchReference value={commands.key} /></div></section>}
      {notice && <p role="status" className="tt-notice">{notice}</p>}
      {directory && <window.TrialCatalog.Directory revision={revision} onOpen={open} filterBase={base}
        fixedBase={origin ? { plan_ref: origin.plan_ref } : null} />}
      <U.ErrorBox error={read.error} />{key && (read.busy || read.error) && <p className="tt-muted" role="status">{read.busy ? '正在刷新，暂时不能提交。' : '下面是上次读到的内容，刷新成功后可继续提交。'}</p>}
      {!data && <div className="tt-empty" role="status">{read.busy ? '正在读取试调…' : '尚未打开试调草稿或试调方案'}</div>}
      {data && <>
        <window.TrialResults.Summary data={data} /><div className="tt-main wb-gantt-detail-layout" data-details-open={detailsOpen || undefined}><div className="wb-gantt-main-column">
          <window.TrialGantt key={key} data={data} selected={selected} onSelect={select} detailsOpen={detailsOpen} onToggleDetails={toggleDetails} />
          <window.TrialResults.Results key={key} data={data} onSelect={inspectTask} /></div>
          {detailsOpen && <window.TrialDetails data={data} selected={selected} commands={actions} onSelect={inspectTask} onEditing={setEditing} onRecheck={reload} guardOwner={guardOwner} editorRevision={editorRevision} inspectFocus={inspectFocus} onCollapse={toggleDetails} />}</div>
        <footer className="tt-footer">{data.validation.constraints_status !== 'valid' && <strong>约束检查：{U.statusLabel(data.validation.constraints_status)}</strong>}
          <div className="tt-tools"><U.Button icon="x" disabled={data.status !== 'editing' || actions.blocked || !data.write_context || data.write_context.capabilities['trial.discard'] !== true} onClick={async () => { if (await guard()) setModal('discard'); }}>放弃草稿</U.Button>
            <U.Button icon="check" className="btn primary" disabled={data.status !== 'editing' || actions.blocked || !data.write_context || data.write_context.capabilities['trial.save'] !== true} onClick={async () => { if (await guard()) setModal('save'); }}>保存试调方案</U.Button>
            {data.scenario_ref ? renderAdoption({ scenarioRef: data.scenario_ref, data, onNavigate, disabled: actions.blocked,
              onAdopted: () => { setNotice('采用结果已更新，请在采用面板查看。'); refresh(); } }) :
              <U.Button icon="check" reason="请先保存试调方案，再做正式采用。">采用方案</U.Button>}</div></footer>
        </>}
      {modal === 'create' && <window.TrialCatalog.Create initialBase={origin ? { plan_ref: origin.plan_ref } : base} initialScope={initialTarget.base ? initialTarget.scope || {} : {}}
        fixedBase={!!origin} onExisting={origin ? () => { commands.clearError(); setModal(null); setDirectory(true); } : undefined} commands={commands} onClose={() => { commands.clearError(); setModal(null); }} />}
      {finishing && <Finish data={data} kind={modal} commands={actions} onClose={() => { commands.clearError(); setModal(null); }} onRecheck={reload} />}
    </div>;
  }
  // Load after TrialContract/API/Session/Controls/Catalog/Gantt/Details/Results.
  // initialTarget: {} | {draft_ref} | {scenario_ref} | {base:{plan_ref|candidate_ref},scope?}.
  // task_origin stays in navigation only; saved scenarios clear the original-task focus.
  function WorkbenchTrialWorkspace({ initialTarget, onNavigate, renderAdoption, onTargetChange }) {
    try { C.target(initialTarget); }
    catch (error) { return <div className="trial-workspace"><U.ErrorBox error={error} /></div>; }
    const navigate = (view, context = {}) => onNavigate(view, { ...context, ...(initialTarget.return_decision_history_context && context.source !== 'run_history' ? { return_decision_history_context: initialTarget.return_decision_history_context } : {}) });
    return <Session key={JSON.stringify(initialTarget)} initialTarget={initialTarget} onNavigate={navigate} renderAdoption={renderAdoption} onTargetChange={onTargetChange} />;
  }
  window.WorkbenchTrialWorkspace = WorkbenchTrialWorkspace;
})();
