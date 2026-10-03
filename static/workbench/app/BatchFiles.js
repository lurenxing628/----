(function () {
  'use strict';

  const B = window.APSBatchContract,
    C = window.APSResourceContract,
    T = window.WorkbenchTerms,
    {
      Button,
      Modal,
      ErrorBox,
      Issues,
      Icon
    } = window.ResourceControls;
  const TEMPLATE_NAME = '批次导入模板.xlsx',
    EXPORT_NAME = '批次清单.xlsx';
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
    }, names[key], "\uFF1A", window.BatchControls.display(key, row.before && row.before.fields[key]), " \u2192 ", window.BatchControls.display(key, row.input.fields[key]))))));
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
      [preview, setPreview] = React.useState(null),
      [acknowledged, setAcknowledged] = React.useState(false);
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
    // 已选文件或已有预检结果就算没做完：关闭前先确认，避免误关丢掉文件和预检。
    const guardOwner = window.WorkbenchGuards.useDirtyGuard({
      dirty: importing && !done && (!!file || !!preview),
      locked: command.locked || busy,
      message: '批次导入还没有完成，离开会放弃已选文件和预检结果。'
    });
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
    function invalidate() {
      setPreview(null);
      setError(null);
      setAcknowledged(false);
      serial.current++;
    }
    function changeMode(value) {
      setMode(value);
      invalidate();
    }
    function chooseFile(list) {
      setFile(list && list[0] || null);
      invalidate();
    }
    async function close(detail) {
      if (command.locked || busy) return;
      if (!(detail && detail.guardConfirmed === true && detail.guardOwner === guardOwner) && !(await window.WorkbenchGuards.confirmLeave({
        owner: guardOwner
      }))) return;
      onClose();
    }
    async function work(action) {
      if (locked) return;
      const id = ++serial.current;
      setBusy(true);
      setError(null);
      setNotice('');
      try {
        if (action === 'template') {
          saveDownload(await adapter.downloadTemplate(), TEMPLATE_NAME);
          if (alive.current && id === serial.current) setNotice(T.download_started(TEMPLATE_NAME));
        } else if (action === 'preview') {
          const result = await adapter.importPreview(file, mode, scope, snapshot);
          const data = result && result.data;
          if (!data || data.operation !== 'batch.import_confirm' || data.mode !== mode || !Array.isArray(data.rows) || !Array.isArray(data.deleted) || typeof data.can_confirm !== 'boolean' || data.can_confirm && (!data.write_context || !B.context(data.write_context))) throw C.failure('读到的导入预检结果不完整，没有写入批次。请再点一次「开始预检」。');
          if (alive.current && id === serial.current) setPreview(data);
        } else {
          const result = await adapter.exportPreview(selection, {
            ...scope,
            snapshot_ref: snapshot
          }, selected);
          if (!result.data || typeof result.data.export_ref !== 'string' || !Number.isSafeInteger(result.data.count)) throw C.failure('导出范围没有确认，文件没有生成。请刷新批次列表后重试。');
          const downloaded = await adapter.downloadExport(result.data.export_ref);
          saveDownload(downloaded, EXPORT_NAME);
          if (alive.current && id === serial.current) setNotice(T.download_started(EXPORT_NAME) + '（共 ' + window.WorkbenchFormat.number(result.data.count, {
            digits: 0
          }) + ' 个批次）');
        }
      } catch (error) {
        if (alive.current && id === serial.current) setError(error);
      } finally {
        if (alive.current && id === serial.current) setBusy(false);
      }
    }
    // 「先清除全部批次再重导」会删掉表格以外的所有批次：主按钮按危险动作着色，且必须先核对勾选。
    const replacing = mode === 'replace',
      replaceReason = replacing && !acknowledged ? '请先核对将删除的全部批次，并勾选确认。' : '';
    return /*#__PURE__*/React.createElement("div", {
      className: 'plana rm-actions' + (preview ? ' rm-wide' : '')
    }, /*#__PURE__*/React.createElement(Modal, {
      title: importing ? '批量导入批次' : '导出批次清单',
      icon: "box",
      locked: command.locked || busy,
      guardOwner: guardOwner,
      onClose: close,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: () => close(),
        disabled: command.locked || busy
      }, done ? '关闭' : '取消'), importing ? !done && /*#__PURE__*/React.createElement(React.Fragment, null, !preview ? /*#__PURE__*/React.createElement(Button, {
        transfer: "import",
        disabled: locked || !file,
        onClick: () => work('preview')
      }, "\u5F00\u59CB\u9884\u68C0") : /*#__PURE__*/React.createElement(Button, {
        transfer: "import",
        className: 'btn ' + (replacing ? 'danger' : 'primary'),
        disabled: locked || !preview.can_confirm,
        reason: replaceReason,
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
    }, notice), importing ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "tmpl-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "tmpl-ico"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "file-input"
    })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "tmpl-t"
    }, TEMPLATE_NAME), /*#__PURE__*/React.createElement("div", {
      className: "tmpl-s"
    }, "\u7A7A\u767D\u8868\u5934\u6A21\u677F\uFF0C\u4E0D\u542B\u793A\u4F8B\u6279\u6B21")), /*#__PURE__*/React.createElement(Button, {
      className: "mini",
      transfer: "template",
      disabled: locked,
      onClick: () => work('template')
    }, "\u4E0B\u8F7D\u6A21\u677F")), /*#__PURE__*/React.createElement("div", {
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
    }, "\u5148\u6E05\u9664\u5168\u90E8\u6279\u6B21\uFF0C\u518D\u6309\u8868\u683C\u91CD\u5BFC")))), !preview && /*#__PURE__*/React.createElement("div", {
      className: 'drop rm-upload' + (file ? ' has' : ''),
      "aria-disabled": locked,
      onDragOver: event => event.preventDefault(),
      onDrop: event => {
        event.preventDefault();
        if (!locked) chooseFile(event.dataTransfer.files);
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "di"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "file-input"
    })), /*#__PURE__*/React.createElement("div", {
      className: "dt"
    }, file ? file.name : '选择 XLSX 文件'), /*#__PURE__*/React.createElement("div", {
      className: "ds"
    }, file ? window.WorkbenchFormat.number(file.size, {
      digits: 0
    }) + ' 字节 · 只接受 .xlsx 文件' : '只接受 .xlsx 文件，也可以把文件拖到这里'), /*#__PURE__*/React.createElement("input", {
      type: "file",
      "aria-label": "\u9009\u62E9\u6587\u4EF6",
      accept: ".xlsx",
      disabled: locked,
      onChange: event => {
        chooseFile(event.target.files);
        event.target.value = '';
      }
    })), /*#__PURE__*/React.createElement("p", {
      className: "iohint"
    }, "\u65B0\u6279\u6B21\u5BFC\u5165\u540E\u9700\u751F\u6210\u5DE5\u5E8F\uFF1B\u66F4\u65B0\u65F6\u7A7A\u767D\u5355\u5143\u683C\u4FDD\u7559\u539F\u503C\u3002\u7EF4\u62A4\u9F50\u5957\u6807\u8BB0\u517C\u5BB9\u65E7\u201C\u9F50\u5957\u201D\u5217\uFF1B\u72B6\u6001\u548C\u5F53\u524D\u6709\u6548\u9F50\u5957\u53EA\u4F9B\u6838\u5BF9\uFF0C\u4E0D\u5BFC\u5165\u3002"), preview && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "tmpl-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "tmpl-ico"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "file-input"
    })), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("div", {
      className: "tmpl-t"
    }, file && file.name), /*#__PURE__*/React.createElement("div", {
      className: "tmpl-s"
    }, window.WorkbenchFormat.number(preview.count, {
      digits: 0
    }), " \u884C \xB7 ", preview.can_confirm ? '全部核对通过，一起保存' : '存在未通过检查的行，请修正')), /*#__PURE__*/React.createElement(Button, {
      icon: "file-input",
      onClick: invalidate,
      disabled: locked
    }, "\u66F4\u6362\u6587\u4EF6")), /*#__PURE__*/React.createElement("div", {
      className: "batch-preview wb-table-frame",
      "data-sticky-head": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": "\u6279\u6B21\u5BFC\u5165\u9884\u68C0"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u6279\u6B21\u5BFC\u5165\u9884\u68C0"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u884C\u53F7 / \u6279\u6B21"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u64CD\u4F5C"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u6838\u5BF9\u5185\u5BB9"))), /*#__PURE__*/React.createElement("tbody", null, preview.rows.map(row => /*#__PURE__*/React.createElement(PreviewRow, {
      key: row.row,
      row: row
    }))))), preview.deleted.length > 0 && /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h3", null, "\u5C06\u5220\u9664\u7684\u5168\u90E8\u6279\u6B21"), preview.deleted.map(row => /*#__PURE__*/React.createElement("div", {
      key: row.entity_ref
    }, row.before.business_code, " \xB7 ", row.before.operations.length, " \u9053\u5DE5\u5E8F", row.errors.length ? ' · ' + row.errors.join('；') : ''))), /*#__PURE__*/React.createElement(Issues, {
      issues: preview.warnings
    }), replacing && !done && /*#__PURE__*/React.createElement("label", {
      className: "rm-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: acknowledged,
      disabled: locked,
      onChange: event => setAcknowledged(event.target.checked)
    }), /*#__PURE__*/React.createElement("span", null, "\u5DF2\u6838\u5BF9\u5C06\u5220\u9664\u7684\u5168\u90E8\u6279\u6B21\u548C\u5BFC\u5165\u660E\u7EC6\uFF0C\u786E\u8BA4\u5148\u6E05\u9664\u518D\u91CD\u5BFC\u3002")))) : /*#__PURE__*/React.createElement("div", {
      className: "batch-value-list"
    }, /*#__PURE__*/React.createElement("p", null, "\u201C\u5F53\u524D\u6709\u6548\u9F50\u5957\uFF08\u53EA\u8BFB\uFF09\u201D\u4E0E\u5F53\u524D\u5217\u8868\u548C\u7B5B\u9009\u4E00\u81F4\uFF1B\u201C\u7EF4\u62A4\u9F50\u5957\u6807\u8BB0\u201D\u4FDD\u7559\u539F\u7EF4\u62A4\u503C\uFF0C\u539F\u6837\u56DE\u5BFC\u4E0D\u4F1A\u8986\u76D6\u6309\u7269\u6599\u8BA1\u7B97\u7684\u6709\u6548\u72B6\u6001\u3002"), /*#__PURE__*/React.createElement("label", null, /*#__PURE__*/React.createElement("input", {
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
    }))));
  }
  window.BatchFiles = BatchFiles;
})();
