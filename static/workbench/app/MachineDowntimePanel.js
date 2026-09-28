(function () {
  'use strict';

  const C = window.APSResourceContract,
    S = window.APSResourceSession;
  const {
    Button,
    Modal,
    Field,
    ErrorBox
  } = window.ResourceControls;
  const blank = () => ({
    start_time: '',
    end_time: '',
    reason_code: 'maintenance',
    reason_detail: ''
  });
  function MachineDowntimePanel({
    adapter,
    entity,
    source,
    onClose,
    onCommitted
  }) {
    const command = S.useCommand(adapter),
      [selection, setSelection] = React.useState(null);
    const [draft, setDraft] = React.useState(blank),
      [original, setOriginal] = React.useState(blank),
      [error, setError] = React.useState(null);
    const [confirmCancel, setConfirmCancel] = React.useState(false),
      [review, setReview] = React.useState(null),
      seen = React.useRef(null);
    const query = S.useQuery(signal => adapter.downtimes(entity.ref, signal), [adapter, entity.ref]);
    const data = query.result && query.result.data,
      done = command.phase === 'done',
      locked = command.locked || done;
    const dirty = JSON.stringify(draft) !== JSON.stringify(original),
      form = React.useId();
    const owner = window.WorkbenchGuards.useDirtyGuard({
      dirty: !done && dirty,
      locked: command.locked,
      message: '停机资料尚未保存，离开会丢失本次填写。'
    });
    React.useEffect(() => {
      if (!done || seen.current === command.result.receipt_ref) return;
      const receipt = command.result,
        intent = command.intent;
      if (!intent || receipt.data.operation !== 'machine.' + intent.action || intent.ref !== entity.ref || receipt.data.entity_ref !== entity.ref) {
        setError(C.failure('保存结果与当前设备不一致，请查询结果后核对。'));
        return;
      }
      seen.current = receipt.receipt_ref;
      query.reload();
      if (onCommitted) onCommitted(receipt);
    }, [done, command.result]);
    async function close(detail) {
      if (command.locked) return;
      if (detail && detail.guardConfirmed && detail.guardOwner === owner || (await window.WorkbenchGuards.confirmLeave({
        owner
      }))) onClose();
    }
    function select(row) {
      const value = row ? Object.fromEntries(Object.keys(blank()).map(key => [key, row[key] || ''])) : blank();
      value.start_time = value.start_time.replace(' ', 'T');
      value.end_time = value.end_time.replace(' ', 'T');
      setSelection(row);
      setDraft(value);
      setOriginal(value);
      setConfirmCancel(false);
      setError(null);
    }
    async function save(event) {
      event.preventDefault();
      if (locked || !data || review) return;
      const action = confirmCancel ? 'cancel' : selection ? 'update' : 'create';
      const reason = C.blocked(data.write_context, 'machine', 'downtime_' + action, source);
      if (reason) {
        setError(C.failure(reason));
        return;
      }
      if (!confirmCancel && (!draft.start_time || !draft.end_time || draft.end_time <= draft.start_time)) {
        setError(C.failure('请填写停机起止，结束必须晚于开始。'));
        return;
      }
      setError(null);
      await command.submit('machine', 'downtime_' + action, entity.ref, data.write_context, {
        ...(confirmCancel ? {} : draft),
        ...(selection ? {
          downtime_ref: selection.ref
        } : {})
      });
    }
    async function reload() {
      try {
        const latest = await adapter.downtimes(entity.ref);
        setReview(latest);
        setError(null);
      } catch (e) {
        setError(e);
      }
    }
    return /*#__PURE__*/React.createElement(Modal, {
      title: '停机计划 · ' + entity.business_code,
      icon: "wrench",
      onClose: close,
      guardOwner: owner,
      locked: command.locked,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: close,
        disabled: command.locked
      }, "\u5173\u95ED"), !done && /*#__PURE__*/React.createElement(Button, {
        form: form,
        type: "submit",
        className: "btn primary",
        disabled: locked || !data || !!review
      }, confirmCancel ? '确认取消这段停机' : '保存停机计划'))
    }, /*#__PURE__*/React.createElement("form", {
      id: form,
      className: "modal-b form scroll",
      onSubmit: save
    }, /*#__PURE__*/React.createElement("p", null, "\u505C\u673A\u8BA1\u5212\u6309\u8D77\u6B62\u65F6\u95F4\u9650\u5236\u6392\u4EA7\u3002\u8BBE\u5907\u6539\u4E3A\u53EF\u7528\u540E\uFF0C\u5DF2\u6709\u6709\u6548\u505C\u673A\u8BA1\u5212\u4ECD\u7136\u751F\u6548\uFF1B\u53D6\u6D88\u8BA1\u5212\u4F1A\u4FDD\u7559\u539F\u8BB0\u5F55\u3002"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: query.error
    }), query.loading && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u505C\u673A\u8BB0\u5F55\u2026"), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      "aria-label": "\u8BBE\u5907\u505C\u673A\u8BA1\u5212"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u5F00\u59CB"), /*#__PURE__*/React.createElement("th", null, "\u7ED3\u675F"), /*#__PURE__*/React.createElement("th", null, "\u539F\u56E0"), /*#__PURE__*/React.createElement("th", null, "\u72B6\u6001"), /*#__PURE__*/React.createElement("th", null, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, data && data.rows.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.ref
    }, /*#__PURE__*/React.createElement("td", null, window.WorkbenchFormat.dateTime(row.start_time)), /*#__PURE__*/React.createElement("td", null, window.WorkbenchFormat.dateTime(row.end_time)), /*#__PURE__*/React.createElement("td", null, data.reasons[row.reason_code] || row.reason_code, " ", row.reason_detail), /*#__PURE__*/React.createElement("td", null, row.status === 'active' ? '有效' : row.status === 'cancelled' ? '已取消' : row.status), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      disabled: locked || dirty || row.status !== 'active',
      onClick: () => select(row)
    }, "\u7EF4\u62A4"))))))), !done && /*#__PURE__*/React.createElement(Button, {
      disabled: locked || dirty,
      onClick: () => select(null)
    }, "\u65B0\u589E\u505C\u673A"), !done && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "fgrid"
    }, ['start_time', 'end_time'].map((key, index) => /*#__PURE__*/React.createElement(Field, {
      key: key,
      label: index ? '停机结束' : '停机开始'
    }, /*#__PURE__*/React.createElement("input", {
      type: "datetime-local",
      step: "1",
      value: draft[key],
      disabled: locked || confirmCancel,
      onChange: event => setDraft({
        ...draft,
        [key]: event.target.value
      })
    }))), /*#__PURE__*/React.createElement(Field, {
      label: "\u505C\u673A\u539F\u56E0"
    }, /*#__PURE__*/React.createElement("select", {
      value: draft.reason_code,
      disabled: locked || confirmCancel,
      onChange: event => setDraft({
        ...draft,
        reason_code: event.target.value
      })
    }, data && Object.entries(data.reasons).map(([key, label]) => /*#__PURE__*/React.createElement("option", {
      key: key,
      value: key
    }, label)))), /*#__PURE__*/React.createElement(Field, {
      label: "\u539F\u56E0\u8BF4\u660E"
    }, /*#__PURE__*/React.createElement("input", {
      value: draft.reason_detail,
      disabled: locked || confirmCancel,
      onChange: event => setDraft({
        ...draft,
        reason_detail: event.target.value
      })
    }))), selection && /*#__PURE__*/React.createElement(Button, {
      disabled: locked,
      onClick: () => setConfirmCancel(!confirmCancel)
    }, confirmCancel ? '返回编辑' : '取消这段停机'), confirmCancel && /*#__PURE__*/React.createElement("p", null, "\u786E\u8BA4\u540E\uFF0C\u8BE5\u65F6\u6BB5\u4E0D\u518D\u9650\u5236\u8BBE\u5907\u6392\u4EA7\u3002\u5DF2\u6709\u6392\u7A0B\u4E0D\u4F1A\u81EA\u52A8\u91CD\u6392\u3002"), /*#__PURE__*/React.createElement(Button, {
      onClick: reload,
      disabled: locked
    }, "\u8BFB\u53D6\u6700\u65B0\u8BB0\u5F55")), review && /*#__PURE__*/React.createElement("div", {
      role: "status"
    }, /*#__PURE__*/React.createElement("p", null, "\u91C7\u7528\u6700\u65B0\u8BB0\u5F55\u5C06\u653E\u5F03\u672C\u6B21\u672A\u4FDD\u5B58\u7684\u4FEE\u6539\uFF0C\u8BF7\u91CD\u65B0\u9009\u62E9\u8981\u7EF4\u62A4\u7684\u505C\u673A\u3002"), /*#__PURE__*/React.createElement(Button, {
      disabled: locked,
      onClick: () => {
        select(null);
        setReview(null);
        command.reset();
        query.reload();
      }
    }, "\u91C7\u7528\u6700\u65B0\u8BB0\u5F55\u5E76\u91CD\u65B0\u586B\u5199")), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(window.ResourceForms.Feedback, {
      command: command
    }), done && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, query.loading ? '正在刷新保存结果…' : query.error ? '保存结果已确认，列表尚未刷新；请关闭后重新查看。' : '已刷新停机记录。')));
  }
  window.MachineDowntimePanel = MachineDowntimePanel;
})();
