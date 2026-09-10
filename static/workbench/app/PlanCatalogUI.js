(function () {
  'use strict';

  const {
    Button,
    ErrorBox,
    Issues
  } = window.ResourceControls;
  const C = window.APSResourceContract,
    P = window.APSPlanContract,
    S = window.APSResourceSession;
  function Identity({
    plan
  }) {
    const unavailable = !plan.capabilities.view;
    const text = plan.is_current_official ? '当前正式' : plan.kind === 'official' ? '历史正式' : plan.kind === 'candidate' ? '候选预览' : '场景预览';
    return /*#__PURE__*/React.createElement("span", {
      className: 'plan-state ' + (unavailable ? 'unavailable' : plan.is_current_official ? 'official' : '')
    }, text, unavailable ? ' · 不可查看' : '');
  }
  function Catalog({
    adapter,
    selectedRef,
    onSelect,
    disabled = false
  }) {
    const [collection, setCollection] = React.useState('history'),
      [pages, setPages] = React.useState([{}]),
      [index, setIndex] = React.useState(0);
    const [paused, setPaused] = React.useState(false),
      [collapsed, setCollapsed] = React.useState(false);
    const scope = React.useMemo(() => ({
      collection,
      size: 20,
      ...pages[index]
    }), [collection, pages, index]);
    const read = S.useQuery(async signal => {
      if (typeof adapter.catalog !== 'function') throw C.failure('计划目录接口尚未接入。');
      return P.catalog(await adapter.catalog(scope, signal), scope);
    }, [adapter, scope], !paused);
    const result = read.result,
      data = result && result.data;
    function refresh(next = collection) {
      setCollection(next);
      setPages([{}]);
      setIndex(0);
      setPaused(false);
      read.reload();
    }
    function next() {
      const page = {
        cursor: data.page.next_cursor,
        snapshot_ref: result.meta.snapshot_ref
      };
      setPages(current => current.slice(0, index + 1).map(item => ({
        ...item,
        snapshot_ref: result.meta.snapshot_ref
      })).concat(page));
      setIndex(index + 1);
    }
    return /*#__PURE__*/React.createElement("section", {
      className: "plan-catalog",
      "aria-label": "\u6392\u4EA7\u65B9\u6848\u76EE\u5F55"
    }, /*#__PURE__*/React.createElement("div", {
      className: "plan-toolbar"
    }, /*#__PURE__*/React.createElement(window.PlanSegmentUI, {
      value: collection,
      options: [["history", "历史版本"], ["scenario", "已存场景"]],
      label: "\u8BA1\u5212\u76EE\u5F55\u8303\u56F4",
      onChange: refresh,
      disabled: disabled
    }), /*#__PURE__*/React.createElement("span", {
      className: "plan-muted"
    }, "\u6BCF\u6BB5 20 \u4E2A", collection === 'history' ? '版本' : '场景'), /*#__PURE__*/React.createElement("div", {
      className: "plan-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "btn plan-icon",
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u8BA1\u5212\u76EE\u5F55",
      disabled: disabled,
      busy: read.loading,
      onClick: () => refresh()
    }), read.loading && /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      className: "btn plan-icon",
      "aria-label": "\u53D6\u6D88\u76EE\u5F55\u8BFB\u53D6",
      onClick: () => setPaused(true)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-down",
      className: 'btn plan-icon' + (collapsed ? '' : ' plan-up'),
      "aria-label": collapsed ? '展开计划目录' : '收起计划目录',
      "aria-expanded": !collapsed,
      onClick: () => setCollapsed(!collapsed)
    }))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: read.error
    }), (read.error || paused) && /*#__PURE__*/React.createElement("div", {
      className: "plan-pager"
    }, /*#__PURE__*/React.createElement("span", null, paused ? '目录读取已取消。' : '目录未读取成功，原选中计划未替换。'), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: () => refresh()
    }, "\u91CD\u65B0\u8BFB\u53D6\u76EE\u5F55")), result && /*#__PURE__*/React.createElement(Issues, {
      issues: result.warnings
    }), !collapsed && /*#__PURE__*/React.createElement("div", {
      className: "plan-catalog-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      "aria-label": "\u53EF\u9009\u6392\u4EA7\u65B9\u6848",
      "aria-busy": read.loading
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u8BA1\u5212 / \u65B9\u6848"), /*#__PURE__*/React.createElement("th", null, "\u7248\u672C"), /*#__PURE__*/React.createElement("th", null, "\u8EAB\u4EFD"), /*#__PURE__*/React.createElement("th", null, "\u8BB0\u5F55\u72B6\u6001"))), /*#__PURE__*/React.createElement("tbody", null, data && data.plans.map((plan, row) => /*#__PURE__*/React.createElement("tr", {
      key: plan.plan_ref || 'unavailable-' + row,
      "aria-selected": !!plan.plan_ref && plan.plan_ref === selectedRef
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("label", {
      title: plan.blocked_reasons.map(reason => reason.message).join('\n')
    }, /*#__PURE__*/React.createElement("input", {
      type: "radio",
      name: "plan-choice",
      "aria-label": '选择 ' + plan.display_name,
      checked: !!plan.plan_ref && plan.plan_ref === selectedRef,
      disabled: disabled || !plan.capabilities.view,
      onChange: () => onSelect(plan)
    }), /*#__PURE__*/React.createElement("strong", null, plan.display_name))), /*#__PURE__*/React.createElement("td", null, plan.version === null ? '未记录' : String(plan.version)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Identity, {
      plan: plan
    })), /*#__PURE__*/React.createElement("td", null, {
      complete: '记录完整',
      partial: '部分记录',
      invalid: '无效记录',
      unknown: '无法核实'
    }[plan.completeness], plan.blocked_reasons.length > 0 && /*#__PURE__*/React.createElement("div", {
      className: "plan-muted"
    }, plan.blocked_reasons.map(reason => reason.message).join('；'))))), (!data || !data.plans.length) && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: 4,
      className: "plan-empty"
    }, read.loading ? '正在读取计划目录…' : paused ? '读取已取消' : read.error ? '目录读取失败' : '本段没有计划记录。'))))), data && /*#__PURE__*/React.createElement("div", {
      className: "plan-pager"
    }, /*#__PURE__*/React.createElement("span", null, "\u7B2C ", index + 1, " \u6BB5 \xB7 ", data.plans.length, " \u4E2A\u8EAB\u4EFD\u6761\u76EE", !data.page.has_more ? ' · 已到末段' : ''), selectedRef && !data.plans.some(plan => plan.plan_ref === selectedRef) && /*#__PURE__*/React.createElement("span", {
      className: "plan-muted"
    }, "\u5DF2\u9009\u8BA1\u5212\u4E0D\u5728\u672C\u6BB5\uFF0C\u9009\u62E9\u4FDD\u6301\u4E0D\u53D8"), /*#__PURE__*/React.createElement("div", {
      className: "plan-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      className: "btn plan-icon",
      "aria-label": "\u8BA1\u5212\u76EE\u5F55\u4E0A\u4E00\u6BB5",
      disabled: disabled || read.loading || index === 0,
      onClick: () => setIndex(index - 1)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      className: "btn plan-icon",
      "aria-label": "\u8BA1\u5212\u76EE\u5F55\u4E0B\u4E00\u6BB5",
      disabled: disabled || read.loading || !data.page.has_more,
      onClick: next
    }))));
  }
  window.PlanCatalogUI = {
    Catalog,
    Identity
  };
})();
