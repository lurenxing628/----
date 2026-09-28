(function () {
  'use strict';

  const {
    Button,
    Modal,
    ErrorBox,
    Field
  } = window.ResourceControls;
  const B = window.APSBatchContract;
  function BatchSplitPanel({
    refs,
    day,
    onCommitted
  }) {
    const adapter = React.useMemo(() => window.APSBatchAPI.create(), []);
    const command = window.APSResourceSession.useCommand(adapter);
    const [preview, setPreview] = React.useState(null),
      [error, setError] = React.useState(null),
      [busy, setBusy] = React.useState(false);
    const [quantity, setQuantity] = React.useState(''),
      seen = React.useRef(null),
      serial = React.useRef(0);
    const owner = window.WorkbenchGuards.useDirtyGuard({
      dirty: false,
      locked: command.locked,
      message: '拆分正在确认，请先核对保存结果。'
    });
    React.useEffect(() => {
      serial.current++;
      setPreview(null);
    }, [JSON.stringify(refs), day]);
    React.useEffect(() => () => {
      serial.current++;
    }, []);
    React.useEffect(() => {
      if (command.phase !== 'done' || seen.current === command.result.receipt_ref || command.intent.action !== 'split_confirm') return;
      try {
        const result = B.receipt(command.result, 'split_confirm', command.intent.ref);
        if (!B.ref(result.data.child_ref)) throw window.APSResourceContract.failure('未读到拆分子批，请刷新批次核对。');
        seen.current = result.receipt_ref;
        setPreview(null);
        setQuantity('');
        onCommitted(result.data.child_ref, command.intent.ref);
      } catch (e) {
        setError(e);
      }
    }, [command.phase, command.result]);
    async function inspect() {
      if (refs.length !== 1 || command.locked || busy) return;
      const id = ++serial.current;
      setBusy(true);
      setError(null);
      try {
        command.reset();
        const count = quantity.trim() ? Number(quantity) : null;
        if (count !== null && (!Number.isSafeInteger(count) || count <= 0)) throw window.APSResourceContract.failure('请填写正整数数量，留空则按当前物料可做数量预检。');
        const detail = await adapter.detail('batch', refs[0]),
          input = {
            as_of_date: day,
            quantity: count
          };
        B.detail(detail, refs[0]);
        const response = await adapter.preview('split', refs[0], input, null, detail.meta.snapshot_ref);
        const data = B.preview(response, 'split', refs[0], input);
        if (id === serial.current) setPreview(data);
      } catch (e) {
        if (id === serial.current) setError(e);
      } finally {
        setBusy(false);
      }
    }
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5206\u6279\u5F00\u5DE5\u9884\u68C0"
    }, /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement(Field, {
      label: "\u672C\u6B21\u5148\u505A\u6570\u91CF\uFF08\u53EF\u7559\u7A7A\uFF09"
    }, /*#__PURE__*/React.createElement("input", {
      inputMode: "numeric",
      "aria-label": "\u672C\u6B21\u5148\u505A\u6570\u91CF",
      value: quantity,
      disabled: busy || command.locked,
      onChange: e => {
        setQuantity(e.target.value);
        setPreview(null);
      }
    })), /*#__PURE__*/React.createElement(Button, {
      busy: busy,
      disabled: command.locked || refs.length !== 1,
      onClick: inspect
    }, "\u9884\u68C0\u53EF\u5F00\u5DE5\u6570\u91CF")), /*#__PURE__*/React.createElement("p", null, "\u4E00\u6B21\u9009\u62E9\u4E00\u4E2A\u6279\u6B21\u9884\u68C0\uFF1B\u6309\u6392\u4EA7\u5F00\u59CB\u65E5\u671F ", day, " \u524D\u7684\u5230\u6599\u8BA1\u7B97\u3002\u786E\u8BA4\u540E\u624D\u4FDD\u5B58\u4E3A\u4E24\u4E2A\u6279\u6B21\uFF0C\u5E76\u9009\u4E2D\u53EF\u5F00\u5DE5\u5B50\u6279\u3002\u9700\u6C42\u91CF\u6309\u4EF6\u6570\u6BD4\u4F8B\u5206\u914D\uFF0C\u8BBE\u5907\u6362\u578B\u548C\u5916\u534F\u5468\u671F\u5728\u6BCF\u4E2A\u5B50\u6279\u5206\u522B\u8BA1\u7B97\u3002"), refs.length !== 1 && /*#__PURE__*/React.createElement("p", null, "\u8BF7\u5148\u9009\u62E9\u4E00\u4E2A\u8981\u62C6\u5206\u7684\u5F85\u6392\u6279\u6B21\u3002"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: command
    }), preview && ReactDOM.createPortal(/*#__PURE__*/React.createElement("div", {
      className: "plana"
    }, /*#__PURE__*/React.createElement(Modal, {
      title: "\u786E\u8BA4\u5206\u6279\u5F00\u5DE5",
      icon: "box",
      guardOwner: owner,
      locked: command.locked,
      onClose: () => {
        if (!command.locked) setPreview(null);
      },
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        disabled: command.locked,
        onClick: () => setPreview(null)
      }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
        className: "btn primary",
        disabled: command.locked,
        onClick: () => command.submit('batch', 'split_confirm', preview.entity_ref, preview.write_context, {
          preview_ref: preview.preview_ref
        })
      }, "\u786E\u8BA4\u62C6\u5206\u5E76\u9009\u62E9\u53EF\u5F00\u5DE5\u5B50\u6279"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b"
    }, /*#__PURE__*/React.createElement("p", null, preview.source_code, " \u539F\u6709 ", preview.original_quantity, " \u4EF6\uFF1A", preview.child_code, " \u5148\u505A ", preview.quantity, " \u4EF6\uFF0C\u539F\u6279\u4FDD\u7559 ", preview.remaining_quantity, " \u4EF6\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": "\u62C6\u5206\u7269\u6599\u5206\u914D"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u7269\u6599"), /*#__PURE__*/React.createElement("th", null, "\u5B50\u6279\u9700\u6C42"), /*#__PURE__*/React.createElement("th", null, "\u5269\u4F59\u9700\u6C42"), /*#__PURE__*/React.createElement("th", null, "\u5B50\u6279\u5230\u6599"), /*#__PURE__*/React.createElement("th", null, "\u5269\u4F59\u5230\u6599"))), /*#__PURE__*/React.createElement("tbody", null, preview.materials.map((row, i) => /*#__PURE__*/React.createElement("tr", {
      key: i
    }, /*#__PURE__*/React.createElement("td", null, row.business_code, " \xB7 ", row.label), /*#__PURE__*/React.createElement("td", null, row.child_required), /*#__PURE__*/React.createElement("td", null, row.source_required), /*#__PURE__*/React.createElement("td", null, row.child_available + row.child_arrivals.reduce((n, a) => n + a.quantity, 0)), /*#__PURE__*/React.createElement("td", null, row.source_available + row.source_arrivals.reduce((n, a) => n + a.quantity, 0))))))), /*#__PURE__*/React.createElement("p", null, "\u5230\u6599\u5206\u914D\u5305\u542B\u540E\u7EED\u5230\u6599\uFF0C\u6309\u5404\u81EA\u65E5\u671F\u53EF\u7528\u3002\u53D6\u6D88\u4E0D\u4F1A\u6539\u52A8\u6279\u6B21\uFF1B\u786E\u8BA4\u540E\u4ECD\u9700\u68C0\u67E5\u5E76\u5F00\u59CB\u8BA1\u7B97\u3002"), /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: command
    })))), document.body));
  }
  window.BatchSplitPanel = BatchSplitPanel;
})();
