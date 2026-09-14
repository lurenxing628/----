(function () {
  'use strict';

  const C = window.DashboardContract,
    {
      Button,
      Issues
    } = window.ResourceControls;
  // 跳转标签与侧栏视图标题保持同名（web/routes/workbench/navigation_metadata.py VIEW_TITLES）；outsourcing 是页内目标，侧栏没有对应条目。
  const navigationLabels = {
    gantt: '计划甘特',
    fieldgantt: '现场实际甘特',
    batches: '批次管理',
    analysis: '选择排产方案',
    field: '现场记录',
    run: '执行排产',
    outsourcing: '外协物流登记'
  };
  function navigationTarget(n, onNavigate) {
    C.check(C.object(n) && Object.prototype.hasOwnProperty.call(navigationLabels, n.view) && C.object(n.context) && typeof n.enabled === 'boolean', '这条记录的跳转目标不对，页面没有跳转。请刷新后重试。');
    C.check(n.view === 'outsourcing' ? typeof window.OutsourcingWorkspace === 'function' : typeof onNavigate === 'function', 'dependency not wired: window.OutsourcingWorkspace / props.onNavigate');
    C.check(n.enabled || typeof n.reason === 'string' && n.reason.trim().length > 0, '这条记录暂时打不开，页面没有跳转。请刷新后重试。');
    return navigationLabels[n.view];
  }
  const value = v => v === null || v === undefined || v === '' ? '未填写' : typeof v === 'boolean' ? v ? '是' : '否' : String(v);
  const hours = v => window.WorkbenchFormat.hours(v, 2);
  function Risk({
    risk
  }) {
    return /*#__PURE__*/React.createElement("span", {
      className: 'dy-badge ' + (risk.active === true ? 'danger' : risk.active === false ? 'success' : 'warning')
    }, risk.active === true ? '风险仍在' : risk.active === false ? '当前无风险' : '风险未知');
  }
  function Status({
    handling
  }) {
    return /*#__PURE__*/React.createElement("span", {
      className: 'dy-badge ' + {
        new: 'neutral',
        following: 'info',
        awaiting_verification: 'warning',
        closed: 'success'
      }[handling.status]
    }, C.statuses[handling.status]);
  }
  function CategoryState({
    summary
  }) {
    if (!summary) return /*#__PURE__*/React.createElement("span", null, "\u672A\u8BFB\u53D6");
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", null, C.states[summary.state], summary.risk_count === null ? ' · 总风险未知' : ' · ' + summary.risk_count + ' 项风险'), summary.risk_count === null && summary.known_risk_count > 0 && /*#__PURE__*/React.createElement("small", null, "\u5DF2\u786E\u8BA4 ", summary.known_risk_count, " \u9879\u98CE\u9669"));
  }
  function Overview({
    data,
    analysis,
    onCategory,
    onAnalysis
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "dy-metrics",
      "aria-label": "\u98CE\u9669\u6982\u89C8"
    }, ['delivery', 'pressure', 'actual', 'external', 'downtime', 'material', 'pending'].map(k => {
      if (k === 'pressure' || k === 'pending') {
        const p = analysis && analysis[k === 'pressure' ? 'pressure' : 'pending'];
        return /*#__PURE__*/React.createElement("button", {
          type: "button",
          className: "dy-metric",
          key: k,
          onClick: () => onAnalysis(k === 'pressure' ? 'delivery' : 'material')
        }, /*#__PURE__*/React.createElement("span", null, k === 'pressure' ? '资源压力' : '待排批次'), /*#__PURE__*/React.createElement("strong", null, !p ? '未读取' : p.count === null ? '未知' : p.count), /*#__PURE__*/React.createElement("small", null, k === 'pressure' ? '≥90% · 同范围日峰值' : '本机全部待排批次'), p && k === 'pressure' && (p.unknown_resources > 0 || p.zero_capacity_resources > 0) && /*#__PURE__*/React.createElement("small", null, "\u5BB9\u91CF\u672A\u77E5 ", p.unknown_resources, " \xB7 \u96F6\u53EF\u7528 ", p.zero_capacity_resources));
      }
      const s = data && data.categories[k];
      return /*#__PURE__*/React.createElement("button", {
        type: "button",
        className: "dy-metric",
        key: k,
        onClick: () => onCategory(k)
      }, /*#__PURE__*/React.createElement("span", null, C.categories[k]), /*#__PURE__*/React.createElement("strong", {
        className: s && s.risk_count > 0 ? 'dy-danger' : 'dy-muted'
      }, !s ? '未读取' : s.risk_count === null ? C.states[s.state] === '已读取' ? '未知' : C.states[s.state] : s.risk_count), /*#__PURE__*/React.createElement("small", null, !s ? '未读取' : k === 'external' ? s.awaiting_return_count === null ? '外协风险未读取' : '待回厂 ' + s.awaiting_return_count + ' · 超期 ' + s.overdue_count + ' · 待确认 ' + s.awaiting_confirmation_count : s.risk_count === null ? s.known_risk_count > 0 ? '已确认风险 ' + s.known_risk_count + ' 项' : '总风险未评估' : '已关闭处置 ' + s.closed_count + ' 项'));
    }));
  }
  function Rail({
    data,
    category,
    onCategory
  }) {
    return /*#__PURE__*/React.createElement("aside", {
      className: "dy-rail",
      "aria-label": "\u98CE\u9669\u7C7B\u522B"
    }, /*#__PURE__*/React.createElement("h3", null, "\u9700\u8981\u5173\u6CE8"), Object.entries(C.categories).map(([k, label]) => /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "dy-category",
      key: k,
      "aria-pressed": category === k,
      onClick: () => onCategory(k)
    }, /*#__PURE__*/React.createElement("b", null, label), /*#__PURE__*/React.createElement("small", null, k === 'all' ? '风险与处置分别核对' : k === 'candidate' ? data ? C.states[data.candidate_catalog.state] + ' · 列表不计风险' : '未读取' : /*#__PURE__*/React.createElement(CategoryState, {
      summary: data && data.categories[k]
    })))));
  }
  function Filters({
    query,
    busy,
    onChange
  }) {
    const [draft, setDraft] = React.useState(query.query);
    React.useEffect(() => setDraft(query.query), [query.query]);
    return /*#__PURE__*/React.createElement("form", {
      className: "dy-filters",
      onSubmit: e => {
        e.preventDefault();
        onChange({
          query: draft
        });
      }
    }, /*#__PURE__*/React.createElement("label", {
      className: "dy-search"
    }, "\u6761\u76EE\u641C\u7D22", /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u6761\u76EE\u3001\u8D23\u4EFB\u4EBA\u3001\u884C\u52A8\u6216\u5907\u6CE8",
      value: draft,
      maxLength: 200,
      onChange: e => setDraft(e.target.value)
    })), /*#__PURE__*/React.createElement("label", null, "\u5904\u7F6E\u72B6\u6001", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5904\u7F6E\u72B6\u6001",
      value: query.status,
      onChange: e => onChange({
        status: e.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "all"
    }, "\u5168\u90E8\u72B6\u6001"), /*#__PURE__*/React.createElement("option", {
      value: "open"
    }, "\u672A\u5173\u95ED"), Object.entries(C.statuses).map(([k, label]) => /*#__PURE__*/React.createElement("option", {
      value: k,
      key: k
    }, label)))), /*#__PURE__*/React.createElement("label", null, "\u6392\u5E8F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u6392\u5E8F",
      value: query.sort,
      onChange: e => onChange({
        sort: e.target.value
      })
    }, [['subject', '涉及记录'], ['category', '风险类别'], ['status', '处置状态'], ['deadline', '责任期限']].map(([k, label]) => /*#__PURE__*/React.createElement("option", {
      key: k,
      value: k
    }, label)))), /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: "chevron-down",
      className: 'btn dy-sort-' + query.direction,
      "aria-label": query.direction === 'asc' ? '改为降序' : '改为升序',
      onClick: () => onChange({
        direction: query.direction === 'asc' ? 'desc' : 'asc'
      })
    }), /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      type: "submit",
      icon: "search",
      "aria-label": "\u6267\u884C\u6761\u76EE\u641C\u7D22",
      busy: busy
    }), /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: "x",
      "aria-label": "\u6E05\u9664\u6761\u76EE\u7B5B\u9009",
      onClick: () => {
        setDraft('');
        onChange({
          query: '',
          status: 'all'
        });
      }
    }));
  }
  function Pager({
    page,
    busy,
    onPage,
    onSize,
    label = '清单'
  }) {
    return /*#__PURE__*/React.createElement(window.WorkbenchListControls.Pager, {
      page: page,
      sizes: [10, 20, 50, 100].concat([page.size]).filter((v, i, a) => a.indexOf(v) === i).sort((a, b) => a - b),
      busy: busy,
      onPage: onPage,
      onSize: onSize,
      label: label,
      sizeLabel: "\u6BCF\u9875\u6761\u76EE\u6570",
      unit: "\u9879"
    });
  }
  function List({
    data,
    selected,
    onSelect,
    query,
    onClear
  }) {
    const filtered = !!query && (query.query !== '' || query.status !== 'all');
    if (!data.items.length) return /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: filtered ? 'filtered' : 'empty',
      title: data.page.total === 0 ? '当前筛选没有条目。' : '当前页没有条目。',
      hint: data.categories.external.state === 'not_connected' ? '外协风险还没有开通，这里的空白不代表没有风险。' : '这里只统计已读到的范围，读不到或无法评估的来源会单独列出。',
      action: filtered ? /*#__PURE__*/React.createElement(Button, {
        reasonDisplay: "inline",
        icon: "x",
        onClick: onClear
      }, "\u6E05\u9664\u7B5B\u9009\u5E76\u67E5\u770B\u5904\u7F6E\u6E05\u5355") : null
    });
    return /*#__PURE__*/React.createElement("div", {
      className: "wb-table-frame dy-scroll",
      "data-sticky-head": true,
      "data-sticky-actions": true
    }, /*#__PURE__*/React.createElement("table", {
      className: "wb-table dy-table"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-sr-only"
    }, "\u503C\u73ED\u53F0\u98CE\u9669\u4E0E\u5904\u7F6E\u6E05\u5355"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-key"
    }, "\u6D89\u53CA\u8BB0\u5F55 / \u7C7B\u522B"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u98CE\u9669\u8BF4\u660E"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5904\u7F6E\u72B6\u6001"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u8D23\u4EFB\u4EBA / \u671F\u9650"), /*#__PURE__*/React.createElement("th", {
      scope: "col",
      className: "wb-col-actions"
    }, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, data.items.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.item_ref,
      "data-item-ref": row.item_ref,
      "data-category": row.category,
      "data-selected": selected === row.item_ref
    }, /*#__PURE__*/React.createElement("td", {
      className: "wb-col-key"
    }, /*#__PURE__*/React.createElement("b", null, row.subject), /*#__PURE__*/React.createElement("div", {
      className: "dy-muted"
    }, C.categories[row.category])), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Risk, {
      risk: row.risk
    }), /*#__PURE__*/React.createElement("div", null, row.risk.message)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Status, {
      handling: row.handling
    }), /*#__PURE__*/React.createElement("div", {
      className: "dy-muted"
    }, "\u5386\u53F2 ", row.handling.history_count, " \u6761")), /*#__PURE__*/React.createElement("td", null, value(row.handling.owner), /*#__PURE__*/React.createElement("div", {
      className: row.handling.deadline_overdue ? 'dy-danger' : 'dy-muted'
    }, value(row.handling.deadline), row.handling.deadline_overdue ? ' · 处置超期' : '')), /*#__PURE__*/React.createElement("td", {
      className: "wb-col-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      className: "mini",
      icon: "search",
      "aria-label": '查看 ' + row.subject + ' ' + C.categories[row.category],
      onClick: () => onSelect(row.item_ref)
    }, "\u8BE6\u60C5")))))));
  }
  function Gaps({
    categories,
    selected
  }) {
    const rows = Object.entries(categories).filter(([key]) => selected === 'all' || key === selected),
      seen = new Set(),
      issues = [];
    let count = 0;
    rows.forEach(([, summary]) => summary.issues.forEach(issue => {
      count += 1;
      const key = JSON.stringify(issue);
      if (!seen.has(key)) {
        seen.add(key);
        issues.push(issue);
      }
    }));
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Issues, {
      issues: issues
    }), count > issues.length && /*#__PURE__*/React.createElement("details", {
      className: "dy-evidence"
    }, /*#__PURE__*/React.createElement("summary", null, "\u67E5\u770B\u5404\u6765\u6E90\u8BFB\u53D6\u72B6\u6001"), /*#__PURE__*/React.createElement("dl", {
      className: "dy-facts"
    }, rows.filter(([, summary]) => summary.issues.length).map(([key, summary]) => /*#__PURE__*/React.createElement("div", {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, C.categories[key]), /*#__PURE__*/React.createElement("dd", null, /*#__PURE__*/React.createElement(CategoryState, {
      summary: summary
    })))))), rows.map(([key, summary]) => summary.evaluation_gaps.length > 0 && /*#__PURE__*/React.createElement("details", {
      key: key,
      className: "dy-evidence"
    }, /*#__PURE__*/React.createElement("summary", null, C.categories[key], " \xB7 \u65E0\u6CD5\u8BC4\u4F30 ", summary.unknown_count, " \u9879"), summary.evaluation_gaps.map(gap => /*#__PURE__*/React.createElement("p", {
      key: gap.source_ref
    }, gap.subject, "\uFF1A", gap.message)))));
  }
  function Facts({
    handling
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("dl", {
      className: "dy-facts"
    }, ['status', ...C.fields.filter(k => k !== 'evidence_ref')].map(k => /*#__PURE__*/React.createElement("div", {
      key: k
    }, /*#__PURE__*/React.createElement("dt", null, C.labels[k]), /*#__PURE__*/React.createElement("dd", null, k === 'status' ? C.statuses[handling.status] : k === 'completed_at' ? window.WorkbenchFormat.dateTime(handling[k]) : value(handling[k]))))), handling.evidence_ref ? /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '已核验附件编号': handling.evidence_ref
      }
    }) : /*#__PURE__*/React.createElement("p", {
      className: "dy-muted"
    }, "\u672A\u5173\u8054\u5DF2\u6838\u9A8C\u9644\u4EF6"));
  }
  function Evidence({
    source
  }) {
    return /*#__PURE__*/React.createElement(window.DashboardEvidence.Evidence, {
      source: source
    });
  }
  function Detail({
    item,
    onHandle,
    onHistory,
    navigate,
    canNavigate,
    onClose
  }) {
    return /*#__PURE__*/React.createElement(window.WorkbenchDetailPanel, {
      title: "\u98CE\u9669\u6761\u76EE\u8BE6\u60C5",
      subtitle: item.subject + ' · ' + C.categories[item.category],
      detailKey: item.item_ref,
      onClose: onClose
    }, /*#__PURE__*/React.createElement("section", {
      className: "dy-detail",
      "aria-label": "\u6761\u76EE\u8BE6\u60C5",
      "data-detail-ref": item.item_ref
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-heading"
    }, /*#__PURE__*/React.createElement("h3", null, item.subject, " \xB7 ", C.categories[item.category]), /*#__PURE__*/React.createElement("div", {
      className: "dy-tools"
    }, /*#__PURE__*/React.createElement(Risk, {
      risk: item.risk
    }), /*#__PURE__*/React.createElement(Status, {
      handling: item.handling
    }))), /*#__PURE__*/React.createElement("p", null, item.risk.message), /*#__PURE__*/React.createElement(Facts, {
      handling: item.handling
    }), /*#__PURE__*/React.createElement(Evidence, {
      source: item.source
    }), /*#__PURE__*/React.createElement("div", {
      className: "dy-tools"
    }, /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: item.handling.status === 'closed' ? 'refresh-cw' : 'square-pen',
      onClick: onHandle
    }, item.handling.status === 'closed' ? '独立重开' : '登记处置'), /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: "history",
      onClick: onHistory
    }, "\u67E5\u770B\u5904\u7F6E\u5386\u53F2"), item.navigation.map((n, i) => /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      key: i,
      icon: "arrow-right",
      onClick: () => navigate(n, item)
    }, n.view === 'outsourcing' ? '外协物流登记' : navigationLabels[n.view] || '未知跳转目标')), item.category === 'actual' && item.navigation.some(n => n.enabled && n.command_context === 'read_execution_write_context') && /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: "arrow-right",
      reason: !canNavigate ? window.WorkbenchTerms.outcomes.unavailable : '',
      onClick: () => navigate({
        ...item.navigation[0],
        view: 'field'
      })
    }, navigationLabels.field)), item.category === 'external' && /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, "\u5173\u95ED\u98CE\u9669\u5904\u7F6E\u4E0D\u4EE3\u8868\u5DF2\u56DE\u5382\uFF0C\u4E5F\u4E0D\u4EE3\u8868\u5DE5\u5E8F\u5B8C\u5DE5\u3002\u7269\u6D41\u767B\u8BB0\u548C\u5904\u7F6E\u5386\u53F2\u5206\u5F00\u4FDD\u5B58\u3002"), item.handling.status === 'closed' && /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, "\u5904\u7F6E\u5DF2\u5173\u95ED\uFF0C\u98CE\u9669\u4ECD\u6309\u6700\u65B0\u6570\u636E\u7EE7\u7EED\u8BC4\u4F30\u3002")));
  }
  function NavigationConfirmation({
    entry,
    error,
    onClose,
    onConfirm
  }) {
    const {
        Modal,
        ErrorBox
      } = window.ResourceControls,
      {
        item,
        navigation,
        label
      } = entry;
    return /*#__PURE__*/React.createElement(Modal, {
      title: "\u8FD9\u6761\u8BB0\u5F55\u6682\u65F6\u6253\u4E0D\u5F00",
      icon: "circle-alert",
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        reasonDisplay: "inline",
        icon: "x",
        onClick: onClose
      }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
        reasonDisplay: "inline",
        icon: "arrow-right",
        onClick: onConfirm
      }, "\u6253\u5F00", label, "\u6982\u89C8"))
    }, /*#__PURE__*/React.createElement("div", {
      className: "modal-b scroll",
      style: {
        overflowWrap: 'anywhere'
      }
    }, /*#__PURE__*/React.createElement("h3", null, item.subject, " \xB7 ", C.categories[item.category]), /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, navigation.reason), /*#__PURE__*/React.createElement("div", {
      className: "dy-context"
    }, item.source_state === 'current' ? '当前来源' : '这条来源现在没有评估'), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '条目编号': item.item_ref
      }
    }), /*#__PURE__*/React.createElement(Evidence, {
      source: item.source
    }), /*#__PURE__*/React.createElement("p", null, "\u8FD9\u6761\u8BB0\u5F55\u548C\u5B83\u7684\u5904\u7F6E\u72B6\u6001\u90FD\u6CA1\u6709\u53D8\u3002"), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    })));
  }
  function Pressure({
    data,
    navigate,
    canNavigate
  }) {
    const p = data.resource_pressure,
      rows = p.resources;
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u8D44\u6E90\u538B\u529B"
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u6B63\u5F0F\u8BA1\u5212\u8D44\u6E90\u538B\u529B"), data.plan && /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: "arrow-right",
      reason: !canNavigate ? window.WorkbenchTerms.outcomes.unavailable : '',
      onClick: () => navigate({
        view: 'gantt',
        context: {
          plan_ref: data.plan.plan_ref
        },
        enabled: true
      })
    }, "\u8BA1\u5212\u7518\u7279")), /*#__PURE__*/React.createElement("div", {
      className: "dy-context"
    }, data.plan ? data.plan.display_name : data.categories.delivery.state === 'no_official_plan' ? '无正式计划' : '正式计划未能读取', " \xB7 ", p.time_scope ? window.WorkbenchFormat.dateTime(p.time_scope.range_start) + ' 至 ' + window.WorkbenchFormat.dateTime(p.time_scope.range_end) + ' · 含起日，不含止日' : '时间范围未读取'), /*#__PURE__*/React.createElement(Issues, {
      issues: p.issues
    }), /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, "\u5360\u7528\u5C0F\u65F6\u4E0D\u7B49\u4E8E\u6709\u6548\u52A0\u5DE5\u5DE5\u65F6\u3002", /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u8BF4\u660E"), "\u53EF\u7528\u4EA7\u80FD\u672A\u77E5\u65F6\uFF0C\u5229\u7528\u7387\u4E5F\u6309\u672A\u77E5\u663E\u793A\u3002\u505C\u673A\u548C\u73ED\u8868\u90FD\u6309\u540C\u4E00\u4EFD\u6B63\u5F0F\u8BA1\u5212\u6838\u5BF9\u3002")), !rows || !rows.length ? /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "empty",
      title: !rows ? '资源压力无法评估，这里不会按零负荷显示。' : '当前正式计划没有资源占用数据。'
    }) : /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "dy-resource"
    }, /*#__PURE__*/React.createElement("caption", {
      className: "wb-sr-only"
    }, "\u6B63\u5F0F\u8BA1\u5212\u8D44\u6E90\u538B\u529B"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u8D44\u6E90"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5360\u7528 / \u5B89\u6392"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u53EF\u7528"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, window.WorkbenchTerms.utilization), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u91CD\u53E0\u5360\u7528"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u73ED\u8868\u5916\u5360\u7528"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5BB9\u91CF\u7F3A\u53E3"))), /*#__PURE__*/React.createElement("tbody", null, rows.map(r => /*#__PURE__*/React.createElement("tr", {
      key: r.kind + r.resource_ref,
      "data-resource-ref": r.resource_ref
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("b", null, r.label || '名称未填写'), /*#__PURE__*/React.createElement("div", {
      className: "dy-muted"
    }, r.kind === 'machine' ? '设备' : '人员', " \xB7 ", r.operation_count, " \u9053\u5DE5\u5E8F")), /*#__PURE__*/React.createElement("td", null, hours(r.occupied_hours), " / ", hours(r.arranged_hours)), /*#__PURE__*/React.createElement("td", null, hours(r.available_hours)), /*#__PURE__*/React.createElement("td", null, window.WorkbenchFormat.percent(r.utilization), r.utilization !== null && /*#__PURE__*/React.createElement("div", {
      className: 'dy-meter' + (r.capacity_insufficient || r.has_overlap ? ' hot' : '')
    }, /*#__PURE__*/React.createElement("i", {
      style: {
        width: Math.min(100, Math.max(0, r.utilization * 100)) + '%'
      }
    }))), /*#__PURE__*/React.createElement("td", {
      className: r.has_overlap ? 'dy-danger' : ''
    }, hours(r.overlap_hours)), /*#__PURE__*/React.createElement("td", {
      className: r.outside_available_hours > 0 ? 'dy-warning' : ''
    }, hours(r.outside_available_hours)), /*#__PURE__*/React.createElement("td", null, hours(r.capacity_shortfall_hours), /*#__PURE__*/React.createElement(Issues, {
      issues: r.issues
    }))))))));
  }
  function Candidates({
    data,
    navigate,
    canNavigate
  }) {
    const c = data.candidate_catalog,
      runStates = {
        queued: '排队中',
        running: '计算中',
        complete: '计算完成',
        partial: '部分完成',
        failed: '失败',
        interrupted: '已中断'
      };
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5019\u9009\u65B9\u6848\u5217\u8868"
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5019\u9009\u65B9\u6848\u5217\u8868"), /*#__PURE__*/React.createElement("div", {
      className: "dy-tools"
    }, /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: "history",
      reason: !canNavigate ? window.WorkbenchTerms.outcomes.unavailable : '',
      onClick: () => navigate({
        view: 'analysis',
        context: {
          source: 'run_history'
        },
        enabled: true
      })
    }, "\u6392\u4EA7\u8BB0\u5F55"), /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: "play",
      reason: !canNavigate ? window.WorkbenchTerms.outcomes.unavailable : '',
      onClick: () => navigate({
        view: 'run',
        context: {},
        enabled: true
      })
    }, "\u53BB\u6267\u884C\u6392\u4EA7"))), /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, "\u5DF2\u4FDD\u5B58\u7684\u6392\u4EA7\u8BB0\u5F55 \xB7 \u4E0D\u662F\u5F53\u524D\u6B63\u5F0F\u8BA1\u5212"), /*#__PURE__*/React.createElement(Issues, {
      issues: c.issues
    }), c.state === 'unavailable' ? /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "empty",
      title: "\u5019\u9009\u65B9\u6848\u5217\u8868\u8BFB\u4E0D\u5230\u3002",
      hint: "\u8BF7\u70B9\u300C\u5237\u65B0\u300D\u91CD\u8BD5\uFF1B\u73B0\u5728\u65E0\u6CD5\u5224\u65AD\u5019\u9009\u65B9\u6848\u6570\u91CF\u3002"
    }) : !c.runs.length ? /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "empty",
      title: "\u8FD8\u6CA1\u6709\u6392\u4EA7\u8BB0\u5F55\u3002"
    }) : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("caption", {
      className: "wb-sr-only"
    }, "\u5019\u9009\u65B9\u6848\u6392\u4EA7\u8BB0\u5F55"), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u6392\u4EA7\u63D0\u4EA4\u65F6\u95F4"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u8BA1\u7B97\u72B6\u6001"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5019\u9009\u6570\u91CF"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u8303\u56F4"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, c.runs.map(r => /*#__PURE__*/React.createElement("tr", {
      key: r.run_ref,
      "data-run-ref": r.run_ref
    }, /*#__PURE__*/React.createElement("td", null, window.WorkbenchFormat.dateTime(r.accepted_at)), /*#__PURE__*/React.createElement("td", null, runStates[r.state] || '状态未知'), /*#__PURE__*/React.createElement("td", null, r.candidate_count), /*#__PURE__*/React.createElement("td", null, r.scope_summary ? value(r.scope_summary.batch_count) + ' 个批次' : '范围未知'), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: "arrow-right",
      reason: !canNavigate ? window.WorkbenchTerms.outcomes.unavailable : '',
      onClick: () => navigate({
        view: 'analysis',
        context: {
          run_ref: r.run_ref
        },
        enabled: true
      })
    }, "\u67E5\u770B\u5019\u9009"))))))), /*#__PURE__*/React.createElement("div", {
      className: "dy-pager"
    }, "\u6392\u4EA7\u8BB0\u5F55 ", c.page.total, " \u6B21 \xB7 \u5F53\u524D\u663E\u793A ", c.runs.length, " \u6B21", c.page.has_more ? ' · 还有更多，请点「排产记录」查看' : '')));
  }
  function ExternalRegistration({
    summary,
    onUpdated
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, summary && /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5916\u534F\u6C47\u603B"
    }, /*#__PURE__*/React.createElement("dl", {
      className: "dy-facts"
    }, [['receipt_count', '全部登记'], ['current_receipt_count', '来源仍有效的登记'], ['awaiting_return_count', '待回厂'], ['overdue_count', '超期未回'], ['returned_count', '已回厂'], ['awaiting_confirmation_count', '待确认'], ['unregistered_count', '未登记工序'], ['source_gap_count', '来源缺口']].map(([k, label]) => /*#__PURE__*/React.createElement("div", {
      key: k
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", {
      "data-external-count": k
    }, summary[k] === null ? '未知' : summary[k])))), /*#__PURE__*/React.createElement("div", {
      className: "dy-context"
    }, "\u5DF2\u786E\u8BA4\u98CE\u9669 ", summary.known_risk_count, " \u9879", summary.risk_count === null ? ' · 总风险未知' : '', " \xB7 \u767B\u8BB0\u548C\u66F4\u6B63\u5386\u53F2\u90FD\u5355\u72EC\u4FDD\u5B58")), typeof window.OutsourcingWorkspace === 'function' ? /*#__PURE__*/React.createElement(window.OutsourcingWorkspace, {
      onUpdated: onUpdated
    }) : /*#__PURE__*/React.createElement("div", {
      className: "dy-note warning",
      role: "status"
    }, window.WorkbenchTerms.outcomes.unavailable));
  }
  function ExternalHandlingState({
    summary
  }) {
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5916\u534F\u98CE\u9669\u5904\u7F6E"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5916\u534F\u98CE\u9669\u5904\u7F6E"), summary.handling_supported ? /*#__PURE__*/React.createElement("div", {
      className: "dy-context"
    }, "\u5DF2\u767B\u8BB0\u5904\u7F6E ", summary.handling_count, " \u9879 \xB7 \u5DF2\u5173\u95ED\u5904\u7F6E ", summary.closed_count, " \u9879 \xB7 \u5173\u95ED\u4E0D\u4F1A\u6539\u53D8\u56DE\u5382\u72B6\u6001") : /*#__PURE__*/React.createElement("div", {
      className: "dy-note warning",
      role: "status"
    }, summary.handling_state === 'unavailable' ? '外协处置记录读不到' : '外协风险处置尚未开通', " \xB7 \u5904\u7F6E\u6570\u91CF\u672A\u77E5\uFF0C\u8FD9\u91CC\u4E0D\u4F1A\u6309\u96F6\u663E\u793A\u3002"), /*#__PURE__*/React.createElement(Issues, {
      issues: summary.handling_issues || []
    }));
  }
  window.DashboardPanels = {
    Overview,
    Rail,
    Filters,
    Pager,
    List,
    Gaps,
    Facts,
    Evidence,
    Detail,
    NavigationConfirmation,
    navigationTarget,
    Pressure,
    Candidates,
    Risk,
    Status,
    CategoryState,
    value,
    ExternalRegistration,
    ExternalHandlingState
  };
})();
