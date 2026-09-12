(function () {
  'use strict';

  const C = window.FieldContract,
    {
      Button,
      ErrorBox,
      Issues,
      State
    } = window.FieldControls;
  function Timeline({
    task
  }) {
    const [selected, setSelected] = React.useState(null),
      [tip, setTip] = React.useState(null);
    const parse = value => value ? Date.parse(value.replace(' ', 'T') + 'Z') : null;
    const plan = {
      ...task,
      start: task.planned_start,
      end: task.planned_end
    };
    const rows = [{
      key: 'plan',
      label: '计划安排',
      start: plan.start,
      end: plan.end,
      point: window.PointContract.isPoint(plan)
    }, ...task.execution.reports.map(row => ({
      key: row.report_ref,
      label: row.report_no,
      start: row.actual_start,
      end: row.actual_end,
      point: !!row.actual_start && (!row.actual_end || row.actual_start === row.actual_end)
    }))];
    const points = rows.flatMap(row => [parse(row.start), parse(row.end)]).filter(Number.isFinite);
    const axis = window.PointGanttModel.bounds(Math.min(...points), Math.max(...points), rows.some(row => row.point));
    function hover(title, event) {
      if (!event) {
        setTip(null);
        return;
      }
      const rect = event.currentTarget.getBoundingClientRect();
      setTip({
        title,
        x: rect.left,
        y: rect.bottom
      });
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "field-timeline",
      "aria-label": "\u4F5C\u4E1A\u65F6\u95F4\u7EBF"
    }, /*#__PURE__*/React.createElement(window.PointGantt.Styles, null), /*#__PURE__*/React.createElement("div", {
      className: "field-timeline-axis"
    }, /*#__PURE__*/React.createElement("span", null, C.date(new Date(Math.min(...points)).toISOString().slice(0, 19))), /*#__PURE__*/React.createElement("span", null, C.date(new Date(Math.max(...points)).toISOString().slice(0, 19)))), rows.map(row => {
      const title = (row.key === 'plan' ? row.point ? '计划点 · 0 秒 · 不占用排产资源；完成状态以实际记录为准' : '计划安排' : row.point ? '报工时点' : '实际报工时段') + '\n' + row.label + '\n' + C.date(row.start) + ' 至 ' + (row.end ? C.date(row.end) : '结束未填写');
      const left = (parse(row.start) - axis.start) / (axis.end - axis.start) * 100 + '%';
      return /*#__PURE__*/React.createElement("div", {
        key: row.key,
        className: "field-timeline-row"
      }, /*#__PURE__*/React.createElement("span", null, row.label), /*#__PURE__*/React.createElement("div", {
        className: "field-timeline-track",
        title: title
      }, !row.start ? /*#__PURE__*/React.createElement("span", null, "\u5B9E\u9645\u5F00\u5DE5\u5F85\u8865") : row.point ? /*#__PURE__*/React.createElement(window.PointGantt.Marker, {
        task: row.key === 'plan' ? plan : {
          task_ref: row.key,
          start: row.start
        },
        x: left,
        top: 0,
        title: title,
        tone: row.key === 'plan' ? 'plan' : '',
        selected: selected === row.key,
        "data-field-point": row.key === 'plan' ? 'plan' : 'report',
        "data-task-ref": task.task_ref,
        "data-report-ref": row.key === 'plan' ? undefined : row.key,
        onSelect: () => setSelected(row.key),
        onHover: event => hover(title, event),
        onFocus: event => hover(title, event),
        onBlur: () => setTip(null)
      }) : /*#__PURE__*/React.createElement("i", {
        className: row.key === 'plan' ? 'planned' : 'actual',
        style: {
          left,
          width: (parse(row.end) - parse(row.start)) / (axis.end - axis.start) * 100 + '%'
        }
      })), /*#__PURE__*/React.createElement("span", null, row.end ? '' : '结束待补'));
    }), tip && /*#__PURE__*/React.createElement("div", {
      className: "field-point-tip",
      role: "tooltip",
      style: {
        left: Math.max(8, Math.min(tip.x, window.innerWidth - 336)),
        top: Math.max(8, Math.min(tip.y + 8, window.innerHeight - 170))
      }
    }, tip.title));
  }
  function History({
    record
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "field-history"
    }, /*#__PURE__*/React.createElement("dl", null, /*#__PURE__*/React.createElement("dt", null, "\u5F55\u5165\u65F6\u95F4"), /*#__PURE__*/React.createElement("dd", null, C.date(record.recorded_at)), /*#__PURE__*/React.createElement("dt", null, "\u672C\u673A\u64CD\u4F5C\u8005"), /*#__PURE__*/React.createElement("dd", null, C.display(record.local_operator)), /*#__PURE__*/React.createElement("dt", null, "\u73B0\u573A\u58F0\u660E\u4EBA"), /*#__PURE__*/React.createElement("dd", null, C.display(record.declared_operator)), /*#__PURE__*/React.createElement("dt", null, "\u5F55\u5165\u6765\u6E90"), /*#__PURE__*/React.createElement("dd", null, record.source === 'excel' ? 'Excel' : '手工')), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '报工编号': record.report_ref,
        '报工版本编号': record.revision_ref
      }
    }), record.correction_history.map((item, index) => /*#__PURE__*/React.createElement("div", {
      key: index
    }, /*#__PURE__*/React.createElement("strong", null, item.action === 'supplement' ? '补齐' : item.action === 'create' ? '新增' : '更正'), " ", C.date(item.recorded_at), " \xB7 ", item.reason, item.before && item.after && /*#__PURE__*/React.createElement("dl", null, C.fields.filter(key => item.before[key] !== item.after[key]).map(key => /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, {
      completed_quantity: '数量',
      effective_processing_hours: '有效工时',
      actual_start: '实际开工',
      actual_end: '本次完工',
      actual_machine_ref: '实际设备',
      actual_operator_ref: '实际人员',
      remark: '备注'
    }[key]), /*#__PURE__*/React.createElement("dd", null, key.endsWith('_ref') ? '资源已更正' : C.display(item.before[key]) + ' → ' + C.display(item.after[key]))))))));
  }
  function FieldDetail({
    adapter,
    taskRef,
    scope,
    snapshot,
    revision,
    command,
    editor,
    retained,
    onDraft,
    onEdit,
    onCloseEditor,
    onDone,
    onNavigate,
    nextDraft,
    onContinueReady
  }) {
    const [historyRef, setHistoryRef] = React.useState(null);
    const [timeline, setTimeline] = React.useState(false);
    const detail = React.useRef(null);
    const request = window.APSResourceSession.useQuery(async signal => C.query(await adapter.detail(taskRef, {
      ...scope,
      snapshot_ref: snapshot
    }, signal), 'detail', taskRef), [adapter, taskRef, scope, snapshot, revision]);
    const task = request.result && request.result.data.task,
      p = task && task.execution;
    React.useEffect(() => {
      if (nextDraft && task && !request.loading && !request.error) onContinueReady(task);
    }, [nextDraft, task, request.loading, request.error, onContinueReady]);
    React.useEffect(() => {
      if (task && detail.current && !editor && !nextDraft) detail.current.scrollIntoView({
        block: 'start',
        inline: 'nearest'
      });
    }, [task, editor, nextDraft]);
    if (request.loading) return /*#__PURE__*/React.createElement("div", {
      className: "field-note",
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u9010\u6B21\u62A5\u5DE5\u2026");
    if (!task) return /*#__PURE__*/React.createElement("div", {
      className: "field-error"
    }, /*#__PURE__*/React.createElement(ErrorBox, {
      error: request.error
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: request.reload,
      disabled: command.locked
    }, "\u91CD\u8BFB\u8BE6\u60C5"), editor && /*#__PURE__*/React.createElement(Button, {
      onClick: onCloseEditor,
      disabled: command.locked
    }, "\u53D6\u6D88\u6682\u5B58\u7F16\u8F91"));
    const report = editor && p.reports.find(row => row.report_ref === editor.reportRef);
    const legacy = editor && p.legacy_facts.find(row => row.legacy_fact_ref === editor.legacyRef);
    const missingOriginal = editor && (editor.reportRef && !report || editor.legacyRef && !legacy);
    return /*#__PURE__*/React.createElement("section", {
      ref: detail,
      className: "field-detail",
      "aria-label": '逐次报工 ' + task.batch_id
    }, /*#__PURE__*/React.createElement("div", {
      className: "field-detail-heading"
    }, /*#__PURE__*/React.createElement("h3", {
      style: {
        maxWidth: '100%',
        overflowWrap: 'anywhere'
      }
    }, task.batch_id, " \xB7 ", task.operation_label, " \xB7 ", C.pieceLabel(task)), /*#__PURE__*/React.createElement(State, {
      value: p.execution_state
    }), /*#__PURE__*/React.createElement("span", {
      className: "field-note"
    }, "\u8BA1\u5212\u5E94\u505A ", C.quantity(task.quantity), " \u4EF6 \xB7 \u6279\u6B21 ", C.quantity(task.batch_quantity), " \u4EF6", task.quantity_reason ? ' · ' + C.quantityReasons[task.quantity_reason] : ''), /*#__PURE__*/React.createElement(Button, {
      icon: "clock-3",
      "aria-expanded": timeline,
      onClick: () => setTimeline(value => !value)
    }, "\u4F5C\u4E1A\u65F6\u95F4\u7EBF"), /*#__PURE__*/React.createElement(Button, {
      icon: "plus",
      disabled: command.locked || !!editor || !!nextDraft,
      reason: p.execution_state === 'complete' ? '工序已完工，请补齐原记录或明确更正。' : C.blocked(p.write_context, 'create'),
      onClick: () => onEdit({
        taskRef,
        action: 'create'
      })
    }, "\u65B0\u589E\u672C\u6B21\u62A5\u5DE5"), onNavigate && /*#__PURE__*/React.createElement(Button, {
      icon: "chart-gantt",
      disabled: command.locked || !!editor,
      onClick: () => {
        const common = {
          ...scope
        };
        delete common.state;
        onNavigate('fieldgantt', {
          plan_ref: task.plan_ref,
          task_ref: taskRef,
          operation_ref: task.operation_ref,
          scope: common,
          return_to: {
            view: 'field',
            context: {
              plan_ref: task.plan_ref,
              task_ref: taskRef,
              scope
            }
          }
        });
      }
    }, "\u5B9E\u9645\u7518\u7279")), timeline && /*#__PURE__*/React.createElement(Timeline, {
      task: task
    }), p.completion_basis === 'legacy_finish_event' && /*#__PURE__*/React.createElement("div", {
      className: "field-note"
    }, "\u5DF2\u6709\u65E7\u5B8C\u5DE5\u4E8B\u5B9E\uFF0C\u5DE5\u5E8F\u4ECD\u4E3A\u5DF2\u5B8C\u5DE5\uFF1B\u7F3A\u5931\u7684\u6570\u91CF\u548C\u6709\u6548\u5DE5\u65F6\u672A\u8865\u9020\u3002"), /*#__PURE__*/React.createElement(Issues, {
      issues: p.data_gaps
    }), /*#__PURE__*/React.createElement("div", {
      className: "field-scroll wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true,
      tabIndex: "0",
      "aria-label": "\u9010\u6B21\u62A5\u5DE5\u8868\u683C\u6EDA\u52A8\u533A"
    }, /*#__PURE__*/React.createElement("table", {
      className: "field-table wb-table",
      "aria-label": "\u9010\u6B21\u62A5\u5DE5\u8BB0\u5F55"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u672C\u5DE5\u5E8F\u6BCF\u6B21\u62A5\u5DE5\u7684\u6570\u91CF\u3001\u5B9E\u9645\u8D77\u6B62\u3001\u6709\u6548\u5DE5\u65F6\u3001\u8D44\u6E90\u548C\u66F4\u6B63\u64CD\u4F5C"), /*#__PURE__*/React.createElement("colgroup", null, /*#__PURE__*/React.createElement("col", {
      style: {
        width: '15%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '9%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '16%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '16%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '9%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '12%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '12%'
      }
    }), /*#__PURE__*/React.createElement("col", {
      style: {
        width: '11%'
      }
    })), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, ['报工编号', '本次数量', '实际开工', '本次完工', '有效工时(h)', '实际设备 / 人员', '备注', '操作'].map((name, index) => /*#__PURE__*/React.createElement("th", {
      key: name,
      scope: "col",
      className: index === 7 ? 'wb-col-actions' : undefined
    }, name)))), /*#__PURE__*/React.createElement("tbody", null, p.reports.map(record => /*#__PURE__*/React.createElement(React.Fragment, {
      key: record.report_ref
    }, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", null, record.report_no, /*#__PURE__*/React.createElement("small", null, record.recorded_against_plan_ref !== task.plan_ref ? '按旧计划录入' : '按本计划录入'), /*#__PURE__*/React.createElement(Button, {
      icon: "history",
      "aria-label": '录入信息 ' + record.report_no,
      "aria-expanded": historyRef === record.report_ref,
      onClick: () => setHistoryRef(historyRef === record.report_ref ? null : record.report_ref)
    })), /*#__PURE__*/React.createElement("td", null, C.display(record.completed_quantity)), /*#__PURE__*/React.createElement("td", null, C.date(record.actual_start)), /*#__PURE__*/React.createElement("td", null, C.date(record.actual_end)), /*#__PURE__*/React.createElement("td", null, C.display(record.effective_processing_hours)), /*#__PURE__*/React.createElement("td", null, C.display(record.actual_machine_label), /*#__PURE__*/React.createElement("small", null, C.display(record.actual_operator_label))), /*#__PURE__*/React.createElement("td", null, C.display(record.remark)), /*#__PURE__*/React.createElement("td", {
      className: "wb-col-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "file-plus",
      "aria-label": '补齐 ' + record.report_no,
      reasonDisplay: "tooltip",
      reason: C.blocked(record.write_context, 'supplement'),
      disabled: command.locked || !!editor,
      onClick: () => onEdit({
        taskRef,
        reportRef: record.report_ref,
        action: 'supplement'
      })
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "square-pen",
      "aria-label": '更正 ' + record.report_no,
      reasonDisplay: "tooltip",
      reason: C.blocked(record.write_context, 'correct'),
      disabled: command.locked || !!editor,
      onClick: () => onEdit({
        taskRef,
        reportRef: record.report_ref,
        action: 'correct'
      })
    }))), historyRef === record.report_ref && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: "8"
    }, /*#__PURE__*/React.createElement(History, {
      record: record
    }))))), !p.reports.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: "8"
    }, /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      title: "\u6682\u65E0\u9010\u6B21\u62A5\u5DE5",
      hint: "\u53EF\u65B0\u589E\u672C\u6B21\u62A5\u5DE5\uFF1B\u539F\u59CB\u6267\u884C\u4E8B\u5B9E\u4E2D\u7684\u672A\u77E5\u503C\u4ECD\u4FDD\u6301\u672A\u77E5\u3002"
    })))))), missingOriginal && /*#__PURE__*/React.createElement("div", {
      className: "field-note"
    }, /*#__PURE__*/React.createElement("p", {
      role: "alert"
    }, "\u539F\u8BB0\u5F55\u5DF2\u4E0D\u5728\u5F53\u524D\u4EFB\u52A1\u4E2D\uFF0C\u6682\u5B58\u5185\u5BB9\u672A\u5199\u5165\uFF0C\u672A\u6539\u6307\u5176\u4ED6\u8BB0\u5F55\u3002"), /*#__PURE__*/React.createElement(Button, {
      onClick: onCloseEditor,
      disabled: command.locked
    }, "\u53D6\u6D88\u6682\u5B58\u7F16\u8F91")), editor && !missingOriginal && (editor.action === 'create' || report) && /*#__PURE__*/React.createElement(window.FieldEditor, {
      key: editor.action + ':' + (editor.reportRef || editor.legacyRef || taskRef),
      task: task,
      record: report,
      legacy: legacy,
      action: editor.action,
      adapter: adapter,
      command: command,
      retained: retained,
      onDraft: onDraft,
      onClose: onCloseEditor,
      onDone: onDone
    }), p.legacy_facts.length > 0 && /*#__PURE__*/React.createElement("details", {
      className: "field-note"
    }, /*#__PURE__*/React.createElement("summary", null, "\u539F\u59CB\u6267\u884C\u4E8B\u5B9E \xB7 ", p.legacy_facts.length, " \u6761"), p.legacy_facts.map((fact, index) => /*#__PURE__*/React.createElement("div", {
      key: fact.legacy_fact_ref || index
    }, C.date(fact.event_time), " \xB7 ", {
      start: '开工',
      finish: '完工',
      pause: '暂停',
      resume: '恢复',
      exception: '异常'
    }[fact.event_type] || '原始事实', " \xB7 ", C.display(fact.remark), fact.event_type === 'finish' && !p.reports.some(row => row.legacy_fact_ref === fact.legacy_fact_ref) && /*#__PURE__*/React.createElement(Button, {
      icon: "plus",
      disabled: command.locked || !!editor,
      reason: C.blocked(p.write_context, 'create'),
      onClick: () => onEdit({
        taskRef,
        legacyRef: fact.legacy_fact_ref,
        action: 'create'
      })
    }, "\u8865\u9F50\u539F\u59CB\u5B8C\u5DE5\u8BB0\u5F55")))));
  }
  window.FieldDetail = FieldDetail;
})();
