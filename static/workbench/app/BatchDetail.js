(function () {
  'use strict';

  const B = window.APSBatchContract,
    S = window.APSResourceSession;
  const {
    Button,
    ErrorBox,
    Issues
  } = window.ResourceControls;
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
    const [strict, setStrict] = React.useState(false),
      entity = read.result && read.result.data;
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
    }, "\u91CD\u8BD5\u8BFB\u53D6\u8BE6\u60C5"));
    const reason = action => B.reason(entity.write_context, action, read.result.meta.source);
    return /*#__PURE__*/React.createElement("div", {
      "data-batch-detail": entity.ref
    }, /*#__PURE__*/React.createElement("section", {
      className: "batch-band"
    }, /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement("h2", null, "\u6279\u6B21\u8BE6\u60C5 \xB7 ", entity.business_code), /*#__PURE__*/React.createElement("span", {
      className: "tb-spacer"
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-left",
      onClick: onBack,
      disabled: disabled
    }, "\u8FD4\u56DE\u5217\u8868"), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      disabled: disabled,
      reason: reason('delete'),
      onClick: () => onDelete(entity)
    }, "\u5220\u9664\u6279\u6B21")), /*#__PURE__*/React.createElement("div", {
      className: "batch-readiness"
    }, /*#__PURE__*/React.createElement("span", null, "\u56FE\u53F7\uFF1A", entity.relationships.part_no, " \xB7 ", entity.label), /*#__PURE__*/React.createElement("span", null, "\u6570\u91CF\uFF1A", B.label('', entity.fields.quantity)), /*#__PURE__*/React.createElement("span", null, "\u72B6\u6001\uFF1A", B.label('status', entity.status)), /*#__PURE__*/React.createElement("span", null, "\u5DE5\u5E8F\u5168\u90E8\u5B8C\u6210\uFF1A", entity.all_operations_complete ? '是' : '否')), /*#__PURE__*/React.createElement(Issues, {
      issues: entity.issues
    })), /*#__PURE__*/React.createElement("section", {
      className: "batch-band"
    }, /*#__PURE__*/React.createElement("div", {
      className: "toolbar"
    }, /*#__PURE__*/React.createElement("h3", null, "\u2460 \u6279\u6B21\u57FA\u7840\u4FE1\u606F"), /*#__PURE__*/React.createElement("span", {
      className: "tb-spacer"
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "square-pen",
      onClick: () => onEdit(entity),
      disabled: disabled,
      reason: reason('update')
    }, "\u7F16\u8F91\u57FA\u7840\u4FE1\u606F")), /*#__PURE__*/React.createElement("div", {
      className: "batch-readiness"
    }, /*#__PURE__*/React.createElement("span", null, "\u4EA4\u671F\uFF1A", B.label('', entity.fields.due_date)), /*#__PURE__*/React.createElement("span", null, "\u4F18\u5148\u7EA7\uFF1A", B.label('priority', entity.fields.priority)), /*#__PURE__*/React.createElement("span", null, "\u9F50\u5957\u663E\u793A\uFF1A", B.label('ready_status', entity.fields.ready_status)), /*#__PURE__*/React.createElement("span", null, "\u9F50\u5957\u65E5\u671F\uFF1A", B.label('', entity.fields.ready_date)), /*#__PURE__*/React.createElement("span", null, "\u5907\u6CE8\uFF1A", B.label('', entity.fields.remark))), entity.materials.count > 0 && /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u7269\u6599\u9F50\u5957\u539F\u8BB0\u5F55 \xB7 ", entity.materials.count, " \u9879"), /*#__PURE__*/React.createElement("div", {
      className: "card-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl",
      style: {
        minWidth: 640
      },
      "aria-label": "\u6279\u6B21\u7269\u6599\u9F50\u5957"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u7269\u6599"), /*#__PURE__*/React.createElement("th", null, "\u9700\u6C42\u91CF"), /*#__PURE__*/React.createElement("th", null, "\u5230\u6599\u91CF"), /*#__PURE__*/React.createElement("th", null, "\u5355\u4F4D"), /*#__PURE__*/React.createElement("th", null, "\u9F50\u5957\u8BB0\u5F55"))), /*#__PURE__*/React.createElement("tbody", null, entity.materials.requirements.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.material_ref
    }, /*#__PURE__*/React.createElement("td", null, row.business_code, " \xB7 ", row.label, /*#__PURE__*/React.createElement(Issues, {
      issues: row.issues
    })), /*#__PURE__*/React.createElement("td", null, B.label('', row.required_quantity)), /*#__PURE__*/React.createElement("td", null, B.label('', row.available_quantity)), /*#__PURE__*/React.createElement("td", null, row.unit || '未填写'), /*#__PURE__*/React.createElement("td", null, B.label('ready_status', row.ready_status))))))))), /*#__PURE__*/React.createElement("section", {
      className: "batch-band"
    }, /*#__PURE__*/React.createElement("h3", null, "\u2461 \u6309\u5DE5\u827A\u6A21\u677F\u540C\u6B65\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("label", null, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: strict,
      disabled: disabled,
      onChange: event => setStrict(event.target.checked)
    }), "\u8D44\u6599\u4E0D\u5B8C\u6574\u65F6\u505C\u6B62\u5237\u65B0"), /*#__PURE__*/React.createElement("p", null, "\u5F53\u524D\u6A21\u677F\uFF1A", entity.template.origin === 'managed' ? entity.template.ready ? '已确认就绪' : '尚未完成三阶段确认' : '存量模板', "\u3002"), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      disabled: disabled,
      reason: reason('sync_confirm'),
      onClick: () => onSync(entity, strict, read.result.meta.snapshot_ref)
    }, "\u6309\u6700\u65B0\u5DE5\u827A\u6A21\u677F\u5237\u65B0\u672C\u6279\u6B21\u5DE5\u5E8F")), /*#__PURE__*/React.createElement("section", {
      className: "batch-band"
    }, /*#__PURE__*/React.createElement("h3", null, "\u2462 \u5DE5\u5E8F\u6982\u51B5"), /*#__PURE__*/React.createElement("div", {
      className: "batch-readiness"
    }, /*#__PURE__*/React.createElement("span", null, "\u5DE5\u5E8F\u603B\u6570\uFF1A", entity.operations.length), /*#__PURE__*/React.createElement("span", null, "\u81EA\u5236\uFF1A", entity.operations.filter(op => op.source === 'internal').length), /*#__PURE__*/React.createElement("span", null, "\u5916\u534F\uFF1A", entity.operations.filter(op => op.source === 'external').length), /*#__PURE__*/React.createElement("span", null, "\u5DF2\u5B8C\u5DE5\uFF1A", entity.relationships.completed_count), /*#__PURE__*/React.createElement("span", null, "\u5F85\u8865\u9F50\uFF1A", entity.relationships.gap_count))), /*#__PURE__*/React.createElement("section", {
      className: "batch-band"
    }, /*#__PURE__*/React.createElement("h3", null, "\u2463 \u6279\u6B21\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("div", {
      className: "card-scroll wb-table-frame"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tbl",
      style: {
        minWidth: 1060
      },
      "aria-label": "\u6279\u6B21\u5DE5\u5E8F"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, ['工序编码', '工序', '工种', '归属', '资源补充', '完工', '操作'].map((name, index) => /*#__PURE__*/React.createElement("th", {
      key: name,
      style: {
        width: [160, 80, 130, 80, 330, 100, 130][index]
      }
    }, name)))), /*#__PURE__*/React.createElement("tbody", null, entity.operations.map(op => /*#__PURE__*/React.createElement("tr", {
      key: op.ref
    }, /*#__PURE__*/React.createElement("td", null, op.business_code), /*#__PURE__*/React.createElement("td", null, op.sequence), /*#__PURE__*/React.createElement("td", null, op.label), /*#__PURE__*/React.createElement("td", null, op.source === 'internal' ? '自制' : op.source === 'external' ? '外协' : '未归类'), /*#__PURE__*/React.createElement("td", null, op.source === 'internal' ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, op.resources.machine ? op.resources.machine.label : '设备未选', " \xB7 ", op.resources.operator ? op.resources.operator.label : '人员未选'), /*#__PURE__*/React.createElement("div", null, "\u6362\u578B ", B.label('', op.setup_hours), " / \u5355\u4EF6 ", B.label('', op.unit_hours), " \u5C0F\u65F6")) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, op.resources.supplier ? op.resources.supplier.label : '供应商未选'), /*#__PURE__*/React.createElement("div", null, op.external_group && op.external_group.merge_mode === 'merged' ? '整组 ' + B.label('', op.external_group.total_days) : '本序 ' + B.label('', op.external_days), " \u5929")), /*#__PURE__*/React.createElement(Issues, {
      issues: op.issues
    })), /*#__PURE__*/React.createElement("td", null, op.completed ? '已完工' : op.status === 'processing' ? '加工中' : op.status === 'skipped' ? '已跳过' : '未完工'), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      icon: "square-pen",
      onClick: () => onOperation(entity, op),
      disabled: disabled || !op.editable,
      reason: reason('operation_update')
    }, "\u8865\u5145\u8D44\u6599")))), !entity.operations.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 7
    }, "\u5C1A\u672A\u751F\u6210\u5DE5\u5E8F")))))));
  }
  window.BatchDetail = BatchDetail;
})();
