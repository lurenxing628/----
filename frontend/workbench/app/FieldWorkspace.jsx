(function () {
  'use strict';
  const S = window.APSResourceSession, { Styles, Button, ErrorBox, Feedback } = window.FieldControls;
  let productionAdapter;
  function FieldWorkspace({ adapter, onNavigate, initialContext = {} }) {
    const api = React.useMemo(() => adapter || (productionAdapter || (productionAdapter = window.FieldAPI.create())), [adapter]);
    const [scope, setScope] = React.useState(() => window.FieldAPI.initial(initialContext));
    const [opened, setOpened] = React.useState(initialContext.task_ref || initialContext.entity_ref || null), [editor, setEditor] = React.useState(null), [files, setFiles] = React.useState(false), [revision, setRevision] = React.useState(0);
    const drafts = React.useRef(new Map());
    const [, renderDrafts] = React.useReducer(value => value + 1, 0);
    const [nextDraft, setNextDraft] = React.useState(null), [notice, setNotice] = React.useState('');
    const command = S.useCommand(api);
    const currentDraft = editor && drafts.current.get(editor.taskRef);
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({ dirty: !!(currentDraft && currentDraft.retained.dirty && command.phase !== 'done'), locked: command.locked,
      message: '当前报工有未保存草稿，继续会丢弃这些内容。' });
    window.WorkbenchGuards.useDirtyGuard({ dirty: Array.from(drafts.current.values()).some(value => value.retained.dirty && (!editor || value.editor.taskRef !== editor.taskRef)),
      message: '其他任务有临时保留的报工草稿，离开页面会丢弃这些内容。' });
    const retainDraft = React.useCallback(retained => {
      if (!editor) return;
      drafts.current.set(editor.taskRef, { editor, retained });
      renderDrafts();
    }, [editor]);
    const read = S.useQuery(signal => window.FieldAPI.readView(api, scope, signal), [api, scope, revision]);
    const data = read.result && read.result.data, snapshot = read.result && read.result.meta.snapshot_ref;
    const readPlan = React.useRef(scope.plan_ref);
    if (data && !read.loading && !read.error) readPlan.current = data.scope.plan_ref;
    const captionPlan = !read.loading && !read.error && data && data.plan;
    const captionStatus = captionPlan && ({ official: captionPlan.is_current_official ? '当前正式采用' : '历史正式计划', candidate: window.WorkbenchTerms.candidate, scenario: window.WorkbenchTerms.trial_scenario })[captionPlan.kind];
    window.WorkbenchCaption.useCaption(captionStatus ? {
      reference: captionPlan.plan_ref, label: '现场计划', name: captionPlan.display_name, status: captionStatus,
      version: captionPlan.kind === 'official' && Number.isSafeInteger(captionPlan.version) ? '正式 v' + captionPlan.version : undefined,
      range: data.scope.plan_finish_date_from && data.scope.plan_finish_date_to ? '计划完工 ' + data.scope.plan_finish_date_from + ' 至 ' + data.scope.plan_finish_date_to : undefined
    } : null);
    const selectedTask = data && data.tasks.find(task => task.task_ref === opened);
    window.WorkbenchPageContext.useSnapshot(data ? {
      plan_ref: data.scope.plan_ref, scope: data.scope,
      table: { page: data.page.number, size: data.page.size }, task_ref: opened,
      operation_ref: selectedTask ? selectedTask.operation_ref : undefined, return_to: initialContext.return_to
    } : null, !!data && !read.loading && !read.error && !command.locked && command.phase !== 'done' && (!opened || !!selectedTask));
    const blocked = command.locked || !!editor || files || !!nextDraft || command.phase === 'done';
    const rowBlocked = command.locked || files || !!nextDraft || command.phase === 'done';
    function openTask(ref) {
      if (rowBlocked || !command.reset()) return;
      const next = opened === ref ? null : ref, saved = next && drafts.current.get(next);
      setOpened(next); setEditor(saved ? saved.editor : null);
    }
    // The save notice describes the read that follows a save; any user-initiated read replaces it.
    function filter(next) { if (blocked) return; setNotice(''); setScope({ ...next, page: 1, size: scope.size, snapshot_ref: undefined }); setOpened(null); }
    function refresh() {
      if (blocked) return;
      setNotice('');
      setScope(current => ({ ...current, plan_ref: current.plan_ref || readPlan.current, task_ref: opened || undefined,
        operation_ref: selectedTask ? selectedTask.operation_ref : undefined, snapshot_ref: undefined }));
      setRevision(value => value + 1);
    }
    async function closeEditor() {
      if (!await window.WorkbenchGuards.confirmLeave({ owner: guardOwner }) || !command.reset()) return;
      if (editor) drafts.current.delete(editor.taskRef);
      setEditor(null);
    }
    function done(options = {}) {
      if (command.phase !== 'done' || !command.reset()) return;
      if (editor) drafts.current.delete(editor.taskRef);
      setNextDraft(options.continueAfter ? options : null); setNotice('已保存，正在自动刷新最新报工。');
      setEditor(null); setFiles(false); setScope(current => ({ ...current, plan_ref: current.plan_ref || readPlan.current,
        page: undefined, task_ref: opened || undefined, snapshot_ref: undefined })); setRevision(value => value + 1);
    }
    function continueReady(task) {
      if (!nextDraft || command.locked) return;
      const reason = window.FieldDraftModel.continuation(nextDraft.previousContext, task, nextDraft);
      setNextDraft(null); setNotice(reason || '已核对最新报工，已打开新的报工草稿。');
      if (!reason) setEditor({ taskRef: task.task_ref, action: 'create' });
    }
    const effectiveScope = data ? data.scope : scope;
    const filtered = !!(scope.query || scope.state && scope.state !== 'all' || scope.plan_finish_date_from || scope.plan_finish_date_to || scope.range_start || scope.batch_ids || scope.resource_ref);
    const returnTarget = initialContext.return_to;
    const returnView = typeof returnTarget === 'string' ? returnTarget : returnTarget && returnTarget.view;
    const canReturn = ['analysis', 'gantt', 'fieldgantt', 'reports', 'review', 'dashboard'].includes(returnView);
    return <section className="plana field-workspace" data-field-workspace aria-label="现场记录"><Styles />
      <div className="field-toolbar"><h2 className="wb-page-title">现场记录</h2><span className="field-note wb-page-context">{data ? data.plan ? data.plan.display_name : '暂无正式计划' : read.loading ? '正在读取计划' : '计划未读取'}</span><span className="field-space" />
        {canReturn && onNavigate && <Button icon="arrow-left" disabled={blocked} onClick={() => onNavigate(returnView, typeof returnTarget === 'object' ? returnTarget.context || {} : { plan_ref: effectiveScope.plan_ref })}>返回</Button>}
        <Button icon="refresh-cw" aria-label="刷新现场记录" disabled={blocked || read.loading} onClick={refresh} />
        <Button transfer="import" disabled={blocked || !data} onClick={() => { command.reset(); setFiles(true); }}>报工文件</Button>
      </div>
      {!editor && !files && <Feedback command={command} onDone={done} />}
      {notice && <p className="field-note field-save-status" role="status">{read.error ? '报工已保存，但刷新失败；请再点「刷新现场记录」，没有重复写入。' : read.loading ? notice : nextDraft ? '已保存，正在核对最新数据…' : notice === '已保存，正在自动刷新最新报工。' ? '已保存并刷新最新报工。' : notice}</p>}
      <window.FieldFilters scope={effectiveScope} onChange={filter} disabled={blocked || read.loading} summary={data && data.summary} />
      <ErrorBox error={read.error} />
      <window.FieldTable tasks={data ? data.tasks : []} loading={read.loading} loaded={!!data} filtered={filtered} onClear={() => filter({ plan_ref: effectiveScope.plan_ref })} error={read.error} onRetry={() => { if (!command.locked) { setScope(current => ({ ...current, snapshot_ref: undefined })); setRevision(value => value + 1); } }} opened={opened} disabled={rowBlocked || read.loading} onOpen={openTask} />
      {data && <window.WorkbenchListControls.Pager page={data.page} sizes={[10, 20, 50, 100]} unit="道工序" label="现场" sizeLabel="现场每页数量" disabled={blocked} busy={read.loading}
        onPage={page => { setNotice(''); setScope({ ...effectiveScope, size: scope.size, page, snapshot_ref: snapshot }); setOpened(null); }}
        onSize={size => { setNotice(''); setScope({ ...effectiveScope, size, page: 1, snapshot_ref: snapshot }); setOpened(null); }} />}
      {selectedTask && <window.FieldDetail key={selectedTask.task_ref} adapter={api} taskRef={selectedTask.task_ref} scope={effectiveScope} snapshot={snapshot} revision={revision} command={command} editor={editor}
        retained={drafts.current.get(selectedTask.task_ref)?.retained} onDraft={retainDraft} nextDraft={nextDraft} onContinueReady={continueReady}
        onEdit={value => { if (command.reset()) setEditor(value); }} onCloseEditor={closeEditor} onDone={done} onNavigate={onNavigate} />}
      {files && <window.FieldFiles adapter={api} scope={effectiveScope} snapshot={snapshot} command={command} onClose={() => { if (command.reset()) setFiles(false); }} onDone={done} />}
    </section>;
  }
  window.FieldWorkspace = FieldWorkspace;
})();
