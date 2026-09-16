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
  const fields = [['actual_start', '实际开工'], ['actual_end', '本次结束'], ['completed_quantity', '完成数量'], ['effective_processing_hours', '有效加工工时（小时）'], ['remark', '备注']];
  function Refs({
    rows
  }) {
    // 编号、版本号一律进折叠的「编号」区，正文只留人看得懂的内容。
    const visible = rows.filter(([label]) => !/(编号|版本)$/.test(label));
    const refs = Object.fromEntries(rows.filter(([label]) => /(编号|版本)$/.test(label)));
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dl", {
      className: "ca-refs"
    }, visible.map(([label, value]) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: label
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, ['实际开工', '本次结束', '登记时间', '生成时间', '数据截至'].includes(label) && value ? window.WorkbenchFormat.dateTime(value, {
      seconds: true
    }) : text(value))))), !!Object.keys(refs).length && /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: refs
    }));
  }
  function Report({
    report
  }) {
    return /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u62A5\u5DE5 \xB7 ", report.actual_end ? window.WorkbenchFormat.dateTime(report.actual_end) : '结束时间未知', " \xB7 \u6570\u91CF ", text(report.completed_quantity), " \xB7 ", hours(report.effective_processing_hours, '工时未知')), /*#__PURE__*/React.createElement(Refs, {
      rows: [["单号", report.report_no], ["记录编号", report.report_ref], ["记录人", report.local_operator], ["经办人", report.declared_operator], ["登记时间", report.recorded_at], ["原计划记录编号", report.recorded_against_plan_ref], ["原任务记录编号", report.recorded_against_task_ref], ["当前版本编号", report.revision_ref]]
    }), /*#__PURE__*/React.createElement(Refs, {
      rows: fields.map(([key, label]) => [label, report[key]])
    }), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '设备编号': report.actual_machine_ref,
        '人员编号': report.actual_operator_ref,
        '报工来源': report.source
      }
    }), /*#__PURE__*/React.createElement("h4", null, "\u767B\u8BB0\u4E0E\u66F4\u6B63\u8BB0\u5F55\uFF08", report.correction_history.length, " \u6761\uFF09"), report.correction_history.map(revision => /*#__PURE__*/React.createElement("details", {
      key: revision.revision_ref
    }, /*#__PURE__*/React.createElement("summary", null, window.WorkbenchTerms.report_actions[revision.action] || revision.action, " \xB7 ", window.WorkbenchFormat.dateTime(revision.recorded_at)), /*#__PURE__*/React.createElement(Refs, {
      rows: [["更正原因", revision.reason || '无'], ["记录人", revision.local_operator], ["经办人", revision.declared_operator], ["版本编号", revision.revision_ref], ["结果编号", revision.receipt_ref]]
    }), /*#__PURE__*/React.createElement("div", {
      className: "ca-table-scroll wb-table-frame"
    }, /*#__PURE__*/React.createElement("table", {
      className: "ca-table",
      "aria-label": "\u66F4\u6B63\u524D\u540E\u503C"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u9010\u6B21\u62A5\u5DE5\u66F4\u6B63\u524D\u540E\u7684\u503C"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u9879\u76EE"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u66F4\u6B63\u524D"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u66F4\u6B63\u540E"))), /*#__PURE__*/React.createElement("tbody", null, fields.map(([key, label]) => /*#__PURE__*/React.createElement("tr", {
      key: key
    }, /*#__PURE__*/React.createElement("th", {
      scope: "row"
    }, label), /*#__PURE__*/React.createElement("td", null, revision.before === null ? '新增，无原值' : text(revision.before && revision.before[key])), /*#__PURE__*/React.createElement("td", null, text(revision.after && revision.after[key]))))))), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '原设备编号': revision.before && revision.before.actual_machine_ref,
        '新设备编号': revision.after && revision.after.actual_machine_ref,
        '原人员编号': revision.before && revision.before.actual_operator_ref,
        '新人员编号': revision.after && revision.after.actual_operator_ref
      }
    }))));
  }
  function Sample({
    sample,
    opened,
    onOpen
  }) {
    const state = sample.selected ? '可用记录' : sample.template_operation_ref === null ? '未关联核对' : '已关联但剔除';
    return /*#__PURE__*/React.createElement("details", {
      className: "ca-evidence ca-sample",
      open: opened,
      "data-sample-ref": sample.sample_ref,
      onToggle: event => {
        if (event.target === event.currentTarget && event.currentTarget.open !== opened) onOpen(event.currentTarget.open ? sample.sample_ref : null);
      }
    }, /*#__PURE__*/React.createElement("summary", null, state, " \xB7 ", sample.batch_code, " \xB7 ", sample.confirmed_finish ? window.WorkbenchFormat.dateTime(sample.confirmed_finish) : '完工时间未知', " \xB7 \u5DF2\u77E5\u6570\u91CF ", text(sample.completed_quantity), sample.unknown_record_count > 0 && ' · ' + sample.unknown_record_count + ' 条数量未知', " \xB7 ", hours(sample.effective_processing_hours, '工时未知')), opened && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Refs, {
      rows: [["批次", sample.batch_code], ["工序单号", sample.operation_code], ["完工记录编号", sample.execution_operation_ref], ["来源模板编号", sample.template_operation_ref], ["来源模板版本", sample.template_revision], ["来源证据编号", sample.lineage_evidence_ref], ["记录版本", sample.sample_revision]]
    }), /*#__PURE__*/React.createElement("p", null, "\u5355\u4EF6\u5DE5\u65F6\uFF1A", hours(sample.unit_hours, '未知'), "\uFF1B\u6570\u91CF\u672A\u77E5\u8BB0\u5F55 ", sample.unknown_record_count, " \u6761\u3002"), /*#__PURE__*/React.createElement("ul", null, sample.exclusion_reasons.map((reason, index) => /*#__PURE__*/React.createElement("li", {
      key: reason.code + ':' + index
    }, reason.message))), /*#__PURE__*/React.createElement("h4", null, "\u9010\u6B21\u62A5\u5DE5\uFF08", sample.reports.length, " \u6761\uFF09"), sample.reports.map(report => /*#__PURE__*/React.createElement(Report, {
      key: report.report_ref,
      report: report
    })), /*#__PURE__*/React.createElement("h4", null, "\u5386\u53F2\u73B0\u573A\u8BB0\u5F55\uFF08", sample.legacy_facts.length, " \u6761\uFF09"), sample.legacy_facts.map((fact, index) => /*#__PURE__*/React.createElement("details", {
      key: fact.legacy_fact_ref || index
    }, /*#__PURE__*/React.createElement("summary", null, "\u5386\u53F2\u73B0\u573A\u8BB0\u5F55 ", index + 1), /*#__PURE__*/React.createElement(window.ReportEvidence.StructuredFacts, {
      value: fact
    }))), !!sample.data_gaps.length && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("h4", null, "\u6570\u636E\u7F3A\u53E3"), /*#__PURE__*/React.createElement("ul", null, sample.data_gaps.map((gap, index) => /*#__PURE__*/React.createElement("li", {
      key: index
    }, gap.message || /*#__PURE__*/React.createElement(window.ReportEvidence.StructuredFacts, {
      value: gap
    })))))));
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
    }, /*#__PURE__*/React.createElement("h4", null, label, "\uFF08", samples.length, "\uFF09"), !samples.length && /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "empty",
      title: "\u6682\u65E0\u8BB0\u5F55"
    }), samples.slice((paging.page - 1) * paging.size, paging.page * paging.size).map(sample => /*#__PURE__*/React.createElement(Sample, {
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
      row = data && data.suggestion;
    const groups = React.useMemo(() => data ? [['可用记录', 'selected', data.suggestion.sample_refs.map(ref => data.samples.find(sample => sample.sample_ref === ref))], ['已关联但剔除', 'excluded', data.samples.filter(sample => sample.template_operation_ref !== null && !sample.selected)], ['同零件未关联核对', 'unbound', data.samples.filter(sample => sample.template_operation_ref === null)]] : [], [data]);
    const actions = /*#__PURE__*/React.createElement("div", {
      className: "ca-actions"
    }, !window.CalibrationAdoptionAction && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
      icon: "check",
      reason: writeReason
    }, "\u91C7\u7528"), /*#__PURE__*/React.createElement(Button, {
      icon: "lock",
      reason: writeReason
    }, "\u9501\u5B9A")));
    return /*#__PURE__*/React.createElement(window.WorkbenchDetailPanel, {
      className: "ca-detail",
      detailKey: selected,
      title: row ? row.part_no + ' · ' + row.sequence + ' ' + row.operation_label : '已选校准记录',
      subtitle: "\u6821\u51C6\u8BE6\u60C5",
      actions: actions,
      onClose: onClose
    }, !row && /*#__PURE__*/React.createElement(Refs, {
      rows: [["已选记录编号", selected], ["已选完工记录编号", sampleRef]]
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), stale && /*#__PURE__*/React.createElement("p", {
      className: "ca-note"
    }, "\u6570\u636E\u5DF2\u66F4\u65B0\uFF0C\u8BF7\u5237\u65B0\u6240\u9009\u8BB0\u5F55\u3002"), (error || stale) && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: onRefresh
    }, "\u5237\u65B0\u6240\u9009\u8BB0\u5F55"), busy && /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "loading",
      title: "\u6B63\u5728\u8BFB\u53D6\u5B8C\u5DE5\u8BB0\u5F55\u6765\u6E90"
    }), row && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dl", {
      className: "ca-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u539F\u5B9A\u989D"), /*#__PURE__*/React.createElement("dd", null, hours(row.old_unit_hours), " / \u4EF6")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5EFA\u8BAE\u5B9A\u989D"), /*#__PURE__*/React.createElement("dd", null, hours(row.suggested_unit_hours, '暂无建议'))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u53EF\u7528\u8BB0\u5F55\u6570"), /*#__PURE__*/React.createElement("dd", null, row.sample_count, " \u6761")), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6838\u5BF9\u8BB0\u5F55\u603B\u6570"), /*#__PURE__*/React.createElement("dd", null, row.candidate_count, " \u6761"))), row.suggested_unit_hours === null && /*#__PURE__*/React.createElement("p", {
      className: "ca-note"
    }, "\u540C\u6A21\u677F\u3001\u540C\u7248\u672C\u7684\u53EF\u7528\u5B8C\u5DE5\u8BB0\u5F55\u4E0D\u8DB3 5 \u6761\uFF0C\u6682\u65E0\u5EFA\u8BAE\u3002"), /*#__PURE__*/React.createElement("details", {
      className: "ca-evidence"
    }, /*#__PURE__*/React.createElement("summary", null, "\u5B9A\u989D\u8BB0\u5F55\u4E0E\u8BA1\u7B97\u4F9D\u636E"), /*#__PURE__*/React.createElement(Refs, {
      rows: [["模板工序编号", row.template_operation_ref], ["模板版本", row.template_revision], ["模板数据版本", row.template_snapshot], ["零件记录编号", row.part_ref], ["计算方法编号", row.method_version], ["生成时间", row.generated_at], ["数据截至", row.as_of], ["数据版本编号", row.snapshot_ref]]
    }), /*#__PURE__*/React.createElement("p", null, "\u53D6\u6700\u8FD1 20 \u6761\u6765\u6E90\u4E0E\u7248\u672C\u5DF2\u786E\u8BA4\u7684\u6574\u9053\u5B8C\u5DE5\u8BB0\u5F55\uFF0C\u81F3\u5C11 5 \u6761\u624D\u751F\u6210\u4E2D\u4F4D\u6570\u5EFA\u8BAE\u3002\u539F\u5B9A\u989D\u4E3A 0 \u6216\u672A\u586B\u5199\u65F6\u90FD\u4E0D\u7B97\u76F8\u5BF9\u504F\u5DEE\u3002"), /*#__PURE__*/React.createElement("ul", null, row.exclusion_reasons.map((reason, index) => /*#__PURE__*/React.createElement("li", {
      key: reason.code + ':' + index
    }, reason.message, "\uFF08", reason.count, " \u6761\u8BB0\u5F55\uFF09")))), /*#__PURE__*/React.createElement("h3", null, "\u5B8C\u5DE5\u8BB0\u5F55\u4E0E\u6765\u6E90\u6838\u5BF9"), sampleRef && !data.samples.some(sample => sample.sample_ref === sampleRef) && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "ca-note"
    }, "\u6240\u9009\u5B8C\u5DE5\u8BB0\u5F55\u5DF2\u4E0D\u5728\u5F53\u524D\u7ED3\u679C\u4E2D\u3002"), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      value: sampleRef,
      label: "\u539F\u9009\u5B8C\u5DE5\u8BB0\u5F55\u7F16\u53F7"
    })), groups.map(([label, kind, samples]) => /*#__PURE__*/React.createElement(SampleGroup, {
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
