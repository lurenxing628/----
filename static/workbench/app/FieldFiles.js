(function () {
  'use strict';

  const C = window.FieldContract,
    {
      Button,
      Modal,
      ErrorBox,
      Feedback
    } = window.FieldControls;
  function FieldFiles({
    adapter,
    scope,
    snapshot,
    command,
    onClose,
    onDone
  }) {
    const [file, setFile] = React.useState(null),
      [preview, setPreview] = React.useState(null),
      [error, setError] = React.useState(null),
      [busy, setBusy] = React.useState(false);
    const input = React.useRef(null),
      active = React.useRef(true),
      controller = React.useRef(null);
    React.useEffect(() => () => {
      active.current = false;
      if (controller.current) controller.current.abort();
    }, []);
    const locked = busy || command.locked || command.phase === 'done';
    async function run(action) {
      setError(null);
      setBusy(true);
      controller.current = new AbortController();
      try {
        if (action === 'preview') {
          if (!file || !/\.xlsx$/i.test(file.name) || file.size > 8 * 1024 * 1024) throw window.APSResourceContract.failure('请选择不超过 8 MB 的 XLSX 文件。');
          const value = C.query(await adapter.previewFile(file, scope, snapshot, controller.current.signal), 'preview').data;
          if (active.current) setPreview(value);
        } else if (action === 'errors') C.saveFile(await adapter.downloadErrors(preview.preview_ref, controller.current.signal), '报工导入问题.xlsx');else C.saveFile(await adapter.download(action, scope, snapshot, controller.current.signal), action === 'template' ? '现场分次报工模板.xlsx' : '现场报工导出.xlsx');
      } catch (error) {
        if (active.current) setError(error);
      } finally {
        if (active.current) setBusy(false);
      }
    }
    return /*#__PURE__*/React.createElement(Modal, {
      title: "\u62A5\u5DE5\u6587\u4EF6",
      icon: "file-input",
      locked: busy || command.locked,
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: onClose,
        disabled: busy || command.locked
      }, command.phase === 'done' ? '关闭' : '取消'), !preview && /*#__PURE__*/React.createElement(Button, {
        icon: "search",
        disabled: locked || !file,
        onClick: () => run('preview')
      }, "\u9884\u68C0\u6587\u4EF6"), preview && command.phase !== 'done' && /*#__PURE__*/React.createElement(Button, {
        transfer: "import",
        className: "btn primary",
        disabled: locked || !preview.can_confirm,
        reason: preview.can_confirm ? C.blocked(preview.write_context, 'import_confirm') : '文件存在问题，未写入任何报工。',
        onClick: () => command.submit('execution', 'import_confirm', preview.preview_ref, preview.write_context, {
          preview_ref: preview.preview_ref
        })
      }, "\u786E\u8BA4\u5BFC\u5165"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b"
    }, /*#__PURE__*/React.createElement("div", {
      className: "field-toolbar",
      style: {
        padding: '0 0 14px'
      }
    }, /*#__PURE__*/React.createElement(Button, {
      transfer: "template",
      disabled: locked,
      onClick: () => run('template')
    }, "\u4E0B\u8F7D\u6A21\u677F"), /*#__PURE__*/React.createElement(Button, {
      transfer: "export",
      disabled: locked,
      onClick: () => run('export')
    }, "\u5BFC\u51FA\u5F53\u524D\u8303\u56F4")), /*#__PURE__*/React.createElement("div", {
      className: "field-note"
    }, "XLSX \xB7 13 \u5217 \xB7 \u4EFB\u52A1\u7F16\u53F7\u3001\u5DE5\u5E8F\u8303\u56F4\u3001\u5355\u4EF6\u7F16\u53F7\u5DF2\u9884\u586B\uFF0C\u4E0D\u53EF\u4FEE\u6539 \xB7 \u517C\u5BB9\u65E7 10 \u5217"), /*#__PURE__*/React.createElement("div", {
      className: "field-upload"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "folder-open",
      disabled: locked,
      onClick: () => input.current.click()
    }, "\u9009\u62E9 Excel \u6587\u4EF6"), /*#__PURE__*/React.createElement("span", null, file ? file.name : '尚未选择文件'), /*#__PURE__*/React.createElement("input", {
      ref: input,
      hidden: true,
      type: "file",
      accept: ".xlsx",
      "aria-label": "\u62A5\u5DE5 XLSX \u6587\u4EF6",
      disabled: locked,
      onChange: event => {
        setFile(event.target.files[0] || null);
        setPreview(null);
        setError(null);
      }
    })), busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u6838\u5BF9\u6587\u4EF6\u548C\u73B0\u573A\u8BB0\u5F55\u2026"), preview && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "field-files-summary"
    }, [['total', '行数'], ['changed', '变更'], ['unchanged', '重复'], ['blank', '空白'], ['rejected', '问题']].map(([key, label]) => /*#__PURE__*/React.createElement("span", {
      key: key
    }, label, " ", /*#__PURE__*/React.createElement("b", null, preview.summary[key] || 0)))), /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, preview.can_confirm ? '预检通过，尚未写入报工。' : preview.summary.rejected ? '预检未通过，未写入任何报工。' : '没有可导入的实际记录，未写入报工。'), /*#__PURE__*/React.createElement("div", {
      className: "field-scroll wb-table-frame",
      "data-sticky-head": true,
      tabIndex: "0",
      "aria-label": "\u6587\u4EF6\u9884\u68C0\u8868\u683C\u6EDA\u52A8\u533A"
    }, /*#__PURE__*/React.createElement("table", {
      className: "field-table wb-table",
      "aria-label": "\u6587\u4EF6\u9010\u884C\u9884\u68C0"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u5F53\u524D\u6587\u4EF6\u9010\u884C\u9884\u68C0\u7ED3\u679C"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "Excel \u884C\u53F7"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5904\u7406\u7ED3\u679C"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u95EE\u9898"))), /*#__PURE__*/React.createElement("tbody", null, preview.rows.map((row, index) => /*#__PURE__*/React.createElement("tr", {
      key: index
    }, /*#__PURE__*/React.createElement("td", null, row.row_number || row.row), /*#__PURE__*/React.createElement("td", null, {
      create: '新增',
      supplement: '补齐',
      unchanged: '重复',
      blank: '空白',
      rejected: '拒绝',
      committed: '将变更',
      pending: '未执行'
    }[row.result] || '待核对'), /*#__PURE__*/React.createElement("td", null, (row.errors || []).map(item => item.message).join('；'))))))), preview.summary.rejected > 0 && /*#__PURE__*/React.createElement(Button, {
      transfer: "export",
      disabled: locked,
      onClick: () => run('errors')
    }, "\u4E0B\u8F7D\u95EE\u9898\u6E05\u5355"), !locked && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: () => {
        setPreview(null);
        run('preview');
      }
    }, "\u91CD\u65B0\u9884\u68C0\u539F\u6587\u4EF6")), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(Feedback, {
      command: command,
      onDone: onDone
    })));
  }
  window.FieldFiles = FieldFiles;
})();
