(function () {
  'use strict';

  const {
    Button,
    ErrorBox,
    Page,
    text,
    hours,
    writeReason
  } = window.CalibrationControls;
  const fields = [['actual_start', '实际开工'], ['actual_end', '本次结束'], ['completed_quantity', '完成数量'], ['effective_processing_hours', '有效加工小时'], ['actual_machine_ref', '设备记录编号'], ['actual_operator_ref', '人员记录编号'], ['remark', '备注']];
  function Refs({
    rows
  }) {
    return /*#__PURE__*/React.createElement("dl", {
      className: "ca-refs"
    }, rows.map(([label, value]) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: label
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, text(value)))));
  }
  function Report({
    report
  }) {
    return /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u62A5\u5DE5 \xB7 ", report.actual_end || '结束时间未知', " \xB7 \u6570\u91CF ", text(report.completed_quantity), " \xB7 ", hours(report.effective_processing_hours, '工时未知')), /*#__PURE__*/React.createElement(Refs, {
      rows: [["单号", report.report_no], ["记录编号", report.report_ref], ["来源", report.source], ["登记人员", report.local_operator], ["声明人员", report.declared_operator], ["登记时间", report.recorded_at], ["原计划记录编号", report.recorded_against_plan_ref], ["原任务记录编号", report.recorded_against_task_ref], ["当前修订编号", report.revision_ref]]
    }), /*#__PURE__*/React.createElement(Refs, {
      rows: fields.map(([key, label]) => [label, report[key]])
    }), /*#__PURE__*/React.createElement("h4", null, "\u767B\u8BB0\u4E0E\u66F4\u6B63\u8BB0\u5F55\uFF08", report.correction_history.length, " \u6761\uFF09"), report.correction_history.map(revision => /*#__PURE__*/React.createElement("details", {
      key: revision.revision_ref
    }, /*#__PURE__*/React.createElement("summary", null, {
      create: '首次登记',
      supplement: '补录',
      correct: '更正'
    }[revision.action] || revision.action, " \xB7 ", revision.recorded_at), /*#__PURE__*/React.createElement(Refs, {
      rows: [["更正原因", revision.reason || '无'], ["登记人员", revision.local_operator], ["声明人员", revision.declared_operator], ["修订编号", revision.revision_ref], ["回执编号", revision.receipt_ref]]
    }), /*#__PURE__*/React.createElement("table", {
      className: "ca-table",
      "aria-label": "\u66F4\u6B63\u524D\u540E\u503C"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u9879\u76EE"), /*#__PURE__*/React.createElement("th", null, "\u66F4\u6B63\u524D"), /*#__PURE__*/React.createElement("th", null, "\u66F4\u6B63\u540E"))), /*#__PURE__*/React.createElement("tbody", null, fields.map(([key, label]) => /*#__PURE__*/React.createElement("tr", {
      key: key
    }, /*#__PURE__*/React.createElement("td", null, label), /*#__PURE__*/React.createElement("td", null, revision.before === null ? '首次登记，无前值' : text(revision.before && revision.before[key])), /*#__PURE__*/React.createElement("td", null, text(revision.after && revision.after[key])))))))));
  }
  function Sample({
    sample,
    opened,
    onOpen
  }) {
    const state = sample.selected ? '有效样本' : sample.template_operation_ref === null ? '未关联核对' : '已关联但剔除';
    return /*#__PURE__*/React.createElement("details", {
      className: "ca-evidence ca-sample",
      open: opened,
      "data-sample-ref": sample.sample_ref,
      onToggle: event => {
        if (event.target === event.currentTarget && event.currentTarget.open !== opened) onOpen(event.currentTarget.open ? sample.sample_ref : null);
      }
    }, /*#__PURE__*/React.createElement("summary", null, state, " \xB7 ", sample.batch_code, " \xB7 ", sample.confirmed_finish || '完工时间未知', " \xB7 \u5DF2\u77E5\u6570\u91CF ", text(sample.completed_quantity), sample.unknown_record_count > 0 && ' · ' + sample.unknown_record_count + ' 条数量未知', " \xB7 ", hours(sample.effective_processing_hours, '工时未知')), opened && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Refs, {
      rows: [["批次", sample.batch_code], ["工序单号", sample.operation_code], ["实例记录编号", sample.execution_operation_ref], ["来源模板编号", sample.template_operation_ref], ["来源模板修订", sample.template_revision], ["来源证据编号", sample.lineage_evidence_ref], ["样本修订", sample.sample_revision]]
    }), /*#__PURE__*/React.createElement("p", null, "\u5355\u4EF6\u5DE5\u65F6\uFF1A", hours(sample.unit_hours, '未知'), "\uFF1B\u6570\u91CF\u672A\u77E5\u8BB0\u5F55 ", sample.unknown_record_count, " \u6761\u3002"), /*#__PURE__*/React.createElement("ul", null, sample.exclusion_reasons.map((reason, index) => /*#__PURE__*/React.createElement("li", {
      key: reason.code + ':' + index
    }, reason.message))), /*#__PURE__*/React.createElement("h4", null, "\u9010\u6B21\u62A5\u5DE5\uFF08", sample.reports.length, " \u6761\uFF09"), sample.reports.map(report => /*#__PURE__*/React.createElement(Report, {
      key: report.report_ref,
      report: report
    })), /*#__PURE__*/React.createElement("h4", null, "\u65E7\u73B0\u573A\u4E8B\u5B9E\uFF08", sample.legacy_facts.length, " \u6761\uFF09"), sample.legacy_facts.map((fact, index) => /*#__PURE__*/React.createElement("details", {
      key: fact.legacy_fact_ref || index
    }, /*#__PURE__*/React.createElement("summary", null, "\u65E7\u73B0\u573A\u8BB0\u5F55 ", index + 1), /*#__PURE__*/React.createElement("pre", null, JSON.stringify(fact, null, 2)))), !!sample.data_gaps.length && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("h4", null, "\u6570\u636E\u7F3A\u53E3"), /*#__PURE__*/React.createElement("ul", null, sample.data_gaps.map((gap, index) => /*#__PURE__*/React.createElement("li", {
      key: index
    }, gap.message || JSON.stringify(gap)))))));
  }
  function SampleGroup({
    label,
    kind,
    samples,
    sampleRef,
    onSample
  }) {
    const [paging, setPaging] = React.useState({
      page: 1,
      size: 10
    });
    React.useEffect(() => {
      const index = samples.findIndex(sample => sample.sample_ref === sampleRef);
      setPaging(old => ({
        ...old,
        page: index >= 0 ? Math.floor(index / old.size) + 1 : Math.min(old.page, Math.max(1, Math.ceil(samples.length / old.size)))
      }));
    }, [samples, sampleRef]);
    return /*#__PURE__*/React.createElement("section", {
      className: "ca-sample-group",
      "aria-label": label,
      "data-sample-group": kind
    }, /*#__PURE__*/React.createElement("h4", null, label, "\uFF08", samples.length, "\uFF09"), !samples.length && /*#__PURE__*/React.createElement("p", {
      className: "ca-muted"
    }, "\u6682\u65E0\u8BB0\u5F55\u3002"), samples.slice((paging.page - 1) * paging.size, paging.page * paging.size).map(sample => /*#__PURE__*/React.createElement(Sample, {
      key: sample.sample_ref,
      sample: sample,
      opened: sampleRef === sample.sample_ref,
      onOpen: onSample
    })), samples.length > 10 && /*#__PURE__*/React.createElement(Page, {
      label: label,
      page: {
        number: paging.page,
        size: paging.size,
        total: samples.length,
        total_pages: Math.ceil(samples.length / paging.size)
      },
      onChange: patch => setPaging(old => ({
        ...old,
        ...patch
      }))
    }));
  }
  function Detail({
    result,
    busy,
    error,
    selected,
    sampleRef,
    onSample,
    onClose,
    onRefresh,
    stale
  }) {
    const data = result && result.data,
      row = data && data.suggestion,
      root = React.useRef(null);
    const groups = React.useMemo(() => data ? [['有效样本', 'selected', data.suggestion.sample_refs.map(ref => data.samples.find(sample => sample.sample_ref === ref))], ['已关联但剔除', 'excluded', data.samples.filter(sample => sample.template_operation_ref !== null && !sample.selected)], ['同零件未关联核对', 'unbound', data.samples.filter(sample => sample.template_operation_ref === null)]] : [], [data]);
    React.useEffect(() => {
      const previous = document.activeElement;
      root.current.focus({
        preventScroll: true
      });
      root.current.scrollIntoView({
        block: 'start'
      });
      return () => {
        if (previous && previous.isConnected) previous.focus({
          preventScroll: true
        });
      };
    }, [selected]);
    return /*#__PURE__*/React.createElement("section", {
      className: "ca-detail",
      "aria-label": "\u6821\u51C6\u8BE6\u60C5",
      tabIndex: -1,
      ref: root,
      onKeyDown: event => {
        if (event.key === 'Escape' && !event.defaultPrevented) {
          event.stopPropagation();
          onClose();
        }
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "ca-heading"
    }, /*#__PURE__*/React.createElement("h3", null, row ? row.part_no + ' · ' + row.sequence + ' ' + row.operation_label : '已选校准记录'), /*#__PURE__*/React.createElement("div", {
      className: "ca-actions"
    }, !window.CalibrationAdoptionAction && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      icon: "check",
      reason: writeReason
    }, "\u91C7\u7528"), /*#__PURE__*/React.createElement(Button, {
      icon: "lock",
      reason: writeReason
    }, "\u9501\u5B9A")), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u5173\u95ED\u6821\u51C6\u8BE6\u60C5",
      onClick: onClose
    }))), !row && /*#__PURE__*/React.createElement(Refs, {
      rows: [["已选记录编号", selected], ["已选实例编号", sampleRef]]
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), stale && /*#__PURE__*/React.createElement("p", {
      className: "ca-note"
    }, "\u524D\u540E\u5FEB\u7167\u4E0D\u4E00\u81F4\uFF0C\u8BF7\u660E\u786E\u5237\u65B0\u3002\u5DF2\u9009\u8BB0\u5F55\u548C\u6837\u672C\u6765\u6E90\u4FDD\u7559\uFF0C\u4E0D\u4F1A\u81EA\u52A8\u6362\u5230\u5176\u4ED6\u8BB0\u5F55\u3002"), (error || stale) && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: onRefresh
    }, "\u5237\u65B0\u6240\u9009\u8BB0\u5F55"), busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u6837\u672C\u6765\u6E90..."), row && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dl", {
      className: "ca-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u539F\u5B9A\u989D"), /*#__PURE__*/React.createElement("dd", null, hours(row.old_unit_hours), " / \u4EF6")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5EFA\u8BAE\u5B9A\u989D"), /*#__PURE__*/React.createElement("dd", null, hours(row.suggested_unit_hours, '暂无建议'))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6709\u6548\u6837\u672C"), /*#__PURE__*/React.createElement("dd", null, row.sample_count, " \u4E2A")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6838\u5BF9\u5B9E\u4F8B\u603B\u6570"), /*#__PURE__*/React.createElement("dd", null, row.candidate_count, " \u4E2A"))), row.suggested_unit_hours === null && /*#__PURE__*/React.createElement("p", {
      className: "ca-note"
    }, "\u540C\u6A21\u677F\u3001\u540C\u4FEE\u8BA2\u6709\u6548\u6837\u672C\u4E0D\u8DB3 5 \u4E2A\uFF0C\u6682\u65E0\u5EFA\u8BAE\u3002"), /*#__PURE__*/React.createElement("details", {
      className: "ca-evidence"
    }, /*#__PURE__*/React.createElement("summary", null, "\u5B9A\u989D\u8BB0\u5F55\u4E0E\u8BA1\u7B97\u4F9D\u636E"), /*#__PURE__*/React.createElement(Refs, {
      rows: [["模板工序编号", row.template_operation_ref], ["模板修订", row.template_revision], ["模板快照", row.template_snapshot], ["零件记录编号", row.part_ref], ["计算方法", row.method_version], ["生成时间", row.generated_at], ["数据截至", row.as_of], ["范围快照", row.snapshot_ref]]
    }), /*#__PURE__*/React.createElement("p", null, "\u53D6\u6700\u8FD1 20 \u4E2A\u6765\u6E90\u4E0E\u4FEE\u8BA2\u5DF2\u786E\u8BA4\u7684\u6574\u9053\u5B8C\u5DE5\u5B9E\u4F8B\uFF0C\u81F3\u5C11 5 \u4E2A\u624D\u751F\u6210\u4E2D\u4F4D\u6570\u5EFA\u8BAE\u3002\u539F\u5B9A\u989D\u4E3A 0 \u548C\u672A\u63D0\u4F9B\u65F6\u5747\u4E0D\u8BA1\u7B97\u76F8\u5BF9\u504F\u5DEE\u3002"), /*#__PURE__*/React.createElement("ul", null, row.exclusion_reasons.map((reason, index) => /*#__PURE__*/React.createElement("li", {
      key: reason.code + ':' + index
    }, reason.message, "\uFF08", reason.count, " \u4E2A\u5B9E\u4F8B\uFF09")))), /*#__PURE__*/React.createElement("h3", null, "\u6837\u672C\u4E0E\u6765\u6E90\u6838\u5BF9"), sampleRef && !data.samples.some(sample => sample.sample_ref === sampleRef) && /*#__PURE__*/React.createElement("p", {
      className: "ca-note"
    }, "\u539F\u9009\u5B9E\u4F8B\u5DF2\u4E0D\u5728\u8FD4\u56DE\u7ED3\u679C\u4E2D\uFF0C\u672A\u9009\u62E9\u5176\u4ED6\u6765\u6E90\u3002\u8BB0\u5F55\u7F16\u53F7\uFF1A", sampleRef), groups.map(([label, kind, samples]) => /*#__PURE__*/React.createElement(SampleGroup, {
      key: selected + kind,
      label: label,
      kind: kind,
      samples: samples,
      sampleRef: sampleRef,
      onSample: onSample
    }))));
  }
  window.CalibrationDetail = Detail;
})();
