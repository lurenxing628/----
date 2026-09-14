(function () {
  'use strict';

  const C = window.FieldContract,
    {
      Button,
      State
    } = window.FieldControls;
  function FieldTable({
    tasks,
    loading,
    loaded,
    filtered,
    onClear,
    error,
    onRetry,
    opened,
    onOpen,
    disabled
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "field-scroll wb-table-frame",
      "data-sticky-head": true,
      "data-sticky-actions": true,
      tabIndex: "0",
      "aria-label": "\u73B0\u573A\u4EFB\u52A1\u8868\u683C\u6EDA\u52A8\u533A"
    }, /*#__PURE__*/React.createElement("table", {
      className: "field-table wb-table",
      "aria-label": "\u73B0\u573A\u4EFB\u52A1\u5217\u8868"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, "\u5F53\u524D\u8303\u56F4\u7684\u5DE5\u5E8F\u5B89\u6392\u3001\u7D2F\u8BA1\u5B9E\u9645\u62A5\u5DE5\u548C\u62A5\u5DE5\u64CD\u4F5C"), /*#__PURE__*/React.createElement("colgroup", null, [22, 16, 18, 12, 8, 12, 12].map((width, index) => /*#__PURE__*/React.createElement("col", {
      key: index,
      style: {
        width: width + '%'
      }
    }))), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, ['批次 / 工序', '计划设备 / 人员', '计划开工 / 完工', '累计完成 / 计划应做', '执行剩余', '状态', '操作'].map((label, index) => /*#__PURE__*/React.createElement("th", {
      key: label,
      scope: "col",
      className: index === 0 ? 'wb-col-key' : index === 6 ? 'wb-col-actions' : undefined
    }, label)))), /*#__PURE__*/React.createElement("tbody", null, tasks.map(task => /*#__PURE__*/React.createElement(React.Fragment, {
      key: task.task_ref
    }, /*#__PURE__*/React.createElement("tr", {
      "data-field-task": task.task_ref,
      className: opened === task.task_ref ? 'field-selected' : ''
    }, /*#__PURE__*/React.createElement("td", {
      className: "wb-col-key"
    }, /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "field-link",
      disabled: disabled,
      "aria-label": task.batch_id + ' · ' + task.operation_label + ' · ' + C.pieceLabel(task),
      "aria-expanded": opened === task.task_ref,
      onClick: () => onOpen(task.task_ref)
    }, task.batch_id), /*#__PURE__*/React.createElement("small", null, task.part_name, " \xB7 ", task.operation_label), /*#__PURE__*/React.createElement("small", {
      "data-field-piece": true
    }, C.pieceLabel(task))), /*#__PURE__*/React.createElement("td", null, C.display(task.planned_machine_label), /*#__PURE__*/React.createElement("small", null, C.display(task.planned_operator_label))), /*#__PURE__*/React.createElement("td", null, C.date(task.planned_start), /*#__PURE__*/React.createElement("small", null, C.date(task.planned_end))), /*#__PURE__*/React.createElement("td", {
      "data-field-quantity": true
    }, C.display(task.execution.known_completed_quantity), " / ", C.quantity(task.quantity), /*#__PURE__*/React.createElement("small", null, "\u6279\u6B21 ", C.quantity(task.batch_quantity), " \u4EF6"), /*#__PURE__*/React.createElement("small", null, C.quantityReasons[task.quantity_reason]), /*#__PURE__*/React.createElement("small", null, task.execution.unknown_record_count ? task.execution.unknown_record_count + ' 条数量待补' : '')), /*#__PURE__*/React.createElement("td", null, C.display(task.execution.remaining_quantity)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(State, {
      value: task.execution.execution_state
    }), /*#__PURE__*/React.createElement("small", null, task.execution.data_quality === 'invalid' ? '需复核' : task.execution.data_quality === 'complete' ? '' : '资料待补')), /*#__PURE__*/React.createElement("td", {
      className: "wb-col-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: opened === task.task_ref ? 'chevron-up' : 'chevron-down',
      "aria-label": '查看报工 ' + task.batch_id + ' ' + task.operation_label + ' · ' + C.pieceLabel(task),
      disabled: disabled,
      onClick: () => onOpen(task.task_ref)
    }), " ", /*#__PURE__*/React.createElement("span", null, task.execution.reports.length, " \u6B21"))))), !tasks.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: "7"
    }, /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: loading ? 'loading' : error ? 'error' : filtered ? 'filtered' : 'empty',
      title: loading ? '正在读取现场任务…' : loaded ? '当前范围没有任务' : '现场任务尚未读取',
      hint: loaded ? '可调整报工状态、批次或计划完工日期后重新查询。' : undefined,
      action: error ? /*#__PURE__*/React.createElement(Button, {
        onClick: onRetry
      }, "\u5237\u65B0\u73B0\u573A\u4EFB\u52A1") : filtered ? /*#__PURE__*/React.createElement(Button, {
        onClick: onClear,
        disabled: disabled
      }, "\u6E05\u9664\u7B5B\u9009") : undefined
    }))))));
  }
  window.FieldTable = FieldTable;
})();
