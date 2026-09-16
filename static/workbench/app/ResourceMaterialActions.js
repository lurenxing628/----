(function () {
  'use strict';

  // Load after ResourceMaterialContract.js, ResourceMaterialPreview.jsx and ResourceForms.jsx.
  // The host supplies a stable files adapter; mounting does not submit writes.
  const C = window.APSResourceContract,
    S = window.APSResourceSession;
  const {
    Button,
    Modal,
    Icon,
    ErrorBox,
    Issues
  } = window.ResourceControls;
  const Feedback = window.ResourceForms.Feedback,
    Preview = window.ResourceMaterialPreview;
  function Format({
    value,
    onChange,
    disabled
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "rm-format"
    }, /*#__PURE__*/React.createElement("span", {
      className: "seclabel"
    }, "\u6587\u4EF6\u683C\u5F0F"), /*#__PURE__*/React.createElement("div", {
      className: "seg",
      role: "group",
      "aria-label": "\u6587\u4EF6\u683C\u5F0F"
    }, ['xlsx', 'csv'].map(format => /*#__PURE__*/React.createElement("button", {
      key: format,
      type: "button",
      disabled: disabled,
      className: value === format ? 'on' : '',
      "aria-pressed": value === format,
      onClick: () => onChange(format)
    }, format === 'xlsx' ? 'Excel (.xlsx)' : 'CSV (.csv)'))));
  }
  function ExportOptions({
    selection,
    setSelection,
    refs,
    disabled,
    label,
    kind
  }) {
    return /*#__PURE__*/React.createElement("fieldset", {
      style: {
        border: 0,
        margin: 0,
        padding: 0
      },
      disabled: disabled
    }, /*#__PURE__*/React.createElement("legend", {
      className: "seclabel"
    }, "\u5BFC\u51FA\u8303\u56F4"), [['filtered', '当前筛选结果', '当前搜索与状态筛选下的全部记录，不限当前页'], ['all', '全部' + label, '忽略搜索与状态筛选，导出全部' + label + (kind === 'op_type' ? '，保留当前工种类别' : '')], ['selected', '已选' + label, refs.length + ' 条，含非当前页和当前筛选外的勾选记录']].map(([key, title, detail]) => /*#__PURE__*/React.createElement("label", {
      key: key,
      className: 'iorow' + (selection === key ? ' on' : '')
    }, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: kind + '-export-scope',
      value: key,
      checked: selection === key,
      onChange: () => setSelection(key)
    }), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "iotitle"
    }, title), /*#__PURE__*/React.createElement("div", {
      className: "iosub"
    }, detail)))));
  }
  function Actions({
    adapter,
    mode,
    request,
    onClose,
    onCommitted,
    contract: M
  }) {
    const [original] = React.useState(() => ({
      ...request,
      refs: Array.isArray(request.refs) ? request.refs.slice() : request.refs,
      scope: {
        ...request.scope
      }
    }));
    const [format, setFormat] = React.useState('xlsx'),
      [file, setFile] = React.useState(null),
      [selection, setSelection] = React.useState('');
    const [job, setJob] = React.useState(null),
      [error, setError] = React.useState(null),
      [acknowledged, setAcknowledged] = React.useState(false);
    const [download, setDownload] = React.useState({
        busy: false,
        name: null
      }),
      [now, setNow] = React.useState(Date.now());
    const command = S.useCommand(adapter),
      notified = React.useRef(null),
      alive = React.useRef(true),
      downloadAbort = React.useRef(null);
    const category = command.intent ? command.intent.category : original.scope.category;
    const label = M.resourceLabel ? M.resourceLabel(category) : M.label;
    const effectiveMode = command.intent && ['sending', 'pending', 'checking', 'done'].includes(command.phase) ? {
      [M.kind + '_import']: 'import',
      [M.kind + '_bulk']: 'bulk'
    }[command.intent.kind] || mode : mode;
    const isExport = effectiveMode === 'export',
      done = command.phase === 'done',
      recovery = original.recovery === true;
    const query = S.useQuery(async signal => {
      if (typeof adapter.preview !== 'function') throw C.failure('dependency not wired: adapter.preview');
      let body;
      if (effectiveMode === 'import') {
        await M.validateFile(job.file, job.format);
        body = new FormData();
        body.append('file', job.file);
        body.append('format', job.format);
        body.append('mode', 'upsert');
        if (M.kind === 'op_type') body.append('category', M.category(original));
      } else body = M.requestBody(effectiveMode, original, job.selection);
      const raw = await adapter.preview(M.paths[effectiveMode], body, signal);
      if (isExport) {
        const result = M.exportPreview(raw, job.selection, original);
        if (job.selection === 'selected' && result.data.row_count !== M.selection(original).length) throw C.failure('导出预检数量与勾选的' + label + '不一致，没有开始下载。');
        return result;
      }
      return M.preview(raw, effectiveMode, effectiveMode === 'import' ? job.format : M.selection(original), original);
    }, [adapter, job, effectiveMode, M], !!job);
    const result = query.result,
      data = result && result.data;
    const activeRead = !!job && query.loading;
    const controlsDisabled = command.locked || done || activeRead || download.busy;
    React.useEffect(() => () => {
      alive.current = false;
      if (downloadAbort.current) downloadAbort.current.abort();
    }, []);
    React.useEffect(() => {
      if (!data) return undefined;
      const remaining = Date.parse(data.expires_at) - Date.now();
      if (remaining <= 0) {
        setNow(Date.now());
        return undefined;
      }
      const timer = window.setTimeout(() => setNow(Date.now()), Math.min(remaining + 1, 2147483647));
      return () => window.clearTimeout(timer);
    }, [data]);
    React.useEffect(() => {
      if (!done || notified.current === command.intent.request_key) return;
      notified.current = command.intent.request_key;
      Promise.resolve().then(() => onCommitted(command.result)).catch(failure => {
        if (alive.current) setError(C.failure('已保存，但列表刷新失败：' + C.message(failure)));
      });
    }, [done, command.intent, command.result, onCommitted]);
    function close() {
      if (command.locked) return;
      if (!command.reset()) return;
      if (downloadAbort.current) downloadAbort.current.abort();
      onClose();
    }
    function invalidate() {
      setJob(null);
      setAcknowledged(false);
      setError(null);
      setDownload({
        busy: false,
        name: null
      });
    }
    function chooseFormat(value) {
      if (!controlsDisabled) {
        invalidate();
        setFormat(value);
      }
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
      if (controlsDisabled || recovery) return;
      if (!command.reset()) return;
      setError(null);
      setAcknowledged(false);
      setDownload({
        busy: false,
        name: null
      });
      if (effectiveMode === 'import' && !file) {
        setError(C.failure('请先选择文件。'));
        return;
      }
      if (isExport && !selection) {
        setError(C.failure('请先选择导出范围。'));
        return;
      }
      try {
        if (M.category) M.category(original);
        if (effectiveMode === 'bulk' && !M.selection(original).length) throw C.failure('未选中' + label + '，请选择后重试。');
        if (effectiveMode !== 'import') M.requestBody(effectiveMode, original, selection);
        setJob({
          file,
          format,
          selection
        });
        setNow(Date.now());
      } catch (failure) {
        setJob(null);
        setError(failure);
      }
    }
    const needsAcknowledgement = data && !isExport && (effectiveMode === 'bulk' || data.rows.some(row => row.requires_confirmation));
    const expired = data && now >= Date.parse(data.expires_at);
    let reason = isExport ? '' : M.blocked(result, M.source(original));
    if (expired) reason = '预检结果已过期，请重新预检。';
    if (needsAcknowledgement && !acknowledged && !reason) reason = '请先核对并勾选确认项。';
    if (command.phase === 'rejected') reason = '本次没有提交。请重新预检后再确认。';
    function confirm() {
      if (controlsDisabled || reason || !data) return;
      command.submit(M.kind + (effectiveMode === 'import' ? '_import' : '_bulk'), 'confirm', data.preview_ref, data.write_context, {
        preview_ref: data.preview_ref
      }, M.category ? M.category(original) : undefined);
    }
    async function downloadFile(template) {
      if (controlsDisabled || !template && (!data || expired)) return;
      if (typeof adapter.download !== 'function') {
        setError(C.failure('dependency not wired: adapter.download'));
        return;
      }
      if (!template && !data.formats.includes(format)) {
        setError(C.failure('这次导出预检不支持所选文件格式，请重新预检。'));
        return;
      }
      const controller = new AbortController();
      downloadAbort.current = controller;
      setDownload({
        busy: true,
        name: null
      });
      setError(null);
      try {
        const scope = template ? {
          format
        } : {
          export_ref: data.export_ref,
          format
        };
        if (template && M.kind === 'op_type') scope.category = M.category(original);
        const response = await adapter.download(template ? M.paths.template : M.paths.download, scope, controller.signal);
        if (controller.signal.aborted || !alive.current) return;
        const name = await M.saveDownload(response, format, controller.signal);
        if (alive.current) setDownload({
          busy: false,
          name
        });
      } catch (failure) {
        if (alive.current && !controller.signal.aborted) {
          setDownload({
            busy: false,
            name: null
          });
          setError(failure);
        }
      } finally {
        if (downloadAbort.current === controller) downloadAbort.current = null;
      }
    }
    const title = ({
      import: '批量导入',
      export: '批量导出',
      bulk: '批量删除'
    }[effectiveMode] || '操作') + ' · ' + label;
    const refs = Array.isArray(original.refs) ? original.refs : [];
    return /*#__PURE__*/React.createElement("div", {
      className: 'plana rm-actions' + (data && !isExport ? ' rm-wide' : '')
    }, /*#__PURE__*/React.createElement(Preview.Styles, null), /*#__PURE__*/React.createElement(Modal, {
      title: title,
      icon: effectiveMode === 'bulk' ? 'trash-2' : isExport ? 'file-output' : 'file-input',
      onClose: close,
      locked: command.locked,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: close,
        reason: command.locked ? '结果还没确认，暂时不能关闭。' : ''
      }, done || download.name ? '完成' : '取消'), !done && !command.locked && !recovery && /*#__PURE__*/React.createElement(Button, {
        icon: "check",
        onClick: preflight,
        busy: activeRead,
        disabled: download.busy
      }, data || query.error || command.phase === 'rejected' ? '重新预检' : '开始预检'), isExport && data && /*#__PURE__*/React.createElement(Button, {
        transfer: "export",
        className: "btn primary wb-action wb-primary",
        disabled: controlsDisabled,
        reason: expired ? '预检结果已过期，请重新预检。' : '',
        onClick: () => downloadFile(false)
      }, "\u4E0B\u8F7D\u6587\u4EF6"), !isExport && !done && data && /*#__PURE__*/React.createElement(Button, {
        icon: effectiveMode === 'bulk' ? 'trash-2' : 'check',
        className: 'btn ' + (effectiveMode === 'bulk' ? 'danger' : 'primary wb-action wb-primary'),
        busy: command.locked,
        disabled: controlsDisabled,
        reason: reason,
        onClick: confirm
      }, effectiveMode === 'bulk' ? '确认删除' : '确认导入'))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b scroll rm-body"
    }, !recovery && !command.intent && M.source(original) === 'demo' && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u5F53\u524D\u4E3A\u793A\u4F8B\u6570\u636E\uFF0C\u4E0D\u5141\u8BB8\u63D0\u4EA4", label, "\u53D8\u66F4\u3002"), !recovery && !command.intent && !M.source(original) && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u5C1A\u672A\u8BFB\u53D6\u751F\u4EA7\u8D44\u6599\uFF0C\u4E0D\u80FD\u63D0\u4EA4", label, "\u53D8\u66F4\u3002"), recovery && !command.intent && !command.error && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u8BFB\u4E0D\u5230\u4E0A\u6B21\u64CD\u4F5C\u7684\u7F16\u53F7\uFF0C\u6CA1\u6709\u6267\u884C\u5176\u4ED6", label, "\u64CD\u4F5C\u3002"), !recovery && !done && !command.locked && effectiveMode === 'import' && !data && /*#__PURE__*/React.createElement("div", {
      className: "iopane on"
    }, /*#__PURE__*/React.createElement(Format, {
      value: format,
      onChange: chooseFormat,
      disabled: controlsDisabled
    }), /*#__PURE__*/React.createElement("div", {
      className: "tmpl-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "tmpl-ico"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "file-input"
    })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "tmpl-t"
    }, label, "\u5BFC\u5165\u6A21\u677F.", format), /*#__PURE__*/React.createElement("div", {
      className: "tmpl-s"
    }, M.templateHint || '空白表头模板，不含示例物料')), /*#__PURE__*/React.createElement(Button, {
      className: "mini",
      transfer: "template",
      disabled: controlsDisabled,
      onClick: () => downloadFile(true)
    }, "\u4E0B\u8F7D\u6A21\u677F")), /*#__PURE__*/React.createElement("div", {
      className: 'drop rm-upload' + (file ? ' has' : ''),
      "aria-disabled": controlsDisabled,
      onDragOver: event => event.preventDefault(),
      onDrop: event => {
        event.preventDefault();
        chooseFile(event.dataTransfer.files);
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "di"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "file-input"
    })), /*#__PURE__*/React.createElement("div", {
      className: "dt"
    }, file ? file.name : '选择 CSV / XLSX 文件'), /*#__PURE__*/React.createElement("div", {
      className: "ds"
    }, file ? window.WorkbenchFormat.number(file.size, {
      digits: 0
    }) + ' 字节 · 单次导入最多 2,000 行' : '单次导入最多 2,000 行'), /*#__PURE__*/React.createElement("input", {
      type: "file",
      "aria-label": '选择' + label + '导入文件',
      accept: ".csv,.xlsx",
      disabled: controlsDisabled,
      onChange: event => {
        chooseFile(event.target.files);
        event.target.value = '';
      }
    })), /*#__PURE__*/React.createElement("p", {
      className: "iohint"
    }, M.importHint || /*#__PURE__*/React.createElement(React.Fragment, null, "\u6309\u7F16\u53F7\u589E\u91CF\u66F4\u65B0\uFF1A\u7F16\u53F7\u5DF2\u6709\u7684\u66F4\u65B0\uFF0C\u6CA1\u6709\u7684\u65B0\u589E\uFF0C\u6587\u4EF6\u4EE5\u5916\u7684\u7269\u6599\u4E0D\u4F1A\u5220\u9664\u3002\u7A7A\u767D\u683C\u4FDD\u6301\u539F\u503C\uFF1B\u8981\u6E05\u9664\u89C4\u683C\u3001\u5355\u4F4D\u6216\u5907\u6CE8\uFF0C\u8BF7\u5728\u683C\u5B50\u91CC\u586B ", /*#__PURE__*/React.createElement("code", null, '\\N'), "\uFF08\u5927\u5199\uFF09\u3002"))), !done && !command.locked && effectiveMode === 'import' && data && /*#__PURE__*/React.createElement("div", {
      className: "tmpl-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "tmpl-ico"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "file-input"
    })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "tmpl-t"
    }, file && file.name), /*#__PURE__*/React.createElement("div", {
      className: "tmpl-s"
    }, format.toUpperCase(), " \xB7 \u6309\u7F16\u53F7\u589E\u91CF\u66F4\u65B0 \xB7 ", data.rows.length, " \u884C")), /*#__PURE__*/React.createElement(Button, {
      icon: "file-input",
      disabled: controlsDisabled,
      onClick: invalidate
    }, "\u66F4\u6362\u6587\u4EF6")), !recovery && !done && !command.locked && isExport && /*#__PURE__*/React.createElement("div", {
      className: "iopane on"
    }, /*#__PURE__*/React.createElement(ExportOptions, {
      selection: selection,
      setSelection: value => {
        invalidate();
        setSelection(value);
      },
      refs: refs,
      disabled: controlsDisabled,
      label: label,
      kind: M.kind
    }), /*#__PURE__*/React.createElement(Format, {
      value: format,
      onChange: chooseFormat,
      disabled: controlsDisabled
    })), !done && effectiveMode === 'bulk' && (!recovery || command.intent) && (recovery || command.intent && !job ? /*#__PURE__*/React.createElement("p", null, "\u6B63\u5728\u67E5\u8BE2\u4E0A\u6B21\u6279\u91CF\u5220\u9664\u7684\u7ED3\u679C\uFF0C\u5F53\u524D\u5217\u8868\u91CC\u65B0\u52FE\u9009\u7684\u8FD8\u6CA1\u63D0\u4EA4\u3002") : /*#__PURE__*/React.createElement("p", null, "\u672C\u6B21\u52FE\u9009\u4E86 ", /*#__PURE__*/React.createElement("b", null, refs.length), " \u6761", label, "\uFF0C\u542B\u975E\u5F53\u524D\u9875\u548C\u5F53\u524D\u7B5B\u9009\u5916\u7684\u52FE\u9009\u9879\u3002")), activeRead && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u5B8C\u6574\u9884\u68C0\u7ED3\u679C\uFF0C\u5C1A\u672A\u5199\u5165\u6570\u636E\u2026"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: query.error
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: result && result.warnings || []
    }), data && !isExport && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Preview, {
      data: data,
      mode: effectiveMode,
      contract: M,
      label: label
    }), /*#__PURE__*/React.createElement("p", {
      className: "iohint"
    }, "\u672C\u6279\u6574\u4F53\u786E\u8BA4\uFF1B\u4EFB\u610F\u4E00\u884C\u6821\u9A8C\u4E0D\u901A\u8FC7\uFF0C\u5168\u90E8\u4E0D\u5199\u5165\u3002"), needsAcknowledgement && !done && /*#__PURE__*/React.createElement("label", {
      className: "rm-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: acknowledged,
      disabled: controlsDisabled,
      onChange: event => setAcknowledged(event.target.checked)
    }), /*#__PURE__*/React.createElement("span", null, effectiveMode === 'bulk' ? '已核对完整删除范围及明细，确认删除这些' + label + '。' : M.kind === 'material' ? '已核对在用物料的修改前后内容，确认这些更新。' : '已核对关键项和关联关系的修改前后内容，确认这些更新。')), reason && !done && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, reason)), data && isExport && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u5DF2\u6838\u5BF9\u5BFC\u51FA\u8303\u56F4\uFF1A", /*#__PURE__*/React.createElement("b", null, data.row_count), " \u6761 \xB7 ", format.toUpperCase(), expired ? ' · 预检结果已过期' : ''), download.busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u4E0B\u8F7D\u6587\u4EF6\u2026"), download.name && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u5DF2\u4EA4\u7ED9\u6D4F\u89C8\u5668\u4E0B\u8F7D\uFF1A", /*#__PURE__*/React.createElement("b", null, download.name)), !isExport && /*#__PURE__*/React.createElement(Feedback, {
      command: command
    }), command.intent && /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '操作编号': command.intent.request_key
      }
    }), done && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, Number.isSafeInteger(command.result.data.deleted_count) ? '已删除 ' + command.result.data.deleted_count + ' 条。' : command.result.data.summary ? '导入结果已确认。' : '已查到上次操作的完成结果。'))));
  }
  window.ResourceFileActionFlow = Actions;
  window.ResourceMaterialActions = props => /*#__PURE__*/React.createElement(Actions, {
    ...props,
    contract: window.APSResourceMaterial
  });
})();
