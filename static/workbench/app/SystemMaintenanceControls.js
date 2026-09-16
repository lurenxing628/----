(function () {
  'use strict';

  const A = window.SystemMaintenanceAPI;
  function Button({
    children,
    icon,
    className = 'btn',
    ...props
  }) {
    const label = typeof children === 'string' ? children : props['aria-label'];
    return /*#__PURE__*/React.createElement(window.ResourceControls.Button, {
      ...props,
      icon: icon === 'rotate-ccw' ? undefined : icon === 'save' ? 'check' : icon,
      title: props.reason || props.title || label,
      "aria-label": props['aria-label'] || (props.reason && label ? label + '：' + props.reason : undefined),
      reasonDisplay: props.reason ? 'inline' : props.reasonDisplay,
      className: className + ' sm-button' + (children ? '' : ' sm-icon-button')
    }, icon === 'rotate-ccw' && /*#__PURE__*/React.createElement(SMIcon, {
      name: "rotate-ccw"
    }), children);
  }
  function Styles() {
    return null;
  }
  function ErrorBox({
    error
  }) {
    return error ? /*#__PURE__*/React.createElement(window.WorkbenchError, {
      error: error
    }) : null;
  }
  function useRead(api, kind, input, revision, enabled = true) {
    const [state, setState] = React.useState({
      data: null,
      error: null,
      loading: true
    });
    const signature = JSON.stringify(input);
    React.useEffect(() => {
      if (!enabled) {
        setState({
          data: null,
          error: null,
          loading: false
        });
        return;
      }
      const controller = new AbortController();
      setState({
        data: null,
        error: null,
        loading: true
      });
      api.read(kind, input, controller.signal).then(data => {
        if (!controller.signal.aborted) setState({
          data,
          error: null,
          loading: false
        });
      }).catch(error => {
        if (!controller.signal.aborted) setState({
          data: null,
          error,
          loading: false
        });
      });
      return () => controller.abort();
    }, [api, kind, signature, revision, enabled]);
    return state;
  }
  function Confirm({
    action,
    row,
    reason,
    onClose,
    onConfirm
  }) {
    const [checked, setChecked] = React.useState(false),
      [typed, setTyped] = React.useState('');
    const destructive = action !== 'create',
      ready = !destructive || checked && (action !== 'restore' || typed === '恢复');
    return /*#__PURE__*/React.createElement(window.ResourceControls.Modal, {
      title: A.actions[action],
      icon: action === 'create' ? 'plus' : action === 'delete' ? 'trash-2' : 'history',
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        onClick: onClose
      }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
        icon: action === 'delete' ? 'trash-2' : 'check',
        className: 'btn ' + (action === 'delete' ? 'danger' : 'primary'),
        reason: reason,
        disabled: !ready,
        onClick: onConfirm
      }, "\u786E\u8BA4", action === 'create' ? '新增' : action === 'delete' ? '删除' : '恢复'))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b form scroll",
      style: {
        overflowWrap: 'anywhere'
      }
    }, row && /*#__PURE__*/React.createElement("p", null, /*#__PURE__*/React.createElement("strong", null, row.filename), /*#__PURE__*/React.createElement("br", null), "\u6587\u4EF6\u4FEE\u6539\u65F6\u95F4 ", window.WorkbenchFormat.dateTime(row.time), " \xB7 ", row.size_bytes, " \u5B57\u8282", /*#__PURE__*/React.createElement("br", null), "\u6587\u4EF6\u5B58\u5728\uFF0C\u5C1A\u65E0\u672C\u6B21\u5B8C\u6574\u6027\u6821\u9A8C\u8BC1\u636E\u3002"), /*#__PURE__*/React.createElement("p", null, action === 'create' ? '备份当前数据库。' : action === 'delete' ? '仅删除此备份文件，删除后不能撤销。' : '将用所选备份替换当前数据库。系统会先生成保护副本；完整性检查不通过时自动还原。'), action === 'restore' && /*#__PURE__*/React.createElement("p", {
      className: "sm-notice"
    }, "\u4E00\u65E6\u63D0\u4EA4\u6062\u590D\uFF0C\u4E1A\u52A1\u64CD\u4F5C\u4F1A\u505C\u7528\u3002\u65E0\u8BBA\u6062\u590D\u6210\u529F\u8FD8\u662F\u5DF2\u8FD8\u539F\uFF0C\u90FD\u8981\u5173\u95ED\u6574\u4E2A\u8F6F\u4EF6\u518D\u542F\u52A8\uFF1B\u53EA\u5237\u65B0\u6D4F\u89C8\u5668\u4E0D\u7B97\u91CD\u542F\u3002"), destructive && /*#__PURE__*/React.createElement("label", {
      className: "sm-inline-label"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: checked,
      onChange: event => setChecked(event.target.checked)
    }), "\u6211\u5DF2\u6838\u5BF9\u6240\u9009\u6587\u4EF6\u4E0E\u64CD\u4F5C\u5F71\u54CD"), action === 'restore' && /*#__PURE__*/React.createElement("label", {
      className: "field",
      style: {
        marginTop: 16
      }
    }, /*#__PURE__*/React.createElement("span", null, "\u8F93\u5165\u201C\u6062\u590D\u201D\u786E\u8BA4"), /*#__PURE__*/React.createElement("input", {
      value: typed,
      onChange: event => setTyped(event.target.value)
    })), reason && /*#__PURE__*/React.createElement(ErrorBox, {
      error: reason
    })));
  }
  const labels = {
    accepted: '已接收',
    checking: '检查中',
    protecting: '生成保护副本',
    restoring: '恢复中',
    verifying: '完整性检查中',
    rolling_back: '还原中',
    succeeded: '已完成',
    failed: '操作失败',
    rolled_back: '恢复失败，已还原',
    rollback_failed: '还原失败，需人工核对',
    recovery_required: '需人工核对'
  };
  function Outcome({
    command
  }) {
    const {
      intent,
      result,
      error,
      busy,
      storageError
    } = command;
    if (!intent && !storageError) return null;
    const op = result && result.kind === 'file_operation' && result.operation;
    return /*#__PURE__*/React.createElement("section", {
      className: "sm-section sm-maintenance-outcome",
      "aria-label": "\u4E0A\u6B21\u7EF4\u62A4\u64CD\u4F5C\u7684\u7ED3\u679C",
      style: {
        padding: '12px 20px',
        background: 'var(--ui-card-bg)',
        borderBottom: '1px solid var(--ui-border)',
        overflowWrap: 'anywhere'
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "sm-section-head"
    }, /*#__PURE__*/React.createElement("h3", null, intent ? intent.summary : '上次操作记录不可用'), /*#__PURE__*/React.createElement("div", {
      className: "sm-actions"
    }, intent && !(result && result.kind === 'rejected') && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      busy: busy,
      onClick: command.lookup
    }, window.WorkbenchTerms.actions.query_result), result && result.terminal && !command.suspended && /*#__PURE__*/React.createElement(Button, {
      icon: "check",
      disabled: busy,
      onClick: command.acknowledge
    }, "\u786E\u8BA4\u7ED3\u679C"))), intent && /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      label: "\u64CD\u4F5C\u7F16\u53F7",
      value: intent.request_key
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: storageError || error
    }), busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u7B49\u5F85\u7EF4\u62A4\u7ED3\u679C\uFF0C\u6CA1\u6709\u91CD\u65B0\u63D0\u4EA4\u3002"), op ? /*#__PURE__*/React.createElement("div", {
      role: "status"
    }, /*#__PURE__*/React.createElement("p", null, /*#__PURE__*/React.createElement("strong", {
      className: op.state === 'succeeded' ? 'sm-tone-success' : 'sm-tone-warning'
    }, labels[op.state]), " \xB7 ", op.message), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      label: "\u7EF4\u62A4\u8BB0\u5F55\u4E0E\u7ED3\u679C\u4EE3\u7801",
      entries: {
        '维护编号': op.job_ref,
        '结果代码': op.code
      }
    }), /*#__PURE__*/React.createElement("p", null, "\u66F4\u65B0\u65F6\u95F4\uFF1A", window.WorkbenchFormat.dateTime(op.updated_at), /*#__PURE__*/React.createElement("br", null), "\u4E1A\u52A1\u5BA1\u8BA1\uFF1A", op.audit_persisted ? '已留存' : '未确认留存', op.replayed ? ' · 查询上次结果' : ''), op.filename && /*#__PURE__*/React.createElement("p", null, "\u76EE\u6807\u6587\u4EF6\uFF1A", op.filename), op.protection_filename && /*#__PURE__*/React.createElement("p", null, "\u4FDD\u62A4\u526F\u672C\uFF1A", op.protection_filename), /*#__PURE__*/React.createElement("details", {
      className: "sm-rules"
    }, /*#__PURE__*/React.createElement("summary", null, "\u7EF4\u62A4\u9636\u6BB5"), op.history.map((step, index) => /*#__PURE__*/React.createElement("p", {
      key: index
    }, window.WorkbenchFormat.dateTime(step.time), " \xB7 ", labels[step.state])))) : result && result.kind === 'config' ? /*#__PURE__*/React.createElement("div", {
      role: "status"
    }, /*#__PURE__*/React.createElement("p", null, result.command.result === 'committed' ? '八项维护配置已保存，操作记录已留存。' : '配置没有变化，没有写入新的操作记录。'), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      label: "\u4FDD\u5B58\u7ED3\u679C\u7F16\u53F7",
      value: result.command.receipt_ref
    }), result.command.replayed && /*#__PURE__*/React.createElement("p", null, "\u67E5\u8BE2\u4E0A\u6B21\u7ED3\u679C")) : result && result.kind === 'rejected' ? /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u7CFB\u7EDF\u62D2\u7EDD\u4E86\u8FD9\u6B21\u63D0\u4EA4\uFF0C\u914D\u7F6E\u6CA1\u6709\u6539\u52A8\u3002\u8BF7\u6309\u4E0A\u9762\u7684\u63D0\u793A\u6539\u597D\u540E\u91CD\u65B0\u63D0\u4EA4\u3002") : null, intent && !(result && result.terminal) && /*#__PURE__*/React.createElement("p", {
      className: "sm-note"
    }, result && result.kind === 'not_recorded' ? result.message : '上次操作还没有确认结果。', " \u8BF7\u70B9\u300C\u67E5\u8BE2\u7ED3\u679C\u300D\uFF0C\u52FF\u91CD\u590D\u63D0\u4EA4\u3002", intent.action === 'restore' ? ' 确认恢复结果前，业务操作暂停。' : ''));
  }
  function Preferences({
    theme,
    onSetTheme,
    pageSize,
    onPageSize,
    compact,
    onCompact
  }) {
    return /*#__PURE__*/React.createElement("section", {
      className: "sm-section sm-preferences"
    }, /*#__PURE__*/React.createElement("div", {
      className: "sm-section-head"
    }, /*#__PURE__*/React.createElement("h3", null, "\u9875\u9762\u504F\u597D")), /*#__PURE__*/React.createElement("div", {
      className: "sm-session-settings"
    }, /*#__PURE__*/React.createElement("fieldset", {
      className: "sm-choice"
    }, /*#__PURE__*/React.createElement("legend", null, "\u4E3B\u9898"), [['light', '浅色'], ['dark', '深色']].map(([value, label]) => /*#__PURE__*/React.createElement("label", {
      key: value
    }, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: "system-maintenance-theme",
      checked: theme === value,
      disabled: typeof onSetTheme !== 'function',
      onChange: () => onSetTheme(value)
    }), label))), /*#__PURE__*/React.createElement("label", {
      className: "sm-inline-label"
    }, "\u6BCF\u9875\u6761\u6570", /*#__PURE__*/React.createElement("select", {
      value: pageSize,
      onChange: event => onPageSize(Number(event.target.value))
    }, [10, 25, 50].map(size => /*#__PURE__*/React.createElement("option", {
      key: size,
      value: size
    }, size, " \u6761")))), /*#__PURE__*/React.createElement("label", {
      className: "sm-inline-label",
      title: "\u5E94\u7528\u4E8E\u5168\u5DE5\u4F5C\u53F0\u8868\u683C"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: compact,
      onChange: event => onCompact(event.target.checked)
    }), "\u7D27\u51D1\u884C\u8DDD")));
  }
  window.SystemMaintenanceControls = {
    Button,
    Styles,
    ErrorBox,
    useRead,
    Confirm,
    Outcome,
    Preferences
  };
})();
