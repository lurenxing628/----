(function () {
  'use strict';

  const B = window.APSBatchContract,
    C = window.APSResourceContract,
    {
      Button,
      Modal,
      ErrorBox,
      Issues
    } = window.ResourceControls;
  function saveDownload(download, filename) {
    if (!download || !download.blob || !download.blob.size) throw C.failure('未收到有效下载文件。');
    const url = URL.createObjectURL(download.blob),
      link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  }
  function PreviewRow({
    row
  }) {
    const names = {
      quantity: '数量',
      due_date: '交期',
      priority: '优先级',
      ready_status: '齐套',
      ready_date: '齐套日期',
      remark: '备注'
    };
    return /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", null, row.row, " \xB7 ", row.business_code), /*#__PURE__*/React.createElement("td", null, {
      create: '新增',
      update: '更新',
      skipped: '跳过',
      rejected: '拒绝'
    }[row.action]), /*#__PURE__*/React.createElement("td", null, row.errors.length ? row.errors.join('；') : row.input && /*#__PURE__*/React.createElement("div", null, B.fields.filter(key => key in row.input.fields).map(key => /*#__PURE__*/React.createElement("div", {
      key: key
    }, names[key], "\uFF1A", B.label(key, row.before && row.before.fields[key]), " \u2192 ", B.label(key, row.input.fields[key]))))));
  }
  function BatchFiles({
    adapter,
    mode: operation,
    scope,
    selected,
    snapshot,
    command,
    onClose,
    onCommitted,
    disabled
  }) {
    const [mode, setMode] = React.useState('overwrite'),
      [file, setFile] = React.useState(null),
      [preview, setPreview] = React.useState(null);
    const [selection, setSelection] = React.useState(selected.length ? 'selected' : 'filtered');
    const [busy, setBusy] = React.useState(false),
      [error, setError] = React.useState(null),
      [notice, setNotice] = React.useState('');
    const serial = React.useRef(0),
      alive = React.useRef(true),
      seen = React.useRef(null),
      form = React.useId();
    const importing = operation === 'import',
      done = command.phase === 'done',
      locked = disabled || command.locked || busy || done;
    React.useEffect(() => () => {
      alive.current = false;
      serial.current++;
    }, []);
    React.useEffect(() => {
      if (!importing || !done || seen.current === command.result.receipt_ref) return;
      try {
        B.receipt(command.result, 'import_confirm', preview && preview.preview_ref);
        seen.current = command.result.receipt_ref;
        onCommitted(command.result);
      } catch (error) {
        setError(error);
      }
    }, [done, command.result]);
    function changeMode(value) {
      setMode(value);
      setPreview(null);
      setError(null);
      serial.current++;
    }
    async function work(action) {
      if (locked) return;
      const id = ++serial.current;
      setBusy(true);
      setError(null);
      setNotice('');
      try {
        if (action === 'template') saveDownload(await adapter.downloadTemplate(), 'batches-template.xlsx');else if (action === 'preview') {
          const result = await adapter.importPreview(file, mode, scope, snapshot);
          const data = result && result.data;
          if (!data || data.operation !== 'batch.import_confirm' || data.mode !== mode || !Array.isArray(data.rows) || !Array.isArray(data.deleted) || typeof data.can_confirm !== 'boolean' || data.can_confirm && (!data.write_context || !B.context(data.write_context))) throw C.failure('文件预览协议不完整。');
          if (alive.current && id === serial.current) setPreview(data);
        } else {
          const result = await adapter.exportPreview(selection, {
            ...scope,
            snapshot_ref: snapshot
          }, selected);
          if (!result.data || typeof result.data.export_ref !== 'string' || !Number.isSafeInteger(result.data.count)) throw C.failure('导出范围未能核实。');
          const downloaded = await adapter.downloadExport(result.data.export_ref);
          saveDownload(downloaded, 'batches.xlsx');
          if (alive.current) setNotice('已生成 ' + result.data.count + ' 个批次的清单。');
        }
      } catch (error) {
        if (alive.current && id === serial.current) setError(error);
      } finally {
        if (alive.current && id === serial.current) setBusy(false);
      }
    }
    return /*#__PURE__*/React.createElement(Modal, {
      title: importing ? '批量维护批次' : '导出批次清单',
      icon: "box",
      locked: command.locked || busy,
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: onClose,
        disabled: command.locked || busy
      }, done ? '关闭' : '取消'), importing ? !done && /*#__PURE__*/React.createElement(React.Fragment, null, !preview ? /*#__PURE__*/React.createElement(Button, {
        transfer: "import",
        disabled: locked || !file,
        onClick: () => work('preview')
      }, "\u9884\u89C8\u5BFC\u5165") : /*#__PURE__*/React.createElement(Button, {
        transfer: "import",
        className: "btn primary",
        disabled: locked || !preview.can_confirm,
        onClick: () => command.submit('batch', 'import_confirm', preview.preview_ref, preview.write_context, {
          preview_ref: preview.preview_ref
        })
      }, "\u786E\u8BA4\u5BFC\u5165")) : /*#__PURE__*/React.createElement(Button, {
        transfer: "export",
        disabled: locked || selection === 'selected' && !selected.length,
        onClick: () => work('export')
      }, "\u4E0B\u8F7D\u6279\u6B21\u6E05\u5355"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b form"
    }, /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), notice && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, notice), importing ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      transfer: "template",
      disabled: locked,
      onClick: () => work('template')
    }, "\u4E0B\u8F7D\u6279\u6B21\u6A21\u677F"), /*#__PURE__*/React.createElement("div", {
      className: "batch-fields",
      style: {
        marginTop: 16
      }
    }, /*#__PURE__*/React.createElement(window.BatchControls.Field, {
      label: "\u5BFC\u5165\u6A21\u5F0F"
    }, /*#__PURE__*/React.createElement("select", {
      value: mode,
      disabled: locked,
      onChange: event => changeMode(event.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: "overwrite"
    }, "\u5DF2\u6709\u6279\u6B21\u5C31\u66F4\u65B0\uFF0C\u6CA1\u6709\u7684\u5C31\u65B0\u589E"), /*#__PURE__*/React.createElement("option", {
      value: "append"
    }, "\u53EA\u65B0\u589E\u6CA1\u6709\u7684\u6279\u6B21\uFF08\u5DF2\u6709\u7684\u8DF3\u8FC7\uFF09"), /*#__PURE__*/React.createElement("option", {
      value: "replace"
    }, "\u5148\u6E05\u7A7A\u5168\u90E8\u6279\u6B21\uFF0C\u518D\u6309\u8868\u683C\u91CD\u5BFC"))), /*#__PURE__*/React.createElement(window.BatchControls.Field, {
      label: "\u9009\u62E9 Excel \u6587\u4EF6"
    }, /*#__PURE__*/React.createElement("input", {
      type: "file",
      accept: ".xlsx",
      disabled: locked,
      onChange: event => {
        setFile(event.target.files[0] || null);
        setPreview(null);
        setError(null);
        serial.current++;
      }
    }))), /*#__PURE__*/React.createElement("p", null, "\u65B0\u5EFA\u6279\u6B21\u4E0D\u81EA\u52A8\u751F\u6210\u5DE5\u5E8F\uFF1B\u5DF2\u6709\u6279\u6B21\u7684\u7A7A\u5355\u5143\u683C\u4E0D\u8986\u76D6\u3002\u786E\u8BA4\u524D\u4E0D\u4F1A\u65B0\u589E\u3001\u66F4\u65B0\u6216\u5220\u9664\u6279\u6B21\u3002"), preview && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", null, preview.count, " \u884C \xB7 ", preview.can_confirm ? '可确认，整批原子保存' : '存在拒绝行，本批不会写入'), /*#__PURE__*/React.createElement("div", {
      className: "batch-preview"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl",
      "aria-label": "\u6279\u6B21\u5BFC\u5165\u9884\u89C8"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u884C\u53F7 / \u6279\u6B21"), /*#__PURE__*/React.createElement("th", null, "\u64CD\u4F5C"), /*#__PURE__*/React.createElement("th", null, "\u6838\u5BF9\u5185\u5BB9"))), /*#__PURE__*/React.createElement("tbody", null, preview.rows.map(row => /*#__PURE__*/React.createElement(PreviewRow, {
      key: row.row,
      row: row
    }))))), preview.deleted.length > 0 && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h3", null, "\u5C06\u5220\u9664\u7684\u5168\u90E8\u6279\u6B21"), preview.deleted.map(row => /*#__PURE__*/React.createElement("div", {
      key: row.entity_ref
    }, row.before.business_code, " \xB7 ", row.before.operations.length, " \u9053\u5DE5\u5E8F", row.errors.length ? ' · ' + row.errors.join('；') : ''))), /*#__PURE__*/React.createElement(Issues, {
      issues: preview.warnings
    }), /*#__PURE__*/React.createElement(Button, {
      onClick: () => setPreview(null),
      disabled: locked
    }, "\u8FD4\u56DE\u6838\u5BF9\u6587\u4EF6"))) : /*#__PURE__*/React.createElement("div", {
      className: "batch-value-list"
    }, /*#__PURE__*/React.createElement("label", null, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: form,
      checked: selection === 'selected',
      disabled: locked || !selected.length,
      onChange: () => setSelection('selected')
    }), "\u5BFC\u51FA\u9009\u4E2D ", selected.length, " \u4E2A\u6279\u6B21\uFF08\u542B\u9690\u85CF\u9009\u4E2D\u9879\uFF09"), /*#__PURE__*/React.createElement("label", null, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: form,
      checked: selection === 'filtered',
      disabled: locked,
      onChange: () => setSelection('filtered')
    }), "\u5BFC\u51FA\u5F53\u524D\u7B5B\u9009\u5168\u90E8\u6279\u6B21")), /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: command
    })));
  }
  window.BatchFiles = BatchFiles;
})();
