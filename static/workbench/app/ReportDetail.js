(function () {
  'use strict';

  const fields = [['actual_start', '实际开工'], ['actual_end', '本次实际结束'], ['completed_quantity', '本次完成数量'], ['effective_processing_hours', '有效加工工时'], ['actual_machine_ref', '实际设备引用'], ['actual_operator_ref', '实际人员引用'], ['remark', '备注']];
  function Evidence({
    record
  }) {
    const {
      text,
      time
    } = window.ReportTable;
    const basis = record.recorded_at_time_basis === 'factory_local' ? '工厂本地时间' : '旧系统原存储时间，未转换';
    return /*#__PURE__*/React.createElement("details", {
      className: "rw-limitations",
      style: {
        overflowWrap: 'anywhere'
      }
    }, /*#__PURE__*/React.createElement("summary", null, record.record_kind_label, " \xB7 ", record.report_no || record.event_label, " \xB7 ", time(record.event_time)), /*#__PURE__*/React.createElement("p", null, "\u767B\u8BB0\u65F6\u95F4\uFF1A", time(record.recorded_at), "\uFF08", basis, "\uFF09"), record.record_kind === 'legacy_event' ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("h4", null, "\u65E7\u539F\u59CB\u4E8B\u5B9E"), /*#__PURE__*/React.createElement("pre", {
      style: {
        whiteSpace: 'pre-wrap',
        color: 'inherit'
      }
    }, JSON.stringify(record.legacy_evidence, null, 2))) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", null, "\u62A5\u5DE5\u6765\u6E90\uFF1A", record.source, "\uFF1B\u767B\u8BB0\u4EBA\u5458\uFF1A", text(record.local_operator), "\uFF1B\u58F0\u660E\u4EBA\u5458\uFF1A", text(record.declared_operator)), /*#__PURE__*/React.createElement("h4", null, "\u9010\u6B21\u62A5\u5DE5\u4FEE\u8BA2\u5386\u53F2\uFF08", record.correction_history.length, " \u6B21\u767B\u8BB0\uFF09"), record.correction_history.map(revision => /*#__PURE__*/React.createElement("details", {
      key: revision.revision_ref
    }, /*#__PURE__*/React.createElement("summary", null, {
      create: '首次报工',
      correct: '更正',
      supplement: '补录'
    }[revision.action] || revision.action, " \xB7 ", time(revision.recorded_at)), /*#__PURE__*/React.createElement("p", null, "\u539F\u56E0\uFF1A", revision.reason || '无', "\uFF1B\u767B\u8BB0\u4EBA\u5458\uFF1A", text(revision.local_operator), "\uFF1B\u58F0\u660E\u4EBA\u5458\uFF1A", text(revision.declared_operator)), /*#__PURE__*/React.createElement("div", {
      className: "rw-table-scroll"
    }, /*#__PURE__*/React.createElement(window.APSWorkbenchUI.DataTable, {
      className: "rw-record-detail",
      rowKey: "field",
      columns: [{
        key: 'label',
        title: '字段',
        width: 150
      }, {
        key: 'before',
        title: '修订前'
      }, {
        key: 'after',
        title: '修订后'
      }].map(column => ({
        ...column,
        sortable: false,
        filterable: false
      })),
      rows: fields.map(([key, label]) => ({
        field: key,
        label,
        before: revision.before === null ? '首次登记，无前值' : text(revision.before[key]),
        after: text(revision.after[key])
      }))
    })), /*#__PURE__*/React.createElement("p", null, "\u4FEE\u8BA2\u5F15\u7528\uFF1A", revision.revision_ref, "\uFF1B\u56DE\u6267\u5F15\u7528\uFF1A", text(revision.receipt_ref))))));
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
      Table
    } = window.ReportTable;
    const request = useRead(signal => api.detail(operationRef, {
      ...input,
      page: 1,
      topic: 'delivery',
      sort: 'batch_label'
    }, signal), operationRef + JSON.stringify(input));
    const detail = request.result && request.result.data.detail;
    const root = React.useRef(null),
      [page, setPage] = React.useState(initialView ? initialView.page : 1),
      [size, setSize] = React.useState(initialView ? initialView.size : 10);
    React.useEffect(() => setPage(initialView ? initialView.page : 1), [operationRef, input.snapshot_ref]);
    React.useEffect(() => {
      const previous = document.activeElement;
      root.current.focus();
      return () => {
        if (previous && previous.isConnected) previous.focus();
      };
    }, [operationRef]);
    const row = detail && detail.operation;
    return /*#__PURE__*/React.createElement("section", {
      className: "rw-detail",
      "aria-label": "\u5DE5\u5E8F\u62A5\u8868\u8BE6\u60C5",
      tabIndex: -1,
      ref: root,
      onKeyDown: event => {
        if (event.key === 'Escape') {
          event.stopPropagation();
          onClose();
        }
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "rw-section-heading"
    }, /*#__PURE__*/React.createElement("h3", null, row ? row.batch_label + ' · ' + row.operation_label : '工序详情'), /*#__PURE__*/React.createElement("div", {
      className: "rw-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      disabled: !row || request.busy,
      reason: typeof onOpenOperation !== 'function' ? '跨工作区工序详情尚未接合。' : '',
      onClick: () => onOpenOperation(operationRef, input, row, 'field')
    }, "\u67E5\u770B\u73B0\u573A\u8BB0\u5F55"), /*#__PURE__*/React.createElement(Button, {
      icon: "chart-gantt",
      disabled: !row || request.busy,
      reason: typeof onOpenOperation !== 'function' ? '跨工作区工序详情尚未接合。' : '',
      onClick: () => onOpenOperation(operationRef, input, row, 'fieldgantt')
    }, "\u67E5\u770B\u5B9E\u9645\u7518\u7279"), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u5173\u95ED\u5DE5\u5E8F\u8BE6\u60C5",
      onClick: onClose
    }))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: request.error
    }), request.busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u5DE5\u5E8F\u4E8B\u5B9E..."), row && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dl", {
      className: "rw-detail-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6574\u9053\u5B8C\u6210"), /*#__PURE__*/React.createElement("dd", null, row.execution_label)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5DF2\u786E\u8BA4\u5B8C\u5DE5\u65F6\u95F4"), /*#__PURE__*/React.createElement("dd", null, time(row.confirmed_finish))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5DF2\u77E5\u7D2F\u8BA1\u6570\u91CF"), /*#__PURE__*/React.createElement("dd", null, text(row.known_completed_quantity), "\uFF1B\u6570\u91CF\u672A\u77E5 ", row.unknown_record_count, " \u6761")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6709\u6548\u52A0\u5DE5\u5DE5\u65F6"), /*#__PURE__*/React.createElement("dd", null, text(row.effective_processing_hours), "\uFF1B\u5DF2\u77E5\u5C0F\u8BA1 ", text(row.known_effective_processing_hours)))), /*#__PURE__*/React.createElement("p", null, "\u65E7\u73B0\u573A\u4E8B\u4EF6 ", row.event_count, " \u6761\uFF1B\u9010\u6B21\u62A5\u5DE5 ", row.production_report_count, " \u6761\uFF1B\u5168\u90E8\u8BB0\u5F55 ", row.record_count, " \u6761\u3002\u5269\u4F59\u6570\u91CF\uFF1A", text(row.remaining_quantity), "\u3002"), /*#__PURE__*/React.createElement("p", null, row.data_gaps.join(' ')), /*#__PURE__*/React.createElement(Table, {
      data: {
        topic: 'records',
        rows: detail.records.slice((page - 1) * size, page * size)
      },
      onLocate: typeof onOpenOperation === 'function' ? record => onOpenOperation(operationRef, input, row, 'fieldgantt', record.report_ref) : undefined
    }), detail.records.slice((page - 1) * size, page * size).map(record => /*#__PURE__*/React.createElement(Evidence, {
      key: record.record_kind + ':' + record.projection_index,
      record: record
    })), /*#__PURE__*/React.createElement(window.ReportControls.Page, {
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
    })));
  }
  window.ReportDetail = Detail;
})();
