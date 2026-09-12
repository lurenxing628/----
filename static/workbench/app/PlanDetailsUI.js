(function () {
  'use strict';

  const {
      Button,
      Issues
    } = window.ResourceControls,
    M = window.PlanGanttModel;
  const riskLabel = {
    overdue: '预计超期',
    on_time: '预计按期',
    unknown: '无法核实'
  };
  const deliveryIssues = {
    operations_unscheduled: '尚有工序未安排',
    operations_missing: '工序资料未记录',
    schedule_time_invalid: '安排时间无效',
    saved_plan_incomplete: '保存的计划不完整',
    due_date_missing: '交期未记录',
    due_date_invalid: '交期无效',
    due_date_unspecified: '未指定交期',
    part_label_missing: '零件名称或图号未记录'
  };
  const issueText = issues => (issues || []).map(issue => typeof issue === 'string' ? deliveryIssues[issue] || '无法核实（' + issue + '）' : issue.message).join('；');
  function Facts({
    items
  }) {
    return /*#__PURE__*/React.createElement("dl", {
      className: "plan-facts"
    }, items.map(([key, value]) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, key), /*#__PURE__*/React.createElement("dd", null, value))));
  }
  function CalendarWindows({
    windows
  }) {
    const [open, setOpen] = React.useState(false),
      [page, setPage] = React.useState(0);
    if (windows === null) return '无法核实';
    return /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(Button, {
      className: "linkbtn",
      "aria-expanded": open,
      onClick: () => setOpen(!open)
    }, windows.length, " \u6BB5"), open && /*#__PURE__*/React.createElement(React.Fragment, null, windows.slice(page * 10, page * 10 + 10).map((item, index) => /*#__PURE__*/React.createElement("div", {
      key: index
    }, M.timeLabel(item.start), " \u2192 ", M.timeLabel(item.end), /*#__PURE__*/React.createElement("div", {
      className: "plan-muted"
    }, "\u666E\u901A", item.allow_normal ? '允许' : '禁止', " \xB7 \u6025\u4EF6", item.allow_urgent ? '允许' : '禁止', " \xB7 \u6548\u7387 ", M.number(item.efficiency)))), windows.length > 10 && /*#__PURE__*/React.createElement("div", {
      className: "plan-pager"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "btn plan-icon",
      icon: "chevron-left",
      "aria-label": "\u65E5\u5386\u7A97\u53E3\u4E0A\u4E00\u6BB5",
      disabled: !page,
      onClick: () => setPage(page - 1)
    }), /*#__PURE__*/React.createElement("span", null, page + 1), /*#__PURE__*/React.createElement(Button, {
      className: "btn plan-icon",
      icon: "chevron-right",
      "aria-label": "\u65E5\u5386\u7A97\u53E3\u4E0B\u4E00\u6BB5",
      disabled: (page + 1) * 10 >= windows.length,
      onClick: () => setPage(page + 1)
    }))));
  }
  function Relations({
    data,
    selected,
    onRelated
  }) {
    const order = data.projections.process_order;
    const relations = window.PlanProcessOrder.relationships(data, selected);
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5DE5\u827A\u524D\u540E\u5E8F"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5DE5\u827A\u524D\u540E\u5E8F"), relations ? ['previous', 'next'].map(kind => /*#__PURE__*/React.createElement("div", {
      key: kind
    }, /*#__PURE__*/React.createElement("h4", null, kind === 'previous' ? '前序' : '后序'), !relations[kind].length && /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, kind === 'previous' ? '无前序工序' : '无后序工序'), /*#__PURE__*/React.createElement("div", {
      className: "plan-actions"
    }, relations[kind].map((row, index) => {
      const task = row.task,
        prefix = kind === 'previous' ? '前序' : '后序';
      const label = task ? prefix + ' ' + task.batch_id + ' · ' + task.sequence + ' ' + task.process_label + ' · ' + M.pieceLabel(task) : prefix + '安排在当前读取范围外';
      return row.task_ref ? /*#__PURE__*/React.createElement(Button, {
        key: row.task_ref,
        icon: kind === 'previous' ? 'chevron-left' : 'chevron-right',
        title: label,
        "aria-label": label,
        disabled: !onRelated,
        onClick: () => onRelated(row.task_ref),
        style: {
          height: 'auto',
          minHeight: 32,
          whiteSpace: 'normal',
          textAlign: 'left',
          overflowWrap: 'anywhere'
        }
      }, task ? label : '读取完整计划并定位' + prefix) : /*#__PURE__*/React.createElement("span", {
        key: 'unplanned:' + index,
        className: "plan-muted"
      }, prefix, "\u672A\u5728\u672C\u8BA1\u5212\u5B89\u6392");
    })))) : /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, !selected ? '尚未选中任务' : selected.before ? '当前关系只属于所选计划，初始安排的关系未单独核实。' : order.issues.map(row => row.message).join('；') || '该任务的冻结关系无法核实。'));
  }
  function TaskDetail({
    data,
    selected,
    onSelect,
    onRelated,
    renderTrial,
    scope = {},
    query = '',
    disabled = false
  }) {
    const task = selected && selected.task,
      labels = React.useMemo(() => M.names(data), [data]);
    const baseline = data.projections.baseline;
    const comparison = task && baseline.state === 'available' && baseline.items.find(item => item.operation_ref === task.operation_ref);
    const risk = task && data.projections.delivery_risks.items.find(row => row.batch_id === task.batch_id);
    const resources = task ? data.projections.occupancy.resources.filter(row => [task.machine_ref, task.operator_ref].includes(row.resource_ref)) : [];
    return /*#__PURE__*/React.createElement("aside", {
      className: "plan-inspector",
      "aria-label": "\u4EFB\u52A1\u8BE6\u60C5",
      "data-plan-inspector": true
    }, /*#__PURE__*/React.createElement("section", null, /*#__PURE__*/React.createElement("h2", null, "\u4EFB\u52A1\u8BE6\u60C5"), !task ? /*#__PURE__*/React.createElement("div", {
      className: "plan-empty"
    }, "\u5C1A\u672A\u9009\u4E2D\u4EFB\u52A1\u3002\u9009\u4E2D\u7518\u7279\u4E2D\u7684\u5B89\u6392\u540E\uFF0C\u8FD9\u91CC\u663E\u793A\u5DE5\u827A\u524D\u540E\u5E8F\u3001\u521D\u59CB\u8BA1\u5212\u5BF9\u7167\u3001\u4EA4\u4ED8\u98CE\u9669\u548C\u8D44\u6E90\u5360\u7528\u3002") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "plan-muted",
      style: {
        marginTop: 9
      }
    }, selected.before ? '初始计划安排' : '当前所选计划安排'), /*#__PURE__*/React.createElement("h3", {
      style: {
        marginTop: 4,
        overflowWrap: 'anywhere'
      }
    }, task.batch_id, " \xB7 ", task.sequence), /*#__PURE__*/React.createElement("p", {
      style: {
        overflowWrap: 'anywhere'
      }
    }, task.process_label), /*#__PURE__*/React.createElement(Facts, {
      items: [['分件', /*#__PURE__*/React.createElement("span", {
        style: {
          overflowWrap: 'anywhere'
        }
      }, M.pieceLabel(task))], ['本工序目标量', M.quantityLabel(task.quantity)], ['计划来源整批量', M.quantityLabel(task.batch_quantity)], ['数量依据', task.quantity_reason ? M.quantityReasons[task.quantity_reason] : task.quantity_basis === 'run_admission' ? '原候选受理快照，已核验采用审计与回执' : '原试调创建快照，已核验采用审计与回执'], ...(window.PointContract.isPoint(task) ? [['安排类型', '时间点'], ['本工序占用', '0 h · 不占用资源']] : []), ['计划开始', M.timeLabel(task.start)], ['计划结束', M.timeLabel(task.end)], ['时间跨度', M.number((M.instant(task.end) - M.instant(task.start)) / 3600000) + ' h'], ['设备', M.resourceLabel(task, 'machine', labels)], ['人员', M.resourceLabel(task, 'operator', labels)], ['供应商', selected.before && ['candidate_adoption', 'trial_adoption'].includes(baseline.basis) ? '未记录' : task.supplier_ref ? labels.get(task.supplier_ref) || '名称未记录' : '未绑定']]
    }), /*#__PURE__*/React.createElement("div", {
      className: "plan-actions"
    }, typeof renderTrial === 'function' ? renderTrial({
      planRef: data.plan.plan_ref,
      scope,
      query,
      taskOrigin: {
        plan_ref: data.plan.plan_ref,
        operation_ref: task.operation_ref,
        task_ref: task.task_ref
      },
      disabled: disabled || selected.before || task.plan_ref !== data.plan.plan_ref,
      label: '调整此工序'
    }) : /*#__PURE__*/React.createElement(Button, {
      icon: "square-pen",
      reason: "\u8BD5\u8C03\u5165\u53E3\u672A\u63A5\u5165\uFF0C\u5F53\u524D\u53EA\u80FD\u67E5\u770B\u8BA1\u5212\u3002"
    }, "\u8C03\u6574\u6B64\u5DE5\u5E8F")))), task && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Relations, {
      data: data,
      selected: selected,
      onRelated: onRelated
    }), /*#__PURE__*/React.createElement("section", null, /*#__PURE__*/React.createElement("h3", null, "\u521D\u59CB\u8BA1\u5212\u5BF9\u7167"), comparison ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Facts, {
      items: [['变化', {
        added: '新增安排',
        removed: '移除安排',
        changed: '安排已变更',
        unchanged: '安排未变更'
      }[comparison.change]], ['初始开始', comparison.before ? M.timeLabel(comparison.before.start) : '未记录'], ['初始结束', comparison.before ? M.timeLabel(comparison.before.end) : '未记录'], ['当前开始', comparison.after ? M.timeLabel(comparison.after.start) : '未记录'], ['当前结束', comparison.after ? M.timeLabel(comparison.after.end) : '未记录']]
    }), !comparison.before_in_scope && comparison.before && /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, "\u521D\u59CB\u5B89\u6392\u5728\u6240\u9009\u65F6\u95F4\u8303\u56F4\u5916\uFF0C\u4ECD\u663E\u793A\u5B8C\u6574\u8D77\u6B62\u65F6\u95F4\u3002"), !comparison.after_in_scope && comparison.after && /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, "\u5F53\u524D\u5B89\u6392\u5DF2\u79FB\u51FA\u6240\u9009\u65F6\u95F4\u8303\u56F4\uFF0C\u4ECD\u663E\u793A\u5B8C\u6574\u8D77\u6B62\u65F6\u95F4\u3002"), comparison.before && !selected.before && /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      onClick: () => onSelect(comparison.before, true)
    }, "\u67E5\u770B\u521D\u59CB\u5B89\u6392"), comparison.after && selected.before && /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      onClick: () => onSelect(comparison.after, false)
    }, "\u67E5\u770B\u5F53\u524D\u5B89\u6392")) : /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, baseline.reason || (task ? '未找到对应对照记录' : '尚未选中任务'))), /*#__PURE__*/React.createElement("section", null, /*#__PURE__*/React.createElement("h3", null, "\u4EA4\u4ED8\u98CE\u9669"), !task ? /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, "\u5C1A\u672A\u9009\u4E2D\u4EFB\u52A1") : selected.before ? /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, "\u5F53\u524D\u4EA4\u4ED8\u98CE\u9669\u5C5E\u4E8E\u6240\u9009\u8BA1\u5212\uFF0C\u672A\u6838\u5B9E\u521D\u59CB\u8BA1\u5212\u7684\u4EA4\u4ED8\u98CE\u9669\u3002") : risk ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Facts, {
      items: [['判定', /*#__PURE__*/React.createElement("span", {
        className: risk.risk === 'overdue' ? 'plan-danger' : ''
      }, riskLabel[risk.risk])], ['交期', risk.due_date || '未记录'], ['计划完工', M.timeLabel(risk.planned_finish)], [window.WorkbenchTerms.delay_hours, risk.delay_hours === null ? '未知' : window.WorkbenchFormat.hours(risk.delay_hours, 2)], ['未排工序', M.number(risk.unscheduled_operation_count)]]
    }), risk.partial_planned_finish && /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, "\u5DF2\u5B89\u6392\u90E8\u5206\u7684\u7ED3\u675F\u65F6\u95F4\uFF1A", M.timeLabel(risk.partial_planned_finish), "\uFF0C\u4E0D\u4EE3\u8868\u6279\u6B21\u5B8C\u5DE5\u3002"), risk.issues.length > 0 && /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, issueText(risk.issues))) : /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, "\u672A\u8BB0\u5F55\uFF0C\u65E0\u6CD5\u6838\u5B9E")), /*#__PURE__*/React.createElement("section", null, /*#__PURE__*/React.createElement("h3", null, "\u8D44\u6E90\u5360\u7528"), window.PointContract.isPoint(task) ? /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, "\u672C\u5DE5\u5E8F\u4E3A\u65F6\u95F4\u70B9\uFF0C\u8D44\u6E90\u5360\u7528 0 h\u3002") : selected && selected.before ? /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, "\u521D\u59CB\u8BA1\u5212\u7684\u65E5\u5386\u548C\u5360\u7528\u672A\u5355\u72EC\u6838\u5B9E\u3002") : !resources.length ? /*#__PURE__*/React.createElement("p", {
      className: "plan-muted"
    }, "\u672A\u8BB0\u5F55\u53EF\u6838\u5B9E\u7684\u8D44\u6E90\u5360\u7528") : resources.map(row => /*#__PURE__*/React.createElement("div", {
      key: row.resource_ref
    }, /*#__PURE__*/React.createElement("strong", null, row.label || labels.get(row.resource_ref) || '资源名称未记录'), /*#__PURE__*/React.createElement(Facts, {
      items: [['已占时间', M.number(row.occupied_hours) + ' h'], ['可用时间', row.available_hours === null ? '无法核实' : M.number(row.available_hours) + ' h'], ['日历内占用', row.utilization === null ? '无法核实' : M.number(row.utilization * 100) + '%'], ['重叠时间', /*#__PURE__*/React.createElement("span", {
        className: row.has_overlap ? 'plan-danger' : ''
      }, M.number(row.overlap_hours), " h")]]
    }), /*#__PURE__*/React.createElement(Issues, {
      issues: row.issues
    }))))));
  }
  function conflictRows(data) {
    const projection = data.projections.occupancy,
      scope = data.time_scope;
    const require = value => {
      if (!value) throw new Error('资源重叠明细的范围或并行依据无法核实，未按零重叠显示。');
    };
    require(projection && projection.basis === 'selected_plan_only' && projection.plan_ref === data.plan.plan_ref && ['available', 'partial', 'unavailable'].includes(projection.state) && Array.isArray(projection.resources) && Array.isArray(projection.issues) && projection.time_scope && scope && ['range_start', 'range_end', 'selection', 'boundary', 'time_basis'].every(key => projection.time_scope[key] === scope[key]));
    const start = M.instant(scope.range_start),
      end = M.instant(scope.range_end),
      rows = [],
      seen = new Set();
    require(Number.isFinite(start) && Number.isFinite(end) && start <= end);
    for (const resource of projection.resources) {
      require(resource && ['machine', 'operator'].includes(resource.kind) && typeof resource.resource_ref === 'string' && /^[a-f0-9]{48}$/.test(resource.resource_ref) && !seen.has(resource.resource_ref) && Array.isArray(resource.segments) && typeof resource.has_overlap === 'boolean');
      seen.add(resource.resource_ref);
      let overlap = false;
      for (const segment of resource.segments) {
        const low = M.instant(segment.start),
          high = M.instant(segment.end),
          count = segment.concurrent_operations;
        require(Number.isFinite(low) && Number.isFinite(high) && start <= low && low < high && high <= end && Number.isSafeInteger(count) && count > 0);
        if (count <= 1) continue;
        overlap = true;
        rows.push({
          kind: resource.kind,
          resource_ref: resource.resource_ref,
          label: resource.label,
          start: segment.start,
          end: segment.end,
          concurrent_operations: count
        });
      }
      require(overlap === resource.has_overlap);
    }
    return {
      rows,
      projection
    };
  }
  function Conflicts({
    data
  }) {
    const [page, setPage] = React.useState(0),
      read = React.useMemo(() => {
        try {
          return conflictRows(data);
        } catch (error) {
          return {
            error
          };
        }
      }, [data]);
    if (read.error) return /*#__PURE__*/React.createElement("section", {
      className: "plan-projections",
      "aria-label": "\u8D44\u6E90\u91CD\u53E0\u660E\u7EC6"
    }, /*#__PURE__*/React.createElement("h3", null, "\u8D44\u6E90\u91CD\u53E0\u660E\u7EC6"), /*#__PURE__*/React.createElement(window.ResourceControls.ErrorBox, {
      error: read.error
    }));
    const {
        rows,
        projection
      } = read,
      current = Math.min(page, Math.max(0, Math.ceil(rows.length / 20) - 1)),
      labels = M.names(data);
    const known = projection.state === 'available',
      scope = projection.time_scope;
    const empty = !known ? '当前范围仍有资料无法核实，不能认定为没有重叠。' : !projection.resources.length ? '当前读取范围没有资源占用记录。' : '当前读取范围未发现资源安排重叠。';
    return /*#__PURE__*/React.createElement("section", {
      className: "plan-projections",
      "aria-label": "\u8D44\u6E90\u91CD\u53E0\u660E\u7EC6"
    }, /*#__PURE__*/React.createElement("h3", null, "\u8D44\u6E90\u91CD\u53E0\u660E\u7EC6"), /*#__PURE__*/React.createElement("div", {
      className: "plan-note"
    }, M.timeLabel(scope.range_start), " \u81F3 ", M.timeLabel(scope.range_end), "\uFF08\u4E0D\u542B\u7ED3\u675F\uFF09", data.scope.range_start !== null ? ' · 当前读取切片，不代表整份计划' : ' · 完整计划读取范围', /*#__PURE__*/React.createElement("div", null, "\u4EC5\u5217\u6240\u9009\u8BA1\u5212\u5728\u8BE5\u8303\u56F4\u7684\u8D44\u6E90\u5B89\u6392\u91CD\u53E0\uFF0C\u4E0D\u4EE3\u8868\u7B49\u5F85\u3001\u505C\u673A\u3001\u7F3A\u6599\u6216\u5EF6\u671F\u539F\u56E0\u3002"), !known && /*#__PURE__*/React.createElement("div", null, projection.state === 'partial' ? '部分资料无法核实。' : '资源依据不可完整核实。', "\u4EE5\u4E0B\u4EC5\u5217\u5DF2\u6838\u5B9E\u7247\u6BB5\uFF0C\u672A\u77E5\u90E8\u5206\u4E0D\u8BA1\u4E3A\u96F6\u3002")), /*#__PURE__*/React.createElement(Issues, {
      issues: projection.issues
    }), rows.length ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "plan-projection-table wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "wb-table",
      "aria-label": "\u8D44\u6E90\u91CD\u53E0\u660E\u7EC6"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u8D44\u6E90\u91CD\u53E0\u660E\u7EC6"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, ['资源', '开始（含）', '结束（不含）', '并行工序'].map((label, index) => /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: index === 0 ? 'wb-col-key' : undefined,
      key: label
    }, label)))), /*#__PURE__*/React.createElement("tbody", null, rows.slice(current * 20, current * 20 + 20).map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.resource_ref + ':' + row.start + ':' + row.end
    }, /*#__PURE__*/React.createElement("td", {
      className: "wb-col-key"
    }, row.label || labels.get(row.resource_ref) || '资源名称未记录', /*#__PURE__*/React.createElement("div", {
      className: "plan-muted"
    }, M.kindLabels[row.kind])), /*#__PURE__*/React.createElement("td", null, M.timeLabel(row.start)), /*#__PURE__*/React.createElement("td", null, M.timeLabel(row.end)), /*#__PURE__*/React.createElement("td", null, row.concurrent_operations)))))), /*#__PURE__*/React.createElement(window.WorkbenchControls.Pager, {
      label: "\u91CD\u53E0\u660E\u7EC6",
      page: current + 1,
      pages: Math.ceil(rows.length / 20),
      total: rows.length,
      size: 20,
      sizes: [20],
      unit: "\u6BB5",
      onPage: next => setPage(next - 1)
    })) : /*#__PURE__*/React.createElement(window.WorkbenchControls.EmptyState, {
      kind: "empty",
      title: empty
    }));
  }
  function ProjectionTables({
    data,
    onBatch,
    onResource
  }) {
    const [tab, setTab] = React.useState('risk'),
      [page, setPage] = React.useState(0);
    const projections = data.projections,
      labels = React.useMemo(() => M.names(data), [data]);
    const rows = tab === 'risk' ? projections.delivery_risks.items : tab === 'load' ? projections.occupancy.resources : projections.calendar.resources || [];
    const visible = rows.slice(page * 20, page * 20 + 20);
    const projection = tab === 'risk' ? projections.delivery_risks : tab === 'load' ? projections.occupancy : projections.calendar;
    return /*#__PURE__*/React.createElement("section", {
      className: "plan-projections",
      "aria-label": "\u8BA1\u5212\u5206\u6790"
    }, /*#__PURE__*/React.createElement(window.PlanSegmentUI, {
      value: tab,
      options: [["risk", "交付风险"], ["load", "资源负荷"], ["calendar", "资源日历"]],
      label: "\u8BA1\u5212\u5206\u6790\u89C6\u56FE",
      onChange: value => {
        setTab(value);
        setPage(0);
      }
    }), /*#__PURE__*/React.createElement("div", {
      className: "plan-note"
    }, tab === 'risk' ? '按所选计划的完整批次安排判定，不代表实际完工或发货。' : tab === 'load' ? '只统计所选计划在此时间范围内的安排；占用率 = 日历内已占时间 / 可用时间。设备有空闲时间不代表人员已就绪。' : '只列出所选时间范围内的可工作时段；普通件、急件能否安排及效率分别记录。', projection.state !== 'available' && /*#__PURE__*/React.createElement("span", null, " \xB7 ", projection.state === 'partial' ? '部分资料无法核实' : '无法核实')), /*#__PURE__*/React.createElement(Issues, {
      issues: projection.issues || []
    }), /*#__PURE__*/React.createElement("div", {
      className: "plan-projection-table wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "wb-table",
      "aria-label": tab === 'risk' ? '交付风险列表' : tab === 'load' ? '资源负荷列表' : '资源日历列表'
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, tab === 'risk' ? '交付风险列表' : tab === 'load' ? '资源负荷列表' : '资源日历列表'), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, (tab === 'risk' ? ['批次 / 零件', '交期', '计划完工', '交付风险', '未排工序', '证据'] : tab === 'load' ? ['资源', '安排 h', '已占 h', '可用 h', '重叠 h', '日历内占用率'] : ['资源', '可用 h', '普通有效 h', '急件有效 h', '窗口', '证据']).map((label, index) => /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: index === 0 ? 'wb-col-key' : undefined,
      key: label
    }, label)))), /*#__PURE__*/React.createElement("tbody", null, visible.map(row => tab === 'risk' ? /*#__PURE__*/React.createElement("tr", {
      key: row.batch_ref
    }, /*#__PURE__*/React.createElement("td", {
      className: "wb-col-key"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "linkbtn",
      onClick: () => onBatch(row.batch_id)
    }, row.batch_id), /*#__PURE__*/React.createElement("div", {
      className: "plan-muted"
    }, row.part_no || '图号未记录', " \xB7 ", row.part_label || '名称未记录')), /*#__PURE__*/React.createElement("td", null, window.WorkbenchFormat.date(row.due_date)), /*#__PURE__*/React.createElement("td", null, M.timeLabel(row.planned_finish), row.partial_planned_finish && /*#__PURE__*/React.createElement("div", {
      className: "plan-muted"
    }, "\u5DF2\u5B89\u6392\u90E8\u5206\u7ED3\u675F\u4E8E\uFF1A", M.timeLabel(row.partial_planned_finish))), /*#__PURE__*/React.createElement("td", {
      className: row.risk === 'overdue' ? 'plan-danger' : ''
    }, riskLabel[row.risk], row.delay_hours !== null && /*#__PURE__*/React.createElement("div", null, M.number(row.delay_hours), " h")), /*#__PURE__*/React.createElement("td", null, row.unscheduled_operation_count), /*#__PURE__*/React.createElement("td", null, issueText(row.issues) || '当前工序安排已覆盖')) : /*#__PURE__*/React.createElement("tr", {
      key: row.resource_ref
    }, /*#__PURE__*/React.createElement("td", {
      className: "wb-col-key"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "linkbtn",
      onClick: () => onResource(labels.get(row.resource_ref) || '')
    }, row.label || labels.get(row.resource_ref) || '名称未记录'), /*#__PURE__*/React.createElement("div", {
      className: "plan-muted"
    }, M.kindLabels[row.kind])), tab === 'load' ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("td", null, M.number(row.arranged_hours)), /*#__PURE__*/React.createElement("td", null, M.number(row.occupied_hours)), /*#__PURE__*/React.createElement("td", null, M.number(row.available_hours)), /*#__PURE__*/React.createElement("td", {
      className: row.has_overlap ? 'plan-danger' : ''
    }, M.number(row.overlap_hours)), /*#__PURE__*/React.createElement("td", null, row.utilization === null ? '未知' : /*#__PURE__*/React.createElement(React.Fragment, null, window.WorkbenchFormat.percent(row.utilization), /*#__PURE__*/React.createElement("span", {
      className: "plan-meter"
    }, /*#__PURE__*/React.createElement("i", {
      style: {
        width: row.utilization * 100 + '%'
      }
    }))), /*#__PURE__*/React.createElement("div", {
      className: "plan-muted"
    }, issueText(row.issues)))) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("td", null, M.number(row.available_hours)), /*#__PURE__*/React.createElement("td", null, M.number(row.normal_effective_hours)), /*#__PURE__*/React.createElement("td", null, M.number(row.urgent_effective_hours)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(CalendarWindows, {
      windows: row.windows
    })), /*#__PURE__*/React.createElement("td", null, issueText(row.issues) || '已读取真实日历')))), !visible.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 6
    }, /*#__PURE__*/React.createElement(window.WorkbenchControls.EmptyState, {
      kind: "empty",
      title: projection.state === 'available' ? '所选时间范围内没有记录。' : '资料未记录或无法核实。'
    })))))), /*#__PURE__*/React.createElement(window.WorkbenchControls.Pager, {
      label: "\u5206\u6790",
      page: page + 1,
      pages: Math.max(1, Math.ceil(rows.length / 20)),
      total: rows.length,
      size: 20,
      sizes: [20],
      onPage: next => setPage(next - 1)
    }));
  }
  window.PlanDetailsUI = {
    TaskDetail,
    ProjectionTables,
    Facts,
    Conflicts,
    conflictRows
  };
})();
