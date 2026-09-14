(function () {
  'use strict';

  const C = window.APSResourceContract,
    P = window.APSProcessContract,
    S = window.APSResourceSession,
    E = window.ProcessStageEditor;
  const {
    Button,
    Modal,
    ErrorBox,
    Issues
  } = window.ResourceControls;
  function Steps({
    entity,
    stage,
    onStage,
    disabled
  }) {
    const subtitle = key => entity.workflow[key].state === 'confirmed' ? '已确认' : entity.workflow[key].state === 'locked' ? key === 'source' ? '待路线确认' : '待归属确认' : key === 'route' ? entity.workflow.route.state === 'present' ? '已有记录 · 待人工确认' : '待录入路线' : '未人工确认';
    return /*#__PURE__*/React.createElement("div", {
      className: "stepper",
      role: "tablist",
      "aria-label": "\u96F6\u4EF6\u5DE5\u827A\u6B65\u9AA4"
    }, [['route', '工艺路线'], ['source', '归属'], ['hours', '工时定额']].map(([key, title], index) => /*#__PURE__*/React.createElement(Button, {
      key: key,
      className: 'stp ' + (stage === key ? 'active' : entity.workflow[key].state === 'confirmed' ? 'done' : ''),
      role: "tab",
      "aria-selected": stage === key,
      disabled: disabled,
      onClick: () => onStage(key)
    }, /*#__PURE__*/React.createElement("span", {
      className: "stp-n"
    }, index + 1), /*#__PURE__*/React.createElement("span", {
      className: "stp-b"
    }, /*#__PURE__*/React.createElement("span", {
      className: "stp-t"
    }, title), /*#__PURE__*/React.createElement("span", {
      className: "stp-s"
    }, subtitle(key))))));
  }
  function Operations({
    entity,
    hours,
    focusRef = null
  }) {
    const paging = E.usePage(entity.operations, focusRef),
      groups = new Map(entity.external_groups.map(row => [row.ref, row])),
      root = React.useRef(null);
    E.useFocus(root, focusRef, paging.page.number);
    return /*#__PURE__*/React.createElement("div", {
      ref: root
    }, /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement(E.Search, {
      paging: paging
    }), /*#__PURE__*/React.createElement("span", null, "\u5168\u90E8\u8BB0\u5F55 ", entity.operations.length, " \xB7 \u6709\u6548\u5DE5\u5E8F ", entity.relationships.operation_count)), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("div", {
      className: "card-scroll wb-table-shell"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": hours ? '已就绪工序汇总' : '路线工序明细',
      style: {
        minWidth: hours ? 1000 : 850,
        tableLayout: 'fixed'
      }
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, hours ? '已就绪工序汇总' : '路线工序明细'), hours && /*#__PURE__*/React.createElement("colgroup", null, [11, 9, 8, 16, 13, 13, 11, 19].map((width, index) => /*#__PURE__*/React.createElement("col", {
      key: index,
      style: {
        width: width + '%'
      }
    }))), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5DE5\u79CD"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u73B0\u6709\u5F52\u5C5E"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u4F9B\u5E94\u5546 / \u5916\u534F\u7EC4"), hours && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u6362\u578B\u5DE5\u65F6\uFF08\u5C0F\u65F6\uFF09"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5355\u4EF6\u5DE5\u65F6\uFF08\u5C0F\u65F6\uFF09"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5916\u534F\u5468\u671F\uFF08\u5929\uFF09")), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u786E\u8BA4\u8BB0\u5F55 / \u95EE\u9898"))), /*#__PURE__*/React.createElement("tbody", null, paging.rows.map(row => {
      const group = groups.get(row.external_group_ref);
      return /*#__PURE__*/React.createElement("tr", {
        key: row.ref,
        "data-process-location": row.ref,
        tabIndex: row.ref === focusRef ? -1 : undefined,
        "aria-current": row.ref === focusRef ? 'true' : undefined
      }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("b", null, row.sequence), " ", row.label, row.ref === focusRef && /*#__PURE__*/React.createElement(window.WorkbenchReference, {
        value: row.ref
      })), /*#__PURE__*/React.createElement("td", null, row.op_type_label || '未选工种'), /*#__PURE__*/React.createElement("td", null, P.sourceLabel(row.source)), /*#__PURE__*/React.createElement("td", null, row.source === 'internal' ? '不适用' : row.supplier_label || '未选供应商', group && /*#__PURE__*/React.createElement("div", null, "\u5916\u534F\u7EC4 ", group.start_sequence, " \u81F3 ", group.end_sequence)), hours && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("td", null, row.source === 'internal' ? E.value(row.setup_hours) : '不适用'), /*#__PURE__*/React.createElement("td", null, row.source === 'internal' ? E.value(row.unit_hours) : '不适用'), /*#__PURE__*/React.createElement("td", {
        "data-process-cycle-group": row.external_days_source === 'group' ? row.external_group_ref : undefined
      }, row.source === 'external' ? P.groupCycle(row, entity.external_groups) || E.value(row.external_days) : '不适用')), /*#__PURE__*/React.createElement("td", null, row.status === 'active' ? '有效' : '已停用工序', /*#__PURE__*/React.createElement("div", {
        className: "muted"
      }, /*#__PURE__*/React.createElement(E.Confirmation, {
        record: row.confirmation[hours ? 'hours' : 'source']
      })), /*#__PURE__*/React.createElement(Issues, {
        issues: row.issues
      })));
    }), !paging.rows.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: hours ? 8 : 5
    }, entity.operations.length ? '没有匹配的工序。' : '尚无工序记录。')))))), /*#__PURE__*/React.createElement(E.Pager, {
      paging: paging
    }));
  }
  function RouteView({
    entity,
    disabled,
    onEntry,
    onFileAction,
    previewAvailable
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "square-pen",
      className: "btn primary",
      disabled: disabled,
      reason: P.reason(entity.capabilities, 'route_preview', previewAvailable),
      onClick: onEntry
    }, "\u5F55\u5165\u8DEF\u7EBF"), /*#__PURE__*/React.createElement(window.ProcessFileButtons, {
      capabilities: entity.capabilities,
      disabled: disabled,
      onAction: onFileAction
    })), /*#__PURE__*/React.createElement("p", null, /*#__PURE__*/React.createElement(E.Confirmation, {
      record: entity.workflow.route
    })), /*#__PURE__*/React.createElement("dl", {
      className: "process-fields"
    }, [['route_raw', '原始路线'], ['route_parsed', '原路线解析标记'], ['remark', '零件备注']].map(([key, label]) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, key === 'route_parsed' ? entity.fields[key] === 'yes' ? '已解析' : entity.fields[key] === 'no' ? '未解析' : '原标记不明确' : E.value(entity.fields[key]))))), /*#__PURE__*/React.createElement(Operations, {
      entity: entity,
      hours: false
    }), /*#__PURE__*/React.createElement(E.Groups, {
      rows: entity.external_groups
    }));
  }
  function DetailSession({
    adapter,
    partRef,
    onClose,
    onCommitted,
    disabled = false,
    initialStage,
    templateOperationRef,
    templateExternalGroupRef,
    navigationReadOnly = false
  }) {
    const [target] = React.useState(() => {
      try {
        return E.location(initialStage, templateOperationRef, templateExternalGroupRef);
      } catch (error) {
        return {
          error
        };
      }
    });
    const command = S.useCommand(adapter),
      [stage, setStage] = React.useState(target.stage || null),
      [current, setCurrent] = React.useState(null);
    const [browsing, setBrowsing] = React.useState(navigationReadOnly || !!initialStage || !!templateOperationRef || !!templateExternalGroupRef);
    const [entry, setEntry] = React.useState(false),
      [entryStarted, setEntryStarted] = React.useState(false),
      [overlay, setOverlay] = React.useState(false);
    const [dirty, setDirty] = React.useState({}),
      [discard, setDiscard] = React.useState(false),
      [saved, setSaved] = React.useState({
        route: 0,
        source: 0,
        hours: 0
      });
    const [refresh, setRefresh] = React.useState({}),
      [receipt, setReceipt] = React.useState(null);
    const [fileAction, setFileAction] = React.useState(null),
      [fileReceipt, setFileReceipt] = React.useState(null);
    const request = React.useRef(null),
      notified = React.useRef(null),
      root = React.useRef(null),
      fileFocus = React.useRef(null);
    const onDirty = React.useCallback((key, value) => setDirty(old => old[key] === value ? old : {
      ...old,
      [key]: value
    }), []);
    async function loadPart(signal) {
      if (target.error) throw target.error;
      if (typeof adapter.detail !== 'function') throw C.failure('dependency not wired: window.APSProcessAPI.detail');
      const raw = await adapter.detail('part', partRef, signal);
      if (raw && raw.data && raw.data.ref !== partRef) throw C.failure('返回的不是原零件记录，不能继续使用同图号的新零件。');
      const value = P.detail(raw, partRef);
      if (value.meta.source !== 'production') throw C.failure('未取得原零件的生产详情，不能使用样例替代。');
      if (browsing) E.locate(value.data, target);
      return value;
    }
    const detail = S.useQuery(loadPart, [adapter, partRef]);
    React.useEffect(() => {
      if (detail.result) setCurrent(old => old || detail.result);
    }, [detail.result]);
    React.useEffect(() => () => {
      if (request.current) request.current.abort();
    }, []);
    const intent = command.intent,
      fileKind = intent && intent.action === 'confirm' && typeof intent.ref === 'string' && /^[A-Za-z0-9_-]{32}$/.test(intent.ref) && ['process_route_import', 'process_hours_import'].includes(intent.kind) ? intent.kind === 'process_route_import' ? 'route' : 'hours' : null;
    const expectedStage = intent && intent.kind === 'process' && ['route_confirm', 'source_confirm', 'hours_confirm'].includes(intent.action) ? intent.action.replace('_confirm', '') : null;
    const receiptMatches = command.phase === 'done' && expectedStage && command.intent.kind === 'process' && command.intent.ref === partRef && C.object(command.result.data) && command.result.data.entity_ref === partRef && command.result.data.stage === expectedStage && ['committed', 'unchanged'].includes(command.result.result);
    const needsReceiptCheck = command.phase === 'done' && !fileKind && !receiptMatches;
    const visibleCommand = fileKind ? {
      ...command,
      phase: 'idle',
      result: null,
      error: null,
      locked: true
    } : needsReceiptCheck ? {
      ...command,
      phase: 'pending',
      locked: true,
      error: C.failure(window.WorkbenchTerms.outcomes.pending('保存'))
    } : command;
    const hasDraft = Object.values(dirty).some(Boolean);
    window.WorkbenchGuards.useDirtyGuard({
      dirty: hasDraft,
      locked: (fileKind ? command.locked : visibleCommand.locked) || needsReceiptCheck,
      message: '零件工艺的路线、归属或工时输入尚未保存。'
    });
    const locked = (fileKind ? command.locked : visibleCommand.locked) || refresh.loading || overlay || !!fileAction;
    const editingBlocked = disabled || locked || command.phase === 'done' || !!fileReceipt && !refresh.done;
    const editorDisabled = disabled || refresh.loading || !!fileAction || !!fileReceipt && !refresh.done;
    React.useEffect(() => {
      if (!fileFocus.current || fileAction || discard || locked || entry) return undefined;
      const frame = requestAnimationFrame(() => {
        const previous = fileFocus.current;
        fileFocus.current = null;
        if (!root.current) return;
        const focusable = node => node && !node.disabled && node.getClientRects().length && getComputedStyle(node).visibility !== 'hidden';
        const selected = root.current.querySelector('.stepper [aria-selected="true"]');
        const target = focusable(previous) ? previous : focusable(selected) ? selected : root.current.querySelector('.modal-x');
        if (focusable(target)) target.focus();
      });
      return () => cancelAnimationFrame(frame);
    }, [fileAction, discard, locked, entry]);
    function fileRequest(recovery = false) {
      return {
        target_ref: partRef,
        source: 'production',
        refs: [partRef],
        scope: {},
        snapshot_ref: current && current.meta.snapshot_ref,
        page_size: 20,
        ...(recovery ? {
          recovery: true
        } : {})
      };
    }
    React.useEffect(() => {
      if (fileKind && !fileAction && !fileReceipt) setFileAction({
        kind: fileKind,
        mode: 'import',
        request: fileRequest(true)
      });
    }, [fileKind, fileAction, fileReceipt]);
    function notify(value) {
      if (notified.current === value.receipt_ref) return;
      notified.current = value.receipt_ref;
      if (onCommitted) onCommitted(value);
    }
    function resetDrafts() {
      setSaved(old => ({
        route: old.route + 1,
        source: old.source + 1,
        hours: old.hours + 1
      }));
      setDirty({});
      setEntry(false);
      setEntryStarted(false);
    }
    function openFile(kind, mode, abandon = false) {
      if (editingBlocked || !current || !['route', 'hours'].includes(kind) || !['import', 'export'].includes(mode) || typeof window.ProcessFileActions !== 'function' || P.reason(current.data.capabilities, mode, true)) return;
      if (!abandon) fileFocus.current = document.activeElement;
      if (hasDraft && !abandon) {
        setDiscard({
          kind,
          mode
        });
        return;
      }
      if (!command.reset()) return;
      resetDrafts();
      setDiscard(false);
      setRefresh({});
      setReceipt(null);
      setFileReceipt(null);
      setFileAction({
        kind,
        mode,
        request: fileRequest()
      });
    }
    async function readSaved() {
      if (command.phase !== 'done' || !expectedStage || fileKind || request.current) return;
      const controller = new AbortController();
      request.current = controller;
      setRefresh({
        loading: true
      });
      try {
        if (!receiptMatches) throw C.failure(window.WorkbenchTerms.outcomes.pending('保存'));
        notify(command.result);
        const fresh = await loadPart(controller.signal);
        if (controller.signal.aborted) return;
        const key = expectedStage;
        setCurrent(fresh);
        setStage(fresh.data.workflow.stage);
        setSaved(old => ({
          ...old,
          [key]: old[key] + 1
        }));
        onDirty(key, false);
        if (key === 'route') {
          setEntry(false);
          setEntryStarted(false);
        }
        setReceipt(command.result);
        setRefresh({
          done: true
        });
        if (!command.reset()) setRefresh({
          error: C.failure('保存已确认，但本机还留着上次操作记录。请点「查询结果」重试。')
        });
      } catch (error) {
        if (!controller.signal.aborted) setRefresh({
          error
        });
      } finally {
        if (request.current === controller) request.current = null;
      }
    }
    React.useEffect(() => {
      if (command.phase === 'done' && expectedStage && !fileKind) readSaved();
    }, [command.phase, command.result]);
    async function readFileSaved(value) {
      if (!value || request.current) return;
      const controller = new AbortController();
      request.current = controller;
      setRefresh({
        loading: true
      });
      try {
        const fresh = await loadPart(controller.signal);
        if (controller.signal.aborted) return;
        setCurrent(fresh);
        setStage(fresh.data.workflow.stage);
        resetDrafts();
        setRefresh({
          done: true
        });
        if (command.reset()) setFileReceipt(null);else setRefresh({
          error: C.failure('文件已保存，但本机还留着上次操作记录。请点「查询结果」重试。')
        });
      } catch (error) {
        if (!controller.signal.aborted) setRefresh({
          error: C.failure('文件已保存，但刷新零件详情失败：' + C.message(error) + ' 请点「查询结果」重试；如果这条零件已删除，不能续用同图号的新零件。')
        });
      } finally {
        if (request.current === controller) request.current = null;
      }
    }
    function fileCommitted(value) {
      window.APSProcessFiles.receipt(value, command.intent, fileAction.kind, null, partRef);
      setFileReceipt(value);
      setReceipt(value);
      setFileAction(null);
      notify(value);
      readFileSaved(value);
    }
    function close() {
      if (locked) return;
      if (hasDraft) {
        setDiscard(true);
        return;
      }
      if (command.reset()) onClose();
    }
    const result = current,
      entity = result && result.data;
    const selected = stage || entity && (entity.workflow.route.state !== 'confirmed' ? 'route' : entity.workflow.stage);
    const prerequisite = entity && (selected === 'source' && entity.workflow.route.state !== 'confirmed' ? '路线尚未确认；当前只读定位，不能确认归属。' : selected === 'hours' && (entity.workflow.route.state !== 'confirmed' || entity.workflow.source.state !== 'confirmed') ? '前置路线或归属尚未确认；当前只读定位，不能确认工时。' : '');
    React.useEffect(() => {
      if (!browsing || !entity || target.operationRef || target.groupRef || !root.current) return undefined;
      const frame = requestAnimationFrame(() => {
        const tab = root.current && root.current.querySelector('.stepper [aria-selected="true"]');
        if (tab) {
          tab.focus();
          tab.scrollIntoView({
            block: 'nearest'
          });
        }
      });
      return () => cancelAnimationFrame(frame);
    }, [browsing, entity, selected, target]);
    return /*#__PURE__*/React.createElement("div", {
      className: "plana process-detail",
      ref: root
    }, /*#__PURE__*/React.createElement(Modal, {
      title: entity ? entity.business_code + ' · ' + entity.label : '零件工艺详情',
      icon: "chart-gantt",
      onClose: close,
      locked: locked,
      suspended: entry || overlay || !!discard || !!fileAction,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
        className: "muted",
        style: {
          marginRight: 'auto'
        }
      }, entity ? '关联批次 ' + entity.relationships.batch_count + ' · 本次不反写已有批次' : ''), /*#__PURE__*/React.createElement(Button, {
        disabled: locked,
        onClick: close
      }, "\u5173\u95ED\u8BE6\u60C5"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b scroll pd-modal-b"
    }, detail.loading && !entity && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u5DE5\u827A\u8BE6\u60C5\u2026"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: detail.error
    }), detail.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: detail.reload
    }, "\u5237\u65B0\u8BE6\u60C5"), !fileKind && !fileReceipt && /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: visibleCommand
    }), refresh.loading && (receiptMatches || fileReceipt) && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u4FDD\u5B58\u5DF2\u786E\u8BA4\uFF0C\u6B63\u5728\u5237\u65B0\u5DE5\u827A\u8BE6\u60C5\u2026"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: refresh.error
    }), refresh.error && !needsReceiptCheck && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: fileReceipt ? () => readFileSaved(fileReceipt) : readSaved
    }, "\u67E5\u8BE2\u7ED3\u679C"), fileReceipt && !refresh.done && !refresh.loading && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u4EE5\u4E0B\u4ECD\u662F\u4FDD\u5B58\u524D\u7684\u8D44\u6599\uFF0C\u6682\u65F6\u4E0D\u80FD\u7EE7\u7EED\u7F16\u8F91\uFF1B\u5237\u65B0\u4E0D\u4F1A\u518D\u6B21\u5BFC\u5165\u6587\u4EF6\u3002"), receipt && refresh.done && command.phase === 'idle' && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u63D0\u4EA4\u5DF2\u786E\u8BA4\uFF0C\u5DE5\u827A\u8BE6\u60C5\u5DF2\u5237\u65B0\u3002"), entity && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Issues, {
      issues: result.warnings
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: entity.issues
    }), /*#__PURE__*/React.createElement(Steps, {
      entity: entity,
      stage: selected,
      disabled: editingBlocked,
      onStage: setStage
    }), browsing && /*#__PURE__*/React.createElement("section", {
      "data-process-navigation-stage": selected
    }, /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement("span", {
      role: "status"
    }, "\u5DF2\u6309\u539F\u96F6\u4EF6\u8BB0\u5F55\u53EA\u8BFB\u5B9A\u4F4D \xB7 ", {
      route: '工艺路线',
      source: '归属',
      hours: '工时定额',
      ready: '已就绪汇总'
    }[selected]), /*#__PURE__*/React.createElement(Button, {
      icon: "square-pen",
      disabled: editingBlocked,
      reason: prerequisite,
      onClick: () => setBrowsing(false)
    }, "\u5F00\u59CB\u7EF4\u62A4")), prerequisite && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, prerequisite), /*#__PURE__*/React.createElement("p", null, /*#__PURE__*/React.createElement(E.Confirmation, {
      record: entity.workflow[selected === 'ready' ? 'hours' : selected]
    })), selected === 'route' && /*#__PURE__*/React.createElement("dl", {
      className: "process-fields"
    }, /*#__PURE__*/React.createElement("dt", null, "\u539F\u59CB\u8DEF\u7EBF"), /*#__PURE__*/React.createElement("dd", null, E.value(entity.fields.route_raw))), /*#__PURE__*/React.createElement(Operations, {
      key: selected,
      entity: entity,
      hours: selected !== 'route',
      focusRef: target.operationRef
    }), /*#__PURE__*/React.createElement(E.Groups, {
      key: 'groups-' + selected,
      rows: entity.external_groups,
      focusRef: target.groupRef
    })), !browsing && /*#__PURE__*/React.createElement(React.Fragment, null, entity.workflow.ready && /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement("span", {
      className: "pill ok"
    }, "\u4E09\u9636\u6BB5\u5DF2\u786E\u8BA4 \xB7 \u5DF2\u5C31\u7EEA"), /*#__PURE__*/React.createElement(Button, {
      icon: "check",
      onClick: () => setStage('ready'),
      disabled: editingBlocked
    }, "\u67E5\u770B\u6C47\u603B")), /*#__PURE__*/React.createElement("div", {
      hidden: selected !== 'route'
    }, /*#__PURE__*/React.createElement(RouteView, {
      entity: entity,
      disabled: editingBlocked,
      onFileAction: openFile,
      previewAvailable: typeof adapter.routePreview === 'function',
      onEntry: () => {
        setEntryStarted(true);
        setEntry(true);
      }
    })), /*#__PURE__*/React.createElement("div", {
      hidden: selected !== 'source'
    }, /*#__PURE__*/React.createElement(window.ProcessSourceEditor, {
      key: saved.source,
      adapter: adapter,
      result: result,
      command: visibleCommand,
      disabled: editorDisabled,
      saved: saved.source,
      onDirty: onDirty,
      onOverlay: setOverlay,
      onResourceCommitted: onCommitted
    })), /*#__PURE__*/React.createElement("div", {
      hidden: selected !== 'hours'
    }, /*#__PURE__*/React.createElement(window.ProcessHoursEditor, {
      key: saved.hours,
      adapter: adapter,
      result: result,
      command: visibleCommand,
      disabled: editorDisabled,
      saved: saved.hours,
      onDirty: onDirty,
      onFileAction: openFile
    })), selected === 'ready' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Operations, {
      entity: entity,
      hours: true
    }), /*#__PURE__*/React.createElement(E.Groups, {
      rows: entity.external_groups
    }), /*#__PURE__*/React.createElement("p", null, /*#__PURE__*/React.createElement(E.Confirmation, {
      record: entity.workflow.hours
    }))))))), entryStarted && result && /*#__PURE__*/React.createElement("div", {
      hidden: !entry
    }, /*#__PURE__*/React.createElement(window.ProcessRouteEntry, {
      adapter: adapter,
      result: result,
      command: visibleCommand,
      active: entry,
      disabled: disabled || refresh.loading,
      refreshState: needsReceiptCheck ? {} : refresh,
      onRefresh: readSaved,
      onDirty: onDirty,
      onClose: () => setEntry(false)
    })), fileAction && /*#__PURE__*/React.createElement(window.ProcessFileActions, {
      adapter: adapter,
      ...fileAction,
      onClose: () => setFileAction(null),
      onCommitted: fileCommitted,
      disabled: disabled
    }), discard && /*#__PURE__*/React.createElement(Modal, {
      title: "\u653E\u5F03\u672A\u4FDD\u5B58\u7684\u5DE5\u827A\u8349\u7A3F\uFF1F",
      icon: "square-pen",
      onClose: () => setDiscard(false),
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: () => setDiscard(false)
      }, "\u7EE7\u7EED\u7F16\u8F91"), /*#__PURE__*/React.createElement(Button, {
        className: "btn danger",
        onClick: () => {
          if (discard.kind) openFile(discard.kind, discard.mode, true);else if (command.reset()) onClose();
        }
      }, discard.kind ? '放弃草稿并打开文件' : '放弃草稿并关闭'))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b"
    }, "\u672A\u4FDD\u5B58\u7684\u8DEF\u7EBF\u3001\u5F52\u5C5E\u548C\u5DE5\u65F6\u4FEE\u6539\u5C06\u88AB\u4E22\u5F03\uFF1B\u5DF2\u7ECF\u4FDD\u5B58\u6210\u529F\u7684\u5185\u5BB9\u4E0D\u53D7\u5F71\u54CD\u3002")));
  }
  function ProcessDetail(props) {
    return /*#__PURE__*/React.createElement(DetailSession, {
      key: props.partRef,
      ...props
    });
  }
  window.ProcessDetail = ProcessDetail;
})();
