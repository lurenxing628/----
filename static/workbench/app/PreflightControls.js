(function () {
  'use strict';

  const {
    Button,
    ErrorBox
  } = window.ResourceControls;
  function Segment({
    label,
    value,
    choices,
    onChange,
    disabled
  }) {
    const id = React.useId();
    return /*#__PURE__*/React.createElement("div", {
      className: "pf-segment",
      role: "radiogroup",
      "aria-label": label
    }, choices.map(([key, text, unavailable]) => /*#__PURE__*/React.createElement("label", {
      key: String(key),
      className: value === key ? 'selected' : ''
    }, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: id,
      checked: value === key,
      disabled: disabled || unavailable,
      onChange: () => onChange(key)
    }), /*#__PURE__*/React.createElement("span", null, text))));
  }
  // 不重排时段：没动过时不带这一项（按交付设置），检查后用本次生效的时段填显示值；改任一端就按本次单独填的发送，点「不设」发送 null。
  function HoldWindow({
    value,
    effective,
    onChange,
    disabled
  }) {
    const C = window.PreflightContract,
      explicit = value.hold_window !== undefined;
    const shown = explicit ? value.hold_window : effective ? effective.hold_window : null,
      bounds = C.holdBounds(value.start_date, value.end_date) || {};
    let problem = '';
    if (explicit) {
      try {
        C.holdWindow(value.hold_window, value.start_date, value.end_date);
      } catch (error) {
        problem = error.message;
      }
    }
    const status = explicit ? value.hold_window === null ? '本次不设' : '本次单独填写' : effective ? effective.hold_window ? '（按交付设置）' : '（按交付设置：不设）' : '未填时按交付设置，检查后显示本次生效的时段';
    function edit(key, text) {
      // 按交付设置推算的时段可能超出这次的排产日期：只改一端时，带过来的另一端先截到日期范围内，免得没动过的一端报错。
      const base = {
        ...(shown || {
          start: '',
          end: ''
        })
      };
      if (!explicit && shown && bounds.min && base.start < bounds.min) base.start = bounds.min;
      if (!explicit && shown && bounds.max && base.end > bounds.max) base.end = bounds.max;
      onChange({
        hold_window: {
          ...base,
          [key]: text
        }
      });
    }
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "pf-rule pf-hold",
      role: "group",
      "aria-label": "\u4E0D\u91CD\u6392\u65F6\u6BB5"
    }, /*#__PURE__*/React.createElement("div", {
      className: "pf-hold-head"
    }, /*#__PURE__*/React.createElement("strong", null, "\u4E0D\u91CD\u6392\u65F6\u6BB5"), /*#__PURE__*/React.createElement("span", {
      className: "pf-muted",
      "data-hold-source": explicit ? 'explicit' : effective ? 'default' : 'unchecked'
    }, status)), /*#__PURE__*/React.createElement("div", {
      className: "pf-hold-fields"
    }, [['start', '开始'], ['end', '结束']].map(([key, label]) => /*#__PURE__*/React.createElement("label", {
      key: key
    }, label, /*#__PURE__*/React.createElement("input", {
      type: "datetime-local",
      "aria-label": '不重排时段' + label,
      min: bounds.min,
      max: bounds.max,
      value: shown ? shown[key] : '',
      disabled: disabled,
      "aria-invalid": !!problem || undefined,
      onChange: event => edit(key, event.target.value)
    }))), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      disabled: disabled || explicit && value.hold_window === null,
      onClick: () => onChange({
        hold_window: null
      })
    }, "\u4E0D\u8BBE"), explicit && /*#__PURE__*/React.createElement(Button, {
      icon: "rotate-ccw",
      disabled: disabled,
      onClick: () => onChange({
        hold_window: undefined
      })
    }, "\u6309\u4EA4\u4ED8\u8BBE\u7F6E"))), /*#__PURE__*/React.createElement("div", {
      className: "pf-rule pf-note"
    }, "\u7518\u7279\u56FE\u4E0A\u843D\u5728\u8FD9\u6BB5\u65F6\u95F4\u91CC\u7684\u5DE5\u5E8F\u4FDD\u6301\u539F\u5B89\u6392\u4E0D\u52A8\uFF0C\u540C\u6279\u6B21\u6392\u5728\u524D\u9762\u7684\u5DE5\u5E8F\u4E5F\u4E00\u8D77\u4E0D\u52A8\uFF1B\u5176\u4F59\u7167\u5E38\u91CD\u6392\u3002"), problem && /*#__PURE__*/React.createElement("div", {
      className: "pf-rule pf-note pf-hold-error",
      role: "alert"
    }, problem));
  }
  const minuteText = value => window.WorkbenchFormat.dateTime(value);
  function HeldRows({
    rows,
    label
  }) {
    const [page, setPage] = React.useState(1),
      pages = Math.max(1, Math.ceil(rows.length / 100));
    return /*#__PURE__*/React.createElement("div", {
      className: "pf-held-group"
    }, /*#__PURE__*/React.createElement("strong", null, label, " \xB7 ", rows.length, " \u9053"), /*#__PURE__*/React.createElement("ul", null, rows.slice((page - 1) * 100, page * 100).map(row => /*#__PURE__*/React.createElement("li", {
      key: row.operation_ref,
      "data-held-basis": row.held.basis
    }, row.batch_id, " \xB7 ", row.sequence, " ", row.label, row.piece_id ? ' · ' + row.piece_id : '', " \xB7 \u539F\u5B89\u6392 ", minuteText(row.held.start), " \u81F3 ", minuteText(row.held.end)))), pages > 1 && /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: page,
      pages: pages,
      total: rows.length,
      size: 100,
      unit: "\u9053",
      label: label,
      onPage: setPage
    }));
  }
  // 检查结果里的“本次不重排”一行；明细列出因不重排时段保持原安排的工序，正式计划里锁定的另列。
  function HoldSummary({
    data
  }) {
    const span = data.effective_config.hold_window,
      kept = data.tasks.filter(row => row.held && row.held.basis === 'hold_window'),
      locked = data.tasks.filter(row => row.held && row.held.basis === 'locked');
    const text = span ? '本次不重排：' + window.WorkbenchTerms.hold_window(span) + '，共 ' + data.counts.hold_window_tasks + ' 道工序保持原安排' : '本次不设不重排时段';
    const source = data.effective_config.hold_window_source === 'default' ? '（按交付设置）' : '';
    if (!kept.length && !locked.length) return /*#__PURE__*/React.createElement("p", {
      className: "pf-hold-summary",
      "data-hold-summary": true,
      role: "status"
    }, text, source);
    return /*#__PURE__*/React.createElement("details", {
      className: "pf-detail pf-hold-summary",
      "data-hold-summary": true
    }, /*#__PURE__*/React.createElement("summary", null, text, source, locked.length ? '；正式计划里已锁定 ' + locked.length + ' 道' : '', " \xB7 \u67E5\u770B\u660E\u7EC6"), !!kept.length && /*#__PURE__*/React.createElement(HeldRows, {
      key: "kept",
      rows: kept,
      label: "\u4E0D\u91CD\u6392\u65F6\u6BB5\u5185\u4FDD\u6301\u539F\u5B89\u6392"
    }), !!locked.length && /*#__PURE__*/React.createElement(HeldRows, {
      key: "locked",
      rows: locked,
      label: "\u6B63\u5F0F\u8BA1\u5212\u91CC\u5DF2\u9501\u5B9A"
    }));
  }
  function Rules({
    value,
    effective,
    onChange,
    disabled
  }) {
    return /*#__PURE__*/React.createElement("section", {
      "aria-labelledby": "pf-rules-title"
    }, /*#__PURE__*/React.createElement("h3", {
      id: "pf-rules-title"
    }, "\u672C\u6B21\u6392\u4EA7\u89C4\u5219"), /*#__PURE__*/React.createElement("div", {
      className: "pf-rows"
    }, /*#__PURE__*/React.createElement("div", {
      className: "pf-rule"
    }, /*#__PURE__*/React.createElement("strong", null, "\u9F50\u5957\u68C0\u67E5"), /*#__PURE__*/React.createElement(Segment, {
      label: "\u9F50\u5957\u68C0\u67E5",
      value: value.ready_check,
      choices: [[true, '开启'], [false, '关闭']],
      disabled: disabled,
      onChange: ready_check => onChange({
        ready_check,
        ...(ready_check ? {} : {
          material_strategy: 'strict'
        })
      })
    })), /*#__PURE__*/React.createElement("div", {
      className: "pf-rule"
    }, /*#__PURE__*/React.createElement("strong", null, "\u7269\u6599\u653E\u884C\u65B9\u5F0F"), /*#__PURE__*/React.createElement(Segment, {
      label: "\u7269\u6599\u653E\u884C\u65B9\u5F0F",
      value: value.material_strategy || 'strict',
      choices: Object.entries(window.WorkbenchTerms.material_strategies),
      disabled: disabled,
      onChange: material_strategy => onChange({
        material_strategy,
        ready_check: true
      })
    })), /*#__PURE__*/React.createElement("div", {
      className: "pf-rule pf-note"
    }, "\u6309\u5DE5\u5E8F\u9F50\u5957\uFF1A\u53EA\u7B49\u5F85\u672C\u5E8F\u53CA\u524D\u5E8F\u9700\u8981\u7684\u7269\u6599\u3002\u5206\u6279\u5F00\u5DE5\uFF1A\u5148\u9884\u68C0\u53EF\u505A\u6570\u91CF\uFF0C\u786E\u8BA4\u4FDD\u5B58\u62C6\u5206\u540E\u518D\u6392\u4EA7\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "pf-rule"
    }, /*#__PURE__*/React.createElement("strong", null, "\u7F3A\u8D44\u6E90\u5DE5\u5E8F"), /*#__PURE__*/React.createElement(Segment, {
      label: "\u7F3A\u8D44\u6E90\u5DE5\u5E8F",
      value: value.missing_resource_policy,
      choices: [["auto_assign", '自动分配'], ['exclude', '暂不排']],
      disabled: disabled,
      onChange: missing_resource_policy => onChange({
        missing_resource_policy
      })
    })), /*#__PURE__*/React.createElement(HoldWindow, {
      value: value,
      effective: effective,
      onChange: onChange,
      disabled: disabled
    }), /*#__PURE__*/React.createElement("div", {
      className: "pf-rule"
    }, /*#__PURE__*/React.createElement("span", {
      className: "pf-fixed"
    }, "\u5DF2\u5F00\u5DE5\u5DE5\u5E8F\uFF1A\u4FDD\u7559\u8BB0\u5F55\uFF08\u4E0D\u53EF\u4FEE\u6539\uFF09")), /*#__PURE__*/React.createElement("div", {
      className: "pf-rule pf-note"
    }, "\u89C4\u5219\u4EC5\u7528\u4E8E\u672C\u6B21\u6392\u4EA7\u3002")));
  }
  function Metrics({
    counts
  }) {
    const items = [['selected_tasks', '范围内工序'], ['ready_tasks', '资料有效'], ['auto_assign_required', '自动分配待补'], ['skipped_tasks', '本次跳过'], ['blocked_tasks', '缺资料工序'], ['no_route_batches', '未生成工艺批次'], ['actual_fact_tasks', '已开工工序']];
    return /*#__PURE__*/React.createElement("dl", {
      className: "pf-metrics"
    }, items.map(([key, label]) => /*#__PURE__*/React.createElement("div", {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, counts ? counts[key] : '未检查'))));
  }
  function Reasons({
    data
  }) {
    const groups = new Map(),
      tasks = new Map(data.tasks.map(row => [row.operation_ref, row]));
    const batches = new Map(data.included_batches.concat(data.excluded_batches).map(row => [row.batch_ref, row.batch_id]));
    data.run_blocked_reasons.concat(data.warnings).forEach(item => {
      if (!groups.has(item.code)) groups.set(item.code, []);
      groups.get(item.code).push(item);
    });
    function summary(code, items) {
      const operations = new Set(items.map(item => item.operation_ref).filter(Boolean)).size;
      const messages = Array.from(new Set(items.map(item => item.message))).join('；');
      if (operations && code === 'operation_blocked') return operations + ' 道工序缺必填资料';
      if (operations && code === 'execution_review_required') return operations + ' 道工序已有执行记录待核对';
      if (code === 'route_not_generated') return new Set(items.map(item => item.batch_ref).filter(Boolean)).size + ' 批尚未生成工艺';
      return (operations ? operations + ' 道工序：' : '') + messages;
    }
    function objectLabel(item) {
      const task = tasks.get(item.operation_ref);
      if (task) return task.batch_id + ' · ' + task.sequence + ' ' + task.label + (task.piece_id ? ' · ' + task.piece_id : '');
      return item.batch_id || batches.get(item.batch_ref) || '批次与工序未读取';
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "pf-alert"
    }, /*#__PURE__*/React.createElement("div", {
      role: "status"
    }, Array.from(groups, ([code, items]) => /*#__PURE__*/React.createElement("div", {
      key: code,
      "data-reason-group": code
    }, summary(code, items)))), /*#__PURE__*/React.createElement("details", {
      className: "pf-reasons"
    }, /*#__PURE__*/React.createElement("summary", null, "\u539F\u56E0\u660E\u7EC6 \xB7 ", data.run_blocked_reasons.length + data.warnings.length, " \u9879"), /*#__PURE__*/React.createElement("div", {
      className: "pf-reason-list"
    }, Array.from(groups, ([code, items]) => /*#__PURE__*/React.createElement("div", {
      key: code
    }, items.map((item, index) => /*#__PURE__*/React.createElement("div", {
      className: "pf-reason-item",
      key: index,
      "data-reason-code": item.code,
      "data-operation-ref": item.operation_ref,
      "data-batch-ref": item.batch_ref
    }, objectLabel(item) && /*#__PURE__*/React.createElement("strong", null, objectLabel(item), "\uFF1A "), item.message, /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '原因编号': item.code,
        '工序编号': item.operation_ref,
        '批次编号': item.batch_ref
      }
    }))))))));
  }
  window.PreflightControls = {
    Button,
    ErrorBox,
    Rules,
    Metrics,
    Reasons,
    HoldSummary
  };
})();
