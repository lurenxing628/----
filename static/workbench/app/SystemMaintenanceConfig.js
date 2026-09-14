(function () {
  'use strict';

  const A = window.SystemMaintenanceAPI,
    C = window.SystemMaintenanceControls;
  function Config({
    api,
    revision,
    command,
    active = true,
    ...preferences
  }) {
    const [refresh, reload] = React.useReducer(value => value + 1, 0),
      [draft, setDraft] = React.useState(null),
      [validated, setValidated] = React.useState(false);
    const [base, setBase] = React.useState(null),
      [replace, setReplace] = React.useState(false);
    const request = C.useRead(api, 'config', {}, revision + ':' + refresh, active),
      incoming = request.data && request.data.data;
    const validation = A.normalize(draft || {}),
      changed = base && draft && A.fields.some(field => String(draft[field.key]) !== String(base.values[field.key]));
    React.useEffect(() => {
      // A receipt or revision alone cannot settle a draft; all eight read-back values must match.
      const matchesDraft = incoming && draft && A.fields.every(field => String(draft[field.key]) === String(incoming.values[field.key]));
      if (incoming && (!changed || matchesDraft)) {
        setBase(incoming);
        setDraft({
          ...incoming.values
        });
        setValidated(false);
      }
    }, [incoming]);
    const ready = incoming && base === incoming && !request.loading && !request.error;
    const reason = command.locked ? '上次维护操作还没有确认结果。请先点「查询结果」。' : !ready ? '请先点「刷新配置」读取正式配置。' : '';
    function refreshNow() {
      setReplace(false);
      setBase(null);
      setDraft(null);
      reload();
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "sm-configuration",
      style: {
        maxWidth: 'none'
      }
    }, /*#__PURE__*/React.createElement(C.Preferences, {
      ...preferences
    }), /*#__PURE__*/React.createElement("section", {
      className: "sm-section sm-maintenance-config"
    }, /*#__PURE__*/React.createElement("div", {
      className: "sm-section-head"
    }, /*#__PURE__*/React.createElement("h3", null, "\u672C\u673A\u81EA\u52A8\u7EF4\u62A4\u914D\u7F6E"), /*#__PURE__*/React.createElement(C.Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u914D\u7F6E",
      busy: request.loading,
      onClick: () => changed ? setReplace(true) : refreshNow()
    })), /*#__PURE__*/React.createElement(C.ErrorBox, {
      error: request.error
    }), request.loading && /*#__PURE__*/React.createElement("p", {
      className: "sm-note",
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u516B\u9879\u7EF4\u62A4\u914D\u7F6E\u2026"), incoming && base && incoming !== base && changed && /*#__PURE__*/React.createElement("div", {
      className: "sm-notice",
      role: "status"
    }, "\u5DF2\u8BFB\u5230\u65B0\u7684\u914D\u7F6E\u6570\u636E\uFF0C\u4F60\u586B\u7684\u5185\u5BB9\u6CA1\u6709\u88AB\u8986\u76D6\u3002\u8BF7\u6838\u5BF9\u53D8\u5316\u540E\u518D\u4FDD\u5B58\u3002", /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u6700\u65B0\u5DF2\u5B58\u914D\u7F6E"), A.fields.map(field => /*#__PURE__*/React.createElement("p", {
      key: field.key
    }, field.label, "\uFF1A", String(incoming.values[field.key]), incoming.dirty_fields.includes(field.key) ? ' · ' + incoming.dirty_reasons[field.key] : ''))), /*#__PURE__*/React.createElement(C.Button, {
      icon: "check",
      disabled: command.locked,
      onClick: () => setBase(incoming)
    }, "\u6838\u5BF9\u540E\u6CBF\u7528\u8349\u7A3F")), draft && base && /*#__PURE__*/React.createElement("form", {
      className: "sm-config-form",
      noValidate: true,
      onSubmit: event => {
        event.preventDefault();
        setValidated(true);
        if (validation.valid && !reason) command.execute('config', base.write_context.write_token, validation.values);
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "sm-config-groups"
    }, [['backup', '备份规则'], ['logs', '操作日志规则']].map(([group, label]) => /*#__PURE__*/React.createElement("fieldset", {
      className: "sm-config-group",
      key: group
    }, /*#__PURE__*/React.createElement("legend", null, label), A.fields.filter(field => field.group === group).map(field => /*#__PURE__*/React.createElement("div", {
      className: "sm-config-row",
      key: field.key,
      style: {
        gridTemplateColumns: 'minmax(140px, 1fr) minmax(140px, 1fr)'
      }
    }, /*#__PURE__*/React.createElement("label", {
      htmlFor: 'sm-maintenance-' + field.key
    }, field.label), /*#__PURE__*/React.createElement("div", null, field.switch ? /*#__PURE__*/React.createElement("label", {
      className: "sm-draft-checkbox"
    }, /*#__PURE__*/React.createElement("input", {
      id: 'sm-maintenance-' + field.key,
      type: "checkbox",
      checked: draft[field.key] === 'yes',
      disabled: !!reason,
      onChange: event => setDraft({
        ...draft,
        [field.key]: event.target.checked ? 'yes' : 'no'
      })
    }), /*#__PURE__*/React.createElement("span", null, draft[field.key] === 'yes' ? '启用' : '关闭')) : /*#__PURE__*/React.createElement("div", {
      className: "sm-number"
    }, /*#__PURE__*/React.createElement("input", {
      id: 'sm-maintenance-' + field.key,
      type: "number",
      min: 1,
      max: field.max,
      step: 1,
      value: draft[field.key],
      disabled: !!reason,
      "aria-invalid": validated && !!validation.errors[field.key],
      "aria-describedby": 'sm-maintenance-help-' + field.key,
      onChange: event => setDraft({
        ...draft,
        [field.key]: event.target.value
      })
    }), /*#__PURE__*/React.createElement("span", null, field.unit)), /*#__PURE__*/React.createElement("small", {
      id: 'sm-maintenance-help-' + field.key,
      className: validated && validation.errors[field.key] ? 'sm-error' : 'sm-meta'
    }, validated && validation.errors[field.key] || (field.switch ? '正式配置' : '1 至 ' + field.max + ' ' + field.unit)), base.dirty_fields.includes(field.key) ? /*#__PURE__*/React.createElement("small", {
      className: "sm-error"
    }, "\u65E7\u914D\u7F6E\u5F02\u5E38\uFF1A", base.dirty_reasons[field.key], base.stored_values[field.key] !== null ? ' · 原值：' + base.stored_values[field.key] : '') : base.defaulted_fields.includes(field.key) ? /*#__PURE__*/React.createElement("small", {
      className: "sm-meta"
    }, "\u9ED8\u8BA4\u503C\uFF0C\u5C1A\u672A\u4FDD\u5B58") : /*#__PURE__*/React.createElement("small", {
      className: "sm-meta"
    }, "\u5DF2\u5B58\u503C\uFF1A", field.switch ? base.values[field.key] === 'yes' ? '启用' : '关闭' : base.values[field.key]))))))), /*#__PURE__*/React.createElement("div", {
      className: "sm-form-footer"
    }, /*#__PURE__*/React.createElement("span", {
      className: "sm-meta"
    }, changed ? '有未保存修改' : base.dirty_fields.length || base.defaulted_fields.length ? '含异常或默认项，还需核对后保存' : '当前值已读取'), /*#__PURE__*/React.createElement("div", {
      className: "sm-actions"
    }, /*#__PURE__*/React.createElement(C.Button, {
      icon: "rotate-ccw",
      disabled: !!reason || !changed,
      onClick: () => setReplace(true)
    }, "\u653E\u5F03\u8349\u7A3F"), /*#__PURE__*/React.createElement(C.Button, {
      icon: "save",
      type: "submit",
      className: "btn primary",
      reason: reason
    }, "\u4FDD\u5B58\u7EF4\u62A4\u914D\u7F6E"))), validated && !validation.valid && /*#__PURE__*/React.createElement("p", {
      className: "sm-error",
      role: "alert"
    }, "\u6709\u51E0\u9879\u586B\u5F97\u4E0D\u5BF9\uFF0C\u914D\u7F6E\u6CA1\u6709\u4FDD\u5B58\u3002\u8BF7\u4FEE\u6B63\u6807\u7EA2\u7684\u9879\u3002")), /*#__PURE__*/React.createElement("details", {
      className: "sm-rules sm-config-help"
    }, /*#__PURE__*/React.createElement("summary", null, "\u751F\u6548\u8303\u56F4\u4E0E\u81EA\u52A8\u7EF4\u62A4\u89C4\u5219"), /*#__PURE__*/React.createElement("p", null, "\u6253\u5F00\u9875\u9762\u65F6\u7CFB\u7EDF\u624D\u4F1A\u68C0\u67E5\u4E00\u6B21\u81EA\u52A8\u7EF4\u62A4\uFF0C\u68C0\u67E5\u95F4\u9694\u4E0D\u4FDD\u8BC1\u5728\u6307\u5B9A\u65F6\u523B\u6267\u884C\u3002\u6E05\u7406\u64CD\u4F5C\u65E5\u5FD7\u4E0D\u4F1A\u6E05\u9664\u8FD0\u884C\u65E5\u5FD7\u6587\u4EF6\u3002"), /*#__PURE__*/React.createElement("p", null, "\u4E3B\u9898\u3001\u6BCF\u9875\u6761\u6570\u3001\u7D27\u51D1\u884C\u8DDD\u5C5E\u4E8E\u9875\u9762\u504F\u597D\uFF0C\u4E0D\u5199\u5165\u4E1A\u52A1\u914D\u7F6E\u3002"))), replace && /*#__PURE__*/React.createElement(window.ResourceControls.Modal, {
      title: "\u653E\u5F03\u5F53\u524D\u8349\u7A3F\u5E76\u5237\u65B0\uFF1F",
      icon: "history",
      onClose: () => setReplace(false),
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(C.Button, {
        onClick: () => setReplace(false)
      }, "\u4FDD\u7559\u8349\u7A3F"), /*#__PURE__*/React.createElement(C.Button, {
        icon: "refresh-cw",
        onClick: refreshNow
      }, "\u653E\u5F03\u5E76\u5237\u65B0"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b form"
    }, /*#__PURE__*/React.createElement("p", null, "\u672A\u4FDD\u5B58\u4FEE\u6539\u5C06\u88AB\u4E22\u5F03\uFF0C\u4E0D\u4F1A\u5199\u5165\u4E1A\u52A1\u914D\u7F6E\u3002"))));
  }
  window.SystemMaintenanceConfig = Config;
})();
