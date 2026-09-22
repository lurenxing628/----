(function () {
  'use strict';

  const {
    Button
  } = window.ReportControls;
  const text = value => value == null ? '未知' : Array.isArray(value) ? value.join('；') : String(value);
  // 实际时间缺失写「未确认」，计划时间缺失写「未排」；由调用处按列传缺值说明。
  const time = (value, missing = '未确认') => value ? window.WorkbenchFormat.dateTime(value) : missing;
  // 表头已写明单位的列，格子里只放整形后的数字；写在句子里的工时带「小时」；缺值只写缺值说明，不拼单位。
  const amount = (value, missing = '未知') => value == null ? missing : window.WorkbenchFormat.number(value, {
    digits: 3,
    trim: true
  });
  const hoursText = (value, missing = '未知') => value == null ? missing : window.WorkbenchFormat.hours(value, {
    digits: 3,
    trim: true
  });
  const minutes = (value, missing = '未知') => value == null ? missing : window.WorkbenchFormat.number(value, {
    digits: 2,
    trim: true
  }) + ' 分钟';
  const signedMinutes = value => (value > 0 ? '+' : '') + minutes(value);
  const legacy = () => window.WorkbenchTerms.legacy_field_records;
  const hoursColumns = new Set(['effective_processing_hours', 'known_effective_processing_hours']);
  const defaultEmpty = {
    title: '当前筛选没有结果',
    hint: '调整计划完工日期、批次或搜索条件后重新查询。'
  };
  function CellText({
    value,
    label
  }) {
    if (typeof value !== 'string' || value.length <= 80) return value;
    return /*#__PURE__*/React.createElement("details", {
      className: "rw-cell-text"
    }, /*#__PURE__*/React.createElement("summary", {
      "aria-label": '展开' + label,
      title: '展开或收起' + label
    }, /*#__PURE__*/React.createElement("span", {
      className: "rw-cell-preview"
    }, value), /*#__PURE__*/React.createElement(window.ReportControls.Icon, {
      name: "chevron-down"
    })));
  }
  const stack = (first, second) => /*#__PURE__*/React.createElement("div", {
    className: "rw-stack"
  }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(CellText, {
    value: first,
    label: "\u4E3B\u4FE1\u606F"
  })), /*#__PURE__*/React.createElement("div", {
    className: "rw-muted"
  }, /*#__PURE__*/React.createElement(CellText, {
    value: second,
    label: "\u5DE5\u5E8F\u4FE1\u606F"
  })));
  function status(row) {
    return /*#__PURE__*/React.createElement("span", {
      className: row.finish_late ? 'rw-danger' : row.late_open ? 'rw-warning' : row.complete ? 'rw-success' : 'rw-muted'
    }, row.execution_label);
  }
  function Table({
    data,
    onDetail,
    onLocate,
    busy,
    primary,
    empty: emptyState = defaultEmpty
  }) {
    const {
      DataTable
    } = window.APSWorkbenchUI;
    const empty = window.ReportEvidence.noFeedback(data.summary);
    const actual = value => window.ReportEvidence.actualValue(value, empty);
    const actualTime = value => value == null && empty ? actual(value) : time(value);
    const actualAmount = value => value == null ? actual(value) : amount(value);
    let columns;
    const detail = row => /*#__PURE__*/React.createElement(Button, {
      className: "rw-icon-button",
      icon: "search",
      "aria-label": '查看工序 ' + row.operation_label,
      disabled: busy || !row.operation_ref,
      onClick: () => onDetail(row.operation_ref)
    });
    // 设计宽度（B1 样式包 2026-09-21 核定）只决定各列的相对比例；详情列 66、定位列 52 与固定列样式对应。
    if (data.topic === 'delivery') columns = [{
      key: 'batch_label',
      title: '批次 / 工序',
      width: 185,
      render: row => stack(row.batch_label, row.operation_label)
    }, {
      key: 'planned_end',
      title: '计划开工 / 完工',
      width: 140,
      render: row => stack(time(row.planned_start, '未排'), time(row.planned_end, '未排'))
    }, {
      key: 'confirmed_finish',
      title: '实际开工 / 整道完工',
      width: 140,
      render: row => stack(actualTime(row.actual_start), actualTime(row.confirmed_finish))
    }, {
      key: 'execution_label',
      title: '执行情况 / 到期',
      width: 150,
      render: row => stack(status(row), row.unclosed ? '到期未确认完成' : row.due ? '到期已确认完成' : '计划尚未到期')
    }, {
      key: 'finish_deviation_minutes',
      title: '整道完工偏差',
      width: 118,
      render: row => row.finish_deviation_minutes == null ? empty ? actual(null) : '尚不可比较' : /*#__PURE__*/React.createElement("span", {
        className: row.finish_late ? 'rw-danger' : ''
      }, signedMinutes(row.finish_deviation_minutes))
    }, {
      key: 'known_completed_quantity',
      title: '已知累计数量',
      width: 120,
      render: row => stack(actual(row.known_completed_quantity), row.unknown_record_count > 0 ? '数量未知 ' + row.unknown_record_count + ' 条' : null)
    },
    // 上一行是有效加工工时，下一行写明是已知小计，表头不再堆两个名字。
    {
      key: 'effective_processing_hours',
      title: '有效工时（小时）',
      width: 120,
      render: row => stack(actualAmount(row.effective_processing_hours), /*#__PURE__*/React.createElement(React.Fragment, null, "\u5DF2\u77E5\u5C0F\u8BA1 ", actualAmount(row.known_effective_processing_hours)))
    }, {
      key: 'action',
      title: '详情',
      width: 66,
      render: detail
    }];else if (data.topic === 'records') columns = [{
      key: 'batch_label',
      title: '批次 / 工序',
      width: 185,
      render: row => stack(row.batch_label, row.operation_label)
    }, {
      key: 'event_label',
      title: '记录来源 / 内容',
      width: 140,
      render: row => stack(row.record_kind_label, row.record_kind === 'production_report' ? row.report_no : row.event_label)
    }, {
      key: 'event_time',
      title: '实际时段 / 记录时间',
      width: 164,
      render: row => row.record_kind === 'production_report' ? stack(time(row.actual_start), time(row.actual_end)) : time(row.event_time, '未知')
    }, {
      key: 'quantity_done',
      title: '本次 / 登记数量',
      width: 130,
      render: row => text(row.quantity_done)
    }, {
      key: 'effective_processing_hours',
      title: '有效工时（小时）',
      width: 100,
      render: row => amount(row.effective_processing_hours)
    }, {
      key: 'machine_label',
      title: '实际设备 / 人员',
      width: 148,
      render: row => stack(row.machine_label, row.operator_label)
    }, {
      key: 'remark',
      title: '备注',
      width: 150,
      render: row => /*#__PURE__*/React.createElement(CellText, {
        value: row.remark || '无',
        label: "\u5907\u6CE8"
      })
    }, {
      key: 'action',
      title: '工序',
      width: 66,
      render: detail
    }];else if (data.topic === 'quality') columns = [{
      key: 'batch_label',
      title: '批次 / 工序',
      width: 210,
      render: row => stack(row.batch_label, row.operation_label)
    }, {
      key: 'execution_label',
      title: '执行情况',
      width: 135,
      render: status
    }, {
      key: 'event_count',
      title: legacy() + '数',
      width: 112
    }, {
      key: 'production_report_count',
      title: '逐次报工数',
      width: 110
    }, {
      key: 'record_count',
      title: '全部记录数',
      width: 110
    }, {
      key: 'data_gaps',
      title: '数据缺口',
      render: row => /*#__PURE__*/React.createElement("span", {
        className: "rw-warning"
      }, text(row.data_gaps))
    }, {
      key: 'action',
      title: '详情',
      width: 66,
      render: detail
    }];else columns = data.columns.filter(column => !column.key.endsWith('_ref')).map(column => ({
      key: column.key,
      title: column.label,
      render: row => /*#__PURE__*/React.createElement(CellText, {
        value: hoursColumns.has(column.key) ? amount(row[column.key]) : text(row[column.key]),
        label: column.label
      }),
      align: ['operations', 'batches', 'events', 'production_reports', 'records', 'effective_processing_hours', 'known_effective_processing_hours', 'unknown_hour_events'].includes(column.key) ? 'right' : 'left'
    }));
    if (data.topic === 'records' && typeof onLocate === 'function') columns.push({
      key: 'locate',
      title: '定位',
      width: 52,
      render: row => /*#__PURE__*/React.createElement(Button, {
        className: "rw-icon-button",
        icon: "chart-gantt",
        "aria-label": '定位实际甘特 ' + (row.report_no || row.event_label),
        disabled: busy,
        onClick: () => onLocate(row)
      })
    });
    const visible = columns.filter(column => column.key !== 'action' || typeof onDetail === 'function');
    const fixedWidth = visible.every(column => typeof column.width === 'number') ? visible.reduce((sum, column) => sum + column.width, 0) : 0;
    const recordsTitle = '逐次报工与' + legacy();
    return data.rows.length ? /*#__PURE__*/React.createElement(window.ReportEvidence.TableFrame, {
      className: primary ? 'rw-primary-table' : '',
      caption: data.topic === 'records' ? recordsTitle : '当前范围报表结果',
      actionColumn: visible.findIndex(column => ['action', 'locate'].includes(column.key)),
      tabIndex: 0,
      role: "region",
      "aria-label": primary ? '报表结果表格' : '报表明细表格'
    }, /*#__PURE__*/React.createElement(DataTable, {
      className: ['machines', 'people'].includes(data.topic) ? 'rw-resource-table' : 'rw-table',
      "aria-label": data.topic === 'records' ? recordsTitle : '当前筛选范围的' + ({
        delivery: '工序完成情况',
        quality: '数据完整性',
        machines: '设备工时',
        people: '人员工时'
      }[data.topic] || '报表结果'),
      columns: visible.map(column => ({
        ...column,
        width: fixedWidth ? column.width / fixedWidth * 100 + '%' : column.width,
        sortable: false,
        filterable: false
      })),
      rows: data.rows.map((row, index) => ({
        ...row,
        _key: (row.operation_ref || row.resource_ref || row.batch_ref || 'row') + ':' + (row.projection_index == null ? index : row.projection_index)
      })),
      rowKey: "_key"
    })) : /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "empty",
      title: emptyState.title,
      hint: emptyState.hint
    });
  }
  function Metrics({
    summary: s,
    topic
  }) {
    const {
      MetricStrip,
      Metric
    } = window.APSWorkbenchUI;
    const empty = window.ReportEvidence.noFeedback(s),
      actual = value => window.ReportEvidence.actualValue(value, empty);
    const pct = value => value == null ? actual(value) : window.WorkbenchFormat.percent(value);
    const values = topic === 'delivery' ? [['到期工序完成率', pct(s.completion_rate), s.confirmed_due + ' 已确认 / ' + s.due + ' 已到期'], ['到期工序按时完成率', pct(s.on_time_rate), s.due_on_time + ' 按时 / ' + s.due + ' 已到期'], ['超时未确认完成', s.late_open, '超过计划完工时间 10 分钟', s.late_open ? 'warning' : undefined, '道'], ['完工偏差中位数', s.median_finish_minutes == null ? actual(null) : window.WorkbenchFormat.number(s.median_finish_minutes, {
      digits: 2,
      trim: true
    }), s.finish_sample ? '完工记录 ' + s.finish_sample + ' 道；90% 的记录完工偏差不超过 ' + minutes(s.p90_finish_minutes) : '暂无已确认完工记录', undefined, s.median_finish_minutes == null ? undefined : '分钟']] : [['范围内工序', s.operations, s.reported_operations + ' 道有反馈；' + s.unreported + ' 道暂无反馈'], ['逐次报工', s.production_reports, legacy() + ' ' + s.events + ' 条'], ['全部记录', s.records, legacy() + '与逐次报工合计'], ['有效加工工时', s.effective_processing_hours == null ? actual(null) : amount(s.effective_processing_hours), empty ? '暂无现场工时记录' : '已知小计 ' + hoursText(s.known_effective_processing_hours) + '；未知 ' + s.unknown_hour_events + ' 条', undefined, s.effective_processing_hours == null ? undefined : '小时']];
    return /*#__PURE__*/React.createElement(MetricStrip, {
      columns: 4,
      className: "rw-metrics"
    }, values.map(([label, value, helper, tone, unit]) => /*#__PURE__*/React.createElement(Metric, {
      key: label,
      label: label,
      value: value,
      unit: unit,
      helper: helper,
      tone: tone
    })));
  }
  window.ReportTable = {
    Table,
    Metrics,
    text,
    time,
    amount,
    hoursText,
    minutes
  };
})();
