(function () {
  'use strict';

  const {
    Icon,
    ErrorBox
  } = window.ResourceControls;
  function Button({
    className = '',
    ...props
  }) {
    return /*#__PURE__*/React.createElement(window.ResourceControls.Button, {
      ...props,
      className: 'wb-action ' + className
    });
  }
  const names = {
    batch_label: '批次',
    planned_end: '计划完工',
    finish_deviation_minutes: '完工偏差（分钟）',
    effective_processing_hours: '有效工时（小时）',
    event_time: '实际结束或事件时间',
    quantity_done: '本次数量或旧登记量',
    resource_label: '资源',
    events: '旧现场事件数',
    event_count: '旧现场事件数',
    data_quality: '完整性'
  };
  // 「清除某个筛选」按钮的可读名字，不用内部键名。
  const scopeNames = {
    plan_finish_date_from: '计划完工起日',
    plan_finish_date_to: '计划完工止日',
    batch_ref: '批次',
    query: '搜索',
    resource_type: '资源类型',
    resource_ref: '关联资源',
    focus: '分析范围'
  };
  const focuses = [['all', '全部工序'], ['unreported', '待报工'], ['unclosed', '到期未确认完成'], ['late_open', '超时未确认完成'], ['finish_late', '已确认晚完成'], ['complete', '已确认整道完工'], ['data_gaps', '数据待补']];
  function Styles() {
    return null;
  }
  function Scope({
    value,
    onChange,
    choices = {},
    busy
  }) {
    const [draft, setDraft] = React.useState(value),
      [more, setMore] = React.useState(false);
    React.useEffect(() => setDraft(value), [JSON.stringify(value)]);
    const set = patch => setDraft(old => ({
      ...old,
      ...patch
    }));
    const options = kind => choices[kind] || [];
    function selectOptions(kind, selected) {
      const rows = options(kind).slice();
      if (selected && selected !== 'unassigned' && !rows.some(row => row.ref === selected)) rows.unshift({
        ref: selected,
        label: '当前范围外的已选项'
      });
      return rows.map(row => /*#__PURE__*/React.createElement("option", {
        value: row.ref,
        key: row.ref
      }, row.label, row.available === false ? '（原资料不可用）' : ''));
    }
    return /*#__PURE__*/React.createElement("form", {
      className: "aw-scope",
      "aria-label": "\u6267\u884C\u5206\u6790\u7B5B\u9009",
      onSubmit: event => {
        event.preventDefault();
        onChange(window.ReportAPI.scope(draft));
      }
    }, /*#__PURE__*/React.createElement("p", {
      className: "rw-source-line"
    }, /*#__PURE__*/React.createElement("span", null, "\u6570\u636E\u6765\u6E90"), /*#__PURE__*/React.createElement("output", {
      className: "rw-source-value",
      "aria-label": "\u6570\u636E\u6765\u6E90"
    }, "\u5F53\u524D\u6B63\u5F0F\u8BA1\u5212")), /*#__PURE__*/React.createElement("div", {
      className: "aw-scope-main"
    }, /*#__PURE__*/React.createElement("label", null, "\u8BA1\u5212\u5B8C\u5DE5\u8D77\u65E5", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u8BA1\u5212\u5B8C\u5DE5\u8D77\u65E5",
      value: draft.plan_finish_date_from || '',
      onChange: event => set({
        plan_finish_date_from: event.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u8BA1\u5212\u5B8C\u5DE5\u6B62\u65E5", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u8BA1\u5212\u5B8C\u5DE5\u6B62\u65E5",
      value: draft.plan_finish_date_to || '',
      onChange: event => set({
        plan_finish_date_to: event.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u6279\u6B21", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u6279\u6B21\u7B5B\u9009",
      value: draft.batch_ref || '',
      onChange: event => set({
        batch_ref: event.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u5168\u90E8\u6279\u6B21"), selectOptions('batch', draft.batch_ref))), /*#__PURE__*/React.createElement("label", null, "\u641C\u7D22", /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u6279\u6B21\u6216\u5DE5\u5E8F",
      value: draft.query || '',
      onChange: event => set({
        query: event.target.value
      })
    })), /*#__PURE__*/React.createElement("div", {
      className: "aw-scope-tools"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      type: "submit",
      busy: busy,
      "aria-label": "\u67E5\u8BE2\u8303\u56F4",
      className: "primary"
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-down",
      "aria-label": "\u66F4\u591A\u7B5B\u9009",
      "aria-expanded": more,
      onClick: () => setMore(old => !old)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u6E05\u9664\u7B5B\u9009",
      onClick: () => onChange({
        source: 'production',
        ...(value.plan_ref ? {
          plan_ref: value.plan_ref
        } : {})
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "aw-scope-filters",
      hidden: !more
    }, /*#__PURE__*/React.createElement("label", null, "\u8D44\u6E90\u7C7B\u578B", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u8D44\u6E90\u7C7B\u578B",
      value: draft.resource_type || '',
      onChange: event => set({
        resource_type: event.target.value,
        resource_ref: ''
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u5168\u90E8\u8D44\u6E90"), /*#__PURE__*/React.createElement("option", {
      value: "machine"
    }, "\u8BBE\u5907"), /*#__PURE__*/React.createElement("option", {
      value: "operator"
    }, "\u4EBA\u5458"))), /*#__PURE__*/React.createElement("label", null, "\u5173\u8054\u8D44\u6E90", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5173\u8054\u8D44\u6E90",
      value: draft.resource_ref || '',
      disabled: !draft.resource_type,
      onChange: event => set({
        resource_ref: event.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u5168\u90E8\u5173\u8054\u8D44\u6E90"), /*#__PURE__*/React.createElement("option", {
      value: "unassigned"
    }, "\u672A\u586B\u5199"), selectOptions(draft.resource_type, draft.resource_ref))), /*#__PURE__*/React.createElement("label", null, "\u5206\u6790\u8303\u56F4", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5206\u6790\u8303\u56F4",
      value: draft.focus || 'all',
      onChange: event => set({
        focus: event.target.value
      })
    }, focuses.map(([key, label]) => /*#__PURE__*/React.createElement("option", {
      value: key,
      key: key
    }, label))))), /*#__PURE__*/React.createElement("div", {
      className: "aw-scope-summary"
    }, /*#__PURE__*/React.createElement("ul", null, Object.entries(value).filter(([key, item]) => !['source', 'plan_ref'].includes(key) && item && item !== 'all').map(([key, item]) => /*#__PURE__*/React.createElement("li", {
      key: key
    }, /*#__PURE__*/React.createElement("span", null, key === 'query' ? item : key === 'focus' ? (focuses.find(row => row[0] === item) || [null, item])[1] : key.endsWith('_ref') ? Object.values(choices).flat().find(row => row.ref === item)?.label || '已选资源' : item === 'machine' ? '设备' : item === 'operator' ? '人员' : item), /*#__PURE__*/React.createElement("button", {
      type: "button",
      "aria-label": '清除' + (scopeNames[key] || '筛选项'),
      onClick: () => {
        const next = {
          ...value
        };
        delete next[key];
        if (key === 'resource_type') delete next.resource_ref;
        if (key.startsWith('plan_finish_date')) {
          delete next.plan_finish_date_from;
          delete next.plan_finish_date_to;
        }
        onChange(next);
      }
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "x"
    })))))));
  }
  function Tabs({
    topic,
    onChange
  }) {
    const labels = ['工序完成情况', '报工记录', '设备工时', '人员工时', '数据完整性'];
    return /*#__PURE__*/React.createElement("div", {
      className: "rw-tabs",
      role: "tablist",
      "aria-label": "\u62A5\u8868\u4E13\u9898"
    }, window.ReportAPI.topics.map((key, index) => /*#__PURE__*/React.createElement("button", {
      key: key,
      id: 'report-tab-' + key,
      type: "button",
      role: "tab",
      "aria-selected": topic === key,
      "aria-controls": "report-topic-panel",
      tabIndex: topic === key ? 0 : -1,
      onClick: () => onChange(key),
      onKeyDown: event => {
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? 4 : (index + (event.key === 'ArrowRight' ? 1 : -1) + 5) % 5;
        onChange(window.ReportAPI.topics[next]);
        document.getElementById('report-tab-' + window.ReportAPI.topics[next]).focus();
      }
    }, labels[index])));
  }
  function Page({
    page,
    onChange,
    busy
  }) {
    return /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: page.number,
      pages: page.pages,
      total: page.total,
      size: page.size,
      sizes: [10, 20, 50],
      label: "",
      busy: busy,
      onPage: number => onChange({
        page: number
      }),
      onSize: size => onChange({
        page: 1,
        size
      })
    });
  }
  function Sort({
    topic,
    state,
    onChange
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("label", null, "\u6392\u5E8F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u6392\u5E8F\u5217",
      value: state.sort,
      onChange: event => onChange({
        sort: event.target.value,
        page: 1
      })
    }, window.ReportAPI.sorts[topic].map(key => /*#__PURE__*/React.createElement("option", {
      value: key,
      key: key
    }, names[key])))), /*#__PURE__*/React.createElement("label", null, "\u987A\u5E8F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u6392\u5E8F\u65B9\u5411",
      value: state.direction,
      onChange: event => onChange({
        direction: event.target.value,
        page: 1
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "asc"
    }, "\u5347\u5E8F"), /*#__PURE__*/React.createElement("option", {
      value: "desc"
    }, "\u964D\u5E8F"))));
  }
  function useRead(load, identity) {
    const [result, setResult] = React.useState(null),
      [error, setError] = React.useState(null),
      [busy, setBusy] = React.useState(true);
    React.useEffect(() => {
      const controller = new AbortController();
      let active = true;
      setBusy(true);
      setError(null);
      setResult(null);
      Promise.resolve().then(() => load(controller.signal)).then(value => {
        if (active) setResult(value);
      }, failure => {
        if (active) setError(failure);
      }).finally(() => {
        if (active) setBusy(false);
      });
      return () => {
        active = false;
        controller.abort();
      };
    }, [identity]);
    return {
      result,
      error,
      busy
    };
  }
  window.ReportControls = {
    Scope,
    Tabs,
    Page,
    Sort,
    useRead,
    Button,
    Icon,
    ErrorBox,
    Styles
  };
})();
