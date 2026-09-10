(function () {
  'use strict';

  const A = window.TrialAPI,
    C = window.TrialContract,
    U = window.TrialControls,
    S = window.TrialSession;
  function Finish({
    data,
    kind,
    commands,
    onClose,
    onRecheck
  }) {
    const [name, setName] = React.useState(''),
      [confirm, setConfirm] = React.useState(false);
    React.useEffect(() => {
      setConfirm(false);
    }, [data]);
    const save = kind === 'save';
    return /*#__PURE__*/React.createElement(U.Modal, {
      title: save ? '保存试调场景' : '确认放弃草稿',
      icon: save ? 'check' : 'x',
      locked: commands.busy,
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(U.Button, {
        icon: "x",
        disabled: commands.busy,
        onClick: onClose
      }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(U.Button, {
        icon: "refresh-cw",
        disabled: commands.busy || !!commands.key,
        onClick: () => {
          setConfirm(false);
          onRecheck();
        }
      }, "\u91CD\u8BFB\u8349\u7A3F"), /*#__PURE__*/React.createElement(U.Button, {
        className: "btn primary",
        icon: save ? 'check' : 'x',
        disabled: !confirm || save && !name.trim() || commands.blocked || !data.write_context || data.write_context.capabilities['trial.' + kind] !== true,
        onClick: () => commands.execute({
          action: kind,
          draft_ref: data.draft_ref,
          input: save ? {
            name
          } : {
            confirm: true
          }
        }, data.write_context.write_token)
      }, save ? '确认保存场景' : '确认放弃'))
    }, /*#__PURE__*/React.createElement("div", {
      className: "trial-modal-body"
    }, /*#__PURE__*/React.createElement("p", null, save ? '保存后草稿关闭，场景保留全部原任务与调整记录，不改变正式计划。' : '仅关闭此草稿，不删除原计划、草稿记录和调整历史。此草稿将不能继续调整。'), /*#__PURE__*/React.createElement("p", null, "\u539F\u6765\u6E90\uFF1A", U.sourceLabel(data.base_identity), " \xB7 \u5B8C\u6574 ", data.task_count, " \u9053\u5B89\u6392 \xB7 \u5F53\u524D\u7EA6\u675F ", U.statusLabel(data.validation.constraints_status)), save && /*#__PURE__*/React.createElement("label", {
      className: "tt-naming"
    }, "\u573A\u666F\u540D\u79F0", /*#__PURE__*/React.createElement("input", {
      "aria-label": "\u573A\u666F\u540D\u79F0",
      maxLength: 120,
      value: name,
      onChange: e => {
        setName(e.target.value);
        setConfirm(false);
      },
      autoComplete: "off"
    })), /*#__PURE__*/React.createElement("label", {
      className: "tt-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: confirm,
      onChange: e => setConfirm(e.target.checked)
    }), save ? '确认保存完整场景，冲突和未排工序一并保留' : '确认放弃当前指定草稿'), /*#__PURE__*/React.createElement(U.ErrorBox, {
      error: commands.error
    })));
  }
  function Session({
    initialTarget,
    onNavigate,
    renderAdoption,
    onTargetChange
  }) {
    React.useEffect(() => {
      let original,
        printing = false;
      function beforePrint() {
        if (printing) return;
        original = document.documentElement.getAttribute('data-theme');
        printing = true;
        document.documentElement.setAttribute('data-theme', 'light');
      }
      function afterPrint() {
        if (!printing) return;
        if (original === null) document.documentElement.removeAttribute('data-theme');else document.documentElement.setAttribute('data-theme', original);
        printing = false;
      }
      window.addEventListener('beforeprint', beforePrint);
      window.addEventListener('afterprint', afterPrint);
      return () => {
        window.removeEventListener('beforeprint', beforePrint);
        window.removeEventListener('afterprint', afterPrint);
        afterPrint();
      };
    }, []);
    const [target, setTarget] = React.useState(initialTarget.base ? {} : initialTarget),
      [base, setBase] = React.useState(initialTarget.base || null);
    const [modal, setModal] = React.useState(initialTarget.base ? 'create' : null),
      [revision, refresh] = React.useReducer(n => n + 1, 0);
    const [stored, setStored] = React.useState(null),
      [selected, setSelected] = React.useState(null),
      [editing, setEditing] = React.useState(false);
    const [error, setError] = React.useState(null),
      [notice, setNotice] = React.useState(''),
      [directory, setDirectory] = React.useState(true);
    const [origin, setOrigin] = React.useState(initialTarget.task_origin || null),
      locatedOrigin = React.useRef(null);
    function notifyTarget(next) {
      if (typeof onTargetChange !== 'function') return;
      const failed = () => setError(new Error('试调对象已定位，但页面恢复地址更新失败。原记录仍在目录中，未重复写入。'));
      try {
        Promise.resolve(onTargetChange({
          ...next,
          ...(origin && next.draft_ref ? {
            task_origin: origin
          } : {})
        })).catch(failed);
      } catch (_) {
        failed();
      }
    }
    const key = target.scenario_ref || target.draft_ref || '',
      isScenario = !!target.scenario_ref;
    const read = S.useRead(async signal => {
      const v = await A.read('/trial/' + (isScenario ? 'scenarios/' : 'drafts/') + key, {}, signal);
      C.workspace(v.data, target);
      return v;
    }, [key, isScenario, revision], !!key);
    React.useEffect(() => {
      if (read.result) {
        setStored({
          key,
          result: read.result
        });
        setBase(read.result.data.base);
      }
    }, [read.result]);
    const result = read.result || stored && stored.key === key && stored.result,
      data = result && result.data;
    const originalTask = React.useMemo(() => {
      if (!origin || !read.result) return {
        task: null,
        error: null
      };
      try {
        return {
          task: C.originTask(read.result.data, origin),
          error: null
        };
      } catch (error) {
        return {
          task: null,
          error
        };
      }
    }, [origin, read.result]);
    React.useEffect(() => {
      if (originalTask.task && locatedOrigin.current !== key) {
        setSelected(originalTask.task.task_ref);
        locatedOrigin.current = key;
      }
    }, [originalTask.task, key]);
    window.WorkbenchCaption.useCaption(data && read.result && !read.busy && !read.error ? {
      reference: data.scenario_ref || data.draft_ref,
      label: data.scenario_ref ? '当前场景' : '当前草稿',
      name: data.name || U.sourceLabel(data.base_identity),
      status: data.scenario_ref ? '已存场景预览' : '试调草稿 · ' + U.statusLabel(data.status),
      ...(data.baseline.version !== null ? {
        version: '创建时正式基线 v' + data.baseline.version
      } : {}),
      range: '完整 ' + data.task_count + ' 道 · ' + U.timeLabel(data.time_scope.start) + ' 至 ' + U.timeLabel(data.time_scope.end)
    } : null);
    const commands = S.useCommands(receipt => {
      const d = receipt.data,
        next = d.scenario_ref ? {
          scenario_ref: d.scenario_ref
        } : {
          draft_ref: d.draft_ref
        };
      setModal(null);
      setEditing(false);
      setTarget(next);
      setDirectory(false);
      if (d.scenario_ref) {
        setSelected(null);
        setOrigin(null);
      }
      refresh();
      setNotice(d.scenario_ref ? '场景已保存，正在读取原场景快照；正式计划未改变。' : d.status === 'discarded' ? '指定草稿已放弃，原记录与历史仍保留。' : '试调已持久保存，正式计划未改变。');
      notifyTarget(next);
    });
    const actions = {
      ...commands,
      blocked: commands.blocked || !!key && (!read.result || !!read.error || read.busy || !!origin && !originalTask.task)
    };
    function guard() {
      if (!editing) {
        setError(null);
        return true;
      }
      setError(new Error('请先保存调整或取消当前工序编辑。'));
      return false;
    }
    function select(ref) {
      if (ref === selected || guard()) setSelected(ref);
    }
    function open(next) {
      if (!guard()) return;
      try {
        C.check(!origin || !!next.draft_ref, '原任务定位只能打开草稿，不能把已存场景当作草稿。');
        C.target(next);
        const canonical = next.scenario_ref ? {
          scenario_ref: next.scenario_ref
        } : {
          draft_ref: next.draft_ref
        };
        setTarget(canonical);
        setStored(null);
        setSelected(null);
        locatedOrigin.current = null;
        setNotice('');
        setDirectory(false);
        refresh();
        notifyTarget(canonical);
      } catch (error) {
        setError(error);
      }
    }
    function reload() {
      commands.restore();
      refresh();
    }
    const title = data ? data.name || U.sourceLabel(data.base_identity) : '尚未选择草稿或场景';
    return /*#__PURE__*/React.createElement("div", {
      className: "plana trial-workspace",
      "data-trial-workspace": true,
      "data-open-ref": key,
      "data-open-kind": isScenario ? 'scenario' : 'draft'
    }, /*#__PURE__*/React.createElement(window.TrialStyles, null), /*#__PURE__*/React.createElement("header", {
      className: "tt-heading"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", null, "\u6392\u4EA7\u65B9\u6848\u8BD5\u8C03"), /*#__PURE__*/React.createElement("span", {
      className: "tt-muted"
    }, title, data && ' · ' + U.statusLabel(data.status))), /*#__PURE__*/React.createElement("div", {
      className: "tt-tools"
    }, onNavigate && /*#__PURE__*/React.createElement(U.Button, {
      icon: "chevron-left",
      onClick: () => {
        if (guard()) onNavigate('analysis', base || {});
      }
    }, "\u8FD4\u56DE\u65B9\u6848"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "folder-open",
      onClick: () => setDirectory(!directory),
      "aria-expanded": directory
    }, "\u8349\u7A3F / \u573A\u666F\u76EE\u5F55"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "plus",
      disabled: commands.blocked,
      onClick: () => {
        if (guard()) setModal('create');
      }
    }, "\u65B0\u5EFA\u8BD5\u8C03"))), /*#__PURE__*/React.createElement(U.ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(U.ErrorBox, {
      error: commands.error
    }), /*#__PURE__*/React.createElement(U.ErrorBox, {
      error: originalTask.error
    }), !commands.key && commands.note && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, commands.note), commands.error && !commands.key && /*#__PURE__*/React.createElement(U.Button, {
      icon: "refresh-cw",
      onClick: reload,
      disabled: commands.busy
    }, "\u91CD\u8BFB\u6062\u590D\u8BB0\u5F55\u4E0E\u5F53\u524D\u5185\u5BB9"), commands.key && /*#__PURE__*/React.createElement("section", {
      className: "tt-notice",
      "aria-label": "\u5F85\u6838\u5B9E\u8BD5\u8C03\u8BF7\u6C42"
    }, /*#__PURE__*/React.createElement("strong", null, "\u539F\u8BD5\u8C03\u8BF7\u6C42\u5F85\u6838\u5B9E"), /*#__PURE__*/React.createElement("p", null, commands.note || '恢复记录只包含原请求编号，尚未读取结果。'), /*#__PURE__*/React.createElement("div", {
      className: "tt-tools"
    }, /*#__PURE__*/React.createElement(U.Button, {
      icon: "refresh-cw",
      onClick: commands.lookup,
      busy: commands.busy
    }, "\u67E5\u8BE2\u539F\u8BF7\u6C42"), /*#__PURE__*/React.createElement("span", {
      className: "tt-ref"
    }, commands.key))), notice && /*#__PURE__*/React.createElement("p", {
      role: "status",
      className: "tt-notice"
    }, notice), directory && /*#__PURE__*/React.createElement(window.TrialCatalog.Directory, {
      revision: revision,
      onOpen: open,
      filterBase: base,
      fixedBase: origin ? {
        plan_ref: origin.plan_ref
      } : null
    }), /*#__PURE__*/React.createElement(U.ErrorBox, {
      error: read.error
    }), key && /*#__PURE__*/React.createElement("div", {
      className: "tt-heading"
    }, /*#__PURE__*/React.createElement("span", {
      className: "tt-muted"
    }, read.busy ? '正在重新读取，写入已暂停。' : read.error ? '读取失败。下方为上次读取内容，写入已暂停。' : result ? '读取于 ' + U.timeLabel(result.meta.as_of) : ''), /*#__PURE__*/React.createElement(U.Button, {
      icon: "refresh-cw",
      "aria-label": "\u91CD\u8BFB\u5F53\u524D\u8BD5\u8C03",
      busy: read.busy,
      disabled: commands.busy || !!commands.key,
      onClick: reload
    })), !data && /*#__PURE__*/React.createElement("div", {
      className: "tt-empty",
      role: "status"
    }, read.busy ? '正在读取完整试调…' : '尚未打开试调草稿或场景'), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "tt-heading"
    }, /*#__PURE__*/React.createElement("span", null, "\u539F\u6765\u6E90\uFF1A", U.sourceLabel(data.base_identity), " \xB7 \u5B8C\u6574 ", data.task_count, " \u9053\u5B89\u6392 \xB7 \u672A\u6392 ", data.unplanned_operations.length, " \u9053"), /*#__PURE__*/React.createElement(U.Download, {
      data: data
    })), /*#__PURE__*/React.createElement("div", {
      className: "tt-muted"
    }, "\u521B\u5EFA\u65F6\u6B63\u5F0F\u57FA\u7EBF\uFF1A", data.baseline.plan_ref ? 'v' + data.baseline.version : '无正式基线', " \xB7 \u5BF9\u6BD4\u59CB\u7EC8\u4F7F\u7528\u539F\u8BD5\u8C03\u57FA\u7840"), /*#__PURE__*/React.createElement(window.TrialResults.Summary, {
      data: data
    }), /*#__PURE__*/React.createElement("div", {
      className: "tt-main"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(window.TrialGantt, {
      key: key,
      data: data,
      selected: selected,
      onSelect: select
    }), /*#__PURE__*/React.createElement(window.TrialResults.Results, {
      key: key,
      data: data,
      onSelect: select
    })), /*#__PURE__*/React.createElement(window.TrialDetails, {
      data: data,
      selected: selected,
      commands: actions,
      onSelect: select,
      onEditing: setEditing,
      onRecheck: reload
    })), /*#__PURE__*/React.createElement("footer", {
      className: "tt-footer"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("strong", null, "\u6574\u4F53\u7EA6\u675F\uFF1A", U.statusLabel(data.validation.constraints_status)), /*#__PURE__*/React.createElement("div", {
      className: "tt-muted"
    }, typeof renderAdoption === 'function' ? '保存试调不代表正式采用' : '完整场景正式采用尚未接入，正式计划未改变')), /*#__PURE__*/React.createElement("div", {
      className: "tt-tools"
    }, /*#__PURE__*/React.createElement(U.Button, {
      icon: "x",
      disabled: data.status !== 'editing' || actions.blocked || !data.write_context || data.write_context.capabilities['trial.discard'] !== true,
      onClick: () => {
        if (guard()) setModal('discard');
      }
    }, "\u653E\u5F03\u8349\u7A3F"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "check",
      className: "btn primary",
      disabled: data.status !== 'editing' || actions.blocked || !data.write_context || data.write_context.capabilities['trial.save'] !== true,
      onClick: () => {
        if (guard()) setModal('save');
      }
    }, "\u4FDD\u5B58\u573A\u666F"), data.scenario_ref && typeof renderAdoption === 'function' ? renderAdoption({
      scenarioRef: data.scenario_ref,
      data,
      onNavigate,
      disabled: actions.blocked,
      onAdopted: () => {
        setNotice('采用结果由独立场景采用回执核实；当前仍为原场景快照。');
        refresh();
      }
    }) : /*#__PURE__*/React.createElement(U.Button, {
      icon: "check",
      reason: data.scenario_ref ? '完整场景正式采用尚未接入，未改变正式计划。' : '须先保存场景，再核对独立场景采用入口。'
    }, "\u6B63\u5F0F\u91C7\u7528"))), /*#__PURE__*/React.createElement("details", {
      className: "tt-refs"
    }, /*#__PURE__*/React.createElement("summary", null, "\u8BD5\u8C03\u8EAB\u4EFD\u4E0E\u8BFB\u53D6\u8303\u56F4"), /*#__PURE__*/React.createElement("div", null, "\u8349\u7A3F\uFF1A", /*#__PURE__*/React.createElement("span", {
      className: "tt-ref"
    }, data.draft_ref)), data.scenario_ref && /*#__PURE__*/React.createElement("div", null, "\u573A\u666F\uFF1A", /*#__PURE__*/React.createElement("span", {
      className: "tt-ref"
    }, data.scenario_ref)), /*#__PURE__*/React.createElement("div", null, "\u539F\u6765\u6E90\uFF1A", /*#__PURE__*/React.createElement("span", {
      className: "tt-ref"
    }, Object.values(data.base)[0])), /*#__PURE__*/React.createElement("div", null, "\u5B8C\u6574\u65F6\u95F4\uFF1A", U.timeLabel(data.time_scope.start), " \u81F3 ", U.timeLabel(data.time_scope.end)))), modal === 'create' && /*#__PURE__*/React.createElement(window.TrialCatalog.Create, {
      initialBase: origin ? {
        plan_ref: origin.plan_ref
      } : base,
      initialScope: initialTarget.base ? initialTarget.scope || {} : {},
      fixedBase: !!origin,
      onExisting: origin ? () => {
        setModal(null);
        setDirectory(true);
      } : undefined,
      commands: commands,
      onClose: () => setModal(null)
    }), data && ['save', 'discard'].includes(modal) && /*#__PURE__*/React.createElement(Finish, {
      data: data,
      kind: modal,
      commands: actions,
      onClose: () => setModal(null),
      onRecheck: reload
    }));
  }
  // Load after TrialContract/API/Session/Controls/Catalog/Gantt/Details/Results/Styles.
  // initialTarget: {} | {draft_ref} | {scenario_ref} | {base:{plan_ref|candidate_ref},scope?}.
  // task_origin stays in navigation only; saved scenarios clear the original-task focus.
  function WorkbenchTrialWorkspace({
    initialTarget = {},
    onNavigate,
    renderAdoption,
    onTargetChange
  }) {
    try {
      C.target(initialTarget);
    } catch (error) {
      return /*#__PURE__*/React.createElement("div", {
        className: "trial-workspace"
      }, /*#__PURE__*/React.createElement(window.TrialStyles, null), /*#__PURE__*/React.createElement(U.ErrorBox, {
        error: error
      }));
    }
    return /*#__PURE__*/React.createElement(Session, {
      key: JSON.stringify(initialTarget),
      initialTarget: initialTarget,
      onNavigate: onNavigate,
      renderAdoption: renderAdoption,
      onTargetChange: onTargetChange
    });
  }
  window.WorkbenchTrialWorkspace = WorkbenchTrialWorkspace;
})();
