(function () {
  'use strict';
  const A = window.TrialAPI, C = window.TrialContract, U = window.TrialControls, S = window.TrialSession;
  function Finish({ data, kind, commands, onClose, onRecheck }) {
    const [name, setName] = React.useState(''), [confirm, setConfirm] = React.useState(false);
    React.useEffect(() => { setConfirm(false); }, [data]);
    const save = kind === 'save';
    return <U.Modal title={save ? '保存试调场景' : '确认放弃草稿'} icon={save ? 'check' : 'x'} locked={commands.busy} onClose={onClose}
      footer={<><U.Button icon="x" disabled={commands.busy} onClick={onClose}>取消</U.Button>
        <U.Button icon="refresh-cw" disabled={commands.busy || !!commands.key} onClick={() => { setConfirm(false); onRecheck(); }}>重读草稿</U.Button><U.Button className="btn primary" icon={save ? 'check' : 'x'}
        disabled={!confirm || save && !name.trim() || commands.blocked || !data.write_context || data.write_context.capabilities['trial.' + kind] !== true}
        onClick={() => commands.execute({ action: kind, draft_ref: data.draft_ref, input: save ? { name } : { confirm: true } }, data.write_context.write_token)}>
        {save ? '确认保存场景' : '确认放弃'}</U.Button></>}><div className="trial-modal-body">
        <p>{save ? '保存后草稿关闭，场景保留全部原任务与调整记录，不改变正式计划。' : '仅关闭此草稿，不删除原计划、草稿记录和调整历史。此草稿将不能继续调整。'}</p>
        <p>原来源：{U.sourceLabel(data.base_identity)} · 完整 {data.task_count} 道安排 · 当前约束 {U.statusLabel(data.validation.constraints_status)}</p>
        {save && <label className="tt-naming">场景名称<input aria-label="场景名称" maxLength={120} value={name} onChange={e => { setName(e.target.value); setConfirm(false); }} autoComplete="off" /></label>}
        <label className="tt-check"><input type="checkbox" checked={confirm} onChange={e => setConfirm(e.target.checked)} />{save ? '确认保存完整场景，冲突和未排工序一并保留' : '确认放弃当前指定草稿'}</label>
        <U.ErrorBox error={commands.error} />
      </div></U.Modal>;
  }
  function Session({ initialTarget, onNavigate, renderAdoption, onTargetChange }) {
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
    function notifyTarget(next) {
      if (typeof onTargetChange !== 'function') return;
      const failed = () => setError(new Error('试调对象已定位，但页面恢复地址更新失败。原记录仍在目录中，未重复写入。'));
      try { Promise.resolve(onTargetChange({ ...next })).catch(failed); } catch (_) { failed(); }
    }
    const key = target.scenario_ref || target.draft_ref || '', isScenario = !!target.scenario_ref;
    const read = S.useRead(async signal => {
      const v = await A.read('/trial/' + (isScenario ? 'scenarios/' : 'drafts/') + key, {}, signal); C.workspace(v.data, target); return v;
    }, [key, isScenario, revision], !!key);
    React.useEffect(() => { if (read.result) { setStored({ key, result: read.result }); setBase(read.result.data.base); } }, [read.result]);
    const result = read.result || stored && stored.key === key && stored.result, data = result && result.data;
    window.WorkbenchCaption.useCaption(data && read.result && !read.busy && !read.error ? {
      reference: data.scenario_ref || data.draft_ref, label: data.scenario_ref ? '当前场景' : '当前草稿',
      name: data.name || U.sourceLabel(data.base_identity),
      status: data.scenario_ref ? '已存场景预览' : '试调草稿 · ' + U.statusLabel(data.status),
      ...(data.baseline.version !== null ? { version: '创建时正式基线 v' + data.baseline.version } : {}),
      range: '完整 ' + data.task_count + ' 道 · ' + U.timeLabel(data.time_scope.start) + ' 至 ' + U.timeLabel(data.time_scope.end),
    } : null);
    const commands = S.useCommands(receipt => {
      const d = receipt.data, next = d.scenario_ref ? { scenario_ref: d.scenario_ref } : { draft_ref: d.draft_ref };
      setModal(null); setEditing(false); setTarget(next); setDirectory(false); if (d.scenario_ref) setSelected(null); refresh();
      setNotice(d.scenario_ref ? '场景已保存，正在读取原场景快照；正式计划未改变。' : d.status === 'discarded' ? '指定草稿已放弃，原记录与历史仍保留。' : '试调已持久保存，正式计划未改变。');
      notifyTarget(next);
    });
    const actions = { ...commands, blocked: commands.blocked || !!key && (!read.result || !!read.error || read.busy) };
    function guard() { if (!editing) { setError(null); return true; } setError(new Error('请先保存调整或取消当前工序编辑。')); return false; }
    function select(ref) { if (ref === selected || guard()) setSelected(ref); }
    function open(next) {
      if (!guard()) return;
      try {
        C.target(next); const canonical = next.scenario_ref ? { scenario_ref: next.scenario_ref } : { draft_ref: next.draft_ref };
        setTarget(canonical); setStored(null); setSelected(null); setNotice(''); setDirectory(false); refresh(); notifyTarget(canonical);
      }
      catch (error) { setError(error); }
    }
    function reload() { commands.restore(); refresh(); }
    const title = data ? data.name || U.sourceLabel(data.base_identity) : '尚未选择草稿或场景';
    return <div className="plana trial-workspace" data-trial-workspace data-open-ref={key} data-open-kind={isScenario ? 'scenario' : 'draft'}><window.TrialStyles />
      <header className="tt-heading"><div><h2>排产方案试调</h2><span className="tt-muted">{title}{data && ' · ' + U.statusLabel(data.status)}</span></div><div className="tt-tools">
        {onNavigate && <U.Button icon="chevron-left" onClick={() => { if (guard()) onNavigate('analysis', base || {}); }}>返回方案</U.Button>}
        <U.Button icon="folder-open" onClick={() => setDirectory(!directory)} aria-expanded={directory}>草稿 / 场景目录</U.Button>
        <U.Button icon="plus" disabled={commands.blocked} onClick={() => { if (guard()) setModal('create'); }}>新建试调</U.Button>
      </div></header>
      <U.ErrorBox error={error} /><U.ErrorBox error={commands.error} />
      {!commands.key && commands.note && <p role="status">{commands.note}</p>}
      {commands.error && !commands.key && <U.Button icon="refresh-cw" onClick={reload} disabled={commands.busy}>重读恢复记录与当前内容</U.Button>}
      {commands.key && <section className="tt-notice" aria-label="待核实试调请求"><strong>原试调请求待核实</strong><p>{commands.note || '恢复记录只包含原请求编号，尚未读取结果。'}</p>
        <div className="tt-tools"><U.Button icon="refresh-cw" onClick={commands.lookup} busy={commands.busy}>查询原请求</U.Button><span className="tt-ref">{commands.key}</span></div></section>}
      {notice && <p role="status" className="tt-notice">{notice}</p>}
      {directory && <window.TrialCatalog.Directory revision={revision} onOpen={open} filterBase={base} />}
      <U.ErrorBox error={read.error} />{key && <div className="tt-heading"><span className="tt-muted">{read.busy ? '正在重新读取，写入已暂停。' : read.error ? '读取失败。下方为上次读取内容，写入已暂停。' : result ? '读取于 ' + U.timeLabel(result.meta.as_of) : ''}</span>
        <U.Button icon="refresh-cw" aria-label="重读当前试调" busy={read.busy} disabled={commands.busy || !!commands.key} onClick={reload} /></div>}
      {!data && <div className="tt-empty" role="status">{read.busy ? '正在读取完整试调…' : '尚未打开试调草稿或场景'}</div>}
      {data && <><div className="tt-heading"><span>原来源：{U.sourceLabel(data.base_identity)} · 完整 {data.task_count} 道安排 · 未排 {data.unplanned_operations.length} 道</span>
        <U.Download data={data} /></div><div className="tt-muted">创建时正式基线：{data.baseline.plan_ref ? 'v' + data.baseline.version : '无正式基线'} · 对比始终使用原试调基础</div>
        <window.TrialResults.Summary data={data} /><div className="tt-main"><div><window.TrialGantt key={key} data={data} selected={selected} onSelect={select} />
          <window.TrialResults.Results key={key} data={data} onSelect={select} /></div>
          <window.TrialDetails data={data} selected={selected} commands={actions} onSelect={select} onEditing={setEditing} onRecheck={reload} /></div>
        <footer className="tt-footer"><div><strong>整体约束：{U.statusLabel(data.validation.constraints_status)}</strong><div className="tt-muted">{typeof renderAdoption === 'function' ? '保存试调不代表正式采用' : '完整场景正式采用尚未接入，正式计划未改变'}</div></div>
          <div className="tt-tools"><U.Button icon="x" disabled={data.status !== 'editing' || actions.blocked || !data.write_context || data.write_context.capabilities['trial.discard'] !== true} onClick={() => { if (guard()) setModal('discard'); }}>放弃草稿</U.Button>
            <U.Button icon="check" className="btn primary" disabled={data.status !== 'editing' || actions.blocked || !data.write_context || data.write_context.capabilities['trial.save'] !== true} onClick={() => { if (guard()) setModal('save'); }}>保存场景</U.Button>
            {data.scenario_ref && typeof renderAdoption === 'function' ? renderAdoption({ scenarioRef: data.scenario_ref, data, onNavigate, disabled: actions.blocked,
              onAdopted: () => { setNotice('采用结果由独立场景采用回执核实；当前仍为原场景快照。'); refresh(); } }) :
              <U.Button icon="check" reason={data.scenario_ref ? '完整场景正式采用尚未接入，未改变正式计划。' : '须先保存场景，再核对独立场景采用入口。'}>正式采用</U.Button>}</div></footer>
        <details className="tt-refs"><summary>试调身份与读取范围</summary><div>草稿：<span className="tt-ref">{data.draft_ref}</span></div>
          {data.scenario_ref && <div>场景：<span className="tt-ref">{data.scenario_ref}</span></div>}<div>原来源：<span className="tt-ref">{Object.values(data.base)[0]}</span></div>
          <div>完整时间：{U.timeLabel(data.time_scope.start)} 至 {U.timeLabel(data.time_scope.end)}</div></details></>}
      {modal === 'create' && <window.TrialCatalog.Create initialBase={base} initialScope={initialTarget.base ? initialTarget.scope || {} : {}} commands={commands} onClose={() => setModal(null)} />}
      {data && ['save', 'discard'].includes(modal) && <Finish data={data} kind={modal} commands={actions} onClose={() => setModal(null)} onRecheck={reload} />}
    </div>;
  }
  // Load after TrialContract/API/Session/Controls/Catalog/Gantt/Details/Results/Styles.
  // initialTarget: {} | {draft_ref} | {scenario_ref} | {base:{plan_ref|candidate_ref},scope?}.
  // onTargetChange receives only {draft_ref} or {scenario_ref}; the host owns history.replaceState.
  function WorkbenchTrialWorkspace({ initialTarget = {}, onNavigate, renderAdoption, onTargetChange }) {
    try { C.target(initialTarget); }
    catch (error) { return <div className="trial-workspace"><window.TrialStyles /><U.ErrorBox error={error} /></div>; }
    return <Session key={JSON.stringify(initialTarget)} initialTarget={initialTarget} onNavigate={onNavigate} renderAdoption={renderAdoption} onTargetChange={onTargetChange} />;
  }
  window.WorkbenchTrialWorkspace = WorkbenchTrialWorkspace;
})();
