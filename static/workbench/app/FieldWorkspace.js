(function () {
  'use strict';

  const S = window.APSResourceSession,
    {
      Styles,
      Button,
      ErrorBox,
      Feedback
    } = window.FieldControls;
  let productionAdapter;
  function FieldWorkspace({
    adapter,
    onNavigate,
    initialContext = {}
  }) {
    const api = React.useMemo(() => adapter || productionAdapter || (productionAdapter = window.FieldAPI.create()), [adapter]);
    const [scope, setScope] = React.useState(() => window.FieldAPI.initial(initialContext));
    const [opened, setOpened] = React.useState(initialContext.task_ref || initialContext.entity_ref || null),
      [editor, setEditor] = React.useState(null),
      [files, setFiles] = React.useState(false),
      [revision, setRevision] = React.useState(0);
    const drafts = React.useRef(new Map());
    const command = S.useCommand(api);
    const read = S.useQuery(signal => window.FieldAPI.readView(api, scope, signal), [api, scope, revision]);
    const data = read.result && read.result.data,
      snapshot = read.result && read.result.meta.snapshot_ref;
    const readPlan = React.useRef(scope.plan_ref);
    if (data && !read.loading && !read.error) readPlan.current = data.scope.plan_ref;
    const captionPlan = !read.loading && !read.error && data && data.plan;
    const captionStatus = captionPlan && {
      official: captionPlan.is_current_official ? '当前正式采用' : '历史正式方案',
      candidate: '候选方案',
      scenario: '试调场景'
    }[captionPlan.kind];
    window.WorkbenchCaption.useCaption(captionStatus ? {
      reference: captionPlan.plan_ref,
      label: '现场计划',
      name: captionPlan.display_name,
      status: captionStatus,
      version: captionPlan.kind === 'official' && Number.isSafeInteger(captionPlan.version) ? '正式 v' + captionPlan.version : undefined,
      range: data.scope.plan_finish_date_from && data.scope.plan_finish_date_to ? '计划完工 ' + data.scope.plan_finish_date_from + ' 至 ' + data.scope.plan_finish_date_to : undefined
    } : null);
    const selectedTask = data && data.tasks.find(task => task.task_ref === opened);
    window.WorkbenchPageContext.useSnapshot(data ? {
      plan_ref: data.scope.plan_ref,
      scope: data.scope,
      table: {
        page: data.page.number,
        size: data.page.size
      },
      task_ref: opened,
      operation_ref: selectedTask ? selectedTask.operation_ref : undefined,
      return_to: initialContext.return_to
    } : null, !!data && !read.loading && !read.error && !command.locked && command.phase !== 'done' && (!opened || !!selectedTask));
    const blocked = command.locked || !!editor || files || command.phase === 'done';
    const rowBlocked = command.locked || files || command.phase === 'done';
    function openTask(ref) {
      if (rowBlocked || !command.reset()) return;
      const next = opened === ref ? null : ref,
        saved = next && drafts.current.get(next);
      setOpened(next);
      setEditor(saved ? saved.editor : null);
    }
    function filter(next) {
      if (blocked) return;
      setScope({
        ...next,
        page: 1,
        size: scope.size,
        snapshot_ref: undefined
      });
      setOpened(null);
    }
    function refresh() {
      if (blocked) return;
      setScope(current => ({
        ...current,
        plan_ref: current.plan_ref || readPlan.current,
        task_ref: opened || undefined,
        operation_ref: selectedTask ? selectedTask.operation_ref : undefined,
        snapshot_ref: undefined
      }));
      setRevision(value => value + 1);
    }
    function closeEditor() {
      if (!command.reset()) return;
      if (editor) drafts.current.delete(editor.taskRef);
      setEditor(null);
    }
    function done() {
      if (!command.reset()) return;
      if (editor) drafts.current.delete(editor.taskRef);
      setEditor(null);
      setFiles(false);
      setScope(current => ({
        ...current,
        plan_ref: current.plan_ref || readPlan.current,
        page: undefined,
        task_ref: opened || undefined,
        snapshot_ref: undefined
      }));
      setRevision(value => value + 1);
    }
    const effectiveScope = data ? data.scope : scope;
    const returnTarget = initialContext.return_to;
    const returnView = typeof returnTarget === 'string' ? returnTarget : returnTarget && returnTarget.view;
    const canReturn = ['analysis', 'gantt', 'fieldgantt', 'reports', 'review', 'dashboard'].includes(returnView);
    return /*#__PURE__*/React.createElement("section", {
      className: "plana field-workspace",
      "data-field-workspace": true,
      "aria-label": "\u73B0\u573A\u8BB0\u5F55"
    }, /*#__PURE__*/React.createElement(Styles, null), /*#__PURE__*/React.createElement("div", {
      className: "field-toolbar"
    }, /*#__PURE__*/React.createElement("h2", null, "\u73B0\u573A\u8BB0\u5F55"), /*#__PURE__*/React.createElement("span", {
      className: "field-note"
    }, data ? data.plan ? data.plan.display_name : '暂无正式计划' : read.loading ? '正在读取计划' : '计划未读取'), /*#__PURE__*/React.createElement("span", {
      className: "field-space"
    }), canReturn && onNavigate && /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-left",
      disabled: blocked,
      onClick: () => onNavigate(returnView, typeof returnTarget === 'object' ? returnTarget.context || {} : {
        plan_ref: effectiveScope.plan_ref
      })
    }, "\u8FD4\u56DE"), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u73B0\u573A\u8BB0\u5F55",
      disabled: blocked || read.loading,
      onClick: refresh
    }), /*#__PURE__*/React.createElement(Button, {
      transfer: "import",
      disabled: blocked || !data,
      onClick: () => {
        command.reset();
        setFiles(true);
      }
    }, "\u62A5\u5DE5\u6587\u4EF6")), !editor && !files && /*#__PURE__*/React.createElement(Feedback, {
      command: command,
      onDone: done
    }), /*#__PURE__*/React.createElement(window.FieldFilters, {
      scope: effectiveScope,
      onChange: filter,
      disabled: blocked || read.loading,
      summary: data && data.summary
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), read.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: blocked,
      onClick: refresh
    }, "\u91CD\u8BFB\u73B0\u573A\u4EFB\u52A1"), /*#__PURE__*/React.createElement(window.FieldTable, {
      tasks: data ? data.tasks : [],
      loading: read.loading,
      loaded: !!data,
      opened: opened,
      disabled: rowBlocked || read.loading,
      onOpen: openTask,
      renderDetail: task => /*#__PURE__*/React.createElement(window.FieldDetail, {
        adapter: api,
        taskRef: task.task_ref,
        scope: effectiveScope,
        snapshot: snapshot,
        revision: revision,
        command: command,
        editor: editor,
        retained: drafts.current.get(task.task_ref)?.retained,
        onDraft: retained => drafts.current.set(task.task_ref, {
          editor,
          retained
        }),
        onEdit: value => {
          if (command.reset()) setEditor(value);
        },
        onCloseEditor: closeEditor,
        onDone: done,
        onNavigate: onNavigate
      })
    }), data && /*#__PURE__*/React.createElement("div", {
      className: "field-footer"
    }, /*#__PURE__*/React.createElement("span", null, "\u5171 ", data.page.total, " \u9053\u5DE5\u5E8F \xB7 \u7B2C ", data.page.number, " / ", data.page.pages, " \u9875"), /*#__PURE__*/React.createElement("span", {
      className: "field-space"
    }), /*#__PURE__*/React.createElement("label", null, "\u6BCF\u9875", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u73B0\u573A\u6BCF\u9875\u6570\u91CF",
      disabled: blocked || read.loading,
      value: scope.size,
      onChange: event => {
        setScope({
          ...effectiveScope,
          size: Number(event.target.value),
          page: 1,
          snapshot_ref: snapshot
        });
        setOpened(null);
      }
    }, [10, 20, 50, 100].map(size => /*#__PURE__*/React.createElement("option", {
      key: size,
      value: size
    }, size)))), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": "\u73B0\u573A\u4E0A\u4E00\u9875",
      disabled: blocked || read.loading || data.page.number <= 1,
      onClick: () => {
        setScope({
          ...effectiveScope,
          size: scope.size,
          page: data.page.number - 1,
          snapshot_ref: snapshot
        });
        setOpened(null);
      }
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": "\u73B0\u573A\u4E0B\u4E00\u9875",
      disabled: blocked || read.loading || data.page.number >= data.page.pages,
      onClick: () => {
        setScope({
          ...effectiveScope,
          size: scope.size,
          page: data.page.number + 1,
          snapshot_ref: snapshot
        });
        setOpened(null);
      }
    })), files && /*#__PURE__*/React.createElement(window.FieldFiles, {
      adapter: api,
      scope: effectiveScope,
      snapshot: snapshot,
      command: command,
      onClose: () => {
        if (command.reset()) setFiles(false);
      },
      onDone: done
    }));
  }
  window.FieldWorkspace = FieldWorkspace;
})();
