(function () {
  'use strict';

  const C = window.APSResourceContract,
    M = window.APSResourceCatalogModel;
  const {
    Button,
    Issues,
    Field: SharedField
  } = window.ResourceControls;
  const names = ['business_code', 'label', 'status', 'remark', 'anchor_date', 'cycle_days'];
  const fieldPaths = names.concat(names.map(name => 'fields.' + name));
  function Field({
    label,
    name,
    required,
    error,
    children,
    full
  }) {
    const errors = C.fieldErrors(error).map(row => ({
      ...row,
      path: row.path.replace(/^input\./, '').replace(/^fields\./, '')
    }));
    return /*#__PURE__*/React.createElement(SharedField, {
      label: label,
      path: name,
      required: required,
      errors: errors,
      full: full
    }, React.cloneElement(children, {
      name,
      'aria-label': label
    }));
  }
  function Pattern({
    value,
    onChange,
    disabled,
    error,
    onValidationError
  }) {
    const [trim, setTrim] = React.useState(null);
    function generate() {
      onValidationError(null);
      try {
        const length = M.cycle(value.cycle_days);
        if (length < value.pattern.length) {
          setTrim(length);
          return;
        }
        onChange('pattern', M.resized(value.pattern, length));
      } catch (failure) {
        onValidationError(failure);
      }
    }
    function rowChange(index, key, next) {
      const rows = value.pattern.map(row => ({
          ...row
        })),
        row = rows[index];
      row[key] = next;
      // Rest has no working interval; retain existing times, canonicalize only empty rest markers.
      if (key === 'is_rest' && next === true) {
        if (!row.shift_start) row.shift_start = '00:00';
        if (!row.shift_end) row.shift_end = '00:00';
      }
      onChange('pattern', rows);
    }
    return /*#__PURE__*/React.createElement("section", {
      className: "rc-pattern",
      "aria-label": "\u8F6E\u6362\u9010\u65E5\u89C4\u5219"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rc-section-head"
    }, /*#__PURE__*/React.createElement("h3", null, "\u9010\u65E5\u89C4\u5219"), /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, value.pattern.length, " \u5929"), /*#__PURE__*/React.createElement(Button, {
      icon: "calendar-days",
      disabled: disabled || trim !== null,
      onClick: generate
    }, value.pattern.length ? '调整逐日规则' : '生成逐日规则')), trim !== null && /*#__PURE__*/React.createElement("div", {
      role: "alert",
      className: "match-note rc-note"
    }, /*#__PURE__*/React.createElement("p", null, "\u5C06\u79FB\u9664\u7B2C ", trim + 1, " \u81F3\u7B2C ", value.pattern.length, " \u5929\uFF0C\u5171 ", value.pattern.length - trim, " \u5929\u3002\u5176\u4F59\u65E5\u671F\u4FDD\u6301\u539F\u503C\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "rowact"
    }, /*#__PURE__*/React.createElement(Button, {
      disabled: disabled,
      onClick: () => {
        onChange('cycle_days', String(value.pattern.length));
        setTrim(null);
      }
    }, "\u4FDD\u7559\u539F\u5468\u671F"), /*#__PURE__*/React.createElement(Button, {
      icon: "minus",
      disabled: disabled,
      onClick: () => {
        onChange('pattern', M.resized(value.pattern, trim));
        setTrim(null);
      }
    }, "\u786E\u8BA4\u79FB\u9664\u672B\u5C3E ", value.pattern.length - trim, " \u5929"))), !value.pattern.length ? /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "empty",
      title: "\u5C1A\u672A\u767B\u8BB0\u9010\u65E5\u89C4\u5219",
      hint: "\u586B\u5199\u8F6E\u6362\u5929\u6570\u540E\uFF0C\u751F\u6210\u5E76\u6838\u5BF9\u6BCF\u4E00\u5929\u7684\u5DE5\u4F5C\u5B89\u6392\u3002"
    }) : /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame rc-pattern-scroll",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table rc-pattern-table"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u73ED\u6B21\u6863\u9010\u65E5\u8F6E\u6362\u89C4\u5219"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-key"
    }, "\u8F6E\u6362\u65E5"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5DE5\u4F5C / \u4F11\u606F"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5F00\u59CB"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u7ED3\u675F"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u8DE8\u591C"))), /*#__PURE__*/React.createElement("tbody", null, value.pattern.map((row, index) => /*#__PURE__*/React.createElement("tr", {
      key: index
    }, /*#__PURE__*/React.createElement("td", {
      className: "wb-col-key"
    }, "\u7B2C ", index + 1, " \u5929"), /*#__PURE__*/React.createElement("td", {
      className: "field"
    }, /*#__PURE__*/React.createElement("select", {
      "aria-label": '第 ' + (index + 1) + ' 天工作安排',
      "aria-invalid": C.fieldErrors(error).some(item => item.path === 'pattern.' + index) || undefined,
      value: row.is_rest === null ? '' : row.is_rest ? 'rest' : 'work',
      disabled: disabled || trim !== null,
      onChange: event => rowChange(index, 'is_rest', event.target.value === 'rest')
    }, /*#__PURE__*/React.createElement("option", {
      value: "",
      disabled: true
    }, "\u8BF7\u9009\u62E9"), /*#__PURE__*/React.createElement("option", {
      value: "work"
    }, "\u5DE5\u4F5C"), /*#__PURE__*/React.createElement("option", {
      value: "rest"
    }, "\u4F11\u606F"))), ['shift_start', 'shift_end'].map((key, position) => /*#__PURE__*/React.createElement("td", {
      key: key
    }, /*#__PURE__*/React.createElement("div", {
      className: "field"
    }, /*#__PURE__*/React.createElement("input", {
      type: "time",
      step: "60",
      "aria-label": '第 ' + (index + 1) + ' 天' + (position ? '结束' : '开始'),
      value: row[key],
      disabled: disabled || trim !== null || row.is_rest === true,
      onChange: event => rowChange(index, key, event.target.value),
      "aria-invalid": C.fieldErrors(error).some(item => item.path === 'pattern.' + index) || undefined
    })))), /*#__PURE__*/React.createElement("td", {
      className: "muted"
    }, row.is_rest === true ? '休息' : row.shift_start && row.shift_end ? row.shift_end <= row.shift_start ? '次日结束' : '当日结束' : '未填写')))))));
  }
  function Facts({
    kind,
    entity
  }) {
    const count = M.memberCount(kind, entity);
    return /*#__PURE__*/React.createElement("section", {
      className: "rc-facts"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rc-section-head"
    }, /*#__PURE__*/React.createElement("b", null, entity.business_code, " \xB7 ", entity.label), /*#__PURE__*/React.createElement("span", null, entity.status === 'active' ? '启用' : entity.status === 'inactive' ? '停用' : '旧状态未知')), /*#__PURE__*/React.createElement("p", null, "\u5DF2\u5173\u8054", kind === 'machine_group' ? '设备' : '人员', "\uFF1A", count === null ? '未读取' : count), kind === 'shift_profile' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", null, "\u5468\u671F\u8D77\u59CB\u65E5\u671F\uFF1A", window.WorkbenchFormat.date(entity.fields.anchor_date), " \xB7 \u8F6E\u6362\u5929\u6570\uFF1A", entity.fields.cycle_days), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame rc-pattern-scroll",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u73ED\u6B21\u6863\u73B0\u6709\u9010\u65E5\u8F6E\u6362\u89C4\u5219"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-key"
    }, "\u8F6E\u6362\u65E5"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5DE5\u4F5C / \u4F11\u606F"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5F00\u59CB"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u7ED3\u675F"))), /*#__PURE__*/React.createElement("tbody", null, (entity.fields.pattern || []).map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.day_offset
    }, /*#__PURE__*/React.createElement("td", {
      className: "wb-col-key"
    }, "\u7B2C ", row.day_offset + 1, " \u5929"), /*#__PURE__*/React.createElement("td", null, row.is_rest ? '休息' : '工作'), /*#__PURE__*/React.createElement("td", null, row.shift_start), /*#__PURE__*/React.createElement("td", null, row.shift_end))))))), /*#__PURE__*/React.createElement("p", {
      className: "rc-wrap"
    }, "\u5907\u6CE8\uFF1A", entity.fields.remark || '未填写'), /*#__PURE__*/React.createElement(Issues, {
      issues: entity.issues
    }));
  }
  function Editor({
    kind,
    editor,
    disabled,
    error,
    onChange,
    onValidationError
  }) {
    const {
      draft: value,
      action,
      base
    } = editor;
    if (action === 'delete') return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", null, "\u786E\u8BA4\u5220\u9664\u8BE5", M.names[kind], "\uFF1F\u670D\u52A1\u7AEF\u5C06\u518D\u6B21\u6838\u5BF9\u5F15\u7528\uFF0C\u5DF2\u88AB\u4F7F\u7528\u7684\u76EE\u5F55\u4E0D\u80FD\u5220\u9664\u3002"), /*#__PURE__*/React.createElement(Facts, {
      kind: kind,
      entity: base
    }));
    const field = (name, label, options = {}) => /*#__PURE__*/React.createElement(Field, {
      name: name,
      label: label,
      required: options.required,
      error: error,
      full: options.full
    }, options.area ? /*#__PURE__*/React.createElement("textarea", {
      value: value[name],
      disabled: disabled,
      onChange: event => onChange(name, event.target.value)
    }) : /*#__PURE__*/React.createElement("input", {
      type: options.type || 'text',
      value: value[name],
      disabled: disabled,
      readOnly: options.readOnly,
      min: options.type === 'number' ? 1 : undefined,
      max: options.type === 'number' ? 366 : undefined,
      step: options.type === 'number' ? 1 : undefined,
      onChange: event => onChange(name, event.target.value)
    }));
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "fgrid"
    }, field('business_code', '编号', {
      required: action === 'create',
      readOnly: action !== 'create'
    }), field('label', '名称', {
      required: true
    }), /*#__PURE__*/React.createElement(Field, {
      name: "status",
      label: "\u72B6\u6001",
      required: true,
      error: error
    }, /*#__PURE__*/React.createElement("select", {
      value: value.status,
      disabled: disabled,
      onChange: event => onChange('status', event.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: "",
      disabled: true
    }, "\u8BF7\u9009\u62E9\u72B6\u6001"), /*#__PURE__*/React.createElement("option", {
      value: "active"
    }, "\u542F\u7528"), /*#__PURE__*/React.createElement("option", {
      value: "inactive"
    }, "\u505C\u7528"), value.status && !['active', 'inactive'].includes(value.status) && /*#__PURE__*/React.createElement("option", {
      value: value.status
    }, "\u65E7\u72B6\u6001\u672A\u77E5\uFF08\u4FDD\u6301\u539F\u503C\uFF09"))), kind === 'shift_profile' && /*#__PURE__*/React.createElement(React.Fragment, null, field('anchor_date', '周期起始日期', {
      required: true,
      type: 'date'
    }), field('cycle_days', '轮换天数', {
      required: true,
      type: 'number'
    })), field('remark', '备注', {
      area: true,
      full: true
    })), kind === 'shift_profile' && /*#__PURE__*/React.createElement(Pattern, {
      value: value,
      onChange: onChange,
      disabled: disabled,
      error: error,
      onValidationError: onValidationError
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: base && base.issues || []
    }));
  }
  Editor.Facts = Facts;
  Editor.fieldPaths = fieldPaths;
  window.ResourceCatalogEditor = Editor;
})();
