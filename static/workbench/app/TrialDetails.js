(function () {
  'use strict';

  const U = window.TrialControls,
    C = window.TrialContract;
  const hoursBasis = value => ({
    effective_processing_hours: '有效加工工时',
    calendar_days: '日历天',
    unknown: '工时依据不明'
  })[value] || '工时依据未识别';
  function References({
    task
  }) {
    return /*#__PURE__*/React.createElement("details", {
      className: "tt-refs"
    }, /*#__PURE__*/React.createElement("summary", null, "\u6C38\u4E45\u5F15\u7528\u4E0E\u539F\u59CB\u4F9D\u636E"), /*#__PURE__*/React.createElement("dl", null, [['任务', task.task_ref], ['行', task.row_ref], ['原任务', task.source_task_ref], ['原行', task.source_row_ref], ['工序', task.operation_ref], ['批次', task.batch_ref]].map(([label, ref]) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: label
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, ref || '无（候选来源无正式任务引用）')))), /*#__PURE__*/React.createElement("div", null, "\u524D\u5E8F\u5DE5\u5E8F\u5F15\u7528\uFF1A", task.predecessor_operation_refs.join('、') || '无'), /*#__PURE__*/React.createElement("div", null, "\u539F\u5DE5\u65F6\u4F9D\u636E\uFF1A", /*#__PURE__*/React.createElement("code", null, task.hours.basis || '未记录')));
  }
  function Execution({
    title,
    value
  }) {
    if (!value) return /*#__PURE__*/React.createElement("div", null, title, "\uFF1A\u672A\u8BB0\u5F55");
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h4", null, title), /*#__PURE__*/React.createElement("dl", {
      className: "tt-facts"
    }, [['目标量', value.target_quantity], ['已知完成量', value.known_completed_quantity], ['剩余量', value.remaining_quantity], ['执行状态', value.execution_state], ['数据质量', value.data_quality], ['目标依据', value.target_basis]].map(([label, v]) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: label
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, U.number(v))))));
  }
  function Editor({
    data,
    task,
    commands,
    onEditing,
    onRecheck
  }) {
    const [editing, setEditing] = React.useState(false),
      [form, setForm] = React.useState(null),
      [error, setError] = React.useState(null),
      [reviewed, setReviewed] = React.useState(false);
    const external = task.source === 'external';
    function close() {
      setEditing(false);
      onEditing(false);
      setError(null);
    }
    function open() {
      setForm({
        machine_ref: external ? null : task.machine_ref,
        operator_ref: external ? null : task.operator_ref,
        start: task.start
      });
      setEditing(true);
      onEditing(true);
      setReviewed(true);
    }
    React.useEffect(() => {
      if (editing) setReviewed(false);
    }, [data]);
    React.useEffect(() => () => onEditing(false), []);
    const editable = data.status === 'editing' && task.edit_context.can_change && data.write_context.capabilities['trial.change'] === true;
    async function submit(e) {
      e.preventDefault();
      setError(null);
      const value = {
        ...form,
        start: form.start.length === 16 ? form.start + ':00' : form.start
      };
      try {
        C.check(C.time(value.start), '开工时间必须是有效的工厂本地时间。');
        C.check(external ? value.machine_ref === null && value.operator_ref === null : C.ref(value.machine_ref) && C.ref(value.operator_ref), '必须明确选择设备与人员。');
        const ok = await commands.execute({
          action: 'change',
          draft_ref: data.draft_ref,
          input: {
            task_ref: task.task_ref,
            ...value
          }
        }, data.write_context.write_token);
        if (ok) close();else setReviewed(false);
      } catch (error) {
        setError(error);
      }
    }
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(U.Issues, {
      rows: task.edit_context.blocked_reasons
    }), !editing ? /*#__PURE__*/React.createElement(U.Button, {
      icon: "square-pen",
      disabled: !editable || commands.blocked,
      onClick: open
    }, "\u8C03\u6574\u6B64\u5DE5\u5E8F") : /*#__PURE__*/React.createElement("form", {
      onSubmit: submit,
      className: "tt-editor"
    }, /*#__PURE__*/React.createElement("h4", null, "\u8C03\u6574\u5DE5\u5E8F"), ['machine', 'operator'].map((kind, i) => /*#__PURE__*/React.createElement("label", {
      key: kind
    }, i ? '调整人员' : '调整设备', /*#__PURE__*/React.createElement("select", {
      "aria-label": i ? '调整人员' : '调整设备',
      value: form[kind + '_ref'] || '',
      disabled: commands.busy || external,
      required: !external,
      onChange: e => setForm({
        ...form,
        [kind + '_ref']: e.target.value || null
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, external ? '外协，无内部资源' : '请选择'), form[kind + '_ref'] && !data.resources[kind + 's'].some(r => r.ref === form[kind + '_ref']) && /*#__PURE__*/React.createElement("option", {
      value: form[kind + '_ref']
    }, "\u539F\u8D44\u6E90\uFF08\u5DF2\u4E0D\u53EF\u8BFB\uFF09"), data.resources[kind + 's'].map(r => /*#__PURE__*/React.createElement("option", {
      key: r.ref,
      value: r.ref,
      disabled: r.status !== 'active'
    }, r.business_code, " \xB7 ", r.label || '名称未记录', r.status !== 'active' ? '（不可用）' : ''))))), /*#__PURE__*/React.createElement("label", null, "\u8C03\u6574\u5F00\u5DE5", /*#__PURE__*/React.createElement("input", {
      type: "datetime-local",
      step: "1",
      "aria-label": "\u8C03\u6574\u5F00\u5DE5",
      required: true,
      value: form.start,
      disabled: commands.busy,
      onChange: e => setForm({
        ...form,
        start: e.target.value
      })
    })), /*#__PURE__*/React.createElement("div", {
      className: "tt-muted"
    }, "\u539F\u5DE5\u65F6\u4E0D\u53D8\uFF1B\u5B8C\u5DE5\u7531\u771F\u5B9E\u65E5\u5386\u8BA1\u7B97\uFF0C\u524D\u540E\u5E8F\u4E0D\u81EA\u52A8\u79FB\u52A8\u3002"), !external && !data.resources.authorizations.some(r => r.machine_ref === form.machine_ref && r.operator_ref === form.operator_ref) && /*#__PURE__*/React.createElement("p", {
      className: "tt-notice"
    }, "\u5F53\u524D\u8BBE\u5907\u4E0E\u4EBA\u5458\u672A\u767B\u8BB0\u64CD\u4F5C\u6388\u6743\uFF0C\u63D0\u4EA4\u540E\u4EE5\u771F\u5B9E\u7EA6\u675F\u68C0\u67E5\u4E3A\u51C6\u3002"), /*#__PURE__*/React.createElement(U.ErrorBox, {
      error: error
    }), /*#__PURE__*/React.createElement(U.ErrorBox, {
      error: commands.error
    }), /*#__PURE__*/React.createElement("label", {
      className: "tt-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: reviewed,
      onChange: e => setReviewed(e.target.checked)
    }), "\u5DF2\u6838\u5BF9\u5F53\u524D\u5DE5\u5E8F\u4E0E\u4FDD\u7559\u8F93\u5165"), /*#__PURE__*/React.createElement("div", {
      className: "tt-tools"
    }, /*#__PURE__*/React.createElement(U.Button, {
      icon: "check",
      type: "submit",
      disabled: !editable || !reviewed || commands.blocked
    }, "\u4FDD\u5B58\u8C03\u6574"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "x",
      disabled: commands.busy,
      onClick: close
    }, "\u53D6\u6D88\u7F16\u8F91"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "refresh-cw",
      disabled: commands.busy || !!commands.key,
      onClick: onRecheck
    }, "\u91CD\u8BFB\u5DE5\u5E8F"))));
  }
  function Detail({
    data,
    selected,
    commands,
    onSelect,
    onEditing,
    onRecheck
  }) {
    const task = data.tasks.find(t => t.task_ref === selected),
      name = window.TrialGantt.resourceNames(data);
    if (!task) return /*#__PURE__*/React.createElement("aside", {
      className: "tt-detail"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5DE5\u5E8F\u8BE6\u60C5"), /*#__PURE__*/React.createElement("div", {
      className: "tt-empty"
    }, "\u5C1A\u672A\u9009\u62E9\u5DE5\u5E8F"));
    return /*#__PURE__*/React.createElement("aside", {
      className: "tt-detail",
      "aria-label": "\u5DE5\u5E8F\u8BE6\u60C5"
    }, /*#__PURE__*/React.createElement("div", {
      className: "tt-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5DE5\u5E8F\u8BE6\u60C5"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "x",
      "aria-label": "\u5173\u95ED\u5DE5\u5E8F\u8BE6\u60C5",
      onClick: () => onSelect(null)
    })), /*#__PURE__*/React.createElement("h4", null, task.batch_id, " \xB7 ", task.process_label), /*#__PURE__*/React.createElement("p", null, task.part_no, " \xB7 ", task.part_name || '零件名称未记录'), /*#__PURE__*/React.createElement(Editor, {
      key: task.task_ref,
      data,
      task,
      commands,
      onEditing,
      onRecheck
    }), /*#__PURE__*/React.createElement("dl", {
      className: "tt-facts"
    }, [['分件', task.piece_id || '整批'], ['原目标量', U.number(task.quantity)], ['批次数量', U.number(task.batch_quantity)], ...(window.PointContract.isPoint(task) ? [['安排类型', '时间点'], ['本工序占用', '0 h · 不占用资源']] : []), ['优先级', {
      normal: '普通',
      urgent: '急件',
      critical: '特急'
    }[task.priority] || '未知'], ['交付截至日', task.due_date || '未记录'], ['来源', task.source === 'internal' ? '自制' : '外协'], ['当前设备', name(task.machine_ref)], ['当前人员', name(task.operator_ref)], ['当前开工', U.timeLabel(task.start)], ['当前完工', U.timeLabel(task.end)], ['原设备', name(task.original.machine_ref)], ['原人员', name(task.original.operator_ref)], ['原开工', U.timeLabel(task.original.start)], ['原完工', U.timeLabel(task.original.end)], ['原准备工时', U.number(task.hours.setup_hours)], ['原单件工时', U.number(task.hours.unit_hours)], ['原总工时', U.number(task.hours.total_hours)], ['工时依据', hoursBasis(task.hours.basis)], ...(task.source === 'external' ? [['原周期（天）', U.number(task.hours.days)]] : [])].map(([label, value]) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: label
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, value)))), /*#__PURE__*/React.createElement("div", {
      className: "tt-tools"
    }, task.predecessor_refs.map(ref => {
      const t = data.tasks.find(t => t.task_ref === ref);
      const piece = typeof t.piece_id === 'string' && t.piece_id.trim() ? '分件 ' + t.piece_id : t.piece_id === null && !t.data_gaps.some(g => g.field === 'piece_id') ? '共同工序' : '分件未记录';
      const label = '前序 ' + piece + ' · ' + t.process_label + ' ' + t.sequence;
      return /*#__PURE__*/React.createElement(U.Button, {
        key: ref,
        icon: "chevron-left",
        title: label,
        "aria-label": label,
        onClick: () => onSelect(ref),
        style: {
          minWidth: 0,
          maxWidth: '100%',
          height: 'auto',
          whiteSpace: 'normal',
          textAlign: 'left'
        }
      }, /*#__PURE__*/React.createElement("span", {
        style: {
          minWidth: 0,
          overflowWrap: 'anywhere',
          wordBreak: 'break-word'
        }
      }, label));
    })), /*#__PURE__*/React.createElement("section", null, /*#__PURE__*/React.createElement("h4", null, "\u5DE5\u5E8F\u7EA6\u675F"), !task.issues.length && /*#__PURE__*/React.createElement("p", {
      className: "tt-muted"
    }, "\u6B64\u5DE5\u5E8F\u672A\u62A5\u544A\u5355\u9879\u95EE\u9898\uFF0C\u4ECD\u987B\u6838\u5BF9\u6574\u4F53\u7EA6\u675F\u3002"), /*#__PURE__*/React.createElement(U.Issues, {
      rows: task.issues,
      onSelect: onSelect
    }), /*#__PURE__*/React.createElement(U.Issues, {
      rows: task.data_gaps
    })), /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u6267\u884C\u4F9D\u636E"), /*#__PURE__*/React.createElement(Execution, {
      title: "\u521B\u5EFA\u65F6\u6267\u884C\u6295\u5F71",
      value: task.execution_at_creation
    }), /*#__PURE__*/React.createElement(Execution, {
      title: "\u672C\u6B21\u8BFB\u53D6\u6267\u884C\u6295\u5F71",
      value: task.execution
    })), /*#__PURE__*/React.createElement(References, {
      task: task
    }));
  }
  window.TrialDetails = Detail;
})();
