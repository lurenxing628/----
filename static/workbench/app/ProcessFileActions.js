(function () {
  'use strict';

  const C = window.APSResourceContract,
    A = window.APSProcessActions,
    F = window.APSProcessFiles,
    S = window.APSResourceSession,
    M = window.APSResourceMaterial;
  const {
    Button,
    Modal,
    ErrorBox,
    Issues,
    Icon
  } = window.ResourceControls;
  function ProcessFileActions({
    adapter,
    kind,
    mode,
    request,
    onClose,
    onCommitted,
    disabled = false
  }) {
    const [original] = React.useState(() => ({
      ...request,
      scope: A.scope(request.scope),
      refs: request.refs && request.refs.slice()
    }));
    const [file, setFile] = React.useState(null),
      [format, setFormat] = React.useState('xlsx'),
      [selection, setSelection] = React.useState(original.target_ref ? 'explicit' : '');
    const [job, setJob] = React.useState(null),
      [error, setError] = React.useState(null),
      [discard, setDiscard] = React.useState(false);
    const [groups, setGroups] = React.useState([]),
      [zero, setZero] = React.useState(false),
      [ack, setAck] = React.useState(false),
      [now, setNow] = React.useState(Date.now());
    const [download, setDownload] = React.useState({
        busy: false
      }),
      abort = React.useRef(null),
      alive = React.useRef(true),
      notified = React.useRef(null),
      checkedPreview = React.useRef(null);
    const command = S.useCommand(adapter),
      importing = mode === 'import',
      recovery = original.recovery === true;
    const label = kind === 'route' ? '工艺路线' : '工时定额';
    let saved = null,
      receiptError = null;
    if (command.phase === 'done') {
      try {
        saved = F.receipt(command.result, command.intent, kind, checkedPreview.current, original.target_ref);
      } catch (failure) {
        receiptError = failure;
      }
    }
    const visible = receiptError ? {
        ...command,
        phase: 'pending',
        locked: true,
        error: receiptError
      } : command,
      done = !!saved;
    const dirty = importing && !!file && !done,
      locked = visible.locked || download.busy;
    const query = S.useQuery(async signal => {
      let body;
      if (importing) {
        await M.validateFile(job.file, job.format);
        if (job.file.size > 16 * 1024 * 1024) throw C.failure('文件超过 16 MiB，请缩小文件后再预检。');
        body = new FormData();
        body.append('file', job.file);
        body.append('format', job.format);
        body.append('mode', 'upsert');
        if (original.target_ref) {
          if (!A.ref(original.target_ref)) throw C.failure('当前零件已无法核对，请返回列表重新选择。');
          body.append('target_ref', original.target_ref);
        }
      } else body = F.exportBody(original, job.selection, job.format);
      const result = await adapter.filePreview(kind, mode, body, signal);
      return importing ? F.preview(result, kind, job.format, original) : F.exportPreview(result, kind, body);
    }, [adapter, job, kind, mode], !!job);
    const result = query.result,
      data = result && result.data,
      busy = !!job && query.loading;
    if (data && importing) checkedPreview.current = data;
    const controlsDisabled = disabled || locked || done || busy;
    React.useEffect(() => () => {
      alive.current = false;
      if (abort.current) abort.current.abort();
    }, []);
    React.useEffect(() => {
      if (!dirty && !receiptError) return undefined;
      const warn = event => {
        event.preventDefault();
        event.returnValue = '';
      };
      window.addEventListener('beforeunload', warn);
      return () => window.removeEventListener('beforeunload', warn);
    }, [dirty, !!receiptError]);
    React.useEffect(() => {
      if (!done || kind === 'hours' || notified.current === command.result.receipt_ref) return;
      notified.current = command.result.receipt_ref;
      if (onCommitted) onCommitted(command.result);
    }, [done, kind, command.result, onCommitted]);
    React.useEffect(() => {
      if (!data) return undefined;
      const timer = setTimeout(() => setNow(Date.now()), Math.max(0, Date.parse(data.expires_at) - Date.now() + 1));
      return () => clearTimeout(timer);
    }, [data]);
    function invalidate() {
      checkedPreview.current = null;
      setJob(null);
      setGroups([]);
      setZero(false);
      setAck(false);
      setError(null);
      setDownload({
        busy: false
      });
    }
    function close(force = false) {
      if (locked) return;
      if (dirty && !force) {
        setDiscard(true);
        return;
      }
      if (done && kind === 'hours' && notified.current !== command.result.receipt_ref) {
        notified.current = command.result.receipt_ref;
        if (onCommitted) onCommitted(command.result);
      }
      if (command.reset()) onClose();
    }
    function chooseFile(files) {
      if (controlsDisabled) return;
      invalidate();
      setFile(null);
      if (!files || files.length !== 1) {
        setError(C.failure('一次只能选择一个 CSV 或 XLSX 文件。'));
        return;
      }
      setFile(files[0]);
    }
    function preflight() {
      if (controlsDisabled || recovery || !command.reset()) return;
      invalidate();
      if (typeof adapter.filePreview !== 'function') {
        setError(C.failure('工艺文件预检接口尚未接入。'));
        return;
      }
      if (importing && !file) {
        setError(C.failure('请先选择文件。'));
        return;
      }
      if (!importing && !selection) {
        setError(C.failure('请先选择导出范围。'));
        return;
      }
      setJob({
        file,
        format,
        selection
      });
      setNow(Date.now());
    }
    let reason = importing ? A.blocked(result, original.source, F.operation(kind)) : '';
    if (data && now >= Date.parse(data.expires_at)) reason = '预检已过期，请重新预检。';
    if (data && importing && !reason) {
      try {
        F.confirmInput(data, groups, zero);
      } catch (failure) {
        reason = C.message(failure);
      }
    }
    if (data && importing && !reason && data.rows.some(row => row.requires_confirmation) && !ack) reason = '请核对修改前后内容并勾选确认。';
    if (command.phase === 'rejected') reason = '本次未导入，请重新预检后再确认。';
    function confirm() {
      if (!importing || controlsDisabled || recovery || !data || reason) return;
      try {
        command.submit('process_' + kind + '_import', 'confirm', data.preview_ref, data.write_context, F.confirmInput(data, groups, zero));
      } catch (failure) {
        setError(failure);
      }
    }
    async function downloadFile(template) {
      if (controlsDisabled || !template && (!data || reason)) return;
      if (typeof adapter.fileDownload !== 'function') {
        setError(C.failure('工艺文件下载接口尚未接入。'));
        return;
      }
      if (!template && data.format !== format) {
        setError(C.failure('当前导出格式已变化，请重新预检。'));
        return;
      }
      const controller = new AbortController();
      abort.current = controller;
      setDownload({
        busy: true
      });
      setError(null);
      try {
        const response = await adapter.fileDownload(kind, template, template ? {
          format
        } : {
          export_ref: data.export_ref
        }, controller.signal);
        if (!controller.signal.aborted && alive.current) {
          const name = await M.saveDownload(response, format, controller.signal);
          if (alive.current) setDownload({
            busy: false,
            name
          });
        }
      } catch (failure) {
        if (alive.current && !controller.signal.aborted) {
          setError(failure);
          setDownload({
            busy: false
          });
        }
      } finally {
        if (abort.current === controller) abort.current = null;
      }
    }
    const allSkipped = data && importing && kind === 'hours' && data.skipped_count === data.rows.length;
    return /*#__PURE__*/React.createElement("div", {
      className: 'plana rm-actions' + ((data || saved) && importing ? ' rm-wide' : '')
    }, /*#__PURE__*/React.createElement(window.ResourceMaterialPreview.Styles, null), /*#__PURE__*/React.createElement(Modal, {
      title: (importing ? '导入' : '导出') + label,
      icon: importing ? 'file-input' : 'file-output',
      locked: locked,
      suspended: discard,
      onClose: () => close(),
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        disabled: locked,
        onClick: () => close()
      }, done || !importing && download.name ? '完成' : '取消'), !done && !recovery && /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        disabled: disabled || locked,
        busy: busy,
        onClick: preflight
      }, job ? '重新预检' : '开始预检'), !done && !recovery && data && /*#__PURE__*/React.createElement(Button, {
        transfer: importing ? 'import' : 'export',
        className: "btn primary",
        disabled: controlsDisabled,
        reason: reason,
        onClick: importing ? confirm : () => downloadFile(false)
      }, importing ? allSkipped ? '确认跳过并记录结果' : '确认导入' : '下载文件'))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b scroll rm-body"
    }, recovery && !done && /*#__PURE__*/React.createElement("p", null, "\u6B63\u5728\u6838\u5B9E\u539F\u6587\u4EF6\u8BF7\u6C42\uFF0C\u4E0D\u4F1A\u91CD\u65B0\u4E0A\u4F20\u6216\u518D\u6B21\u5BFC\u5165\u3002"), !recovery && !done && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "rm-format"
    }, /*#__PURE__*/React.createElement("span", {
      className: "seclabel"
    }, "\u6587\u4EF6\u683C\u5F0F"), /*#__PURE__*/React.createElement("div", {
      className: "seg",
      role: "group",
      "aria-label": "\u6587\u4EF6\u683C\u5F0F"
    }, ['xlsx', 'csv'].map(value => /*#__PURE__*/React.createElement("button", {
      type: "button",
      key: value,
      className: format === value ? 'on' : '',
      "aria-pressed": format === value,
      disabled: controlsDisabled,
      onClick: () => {
        invalidate();
        setFormat(value);
      }
    }, value === 'xlsx' ? 'Excel (.xlsx)' : 'CSV (.csv)')))), importing ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "tmpl-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "tmpl-ico"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "file-input"
    })), /*#__PURE__*/React.createElement("div", {
      className: "tmpl-t"
    }, label, "\u7A7A\u767D\u6A21\u677F.", format), /*#__PURE__*/React.createElement(Button, {
      transfer: "template",
      disabled: controlsDisabled,
      onClick: () => downloadFile(true)
    }, "\u4E0B\u8F7D\u6A21\u677F")), /*#__PURE__*/React.createElement("div", {
      className: "field full"
    }, /*#__PURE__*/React.createElement("label", null, label, "\u6587\u4EF6", /*#__PURE__*/React.createElement("input", {
      type: "file",
      "aria-label": '选择' + label + '文件',
      accept: ".csv,.xlsx",
      disabled: controlsDisabled,
      onChange: event => {
        chooseFile(event.target.files);
        event.target.value = '';
      }
    })), file && /*#__PURE__*/React.createElement("span", {
      className: "fhint"
    }, file.name, " \xB7 ", file.size, " \u5B57\u8282")), original.target_ref && /*#__PURE__*/React.createElement("p", null, "\u53EA\u6838\u5BF9\u5E76\u4FEE\u6539\u5F53\u524D\u96F6\u4EF6\uFF0C\u4E0D\u63A5\u53D7\u6587\u4EF6\u4E2D\u7684\u5176\u4ED6\u96F6\u4EF6\u3002")) : /*#__PURE__*/React.createElement("fieldset", {
      disabled: controlsDisabled,
      style: {
        border: 0,
        padding: 0,
        margin: 0
      }
    }, /*#__PURE__*/React.createElement("legend", {
      className: "seclabel"
    }, "\u5BFC\u51FA\u8303\u56F4"), (original.target_ref ? [['explicit', '当前零件']] : [['filtered', '当前筛选结果（全部页）'], ['all', '全部零件'], ['explicit', '已选零件（含其他页）']]).map(([value, title]) => /*#__PURE__*/React.createElement("label", {
      key: value,
      className: 'iorow' + (selection === value ? ' on' : '')
    }, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: "process-export-selection",
      checked: selection === value,
      onChange: () => {
        invalidate();
        setSelection(value);
      }
    }), /*#__PURE__*/React.createElement("span", {
      className: "iotitle"
    }, title))))), busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u9884\u68C0\uFF0C\u5C1A\u672A\u4FEE\u6539\u96F6\u4EF6\u2026"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: query.error
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: result && result.warnings || []
    }), data && importing && !done && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "iohint"
    }, data.instructions), /*#__PURE__*/React.createElement(window.ProcessFilePreview, {
      data: data,
      groups: groups,
      onGroups: setGroups,
      disabled: controlsDisabled
    }), !done && data.zero_review_required && /*#__PURE__*/React.createElement("label", {
      className: "rm-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: zero,
      disabled: controlsDisabled,
      onChange: event => setZero(event.target.checked)
    }), "\u5DF2\u590D\u6838\u5355\u4EF6\u5DE5\u65F6\u4E3A 0 \u7684\u8BB0\u5F55\uFF0C\u786E\u8BA4\u4FDD\u7559 0\u3002"), !done && data.rows.some(row => row.requires_confirmation) && /*#__PURE__*/React.createElement("label", {
      className: "rm-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: ack,
      disabled: controlsDisabled,
      onChange: event => setAck(event.target.checked)
    }), "\u5DF2\u6838\u5BF9\u5168\u90E8\u4FEE\u6539\u524D\u540E\u5185\u5BB9\uFF0C\u786E\u8BA4\u8FD9\u4E9B\u66F4\u65B0\u3002"), /*#__PURE__*/React.createElement("p", null, kind === 'hours' ? '锁定跳过行不参与写入；其余行整体确认，任何一行不能提交，本批全部不修改。' : '本批整体确认；任何一行不能提交，本批全部不修改。')), data && !importing && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u5DF2\u6838\u5BF9 ", data.part_count, " \u4E2A\u96F6\u4EF6\uFF0C\u5BFC\u51FA ", data.row_count, " \u884C", kind === 'hours' ? '工序记录' : '零件记录', "\uFF0C\u4E0D\u9650\u5F53\u524D\u663E\u793A\u9875\u3002"), reason && data && !done && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, reason), download.name && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u5DF2\u4EA4\u7ED9\u6D4F\u89C8\u5668\u4E0B\u8F7D\uFF1A", download.name), importing && /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: done && kind === 'hours' ? {
        ...visible,
        phase: 'idle'
      } : visible
    }), done && kind === 'hours' && /*#__PURE__*/React.createElement(window.ProcessFileReceipt, {
      data: saved
    }), done && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, kind === 'hours' ? '已核实原文件回执；导入不代替工时阶段的人工确认。' : '已取得原文件请求的完成回执，工艺确认状态以重新读取的详情为准。'))), discard && /*#__PURE__*/React.createElement(Modal, {
      title: "\u653E\u5F03\u672C\u6B21\u6587\u4EF6\u5BFC\u5165\uFF1F",
      icon: "file-input",
      onClose: () => setDiscard(false),
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: () => setDiscard(false)
      }, "\u7EE7\u7EED\u6838\u5BF9"), /*#__PURE__*/React.createElement(Button, {
        className: "btn danger",
        onClick: () => close(true)
      }, "\u653E\u5F03\u5BFC\u5165\u5E76\u5173\u95ED"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b"
    }, "\u5F53\u524D\u9009\u62E9\u7684\u6587\u4EF6\u4E0E\u672A\u63D0\u4EA4\u7684\u786E\u8BA4\u9879\u5C06\u88AB\u4E22\u5F03\uFF0C\u4E0D\u4F1A\u4FEE\u6539\u96F6\u4EF6\u3002")));
  }
  window.ProcessFileActions = ProcessFileActions;
})();
