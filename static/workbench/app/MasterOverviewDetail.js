(function () {
  'use strict';

  const C = window.APSMasterOverviewContract,
    {
      Button,
      ErrorBox
    } = window.ResourceControls;
  const {
    Tabs,
    Pager
  } = window.MasterOverviewTable;
  function MasterOverviewDetail({
    result,
    selected,
    section,
    onSection,
    onPage,
    onLocate,
    onMaintain,
    onBack,
    navigation,
    loading,
    error,
    panelRef
  }) {
    const data = result && result.data,
      entity = data && data.entity;
    return /*#__PURE__*/React.createElement("aside", {
      className: "mo-detail",
      "aria-label": "\u4E3B\u6570\u636E\u5B9E\u4F53\u8BE6\u60C5",
      tabIndex: -1,
      ref: panelRef
    }, /*#__PURE__*/React.createElement(Button, {
      className: "mo-link",
      icon: "chevron-left",
      onClick: onBack,
      disabled: !selected
    }, "\u8FD4\u56DE\u6E05\u5355"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), loading && /*#__PURE__*/React.createElement("p", {
      role: "status",
      className: "mo-muted"
    }, "\u6B63\u5728\u6838\u5BF9\u5B9E\u4F53\u8BE6\u60C5\u2026"), entity ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "mo-detail-head"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
      className: "mo-muted"
    }, C.cell(entity, 'domain'), " \xB7 ", entity.business_code), /*#__PURE__*/React.createElement("h3", null, entity.label || '名称未填')), /*#__PURE__*/React.createElement(Button, {
      className: "btn mo-icon",
      icon: "arrow-right",
      "aria-label": "\u5B9A\u4F4D\u5F53\u524D\u5B9E\u4F53",
      reason: entity.target.unavailable_reason || (!navigation ? '维护导航尚未接入。' : ''),
      onClick: () => onMaintain(entity.target)
    })), /*#__PURE__*/React.createElement("p", {
      className: "mo-muted"
    }, /*#__PURE__*/React.createElement("span", {
      className: "mo-status",
      "data-status": entity.status
    }, C.statuses[entity.status]), " \xB7 \u5DF2\u586B ", entity.filled_fields, " / ", entity.checked_fields, " \u4E2A\u68C0\u67E5\u5B57\u6BB5"), !entity.checks_complete && /*#__PURE__*/React.createElement("p", {
      className: "mo-muted"
    }, "\u90E8\u5206\u6765\u6E90\u6216\u68C0\u67E5\u65E0\u6CD5\u6838\u5B9E\u3002"), selected && selected.title && /*#__PURE__*/React.createElement("div", {
      className: "mo-focus"
    }, /*#__PURE__*/React.createElement("strong", null, selected.title), /*#__PURE__*/React.createElement("p", null, selected.evidence)), /*#__PURE__*/React.createElement(Tabs, {
      label: "\u5B9E\u4F53\u660E\u7EC6\u7C7B\u578B",
      value: section,
      onChange: onSection,
      values: [["issues", "待维护项", data.counts.issues], ["relations", "相关项", data.counts.relations], ["fields", "字段", data.counts.fields]]
    }), /*#__PURE__*/React.createElement("div", {
      role: "tabpanel",
      "aria-label": section === 'fields' ? '实体字段' : section === 'relations' ? '实体相关项' : '实体待维护项'
    }, !data.rows.length && /*#__PURE__*/React.createElement("p", {
      className: "mo-muted"
    }, section === 'relations' ? entity.relations_complete ? '已读取记录中没有可确认的关联项。' : '关联来源不完整，不能认定无关联。' : entity.checks_complete ? '已检查字段未发现待维护项。' : '检查来源不完整，结果未知。'), section === 'fields' ? data.rows.map((field, index) => /*#__PURE__*/React.createElement("dl", {
      className: "mo-field",
      key: index
    }, /*#__PURE__*/React.createElement("dt", null, field.label), /*#__PURE__*/React.createElement("dd", null, field.state === 'unknown' ? '未知' : field.state === 'missing' ? '未填' : C.value(field.value), field.state === 'invalid' ? '（原值待核对）' : ''), /*#__PURE__*/React.createElement("dd", {
      className: "mo-source"
    }, field.source))) : /*#__PURE__*/React.createElement("ul", {
      className: "mo-detail-list"
    }, data.rows.map((item, index) => /*#__PURE__*/React.createElement("li", {
      key: (item.issue_ref || item.key) + ':' + index
    }, section === 'relations' ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "mo-muted"
    }, item.relation), /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "mo-link",
      onClick: () => item.domain === 'batch' ? onMaintain(item.target) : onLocate({
        domain: item.domain,
        entity_ref: item.ref
      }),
      disabled: item.domain === 'batch' && !navigation
    }, /*#__PURE__*/React.createElement("strong", null, item.business_code, " \xB7 ", item.label)), /*#__PURE__*/React.createElement("p", {
      className: "mo-source"
    }, item.source)) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("strong", null, item.title), /*#__PURE__*/React.createElement("p", null, item.evidence), /*#__PURE__*/React.createElement("p", {
      className: "mo-source"
    }, item.rule), /*#__PURE__*/React.createElement(Button, {
      className: "mo-link",
      icon: "arrow-right",
      reason: item.target.unavailable_reason || (!navigation ? '维护导航尚未接入。' : ''),
      onClick: () => onMaintain(item.target)
    }, item.action)))))), /*#__PURE__*/React.createElement(Pager, {
      detail: true,
      page: data.page,
      disabled: loading,
      onPage: onPage
    })) : !loading && !error && /*#__PURE__*/React.createElement("p", {
      className: "mo-muted"
    }, "\u6682\u65E0\u53EF\u67E5\u770B\u7684\u5B9E\u4F53\u3002"));
  }
  window.MasterOverviewDetail = MasterOverviewDetail;
})();
