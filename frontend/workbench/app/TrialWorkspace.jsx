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
        <U.Button icon="refresh-cw" disabled={commands.busy || !!commands.key} onClick={() => { setConfirm(false); onRecheck(); }}>刷新草稿</U.Button><U.Button className="btn primary" icon={save ? 'check' : 'x'}
        disabled={!confirm || save && !name.trim() || commands.blocked || !data.write_context || data.write_context.capabilities['trial.' + kind] !== true}
        onClick={() => commands.execute({ action: kind, draft_ref: data.draft_ref, input: save ? { name } : { confirm: true } }, data.write_context.write_token)}>
        {save ? '确认保存试调方案' : '确认放弃'}</U.Button></>}><div className="trial-modal-body">
        <p>{save ? '保存后草稿关闭，可继续查看试调方案和调整记录。' : '放弃后草稿不可继续调整，可查看历史记录。'}</p>
        <p>原来源：{U.sourceLabel(data.base_identity)} · 完整 {data.task_count} 道安排 · 当前约束 {U.statusLabel(data.validation.constraints_status)}</p>
        {save && <label className="tt-naming">试调方案名称<input aria-label="试调方案名称" maxLength={120} value={name} onChange={e => { setName(e.target.value); setConfirm(false); }} autoComplete="off" /></label>}
        <label className="tt-check"><input type="checkbox" checked={confirm} onChange={e => setConfirm(e.target.checked)} />{save ? '确认保存完整试调方案，冲突和未排工序一并保留' : '确认放弃当前指定草稿'}</label>
        <U.ErrorBox error={commands.error} />
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
    const [stored, setStored] = React.useState(null), [selected, setSelected] = React.useState(null), [editing, setEditing] = React.useState(false);
    const [error, setError] = React.useState(null), [notice, setNotice] = React.useState(''), [directory, setDirectory] = React.useState(true);
    const [origin, setOrigin] = React.useState(initialTarget.task_origin || null), locatedOrigin = React.useRef(null);
    function notifyTarget(next) {
      if (typeof onTargetChange !== 'function') return;
      const failed = () => setError(new Error('试调记录已定位，但页面地址更新失败。可从试调列表重新打开。'));
      try { Promise.resolve(onTargetChange({ ...next, ...(origin && next.draft_ref ? { task_origin: origin } : {}) })).catch(failed); } catch (_) { failed(); }
    }
    const key = target.scenario_ref || target.draft_ref || '', isScenario = !!target.scenario_ref;
    const read = S.useRead(async signal => {
      const v = await A.read('/trial/' + (isScenario ? 'scenarios/' : 'drafts/') + key, {}, signal); C.workspace(v.data, target); return v;
    }, [key, isScenario, revision], !!key);
    React.useEffect(() => { if (read.result) { setStored({ key, result: read.result }); setBase(read.result.data.base); } }, [read.result]);
    const result = read.result || stored && stored.key === key && stored.result, data = result && result.data;
    const originalTask = React.useMemo(() => {
      if (!origin || !read.result) return { task: null, error: null };
      try { return { task: C.originTask(read.result.data, origin), error: null }; }
      catch (error) { return { task: null, error }; }
    }, [origin, read.result]);
    React.useEffect(() => {
      if (originalTask.task && locatedOrigin.current !== key) { setSelected(originalTask.task.task_ref); locatedOrigin.current = key; }
    }, [originalTask.task, key]);
    window.WorkbenchCaption.useCaption(data && read.result && !read.busy && !read.error ? {
      reference: data.scenario_ref || data.draft_ref, label: data.scenario_ref ? '当前试调方案' : '当前试调草稿',
      name: data.name || U.sourceLabel(data.base_identity),
      status: data.scenario_ref ? '已保存的试调方案' : '试调草稿 · ' + U.statusLabel(data.status),
      ...(data.baseline.version !== null ? { version: '建草稿时的正式计划 第 ' + data.baseline.version + ' 版' } : {}),
      range: '完整 ' + data.task_count + ' 道 · ' + U.timeLabel(data.time_scope.start) + ' 至 ' + U.timeLabel(data.time_scope.end),
    } : null);
    const commands = S.useCommands(receipt => {
      const d = receipt.data, next = d.scenario_ref ? { scenario_ref: d.scenario_ref } : { draft_ref: d.draft_ref };
      setModal(null); setEditing(false); setTarget(next); setDirectory(false); if (d.scenario_ref) { setSelected(null); setOrigin(null); } refresh();
      setNotice(d.scenario_ref ? '试调方案已保存，正在刷新。' : d.status === 'discarded' ? '草稿已放弃。' : '试调已保存。');
      notifyTarget(next);
    });
    const actions = { ...commands, blocked: commands.blocked || !!key && (!read.result || !!read.error || read.busy || !!origin && !originalTask.task) };
    window.WorkbenchGuards.useDirtyGuard({ owner: guardOwner, dirty: false, locked: commands.busy || !!commands.key,
      message: '上次提交的结果还没查到，请先留在这个页面。' });
    async function guard() {
      if (!await window.WorkbenchGuards.confirmLeave({ owner: guardOwner })) return false;
      setError(null); if (editing) { setEditing(false); resetEditor(); } return true;
    }
    async function select(ref) { if (ref === selected || await guard()) setSelected(ref); }
    async function open(next) {
      if (!await guard()) return;
      try {
        C.check(!origin || !!next.draft_ref, '原任务定位只能打开试调草稿，不能把已保存的试调方案当成草稿。');
        C.target(next); const canonical = next.scenario_ref ? { scenario_ref: next.scenario_ref } : { draft_ref: next.draft_ref };
        setTarget(canonical); setStored(null); setSelected(null); locatedOrigin.current = null; setNotice(''); setDirectory(false); refresh(); notifyTarget(canonical);
      }
      catch (error) { setError(error); }
    }
    function reload() { commands.restore(); refresh(); }
    const title = data ? data.name || U.sourceLabel(data.base_identity) : '尚未选择试调草稿或试调方案';
    return <div className="plana trial-workspace" data-trial-workspace data-open-ref={key} data-open-kind={isScenario ? 'scenario' : 'draft'}><window.TrialStyles />
      <header className="tt-heading"><div><h2 className="wb-page-title">排产方案试调</h2><span className="tt-muted wb-page-context">{title}{data && ' · ' + U.statusLabel(data.status)}</span></div><div className="tt-tools">
        {onNavigate && <U.Button icon="chevron-left" onClick={() => onNavigate('analysis', base || {})}>返回方案</U.Button>}
        <U.Button icon="folder-open" onClick={() => setDirectory(!directory)} aria-expanded={directory}>草稿 / 试调方案列表</U.Button>
        <U.Button icon="plus" className="btn primary" disabled={commands.blocked} onClick={async () => { if (await guard()) setModal('create'); }}>新增试调</U.Button>
      </div></header>
      <U.ErrorBox error={error} /><U.ErrorBox error={commands.error} /><U.ErrorBox error={originalTask.error} />
      {!commands.key && commands.note && <p role="status">{commands.note}</p>}
      {commands.error && !commands.key && <U.Button icon="refresh-cw" onClick={reload} disabled={commands.busy}>刷新试调内容和操作记录</U.Button>}
      {commands.key && <section className="tt-notice" aria-label="待确认的试调提交"><strong>上次试调提交待确认</strong><p>{commands.note || '上次提交结果尚未确认。'}</p>
        <div className="tt-tools"><U.Button icon="refresh-cw" onClick={commands.lookup} busy={commands.busy}>查询结果</U.Button><window.WorkbenchReference value={commands.key} /></div></section>}
      {notice && <p role="status" className="tt-notice">{notice}</p>}
      {directory && <window.TrialCatalog.Directory revision={revision} onOpen={open} filterBase={base}
        fixedBase={origin ? { plan_ref: origin.plan_ref } : null} />}
      <U.ErrorBox error={read.error} />{key && <div className="tt-heading"><span className="tt-muted">{read.busy ? '正在刷新，暂时不能提交。' : read.error ? '读取失败。下面是上次读到的内容，暂时不能提交。' : result ? '读取于 ' + U.timeLabel(result.meta.as_of) : ''}</span>
        <U.Button icon="refresh-cw" aria-label="刷新当前试调" busy={read.busy} disabled={commands.busy || !!commands.key} onClick={reload} /></div>}
      {!data && <div className="tt-empty" role="status">{read.busy ? '正在读取完整试调…' : '尚未打开试调草稿或试调方案'}</div>}
      {data && <><div className="tt-heading"><span>原来源：{U.sourceLabel(data.base_identity)} · 完整 {data.task_count} 道安排 · 未排 {data.unplanned_operations.length} 道</span>
        <U.Download data={data} /></div><div className="tt-muted">建草稿时的正式计划：{data.baseline.plan_ref ? '第 ' + data.baseline.version + ' 版' : '当时还没有正式计划'} · 对比始终使用原试调基础</div>
        <window.TrialResults.Summary data={data} /><div className="tt-main"><div><window.TrialGantt key={key} data={data} selected={selected} onSelect={select} />
          <window.TrialResults.Results key={key} data={data} onSelect={select} /></div>
          <window.TrialDetails data={data} selected={selected} commands={actions} onSelect={select} onEditing={setEditing} onRecheck={reload} guardOwner={guardOwner} editorRevision={editorRevision} /></div>
        <footer className="tt-footer"><div><strong>整体约束：{U.statusLabel(data.validation.constraints_status)}</strong><div className="tt-muted">{typeof renderAdoption === 'function' ? '保存后可正式采用' : window.WorkbenchTerms.outcomes.unavailable}</div></div>
          <div className="tt-tools"><U.Button icon="x" disabled={data.status !== 'editing' || actions.blocked || !data.write_context || data.write_context.capabilities['trial.discard'] !== true} onClick={async () => { if (await guard()) setModal('discard'); }}>放弃草稿</U.Button>
            <U.Button icon="check" className="btn primary" disabled={data.status !== 'editing' || actions.blocked || !data.write_context || data.write_context.capabilities['trial.save'] !== true} onClick={async () => { if (await guard()) setModal('save'); }}>保存试调方案</U.Button>
            {data.scenario_ref && typeof renderAdoption === 'function' ? renderAdoption({ scenarioRef: data.scenario_ref, data, onNavigate, disabled: actions.blocked,
              onAdopted: () => { setNotice('采用结果已更新，请在采用面板查看。'); refresh(); } }) :
              <U.Button icon="check" reason={data.scenario_ref ? window.WorkbenchTerms.outcomes.unavailable : '请先保存试调方案，再做正式采用。'}>采用方案</U.Button>}</div></footer>
        <details className="tt-refs wb-ref"><summary>编号与读取范围</summary><div>草稿编号：<span className="tt-ref">{data.draft_ref}</span></div>
          {data.scenario_ref && <div>试调方案编号：<span className="tt-ref">{data.scenario_ref}</span></div>}<div>原来源编号：<span className="tt-ref">{Object.values(data.base)[0]}</span></div>
          <div>完整时间：{U.timeLabel(data.time_scope.start)} 至 {U.timeLabel(data.time_scope.end)}</div></details></>}
      {modal === 'create' && <window.TrialCatalog.Create initialBase={origin ? { plan_ref: origin.plan_ref } : base} initialScope={initialTarget.base ? initialTarget.scope || {} : {}}
        fixedBase={!!origin} onExisting={origin ? () => { setModal(null); setDirectory(true); } : undefined} commands={commands} onClose={() => setModal(null)} />}
      {data && ['save', 'discard'].includes(modal) && <Finish data={data} kind={modal} commands={actions} onClose={() => setModal(null)} onRecheck={reload} />}
    </div>;
  }
  // Load after TrialContract/API/Session/Controls/Catalog/Gantt/Details/Results/Styles.
  // initialTarget: {} | {draft_ref} | {scenario_ref} | {base:{plan_ref|candidate_ref},scope?}.
  // task_origin stays in navigation only; saved scenarios clear the original-task focus.
  function WorkbenchTrialWorkspace({ initialTarget = {}, onNavigate, renderAdoption, onTargetChange }) {
    try { C.target(initialTarget); }
    catch (error) { return <div className="trial-workspace"><window.TrialStyles /><U.ErrorBox error={error} /></div>; }
    return <Session key={JSON.stringify(initialTarget)} initialTarget={initialTarget} onNavigate={onNavigate} renderAdoption={renderAdoption} onTargetChange={onTargetChange} />;
  }
  window.WorkbenchTrialWorkspace = WorkbenchTrialWorkspace;
})();
