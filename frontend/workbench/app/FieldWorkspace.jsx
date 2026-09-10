(function () {
  'use strict';
  const C = window.FieldContract, S = window.APSResourceSession, { Styles, Button, ErrorBox, Feedback } = window.FieldControls;
  let productionAdapter;
  function FieldWorkspace({ adapter, onNavigate, initialContext = {} }) {
    const api = React.useMemo(() => adapter || (productionAdapter || (productionAdapter = window.FieldAPI.create())), [adapter]);
    const [scope, setScope] = React.useState(() => ({ ...(initialContext.scope || {}), ...(initialContext.plan_ref ? { plan_ref: initialContext.plan_ref } : {}),
      task_ref: initialContext.task_ref || initialContext.entity_ref, operation_ref: initialContext.operation_ref,
      snapshot_ref: initialContext.snapshot_ref, page: initialContext.table ? initialContext.table.page : 1, size: initialContext.table ? initialContext.table.size : 20 }));
    const [opened, setOpened] = React.useState(initialContext.task_ref || initialContext.entity_ref || null), [editor, setEditor] = React.useState(null), [files, setFiles] = React.useState(false), [revision, setRevision] = React.useState(0);
    const drafts = React.useRef(new Map());
    const command = S.useCommand(api);
    const read = S.useQuery(async signal => C.query(await api.list(scope, signal), 'list'), [api, scope, revision]);
    const data = read.result && read.result.data, snapshot = read.result && read.result.meta.snapshot_ref;
    const captionPlan = !read.loading && !read.error && data && data.plan;
    const captionStatus = captionPlan && ({ official: captionPlan.is_current_official ? '当前正式采用' : '历史正式方案', candidate: '候选方案', scenario: '试调场景' })[captionPlan.kind];
    window.WorkbenchCaption.useCaption(captionStatus ? {
      reference: captionPlan.plan_ref, label: '现场计划', name: captionPlan.display_name, status: captionStatus,
      version: captionPlan.kind === 'official' && Number.isSafeInteger(captionPlan.version) ? '正式 v' + captionPlan.version : undefined,
      range: data.scope.plan_finish_date_from && data.scope.plan_finish_date_to ? '计划完工 ' + data.scope.plan_finish_date_from + ' 至 ' + data.scope.plan_finish_date_to : undefined
    } : null);
    const selectedTask = data && data.tasks.find(task => task.task_ref === opened);
    window.WorkbenchPageContext.useSnapshot(data ? {
      plan_ref: data.scope.plan_ref, scope: data.scope, snapshot_ref: snapshot,
      table: { page: data.page.number, size: data.page.size }, task_ref: opened,
      operation_ref: selectedTask ? selectedTask.operation_ref : undefined, return_to: initialContext.return_to
    } : null, !!data && !read.loading && !read.error && !command.locked && command.phase !== 'done' && (!opened || !!selectedTask));
    const blocked = command.locked || !!editor || files || command.phase === 'done';
    const rowBlocked = command.locked || files || command.phase === 'done';
    function openTask(ref) {
      if (rowBlocked || !command.reset()) return;
      const next = opened === ref ? null : ref, saved = next && drafts.current.get(next);
      setOpened(next); setEditor(saved ? saved.editor : null);
    }
    function filter(next) { if (blocked) return; setScope({ ...next, page: 1, size: scope.size, snapshot_ref: undefined }); setOpened(null); }
    function refresh() { if (blocked) return; setScope(current => ({ ...current, page: 1, snapshot_ref: undefined })); setRevision(value => value + 1); }
    function closeEditor() { if (!command.reset()) return; if (editor) drafts.current.delete(editor.taskRef); setEditor(null); }
    function done() { if (!command.reset()) return; if (editor) drafts.current.delete(editor.taskRef); setEditor(null); setFiles(false); setScope(current => ({ ...current, page: 1, task_ref: opened || undefined, snapshot_ref: undefined })); setRevision(value => value + 1); }
    const effectiveScope = data ? data.scope : scope;
    const returnTarget = initialContext.return_to;
    const returnView = typeof returnTarget === 'string' ? returnTarget : returnTarget && returnTarget.view;
    const canReturn = ['analysis', 'gantt', 'fieldgantt', 'reports', 'dashboard'].includes(returnView);
    return <section className="plana field-workspace" data-field-workspace aria-label="现场记录"><Styles />
      <div className="field-toolbar"><h2>现场记录</h2><span className="field-note">{data ? data.plan ? data.plan.display_name : '暂无正式计划' : read.loading ? '正在读取计划' : '计划未读取'}</span><span className="field-space" />
        {canReturn && onNavigate && <Button icon="arrow-left" disabled={blocked} onClick={() => onNavigate(returnView, typeof returnTarget === 'object' ? returnTarget.context || {} : { plan_ref: effectiveScope.plan_ref })}>返回</Button>}
        <Button icon="refresh-cw" aria-label="刷新现场记录" disabled={blocked || read.loading} onClick={refresh} />
        <Button transfer="import" disabled={blocked || !data} onClick={() => { command.reset(); setFiles(true); }}>报工文件</Button>
      </div>
      {!editor && !files && <Feedback command={command} onDone={done} />}
      <window.FieldFilters scope={effectiveScope} onChange={filter} disabled={blocked || read.loading} summary={data && data.summary} />
      <ErrorBox error={read.error} />{read.error && <Button icon="refresh-cw" disabled={blocked} onClick={refresh}>重读现场任务</Button>}
      <window.FieldTable tasks={data ? data.tasks : []} loading={read.loading} loaded={!!data} opened={opened} disabled={rowBlocked || read.loading} onOpen={openTask}
        renderDetail={task => <window.FieldDetail adapter={api} taskRef={task.task_ref} scope={effectiveScope} snapshot={snapshot} revision={revision} command={command} editor={editor}
          retained={drafts.current.get(task.task_ref)?.retained} onDraft={retained => drafts.current.set(task.task_ref, { editor, retained })}
          onEdit={value => { if (command.reset()) setEditor(value); }} onCloseEditor={closeEditor} onDone={done} onNavigate={onNavigate} />} />
      {data && <div className="field-footer"><span>共 {data.page.total} 道工序 · 第 {data.page.number} / {data.page.pages} 页</span><span className="field-space" />
        <label>每页<select aria-label="现场每页数量" disabled={blocked || read.loading} value={scope.size} onChange={event => { setScope({ ...effectiveScope, size: Number(event.target.value), page: 1, snapshot_ref: snapshot }); setOpened(null); }}>{[10, 20, 50, 100].map(size => <option key={size} value={size}>{size}</option>)}</select></label>
        <Button icon="chevron-left" aria-label="现场上一页" disabled={blocked || read.loading || data.page.number <= 1} onClick={() => { setScope({ ...effectiveScope, size: scope.size, page: data.page.number - 1, snapshot_ref: snapshot }); setOpened(null); }} />
        <Button icon="chevron-right" aria-label="现场下一页" disabled={blocked || read.loading || data.page.number >= data.page.pages} onClick={() => { setScope({ ...effectiveScope, size: scope.size, page: data.page.number + 1, snapshot_ref: snapshot }); setOpened(null); }} /></div>}
      {files && <window.FieldFiles adapter={api} scope={effectiveScope} snapshot={snapshot} command={command} onClose={() => { if (command.reset()) setFiles(false); }} onDone={done} />}
    </section>;
  }
  window.FieldWorkspace = FieldWorkspace;
})();
