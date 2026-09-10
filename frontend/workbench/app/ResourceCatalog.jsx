(function () {
  'use strict';
  const C = window.APSResourceContract, S = window.APSResourceSession, M = window.APSResourceCatalogModel;
  const { Modal, Button, ErrorBox, Issues } = window.ResourceControls;
  const Editor = window.ResourceCatalogEditor;
  const initialScope = () => ({ query: '', status: '', page: 1, size: 20, sort: 'business_code', direction: 'asc' });
  function CatalogList({ kind, list, scope, setScope, onOpen, disabled }) {
    const [search, setSearch] = React.useState(''), data = list.result && list.result.data;
    function filter(patch) { setScope(current => ({ ...current, ...patch, page: 1, snapshot_ref: undefined })); }
    return <><form className="toolbar rc-toolbar" onSubmit={event => { event.preventDefault(); filter({ query: search }); }}>
      <label className="search"><input type="search" aria-label="搜索目录编号或名称" value={search} disabled={disabled} onChange={event => setSearch(event.target.value)} /></label>
      <Button icon="search" type="submit" aria-label="搜索目录" disabled={disabled} />
      <div className="field"><select aria-label="目录状态筛选" value={scope.status} disabled={disabled} onChange={event => filter({ status: event.target.value })}>
        <option value="">全部状态</option><option value="active">启用</option><option value="inactive">停用</option><option value="unknown">旧状态未知</option></select></div>
      <Button icon="refresh-cw" aria-label="刷新目录" disabled={disabled} busy={list.loading} onClick={() => { filter({}); list.reload(); }} />
      <span className="tb-spacer" /><Button icon="plus" className="btn primary" disabled={disabled} reason={C.blocked(data && data.create_context, kind, 'create', list.result && list.result.meta.source)} onClick={() => onOpen('create')}>新增{M.names[kind]}</Button>
    </form><ErrorBox error={list.error} />{list.loading && <p role="status">正在读取目录…</p>}
      {data && <><Issues issues={list.result.warnings} /><table className="tbl rc-list"><thead><tr>
        <th>编号 / 名称</th><th>状态</th><th>{kind === 'machine_group' ? '关联设备' : '关联人员'}</th>{kind === 'shift_profile' && <th>轮换天数</th>}<th>操作</th></tr></thead><tbody>
        {data.entities.map(entity => <tr key={entity.ref}><td className="rc-wrap"><b>{entity.business_code}</b><div>{entity.label}</div></td>
          <td><span className={'pill ' + (entity.status === 'active' ? 'ok' : entity.status === 'inactive' ? 'off' : 'warn')}><span className="dot" />{entity.status === 'active' ? '启用' : entity.status === 'inactive' ? '停用' : '未知'}</span></td>
          <td>{M.memberCount(kind, entity) === null ? '未读取' : M.memberCount(kind, entity)}</td>{kind === 'shift_profile' && <td>{entity.fields.cycle_days}</td>}
          <td><div className="rowact"><Button className="mini" icon="square-pen" aria-label={'编辑 ' + entity.business_code} disabled={disabled} reason={C.blocked(entity.write_context, kind, 'update', list.result.meta.source)} onClick={() => onOpen('update', entity.ref)} />
            <Button className="mini" icon="minus" aria-label={'删除 ' + entity.business_code} disabled={disabled} reason={C.blocked(entity.write_context, kind, 'delete', list.result.meta.source)} onClick={() => onOpen('delete', entity.ref)} /></div></td></tr>)}
        {!data.entities.length && <tr><td colSpan={kind === 'shift_profile' ? 5 : 4} className="muted">当前范围没有目录记录。</td></tr>}</tbody></table>
        <div className="pager"><span>共 {data.page.total} 条 · 第 {data.page.number} / {Math.max(1, data.page.pages)} 页</span><span className="grow" />
          <Button icon="chevron-left" aria-label="目录上一页" disabled={disabled || scope.page <= 1} onClick={() => setScope({ ...scope, page: scope.page - 1, snapshot_ref: list.result.meta.snapshot_ref })} />
          <Button icon="chevron-right" aria-label="目录下一页" disabled={disabled || scope.page >= data.page.pages} onClick={() => setScope({ ...scope, page: scope.page + 1, snapshot_ref: list.result.meta.snapshot_ref })} /></div></>}
    </>;
  }
  function ResourceCatalog({ kind, adapter, onClose, onCommitted }) {
    const [scope, setScope] = React.useState(initialScope), [editor, setEditor] = React.useState(null);
    const [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null), [review, setReview] = React.useState(null);
    const [discard, setDiscard] = React.useState(null), [lastReceipt, setLastReceipt] = React.useState(null), [needsReview, setNeedsReview] = React.useState(false);
    const command = S.useCommand(adapter), generation = React.useRef(0), alive = React.useRef(true), root = React.useRef(null), formId = React.useId();
    React.useEffect(() => { alive.current = true; return () => { alive.current = false; generation.current++; }; }, []);
    const validKind = Object.prototype.hasOwnProperty.call(M.names, kind), done = command.phase === 'done';
    const locked = command.locked || busy, showList = !editor && !command.locked && !done;
    const list = S.useQuery(async signal => C.query(await adapter.list(kind, scope, signal), 'list'), [adapter, kind, scope], validKind && showList);
    React.useEffect(() => {
      const selector = done ? '.modal-f button:not(:disabled)' : 'input:not(:disabled):not([readonly]),select:not(:disabled)';
      const target = root.current && root.current.querySelector(selector);
      if (target) target.focus();
    }, [editor && editor.action, editor && editor.ref, done, showList]);
    React.useEffect(() => {
      if (done) setLastReceipt(command.result);
      if (command.phase === 'rejected') {
        const code = command.error && command.error.error && command.error.error.code;
        if (['stale_write', 'stale_context', 'context_expired'].includes(code)) setNeedsReview(true);
      }
    }, [command.phase, command.result, command.error]);
    async function load(action, ref, reviewing = false) {
      if (locked) return;
      const ticket = ++generation.current; setBusy(true); setError(null);
      try {
        const result = ref ? C.query(await adapter.detail(kind, ref, new AbortController().signal), 'entity') :
          C.query(await adapter.list(kind, { ...scope, page: 1, snapshot_ref: undefined }, new AbortController().signal), 'list');
        if (ref && result.data.ref !== ref) throw C.failure('读取对象与所选目录不一致。');
        if (!alive.current || ticket !== generation.current) return;
        if (reviewing) setReview(result);
        else setEditor({ action, ref, base: ref ? result.data : null, draft: M.draft(ref ? result.data : null),
          context: ref ? result.data.write_context : result.data.create_context, source: result.meta.source });
      } catch (failure) { if (alive.current && ticket === generation.current) setError(failure); }
      finally { if (alive.current && ticket === generation.current) setBusy(false); }
    }
    function open(action, ref = null) {
      if (locked || !command.reset()) return;
      setReview(null); setNeedsReview(false); load(action, ref);
    }
    function finish() {
      const receipt = done ? command.result : lastReceipt;
      if (receipt && onCommitted) onCommitted(receipt); else onClose();
    }
    function back(target) {
      if (locked || !command.reset()) return;
      setEditor(null); setReview(null); setError(null); setDiscard(null); setNeedsReview(false);
      if (target === 'close') finish();
      else setScope(current => ({ ...current, page: 1, snapshot_ref: undefined }));
    }
    function requestClose(target = 'close') {
      if (locked) return;
      if (editor && editor.action !== 'delete' && !done && JSON.stringify(editor.draft) !== JSON.stringify(M.draft(editor.base))) { setDiscard(target); return; }
      back(target);
    }
    function change(key, value) { setEditor(current => ({ ...current, draft: { ...current.draft, [key]: value } })); setError(null); }
    function acceptReview() {
      if (!review || locked || !command.reset()) return;
      // Refresh guards only. The original baseline and draft remain unchanged, so unseen fields are not overwritten.
      setEditor(current => ({ ...current, context: current.ref ? review.data.write_context : review.data.create_context, source: review.meta.source }));
      setReview(null); setNeedsReview(false); setError(null);
    }
    const reason = editor ? needsReview ? '资料已变化，请重新读取并核对。' : review ? '请先核对最新资料。' :
      C.blocked(editor.context, kind, editor.action, editor.source) : '';
    async function submit(event) {
      event.preventDefault(); if (locked || done || !editor || reason || discard) return;
      try {
        const input = editor.action === 'delete' ? {} : M.input(kind, editor.draft, editor.base);
        setError(null); await command.submit(kind, editor.action, editor.ref, editor.context, input);
      } catch (failure) { setError(failure); }
    }
    const title = (editor && !done ? ({ create: '新增', update: '编辑', delete: '删除' })[editor.action] : '维护') + (M.names[kind] || '资源目录');
    return <div className="plana resource-catalog" data-resource-catalog={kind} ref={root}>
      <style>{`
        .resource-catalog .modal.lg { width:min(860px,100%); }
        .resource-catalog .modal-b.scroll { max-height:min(65vh,690px); padding-bottom:18px; }
        .resource-catalog .rc-toolbar { flex-wrap:wrap; gap:8px; margin-bottom:14px; }
        .resource-catalog .rc-toolbar .search { flex:1 1 180px; min-width:120px; max-width:270px; }
        .resource-catalog .rc-toolbar .field { min-width:130px; }
        .resource-catalog .rc-toolbar .field select { height:32px; }
        .resource-catalog table.tbl { min-width:0; width:100%; table-layout:fixed; }
        .resource-catalog .rc-list th:first-child { width:40%; }
        .resource-catalog .rc-list th:last-child { width:112px; }
        .resource-catalog .rc-wrap { overflow-wrap:anywhere; }
        .resource-catalog .rc-error { color:var(--ui-danger-text); }
        .resource-catalog .rc-pattern { margin-top:20px; border-top:1px solid var(--ui-border); padding-top:14px; }
        .resource-catalog .rc-section-head { display:flex; align-items:center; gap:12px; flex-wrap:wrap; margin-bottom:10px; }
        .resource-catalog .rc-section-head h3 { font-size:14px; margin:0; flex:1; }
        .resource-catalog .rc-pattern-table th { width:22%; }
        .resource-catalog .rc-pattern-table th:first-child { width:12%; }
        .resource-catalog .rc-pattern-table th:last-child { width:18%; }
        .resource-catalog .rc-pattern-table td.field { display:table-cell; }
        .resource-catalog .rc-pattern-table .field input, .resource-catalog .rc-pattern-table select { padding-left:6px; padding-right:6px; min-width:0; height:32px; }
        .resource-catalog .rc-pattern-table select { padding-right:24px; }
        .resource-catalog .rc-note { display:block; margin-top:12px; }
        .resource-catalog .rc-facts { overflow-wrap:anywhere; }
        .resource-catalog .rc-list td, .resource-catalog .rc-pattern-table td { vertical-align:middle; }
        .resource-catalog .rc-list .rowact { gap:8px; }
        .resource-catalog .rc-list .mini { width:30px; height:30px; padding:0; flex:none; }
        .resource-catalog .rc-list .mini svg { width:18px; height:18px; flex:none; }
        .resource-catalog .rc-pattern-table td { padding:8px 6px; }
      `}</style>
      <Modal title={title} icon={kind === 'shift_profile' ? 'clock-3' : 'folder-open'} locked={locked} onClose={() => requestClose()}
        footer={discard ? <><Button onClick={() => setDiscard(null)}>继续编辑</Button><Button icon="x" onClick={() => back(discard)}>放弃修改</Button></> :
          <><Button onClick={() => requestClose()} reason={locked ? '操作尚未核实，请保留当前页面。' : ''}>{lastReceipt || done ? '完成并返回' : '关闭'}</Button>
            {editor && !done && <><Button onClick={() => requestClose('list')} disabled={locked}>返回目录</Button><Button type="submit" form={formId} className="btn primary" icon={editor.action === 'delete' ? 'minus' : 'check'} reason={reason} disabled={locked}>
              {editor.action === 'delete' ? '确认删除' : '保存'}</Button></>}
            {done && <Button icon="folder-open" onClick={() => back('list')}>继续维护</Button>}</>}>
        <div className="modal-b form scroll">
          {!validKind && <ErrorBox error={C.failure('不支持此类资源目录。')} />}
          {busy && <p role="status">正在读取目录资料…</p>}
          {validKind && showList && <CatalogList kind={kind} list={list} scope={scope} setScope={setScope} onOpen={open} disabled={locked} />}
          {editor && !done && <form id={formId} onSubmit={submit} noValidate><Editor kind={kind} editor={editor} error={error || command.error} disabled={locked || !!discard} onChange={change} /></form>}
          {discard && <div className="match-note rc-note" role="alert">有尚未保存的修改。确认放弃后才会离开。</div>}
          <ErrorBox error={error} /><ResourceForms.Feedback command={command} />
          {command.intent && command.locked && <p className="rc-wrap muted">原请求：{command.intent.request_key}</p>}
          {editor && !done && !command.locked && <div className="rc-pattern">
            <Button icon="refresh-cw" disabled={busy || !!discard} onClick={() => { setReview(null); load(editor.action, editor.ref, true); }}>重新读取最新资料</Button>
            {reason && <p role="status">{reason}</p>}
            {review && <div className="match-note rc-note"><p>最新资料已读取，已填写的内容保持不变。请核对后继续编辑。</p>
              {editor.ref ? <Editor.Facts kind={kind} entity={review.data} /> : <p>当前目录共有 {review.data.page.total} 条。</p>}
              <Button icon="check" disabled={locked || !!discard} onClick={acceptReview}>已核对，继续编辑</Button></div>}</div>}
        </div></Modal>
    </div>;
  }
  window.ResourceCatalog = ResourceCatalog;
})();
