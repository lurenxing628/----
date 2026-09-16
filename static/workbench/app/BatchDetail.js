(function () {
  'use strict';

  const B = window.APSBatchContract,
    S = window.APSResourceSession;
  const {
    Button,
    ErrorBox,
    Issues
  } = window.ResourceControls;
  // Quotas are shown as entered (up to four decimals); a one-decimal summary would hide non-zero unit hours.
  const ENTERED_HOURS = {
      digits: 4,
      trim: true
    },
    ENTERED_DAYS = {
      digits: 1,
      trim: true
    };
  function BatchDetail({
    adapter,
    batchRef,
    revision,
    onBack,
    onEdit,
    onDelete,
    onOperation,
    onSync,
    disabled
  }) {
    const read = S.useQuery(async signal => B.detail(await adapter.detail('batch', batchRef, signal), batchRef), [adapter, batchRef, revision]);
    const entity = read.result && read.result.data;
    if (!entity) return /*#__PURE__*/React.createElement("section", {
      className: "batch-band"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-left",
      onClick: onBack,
      disabled: disabled
    }, "\u8FD4\u56DE\u5217\u8868"), read.loading && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u6279\u6B21\u8BE6\u60C5\u2026"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), read.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: read.reload
    }, "\u5237\u65B0\u8BE6\u60C5"));
    const reason = action => B.reason(entity.write_context, action, read.result.meta.source);
    const template = entity.template;
    return /*#__PURE__*/React.createElement("div", {
      "data-batch-detail": entity.ref
    }, /*#__PURE__*/React.createElement("section", {
      className: "batch-band"
    }, /*#__PURE__*/React.createElement("div", {
      className: "batch-section-head"
    }, /*#__PURE__*/React.createElement("h2", null, "\u6279\u6B21\u8BE6\u60C5 \xB7 ", entity.business_code), /*#__PURE__*/React.createElement("div", {
      className: "batch-section-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-left",
      onClick: onBack,
      disabled: disabled
    }, "\u8FD4\u56DE\u5217\u8868"), /*#__PURE__*/React.createElement(Button, {
      icon: "trash-2",
      "aria-label": "\u5220\u9664\u6279\u6B21",
      disabled: disabled,
      reasonDisplay: "tooltip",
      reason: reason('delete'),
      onClick: () => onDelete(entity)
    }, "\u5220\u9664\u6279\u6B21"))), /*#__PURE__*/React.createElement("dl", {
      className: "batch-facts-grid"
    }, /*#__PURE__*/React.createElement("div", {
      className: "batch-fact-wide"
    }, /*#__PURE__*/React.createElement("dt", null, "\u56FE\u53F7 / \u96F6\u4EF6"), /*#__PURE__*/React.createElement("dd", null, entity.relationships.part_no, " \xB7 ", entity.label)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6570\u91CF"), /*#__PURE__*/React.createElement("dd", null, window.WorkbenchFormat.number(entity.fields.quantity, {
      digits: 0
    }))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6279\u6B21\u72B6\u6001"), /*#__PURE__*/React.createElement("dd", null, B.label('status', entity.status))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5DE5\u5E8F\u8FDB\u5EA6"), /*#__PURE__*/React.createElement("dd", null, "\u5DF2\u5B8C\u6210 ", entity.relationships.completed_count, " / ", entity.operations.length, " \u9053"))), entity.protected && /*#__PURE__*/React.createElement("div", {
      className: "batch-restriction",
      role: "status"
    }, /*#__PURE__*/React.createElement("p", null, "\u5DF2\u6709\u6392\u4EA7\u3001\u62A5\u5DE5\u6216\u6267\u884C\u72B6\u6001\u8BB0\u5F55\uFF0C\u6682\u4E0D\u80FD\u5220\u9664\u3001\u66FF\u6362\u6216\u7F16\u8F91\u5DE5\u5E8F\u3002"), /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u67E5\u770B\u5173\u8054\u60C5\u51B5"), /*#__PURE__*/React.createElement("p", null, "\u8BA1\u5212\u53CA\u8BD5\u8C03\u5173\u8054 ", entity.relationships.plan_reference_count, " \u6761 \xB7 \u62A5\u5DE5\u53CA\u6267\u884C\u8BB0\u5F55 ", entity.relationships.execution_reference_count, " \u6761 \xB7 \u6279\u6B21\u72B6\u6001 ", B.label('status', entity.status)))), !entity.protected && reason('delete') && /*#__PURE__*/React.createElement("p", {
      className: "batch-restriction",
      role: "status"
    }, reason('delete')), /*#__PURE__*/React.createElement(Issues, {
      issues: entity.issues
    })), /*#__PURE__*/React.createElement("section", {
      className: "batch-band"
    }, /*#__PURE__*/React.createElement("div", {
      className: "batch-section-head"
    }, /*#__PURE__*/React.createElement("h3", null, "\u6279\u6B21\u57FA\u7840\u4FE1\u606F"), /*#__PURE__*/React.createElement(Button, {
      icon: "square-pen",
      onClick: () => onEdit(entity),
      disabled: disabled,
      reasonDisplay: "tooltip",
      reason: reason('update')
    }, "\u7F16\u8F91\u57FA\u7840\u4FE1\u606F")), /*#__PURE__*/React.createElement("dl", {
      className: "batch-facts-grid"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u4EA4\u671F"), /*#__PURE__*/React.createElement("dd", null, window.WorkbenchFormat.date(entity.fields.due_date))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u4F18\u5148\u7EA7"), /*#__PURE__*/React.createElement("dd", null, B.label('priority', entity.fields.priority))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u9F50\u5957\u72B6\u6001"), /*#__PURE__*/React.createElement("dd", null, B.label('ready_status', entity.fields.ready_status))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u9F50\u5957\u65E5\u671F"), /*#__PURE__*/React.createElement("dd", null, window.WorkbenchFormat.date(entity.fields.ready_date))), /*#__PURE__*/React.createElement("div", {
      className: "batch-fact-full"
    }, /*#__PURE__*/React.createElement("dt", null, "\u5907\u6CE8"), /*#__PURE__*/React.createElement("dd", null, B.label('', entity.fields.remark)))), entity.materials.count > 0 && /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u7269\u6599\u9F50\u5957\u539F\u8BB0\u5F55 \xB7 ", entity.materials.count, " \u9879"), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame",
      "data-sticky-head": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      style: {
        minWidth: 640
      },
      "aria-label": "\u6279\u6B21\u7269\u6599\u9F50\u5957"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u6279\u6B21\u7269\u6599\u9F50\u5957"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u7269\u6599"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u9700\u6C42\u91CF"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5230\u6599\u91CF"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5355\u4F4D"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u9F50\u5957\u8BB0\u5F55"))), /*#__PURE__*/React.createElement("tbody", null, entity.materials.requirements.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.material_ref
    }, /*#__PURE__*/React.createElement("td", null, row.business_code, " \xB7 ", row.label, /*#__PURE__*/React.createElement(Issues, {
      issues: row.issues
    })), /*#__PURE__*/React.createElement("td", null, window.WorkbenchFormat.number(row.required_quantity)), /*#__PURE__*/React.createElement("td", null, window.WorkbenchFormat.number(row.available_quantity)), /*#__PURE__*/React.createElement("td", null, row.unit || '未填写'), /*#__PURE__*/React.createElement("td", null, B.label('ready_status', row.ready_status))))))))), /*#__PURE__*/React.createElement("section", {
      className: "batch-band batch-template"
    }, /*#__PURE__*/React.createElement("div", {
      className: "batch-section-head"
    }, /*#__PURE__*/React.createElement("h3", null, "\u4ECE\u5DE5\u827A\u6A21\u677F\u66F4\u65B0\u5DE5\u5E8F")), /*#__PURE__*/React.createElement("dl", {
      className: "batch-facts-grid"
    }, /*#__PURE__*/React.createElement("div", {
      className: "batch-fact-wide"
    }, /*#__PURE__*/React.createElement("dt", null, "\u6765\u6E90\u5DE5\u827A"), /*#__PURE__*/React.createElement("dd", null, entity.relationships.part_no, " \xB7 ", entity.relationships.part_name)), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6709\u6548\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("dd", null, template.operation_count, " \u9053")), /*#__PURE__*/React.createElement("div", {
      className: "batch-fact-full"
    }, /*#__PURE__*/React.createElement("dt", null, "\u66F4\u65B0\u6761\u4EF6"), /*#__PURE__*/React.createElement("dd", null, entity.protected ? '已有排产或执行记录，暂不能替换工序。' : template.complete ? '工艺资料齐全，可以预检本次更新。' : '请先补齐下列工艺资料。'))), /*#__PURE__*/React.createElement(Issues, {
      issues: template.diagnostics
    }), /*#__PURE__*/React.createElement("div", {
      className: "batch-template-action"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u9884\u68C0\u5DE5\u5E8F\u66F4\u65B0",
      disabled: disabled,
      reasonDisplay: "tooltip",
      reason: reason('sync_confirm'),
      onClick: () => onSync(entity, read.result.meta.snapshot_ref)
    }, "\u9884\u68C0\u5DE5\u5E8F\u66F4\u65B0"), /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u5148\u67E5\u770B\u5DE5\u5E8F\u53D8\u5316\u548C\u8BBE\u5907\u3001\u4EBA\u5458\u6307\u5B9A\u7684\u6E05\u9664\u60C5\u51B5\uFF0C\u518D\u786E\u8BA4\u66F4\u65B0\u3002"))), /*#__PURE__*/React.createElement("section", {
      className: "batch-band"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5DE5\u5E8F\u6982\u51B5"), /*#__PURE__*/React.createElement("div", {
      className: "batch-readiness"
    }, /*#__PURE__*/React.createElement("span", null, "\u5DE5\u5E8F\u603B\u6570\uFF1A", entity.operations.length), /*#__PURE__*/React.createElement("span", null, "\u81EA\u5236\uFF1A", entity.operations.filter(op => op.source === 'internal').length), /*#__PURE__*/React.createElement("span", null, "\u5916\u534F\uFF1A", entity.operations.filter(op => op.source === 'external').length), /*#__PURE__*/React.createElement("span", null, "\u5DF2\u5B8C\u5DE5\uFF1A", entity.relationships.completed_count), /*#__PURE__*/React.createElement("span", null, "\u5F85\u8865\u9F50\uFF1A", entity.relationships.gap_count))), /*#__PURE__*/React.createElement("section", {
      className: "batch-band"
    }, /*#__PURE__*/React.createElement("h3", null, "\u6279\u6B21\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl wb-table",
      style: {
        minWidth: 1060
      },
      "aria-label": "\u6279\u6B21\u5DE5\u5E8F"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u6279\u6B21\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, ['工序编码', '工序', '工种', '归属', '资源补充', '完工', '操作'].map((name, index) => /*#__PURE__*/React.createElement("th", {
      key: name,
      scope: "col",
      className: index === 0 ? 'wb-col-key' : index === 6 ? 'wb-col-actions' : undefined,
      style: {
        width: [160, 80, 130, 80, 330, 100, 130][index]
      }
    }, name)))), /*#__PURE__*/React.createElement("tbody", null, entity.operations.map(op => /*#__PURE__*/React.createElement("tr", {
      key: op.ref
    }, /*#__PURE__*/React.createElement("td", {
      className: "wb-col-key"
    }, op.business_code), /*#__PURE__*/React.createElement("td", null, op.sequence), /*#__PURE__*/React.createElement("td", null, op.label), /*#__PURE__*/React.createElement("td", null, op.source === 'internal' ? '自制' : op.source === 'external' ? '外协' : '未归类'), /*#__PURE__*/React.createElement("td", null, op.source === 'internal' ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, op.resources.machine ? op.resources.machine.label : '设备未选', " \xB7 ", op.resources.operator ? op.resources.operator.label : '人员未选'), /*#__PURE__*/React.createElement("div", null, "\u6362\u578B ", window.WorkbenchFormat.hours(op.setup_hours, ENTERED_HOURS), " / \u5355\u4EF6 ", window.WorkbenchFormat.hours(op.unit_hours, ENTERED_HOURS))) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, op.resources.supplier ? op.resources.supplier.label : '供应商未选'), /*#__PURE__*/React.createElement("div", null, op.external_group && op.external_group.merge_mode === 'merged' ? '整组 ' + window.WorkbenchFormat.number(op.external_group.total_days, ENTERED_DAYS) : '本序 ' + window.WorkbenchFormat.number(op.external_days, ENTERED_DAYS), " \u5929")), /*#__PURE__*/React.createElement(Issues, {
      issues: op.issues
    })), /*#__PURE__*/React.createElement("td", null, op.completed ? '已完工' : op.status === 'processing' ? '加工中' : op.status === 'skipped' ? '已跳过' : '未完工'), /*#__PURE__*/React.createElement("td", {
      className: "wb-col-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "square-pen",
      "aria-label": "\u8865\u5145\u8D44\u6599",
      reasonDisplay: "tooltip",
      onClick: () => onOperation(entity, op),
      disabled: disabled || !op.editable,
      reason: reason('operation_update')
    }, "\u8865\u5145\u8D44\u6599")))), !entity.operations.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 7
    }, /*#__PURE__*/React.createElement(window.WorkbenchControls.EmptyState, {
      kind: "empty",
      title: "\u5C1A\u672A\u751F\u6210\u5DE5\u5E8F"
    }))))))));
  }
  window.BatchDetail = BatchDetail;
})();
