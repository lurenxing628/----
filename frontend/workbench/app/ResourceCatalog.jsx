(function () {
  'use strict';
  const C = window.APSResourceContract, S = window.APSResourceSession, M = window.APSResourceCatalogModel;
  const { Modal, Button, ErrorBox, Issues, focusFirstInvalid } = window.ResourceControls;
  const { EmptyState, Pager } = window.WorkbenchListControls;
  const Editor = window.ResourceCatalogEditor;
  const initialScope = () => ({ query: '', status: '', page: 1, size: 20, sort: 'business_code', direction: 'asc' });
  function CatalogList({ kind, list, scope, setScope, onOpen, disabled }) {
    const [search, setSearch] = React.useState(''), data = list.result && list.result.data;
    function filter(patch) { setScope(current => ({ ...current, ...patch, page: 1, snapshot_ref: undefined })); }
    return <><form className="toolbar rc-toolbar" onSubmit={event => { event.preventDefault(); filter({ query: search }); }}>
      <label className="search"><input type="search" aria-label="搜索编号或名称" value={search} disabled={disabled} onChange={event => setSearch(event.target.value)} /></label>
      <Button icon="search" type="submit" aria-label="搜索" disabled={disabled} />
      <div className="field"><select aria-label="状态筛选" value={scope.status} disabled={disabled} onChange={event => filter({ status: event.target.value })}>
        <option value="">全部状态</option><option value="active">启用</option><option value="inactive">停用</option><option value="unknown">旧状态未知</option></select></div>
      <Button icon="refresh-cw" aria-label="刷新列表" disabled={disabled} busy={list.loading} onClick={() => { filter({}); list.reload(); }} />
      <span className="tb-spacer" /><Button icon="plus" className="btn primary" disabled={disabled} reason={C.blocked(data && data.create_context, kind, 'create', list.result && list.result.meta.source)} onClick={() => onOpen('create')}>新增{M.names[kind]}</Button>
    </form><ErrorBox error={list.error} />{list.loading && <EmptyState kind="loading" title="正在读取列表" />}
      {data && <><Issues issues={list.result.warnings} /><div className="wb-table-frame rc-list-scroll" data-sticky-head data-sticky-actions><table className="tbl wb-table rc-list"><caption className="wb-visually-hidden">{M.names[kind]}列表</caption><thead><tr>
        <th scope="col" className="wb-col-key">编号 / 名称</th><th scope="col">状态</th><th scope="col">{kind === 'machine_group' ? '关联设备' : '关联人员'}</th>{kind === 'shift_profile' && <th scope="col">轮换天数</th>}<th scope="col" className="wb-col-actions">操作</th></tr></thead><tbody>
        {data.entities.map(entity => <tr key={entity.ref}><td className="rc-wrap wb-col-key"><b>{entity.business_code}</b><div>{entity.label}</div></td>
          <td><span className={'pill ' + (entity.status === 'active' ? 'ok' : entity.status === 'inactive' ? 'off' : 'warn')}><span className="dot" />{entity.status === 'active' ? '启用' : entity.status === 'inactive' ? '停用' : '旧状态未知'}</span></td>
          <td>{M.memberCount(kind, entity) === null ? '未读取' : M.memberCount(kind, entity)}</td>{kind === 'shift_profile' && <td>{entity.fields.cycle_days}</td>}
          <td className="wb-col-actions"><div className="rowact"><Button className="mini" icon="square-pen" aria-label={'编辑 ' + entity.business_code} disabled={disabled} reasonDisplay="tooltip" reason={C.blocked(entity.write_context, kind, 'update', list.result.meta.source)} onClick={() => onOpen('update', entity.ref)} />
            <Button className="mini" icon="minus" aria-label={'删除 ' + entity.business_code} disabled={disabled} reasonDisplay="tooltip" reason={C.blocked(entity.write_context, kind, 'delete', list.result.meta.source)} onClick={() => onOpen('delete', entity.ref)} /></div></td></tr>)}
        </tbody></table></div>
        {!data.entities.length && <EmptyState kind={scope.query || scope.status ? 'filtered' : 'empty'} title="当前范围没有记录"
          hint="可清除搜索和状态筛选后查看全部记录。" action={scope.query || scope.status ? <Button disabled={disabled} onClick={() => { setSearch(''); filter({ query: '', status: '' }); }}>清除筛选</Button> : undefined} />}
        <Pager page={data.page} sizes={[20]} unit="条" label="列表" disabled={disabled || list.loading}
          onPage={page => setScope({ ...scope, page, snapshot_ref: list.result.meta.snapshot_ref })} /></>}
    </>;
  }
  function ResourceCatalog({ kind, adapter, onClose, onCommitted }) {
    const [scope, setScope] = React.useState(initialScope), [editor, setEditor] = React.useState(null);
    const [busy, setBusy] = React.useState(false), [error, setError] = React.useState(null), [review, setReview] = React.useState(null);
    const [lastReceipt, setLastReceipt] = React.useState(null), [needsReview, setNeedsReview] = React.useState(false);
    const command = S.useCommand(adapter), generation = React.useRef(0), alive = React.useRef(true), root = React.useRef(null), formId = React.useId();
    React.useEffect(() => { alive.current = true; return () => { alive.current = false; generation.current++; }; }, []);
    const validKind = Object.prototype.hasOwnProperty.call(M.names, kind), done = command.phase === 'done';
    const locked = command.locked || busy, showList = !editor && !command.locked && !done;
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({ owner: 'resource-catalog-' + formId,
      dirty: !!(editor && editor.action !== 'delete' && !done && JSON.stringify(editor.draft) !== JSON.stringify(M.draft(editor.base))),
      locked: command.locked, message: (M.names[kind] || '基础资料') + '有尚未保存的填写内容。' });
    React.useEffect(() => { if (error || command.error) focusFirstInvalid(root.current); }, [error, command.error]);
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
        if (ref && result.data.ref !== ref) throw C.failure('读到的记录与所选记录不一致，请刷新后重试。');
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
      setEditor(null); setReview(null); setError(null); setNeedsReview(false);
      if (target === 'close') finish();
      else setScope(current => ({ ...current, page: 1, snapshot_ref: undefined }));
    }
    async function requestClose(target = 'close', options = {}) {
      if (locked) return;
      if (!(options.guardConfirmed && options.guardOwner === guardOwner) && !await window.WorkbenchGuards.confirmLeave({ owner: guardOwner })) return;
      back(target);
    }
    function change(key, value) { setEditor(current => ({ ...current, draft: { ...current.draft, [key]: value } })); setError(null); }
    function acknowledge(value) { setEditor(current => ({ ...current, acknowledged: value })); }
    function acceptReview() {
      if (!review || locked || !command.reset()) return;
      // Refresh guards only. The original baseline and draft remain unchanged, so unseen fields are not overwritten.
      setEditor(current => ({ ...current, context: current.ref ? review.data.write_context : review.data.create_context, source: review.meta.source }));
      setReview(null); setNeedsReview(false); setError(null);
    }
    const reason = editor ? needsReview ? window.WorkbenchTerms.outcomes.stale : review ? '请先核对最新资料。' :
      C.blocked(editor.context, kind, editor.action, editor.source) : '';
    // Deleting basic data needs the checkbox confirmation, so the unchecked state becomes the confirm button's own reason.
    const confirmReason = editor && editor.action === 'delete' && !editor.acknowledged ? '请先勾选已核对要删除的资料及其关联关系。' : '';
    async function submit(event) {
      event.preventDefault(); if (locked || done || !editor || reason || confirmReason) return;
      try {
        const input = editor.action === 'delete' ? {} : M.input(kind, editor.draft, editor.base);
        setError(null); await command.submit(kind, editor.action, editor.ref, editor.context, input);
      } catch (failure) { setError(failure); }
    }
    const title = (editor && !done ? ({ create: '新增', update: '编辑', delete: '删除' })[editor.action] : '维护') + (M.names[kind] || '基础资料');
    return <div className="plana resource-catalog" data-resource-catalog={kind} ref={root}>
      <Modal title={title} icon={kind === 'shift_profile' ? 'clock-3' : 'folder-open'} locked={locked} guardOwner={guardOwner} onClose={options => requestClose('close', options)}
        footer={<><Button onClick={() => requestClose()} reason={locked ? '操作结果还没确认，请保留当前页面。' : ''}>{lastReceipt || done ? '完成并返回' : '关闭'}</Button>
            {editor && !done && <><Button onClick={() => requestClose('list')} disabled={locked}>返回列表</Button><Button type="submit" form={formId} className="btn primary" icon={editor.action === 'delete' ? 'minus' : 'check'} reason={reason || confirmReason} disabled={locked}>
              {editor.action === 'delete' ? '确认删除' : '保存'}</Button></>}
            {done && <Button icon="folder-open" onClick={() => back('list')}>继续维护</Button>}</>}>
        <div className="modal-b form scroll">
          {!validKind && <ErrorBox error={C.failure('不支持这类基础资料。')} />}
          {busy && <p role="status">正在读取资料…</p>}
          {validKind && showList && <CatalogList kind={kind} list={list} scope={scope} setScope={setScope} onOpen={open} disabled={locked} />}
          {editor && !done && <form id={formId} onSubmit={submit} noValidate><Editor kind={kind} editor={editor} error={error || command.error} disabled={locked} onChange={change} onValidationError={setError} onAcknowledge={acknowledge} /></form>}
          <ErrorBox error={error} excludePaths={editor && !done && editor.action !== 'delete' ? Editor.fieldPaths : []} /><ResourceForms.Feedback command={command} excludePaths={editor && !done && editor.action !== 'delete' ? Editor.fieldPaths : []} />
          {command.intent && command.locked && <window.WorkbenchReference entries={{ '操作编号': command.intent.request_key }} />}
          {editor && !done && !command.locked && <div className="rc-pattern">
            <Button icon="refresh-cw" disabled={busy} onClick={() => { setReview(null); load(editor.action, editor.ref, true); }}>刷新最新资料</Button>
            {reason && <p role="status">{reason}</p>}
            {review && <div className="match-note rc-note"><p>最新资料已读取，已填写的内容保持不变。请核对后继续编辑。</p>
              {editor.ref ? <Editor.Facts kind={kind} entity={review.data} /> : <p>当前共有 {review.data.page.total} 条记录。</p>}
              <Button icon="check" disabled={locked} onClick={acceptReview}>已核对，继续编辑</Button></div>}</div>}
        </div></Modal>
    </div>;
  }
  window.ResourceCatalog = ResourceCatalog;
})();
