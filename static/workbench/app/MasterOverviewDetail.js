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
    triggerRef,
    autoFocus = true
  }) {
    const data = result && result.data,
      entity = data && data.entity;
    if (!selected) return null;
    return /*#__PURE__*/React.createElement(window.WorkbenchDetailPanel, {
      title: "\u8D44\u6599\u8BE6\u60C5",
      subtitle: entity ? entity.business_code + ' · ' + (entity.label || '名称未填写') : '正在核对所选记录',
      detailKey: selected.key || selected.entity_ref,
      onClose: onBack,
      triggerRef: triggerRef,
      autoFocus: autoFocus
    }, /*#__PURE__*/React.createElement("div", {
      className: "mo-detail"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "mo-link",
      icon: "chevron-left",
      onClick: onBack
    }, "\u8FD4\u56DE\u6E05\u5355"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }), loading && /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "loading",
      title: "\u6B63\u5728\u6838\u5BF9\u8D44\u6599\u8BE6\u60C5\u2026"
    }), entity ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "mo-detail-head"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("p", {
      className: "mo-muted"
    }, C.cell(entity, 'domain'), " \xB7 ", entity.business_code), /*#__PURE__*/React.createElement("h3", null, entity.label || '名称未填写')), /*#__PURE__*/React.createElement(Button, {
      className: "btn mo-icon",
      icon: "arrow-right",
      "aria-label": "\u5B9A\u4F4D\u5F53\u524D\u8D44\u6599",
      reason: entity.target.unavailable_reason || (!navigation ? window.WorkbenchTerms.outcomes.unavailable : ''),
      onClick: () => onMaintain(entity.target)
    })), /*#__PURE__*/React.createElement("p", {
      className: "mo-muted"
    }, /*#__PURE__*/React.createElement("span", {
      className: "mo-status",
      "data-status": entity.status
    }, C.statuses[entity.status]), " \xB7 \u5DF2\u586B ", entity.filled_fields, " / ", entity.checked_fields, " \u4E2A\u68C0\u67E5\u9879"), !entity.checks_complete && /*#__PURE__*/React.createElement("p", {
      className: "mo-muted"
    }, "\u90E8\u5206\u68C0\u67E5\u5C1A\u672A\u5B8C\u6210\uFF0C\u8BF7\u67E5\u770B\u5F85\u7EF4\u62A4\u9879\u548C\u8D44\u6599\u9879\u3002"), selected && selected.title && /*#__PURE__*/React.createElement("div", {
      className: "mo-focus"
    }, /*#__PURE__*/React.createElement("strong", null, selected.title), /*#__PURE__*/React.createElement("p", null, selected.evidence)), /*#__PURE__*/React.createElement(Tabs, {
      label: "\u8D44\u6599\u660E\u7EC6\u7C7B\u578B",
      value: section,
      onChange: onSection,
      values: [["issues", "待维护项", data.counts.issues], ["relations", "相关项", data.counts.relations], ["fields", "资料项", data.counts.fields]]
    }), /*#__PURE__*/React.createElement("div", {
      role: "tabpanel",
      "aria-label": section === 'fields' ? '资料项' : section === 'relations' ? '资料相关项' : '资料待维护项'
    }, !data.rows.length && /*#__PURE__*/React.createElement("p", {
      className: "mo-muted"
    }, section === 'relations' ? entity.relations_complete ? '暂无关联项。' : '关联资料尚未完成核对。' : entity.checks_complete ? '暂无待维护项。' : '检查尚未完成，请核对资料项。'), section === 'fields' ? data.rows.map((field, index) => /*#__PURE__*/React.createElement("dl", {
      className: "mo-field",
      key: index
    }, /*#__PURE__*/React.createElement("dt", null, field.label), /*#__PURE__*/React.createElement("dd", null, field.state === 'unknown' ? '未知' : field.state === 'missing' ? '未填写' : C.value(field.value), field.state === 'invalid' ? '（原值待核对）' : ''), /*#__PURE__*/React.createElement("dd", null, /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '数据来源': field.source
      }
    })))) : /*#__PURE__*/React.createElement("ul", {
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
    }, /*#__PURE__*/React.createElement("strong", null, item.business_code, " \xB7 ", item.label)), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '数据来源': item.source
      }
    })) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("strong", null, item.title), /*#__PURE__*/React.createElement("p", null, item.evidence), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '检查规则': item.rule
      }
    }), /*#__PURE__*/React.createElement(Button, {
      className: "mo-link",
      icon: "arrow-right",
      reasonDisplay: "inline",
      reason: item.target.unavailable_reason || (!navigation ? window.WorkbenchTerms.outcomes.unavailable : ''),
      onClick: () => onMaintain(item.target)
    }, item.action)))))), /*#__PURE__*/React.createElement(Pager, {
      detail: true,
      page: data.page,
      disabled: loading,
      onPage: onPage
    })) : !loading && !error && /*#__PURE__*/React.createElement("p", {
      className: "mo-muted"
    }, "\u6682\u65E0\u53EF\u67E5\u770B\u7684\u8D44\u6599\u3002")));
  }
  window.MasterOverviewDetail = MasterOverviewDetail;
})();
