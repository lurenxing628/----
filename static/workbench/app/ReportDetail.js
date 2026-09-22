(function () {
  'use strict';

  const fields = [['actual_start', '实际开工'], ['actual_end', '本次实际结束'], ['completed_quantity', '本次完成数量'], ['effective_processing_hours', '有效加工工时（小时）'], ['remark', '备注']];
  function Evidence({
    record
  }) {
    const {
      text,
      time,
      amount
    } = window.ReportTable;
    // 工时列表头已写明单位，格子里只放整形后的数字；其余项照原值显示。
    const cell = (key, value) => key === 'effective_processing_hours' ? amount(value) : text(value);
    const legacy = record.record_kind === 'legacy_event';
    return /*#__PURE__*/React.createElement("details", {
      className: "rw-limitations rw-record-evidence"
    }, /*#__PURE__*/React.createElement("summary", null, record.record_kind_label, " \xB7 ", record.report_no || record.event_label, " \xB7 ", time(record.event_time, '未知')), legacy ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("h4", null, window.WorkbenchTerms.legacy_field_records), /*#__PURE__*/React.createElement(window.ReportEvidence.LegacyRecord, {
      value: record.legacy_evidence
    })) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", null, "\u767B\u8BB0\u65F6\u95F4\uFF1A", time(record.recorded_at), "\uFF08\u73B0\u573A\u8BB0\u5F55\u65F6\u95F4\uFF09\uFF1B\u8BB0\u5F55\u4EBA\uFF1A", text(record.local_operator), "\uFF1B\u7ECF\u529E\u4EBA\uFF1A", text(record.declared_operator)), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '报工来源': record.source
      }
    }), /*#__PURE__*/React.createElement("h4", null, "\u9010\u6B21\u62A5\u5DE5\u66F4\u6B63\u8BB0\u5F55\uFF08", record.correction_history.length, " \u6B21\uFF09"), record.correction_history.map(revision => /*#__PURE__*/React.createElement("details", {
      key: revision.revision_ref
    }, /*#__PURE__*/React.createElement("summary", null, window.WorkbenchTerms.report_actions[revision.action] || revision.action, " \xB7 ", time(revision.recorded_at)), /*#__PURE__*/React.createElement("p", null, "\u539F\u56E0\uFF1A", revision.reason || '无', "\uFF1B\u8BB0\u5F55\u4EBA\uFF1A", text(revision.local_operator), "\uFF1B\u7ECF\u529E\u4EBA\uFF1A", text(revision.declared_operator)), /*#__PURE__*/React.createElement(window.ReportEvidence.TableFrame, {
      caption: "\u62A5\u5DE5\u66F4\u6B63\u524D\u540E\u7684\u503C"
    }, /*#__PURE__*/React.createElement(window.APSWorkbenchUI.DataTable, {
      className: "rw-record-detail",
      rowKey: "field",
      columns: [{
        key: 'label',
        title: '项目',
        width: 150
      }, {
        key: 'before',
        title: '更正前'
      }, {
        key: 'after',
        title: '更正后'
      }].map(column => ({
        ...column,
        sortable: false,
        filterable: false
      })),
      rows: fields.map(([key, label]) => ({
        field: key,
        label,
        before: revision.before === null ? '新增，无原值' : cell(key, revision.before[key]),
        after: cell(key, revision.after[key])
      }))
    })), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '版本编号': revision.revision_ref,
        '结果编号': revision.receipt_ref,
        '原设备编号': revision.before && revision.before.actual_machine_ref,
        '新设备编号': revision.after.actual_machine_ref,
        '原人员编号': revision.before && revision.before.actual_operator_ref,
        '新人员编号': revision.after.actual_operator_ref
      }
    })))));
  }
  function Detail({
    api,
    operationRef,
    input,
    onClose,
    onOpenOperation,
    initialView,
    onView
  }) {
    const {
      useRead,
      Button,
      ErrorBox
    } = window.ReportControls;
    const {
      text,
      time,
      hoursText,
      Table
    } = window.ReportTable;
    const identity = operationRef + JSON.stringify(input);
    const request = useRead(signal => api.detail(operationRef, {
      ...input,
      page: 1,
      topic: 'delivery',
      sort: 'batch_label'
    }, signal), identity);
    const detail = request.result && request.result.data.detail;
    const [page, setPage] = React.useState(initialView ? initialView.page : 1),
      [size, setSize] = React.useState(initialView ? initialView.size : 10);
    React.useEffect(() => setPage(initialView ? initialView.page : 1), [operationRef, input.snapshot_ref]);
    const row = detail && detail.operation;
    const actions = /*#__PURE__*/React.createElement("div", {
      className: "rw-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      disabled: !row || request.busy,
      reasonDisplay: "inline",
      reason: typeof onOpenOperation !== 'function' ? window.WorkbenchTerms.outcomes.unavailable : '',
      onClick: () => onOpenOperation(operationRef, input, row, 'field')
    }, "\u67E5\u770B\u73B0\u573A\u8BB0\u5F55"), /*#__PURE__*/React.createElement(Button, {
      icon: "chart-gantt",
      disabled: !row || request.busy,
      reasonDisplay: "inline",
      reason: typeof onOpenOperation !== 'function' ? window.WorkbenchTerms.outcomes.unavailable : '',
      onClick: () => onOpenOperation(operationRef, input, row, 'fieldgantt')
    }, "\u67E5\u770B\u73B0\u573A\u5B9E\u9645\u7518\u7279"));
    const records = detail ? detail.records.slice((page - 1) * size, page * size) : [];
    return /*#__PURE__*/React.createElement(window.WorkbenchDetailPanel, {
      className: "rw-detail",
      detailKey: operationRef,
      title: row ? row.batch_label + ' · ' + row.operation_label : '工序详情',
      subtitle: "\u5DE5\u5E8F\u62A5\u8868\u8BE6\u60C5",
      actions: actions,
      onClose: onClose
    }, /*#__PURE__*/React.createElement(ErrorBox, {
      error: request.error
    }), request.busy && /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "loading",
      title: "\u6B63\u5728\u8BFB\u53D6\u5DE5\u5E8F\u8BB0\u5F55"
    }), row && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dl", {
      className: "rw-detail-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6574\u9053\u5B8C\u6210"), /*#__PURE__*/React.createElement("dd", null, row.execution_label)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5DF2\u786E\u8BA4\u5B8C\u5DE5\u65F6\u95F4"), /*#__PURE__*/React.createElement("dd", null, time(row.confirmed_finish))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5DF2\u77E5\u7D2F\u8BA1\u6570\u91CF"), /*#__PURE__*/React.createElement("dd", null, text(row.known_completed_quantity), "\uFF1B\u6570\u91CF\u672A\u77E5 ", row.unknown_record_count, " \u6761")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6709\u6548\u52A0\u5DE5\u5DE5\u65F6"), /*#__PURE__*/React.createElement("dd", null, hoursText(row.effective_processing_hours), "\uFF1B\u5DF2\u77E5\u5C0F\u8BA1 ", hoursText(row.known_effective_processing_hours)))), /*#__PURE__*/React.createElement("p", null, window.WorkbenchTerms.legacy_field_records, " ", row.event_count, " \u6761\uFF1B\u9010\u6B21\u62A5\u5DE5 ", row.production_report_count, " \u6761\uFF1B\u5168\u90E8\u8BB0\u5F55 ", row.record_count, " \u6761\u3002\u5269\u4F59\u6570\u91CF\uFF1A", text(row.remaining_quantity), "\u3002"), /*#__PURE__*/React.createElement("p", null, row.data_gaps.join(' ')), /*#__PURE__*/React.createElement(Table, {
      data: {
        topic: 'records',
        rows: records
      },
      empty: {
        title: '这道工序暂无报工记录',
        hint: ''
      },
      onLocate: typeof onOpenOperation === 'function' ? record => onOpenOperation(operationRef, input, row, 'fieldgantt', record.report_ref) : undefined
    }), records.map(record => /*#__PURE__*/React.createElement(Evidence, {
      key: record.record_kind + ':' + record.projection_index,
      record: record
    })), /*#__PURE__*/React.createElement("div", {
      className: "rw-detail-pager"
    }, /*#__PURE__*/React.createElement(window.ReportControls.Page, {
      page: {
        number: page,
        size,
        total: detail.records.length,
        pages: Math.max(1, Math.ceil(detail.records.length / size))
      },
      onChange: patch => {
        setPage(patch.page);
        if (patch.size) setSize(patch.size);
        if (onView) onView({
          page: patch.page,
          size: patch.size || size
        });
      }
    }))));
  }
  window.ReportDetail = Detail;
})();
