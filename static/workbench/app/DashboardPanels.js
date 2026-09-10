(function () {
  'use strict';

  const C = window.DashboardContract,
    {
      Button,
      Issues
    } = window.ResourceControls;
  const navigationLabels = {
    gantt: '计划甘特',
    fieldgantt: '现场实际',
    batches: '批次资料',
    analysis: '候选方案',
    field: '现场报工',
    outsourcing: '外协物流登记'
  };
  function navigationTarget(n, onNavigate) {
    C.check(C.object(n) && Object.prototype.hasOwnProperty.call(navigationLabels, n.view) && C.object(n.context) && typeof n.enabled === 'boolean', '导航目标未知或上下文无效，未打开默认页面。');
    C.check(n.view === 'outsourcing' ? typeof window.OutsourcingWorkspace === 'function' : typeof onNavigate === 'function', '对象导航尚未接入，原条目仍保留。');
    C.check(n.enabled || typeof n.reason === 'string' && n.reason.trim().length > 0, '原对象不可定位的原因缺失，未打开其他对象。');
    return navigationLabels[n.view];
  }
  const value = v => v === null || v === undefined || v === '' ? '未填写' : typeof v === 'boolean' ? v ? '是' : '否' : String(v);
  const hours = v => v === null || v === undefined ? '未知' : v.toLocaleString('zh-CN', {
    maximumFractionDigits: 2
  }) + ' h';
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
    if (!summary) return /*#__PURE__*/React.createElement("span", null, "\u672A\u52A0\u8F7D");
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
        }, /*#__PURE__*/React.createElement("span", null, k === 'pressure' ? '资源压力' : '待排批次'), /*#__PURE__*/React.createElement("strong", null, !p ? '未读取' : p.count === null ? '未知' : p.count), /*#__PURE__*/React.createElement("small", null, k === 'pressure' ? '≥90% · 同范围日峰值' : '本机待排批次池'), p && k === 'pressure' && (p.unknown_resources > 0 || p.zero_capacity_resources > 0) && /*#__PURE__*/React.createElement("small", null, "\u5BB9\u91CF\u672A\u77E5 ", p.unknown_resources, " \xB7 \u96F6\u53EF\u7528 ", p.zero_capacity_resources));
      }
      const s = data && data.categories[k];
      return /*#__PURE__*/React.createElement("button", {
        type: "button",
        className: "dy-metric",
        key: k,
        onClick: () => onCategory(k)
      }, /*#__PURE__*/React.createElement("span", null, C.categories[k]), /*#__PURE__*/React.createElement("strong", {
        className: s && s.risk_count > 0 ? 'dy-danger' : 'dy-muted'
      }, !s ? '未加载' : s.risk_count === null ? C.states[s.state] === '已读取' ? '未知' : C.states[s.state] : s.risk_count), /*#__PURE__*/React.createElement("small", null, !s ? '等待读取' : k === 'external' ? s.awaiting_return_count === null ? '外协风险投影未读取' : '待回厂 ' + s.awaiting_return_count + ' · 超期 ' + s.overdue_count + ' · 待确认 ' + s.awaiting_confirmation_count : s.risk_count === null ? s.known_risk_count > 0 ? '已确认风险 ' + s.known_risk_count + ' 项' : '总风险未评估' : '已关闭处置 ' + s.closed_count + ' 项'));
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
    }, /*#__PURE__*/React.createElement("b", null, label), /*#__PURE__*/React.createElement("small", null, k === 'all' ? '风险与处置分别核对' : k === 'candidate' ? data ? C.states[data.candidate_catalog.state] + ' · 目录不计风险' : '未加载' : /*#__PURE__*/React.createElement(CategoryState, {
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
    }, [['subject', '对象'], ['category', '风险类别'], ['status', '处置状态'], ['deadline', '责任期限']].map(([k, label]) => /*#__PURE__*/React.createElement("option", {
      key: k,
      value: k
    }, label)))), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-down",
      className: 'btn dy-sort-' + query.direction,
      "aria-label": query.direction === 'asc' ? '改为降序' : '改为升序',
      onClick: () => onChange({
        direction: query.direction === 'asc' ? 'desc' : 'asc'
      })
    }), /*#__PURE__*/React.createElement(Button, {
      type: "submit",
      icon: "search",
      "aria-label": "\u6267\u884C\u6761\u76EE\u641C\u7D22",
      busy: busy
    }), /*#__PURE__*/React.createElement(Button, {
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
    return /*#__PURE__*/React.createElement("div", {
      className: "dy-pager"
    }, /*#__PURE__*/React.createElement("span", null, page.total, " \u9879 \xB7 \u7B2C ", page.number, " / ", page.pages, " \u9875"), onSize && /*#__PURE__*/React.createElement("label", null, "\u6BCF\u9875 ", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u6BCF\u9875\u6761\u76EE\u6570",
      value: page.size,
      onChange: e => onSize(Number(e.target.value))
    }, [10, 20, 50, 100].concat([page.size]).filter((v, i, a) => a.indexOf(v) === i).sort((a, b) => a - b).map(n => /*#__PURE__*/React.createElement("option", {
      key: n
    }, n)))), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": label + '上一页',
      disabled: busy || page.number <= 1,
      onClick: () => onPage(page.number - 1)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": label + '下一页',
      disabled: busy || page.number >= page.pages,
      onClick: () => onPage(page.number + 1)
    }));
  }
  function List({
    data,
    selected,
    onSelect
  }) {
    if (!data.items.length) return /*#__PURE__*/React.createElement("div", {
      className: "dy-empty",
      role: "status"
    }, data.page.total === 0 ? '当前筛选没有条目。' : '当前页没有条目。', data.categories.external.state === 'not_connected' && ' 外协风险投影尚未接入，不代表零风险。');
    return /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "dy-table"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u5BF9\u8C61 / \u7C7B\u522B"), /*#__PURE__*/React.createElement("th", null, "\u98CE\u9669\u4E8B\u5B9E"), /*#__PURE__*/React.createElement("th", null, "\u5904\u7F6E\u72B6\u6001"), /*#__PURE__*/React.createElement("th", null, "\u8D23\u4EFB\u4EBA / \u671F\u9650"), /*#__PURE__*/React.createElement("th", null, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, data.items.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.item_ref,
      "data-item-ref": row.item_ref,
      "data-category": row.category,
      "data-selected": selected === row.item_ref
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("b", null, row.subject), /*#__PURE__*/React.createElement("div", {
      className: "dy-muted"
    }, C.categories[row.category])), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Risk, {
      risk: row.risk
    }), /*#__PURE__*/React.createElement("div", null, row.risk.message)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Status, {
      handling: row.handling
    }), /*#__PURE__*/React.createElement("div", {
      className: "dy-muted"
    }, "\u5386\u53F2 ", row.handling.history_count, " \u6761")), /*#__PURE__*/React.createElement("td", null, value(row.handling.owner), /*#__PURE__*/React.createElement("div", {
      className: row.handling.deadline_overdue ? 'dy-danger' : 'dy-muted'
    }, value(row.handling.deadline), row.handling.deadline_overdue ? ' · 处置逾期' : '')), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
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
    return /*#__PURE__*/React.createElement(React.Fragment, null, Object.entries(categories).filter(([key]) => selected === 'all' || key === selected).map(([key, s]) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement(Issues, {
      issues: s.issues
    }), s.evaluation_gaps.length > 0 && /*#__PURE__*/React.createElement("details", {
      className: "dy-evidence"
    }, /*#__PURE__*/React.createElement("summary", null, C.categories[key], " \xB7 \u65E0\u6CD5\u8BC4\u4F30 ", s.unknown_count, " \u9879"), s.evaluation_gaps.map(g => /*#__PURE__*/React.createElement("p", {
      key: g.source_ref
    }, g.subject, "\uFF1A", g.message))))));
  }
  function Facts({
    handling
  }) {
    return /*#__PURE__*/React.createElement("dl", {
      className: "dy-facts"
    }, ['status', ...C.fields].map(k => /*#__PURE__*/React.createElement("div", {
      key: k
    }, /*#__PURE__*/React.createElement("dt", null, C.labels[k]), /*#__PURE__*/React.createElement("dd", null, k === 'status' ? C.statuses[handling.status] : k === 'evidence_ref' && !handling[k] ? '未关联已核验附件' : value(handling[k])))));
  }
  function SourceFacts({
    source
  }) {
    const labels = {
      planned_start: '正式安排开始',
      planned_end: '正式安排结束',
      first_actual_start: '首次实际开始',
      confirmed_finish: '确认完工时间',
      finish_deviation_minutes: '完工偏差（分钟）',
      overlap_hours: '停机重叠（小时）',
      delay_after_reschedule_hours: '重排后延期（小时）'
    };
    const execution = {
      unreported: '尚未报工',
      started: '已开始',
      partial: '部分完成',
      complete: '已完工',
      paused: '已暂停',
      exception: '异常'
    };
    const quality = {
      incomplete: '事实尚不完整',
      complete: '事实完整',
      invalid: '事实待核对',
      legacy: '旧事实需核对'
    };
    return /*#__PURE__*/React.createElement(React.Fragment, null, source.execution_state && /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, "\u6267\u884C\u72B6\u6001\uFF1A", execution[source.execution_state] || source.execution_state, " \xB7 ", quality[source.data_quality] || '完整性待核对'), /*#__PURE__*/React.createElement("dl", {
      className: "dy-facts"
    }, Object.entries(labels).filter(([k]) => Object.prototype.hasOwnProperty.call(source, k)).map(([k, label]) => /*#__PURE__*/React.createElement("div", {
      key: k
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, source[k] === null ? '未知' : value(source[k]).replace('T', ' '))))), source.hours && /*#__PURE__*/React.createElement("dl", {
      className: "dy-facts"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6709\u6548\u52A0\u5DE5\u5C0F\u65F6"), /*#__PURE__*/React.createElement("dd", null, hours(source.hours.effective_processing_hours))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u5B9A\u989D\u52A0\u5DE5\u5C0F\u65F6"), /*#__PURE__*/React.createElement("dd", null, hours(source.hours.quota_processing_hours))), /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("dt", null, "\u6709\u6548\u5DE5\u65F6\u8D85\u8017"), /*#__PURE__*/React.createElement("dd", null, source.hours.overrun === null ? '无法评估' : source.hours.overrun ? '已确认超耗' : '未超耗'))), source.downtimes && /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u505C\u673A\u539F\u56E0"), /*#__PURE__*/React.createElement("th", null, "\u6709\u6548\u505C\u673A\u7A97\u53E3"), /*#__PURE__*/React.createElement("th", null, "\u4E0E\u6B63\u5F0F\u5B89\u6392\u91CD\u53E0"))), /*#__PURE__*/React.createElement("tbody", null, source.downtimes.map(d => /*#__PURE__*/React.createElement("tr", {
      key: d.downtime_ref
    }, /*#__PURE__*/React.createElement("td", null, d.reason || '原因未填写'), /*#__PURE__*/React.createElement("td", null, d.start.replace('T', ' '), " \u81F3 ", d.end.replace('T', ' ')), /*#__PURE__*/React.createElement("td", null, d.overlap_start.replace('T', ' '), " \u81F3 ", d.overlap_end.replace('T', ' '))))))), source.data_gaps && /*#__PURE__*/React.createElement(Issues, {
      issues: source.data_gaps
    }));
  }
  function Evidence({
    source
  }) {
    const e = source.evaluation;
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "dy-context"
    }, source.plan_ref && /*#__PURE__*/React.createElement("span", null, "\u6B63\u5F0F\u8BA1\u5212\u5F15\u7528 ", source.plan_ref), source.batch_ref && /*#__PURE__*/React.createElement("span", null, "\u6279\u6B21\u5F15\u7528 ", source.batch_ref)), source.kind === 'outsourcing_receipt' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("h4", null, "\u539F\u7269\u6D41\u767B\u8BB0\u4E8B\u5B9E"), source.receipt && window.OutsourcingControls ? /*#__PURE__*/React.createElement("div", {
      className: "outsourcing-live"
    }, /*#__PURE__*/React.createElement(window.OutsourcingStyles, null), /*#__PURE__*/React.createElement(window.OutsourcingControls.Facts, {
      facts: source.receipt
    })) : /*#__PURE__*/React.createElement("div", {
      className: "dy-note warning"
    }, "\u539F\u767B\u8BB0\u5F53\u524D\u65E0\u6CD5\u6838\u5BF9\uFF0C\u672A\u63A8\u5B9A\u53D1\u51FA\u6216\u56DE\u5382\u3002")), source.requirements && /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u7269\u6599"), /*#__PURE__*/React.createElement("th", null, "\u9700\u6C42\u91CF"), /*#__PURE__*/React.createElement("th", null, "\u53EF\u7528\u91CF"), /*#__PURE__*/React.createElement("th", null, "\u9F50\u5957"))), /*#__PURE__*/React.createElement("tbody", null, source.requirements.map((r, i) => /*#__PURE__*/React.createElement("tr", {
      key: i
    }, /*#__PURE__*/React.createElement("td", null, r.label || r.business_code || '名称未知'), /*#__PURE__*/React.createElement("td", null, r.required_quantity === null ? '未知' : r.required_quantity, " ", r.unit), /*#__PURE__*/React.createElement("td", null, r.available_quantity === null ? '未知' : r.available_quantity, " ", r.unit), /*#__PURE__*/React.createElement("td", null, {
      yes: '已齐套',
      no: '未齐套',
      partial: '部分齐套'
    }[r.ready_status] || '未知')))))), e && /*#__PURE__*/React.createElement("dl", {
      className: "dy-facts"
    }, [['due_date', '交期'], ['planned_finish', '计划完成'], ['delay_days', '预计晚交天数']].filter(([k]) => Object.prototype.hasOwnProperty.call(e, k)).map(([k, label]) => /*#__PURE__*/React.createElement("div", {
      key: k
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", null, e[k] === null ? '未知' : value(e[k]))))), /*#__PURE__*/React.createElement(SourceFacts, {
      source: source
    }), /*#__PURE__*/React.createElement("details", {
      className: "dy-evidence"
    }, /*#__PURE__*/React.createElement("summary", null, "\u5B8C\u6574\u6765\u6E90\u4F9D\u636E"), /*#__PURE__*/React.createElement("pre", null, JSON.stringify(source, null, 2))));
  }
  function Detail({
    item,
    onHandle,
    onHistory,
    navigate,
    canNavigate
  }) {
    return /*#__PURE__*/React.createElement("section", {
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
      icon: item.handling.status === 'closed' ? 'refresh-cw' : 'square-pen',
      onClick: onHandle
    }, item.handling.status === 'closed' ? '独立重开' : '登记处置'), /*#__PURE__*/React.createElement(Button, {
      icon: "history",
      onClick: onHistory
    }, "\u67E5\u770B\u5904\u7F6E\u5386\u53F2"), item.navigation.map((n, i) => /*#__PURE__*/React.createElement(Button, {
      key: i,
      icon: "arrow-right",
      onClick: () => navigate(n, item)
    }, n.view === 'outsourcing' ? '原外协物流登记' : navigationLabels[n.view] || '未知导航目标')), item.category === 'actual' && item.navigation.some(n => n.enabled && n.command_context === 'read_execution_write_context') && /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      reason: !canNavigate ? '现场报工入口尚未接入' : '',
      onClick: () => navigate({
        ...item.navigation[0],
        view: 'field'
      })
    }, "\u73B0\u573A\u62A5\u5DE5")), item.category === 'external' && /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, "\u5173\u95ED\u98CE\u9669\u5904\u7F6E\u4E0D\u4EE3\u8868\u5DF2\u56DE\u5382\uFF0C\u4E5F\u4E0D\u4EE3\u8868\u5DE5\u5E8F\u5B8C\u5DE5\u3002\u7269\u6D41\u4E8B\u5B9E\u4E0E\u5904\u7F6E\u5386\u53F2\u5206\u522B\u4FDD\u7559\u3002"), item.handling.status === 'closed' && /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, "\u5904\u7F6E\u5DF2\u5173\u95ED\uFF0C\u98CE\u9669\u6309\u5F53\u524D\u771F\u5B9E\u6765\u6E90\u7EE7\u7EED\u8BC4\u4F30\u3002"));
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
      title: "\u539F\u5BF9\u8C61\u6682\u4E0D\u53EF\u5B9A\u4F4D",
      icon: "circle-alert",
      onClose: onClose,
      footer: /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Button, {
        icon: "x",
        onClick: onClose
      }, "\u53D6\u6D88"), /*#__PURE__*/React.createElement(Button, {
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
    }, "\u539F\u6761\u76EE\u5F15\u7528 ", item.item_ref, " \xB7 ", item.source_state === 'current' ? '当前来源' : '原来源当前未评估'), /*#__PURE__*/React.createElement(Evidence, {
      source: item.source
    }), /*#__PURE__*/React.createElement("p", null, "\u539F\u6761\u76EE\u4E0E\u5904\u7F6E\u72B6\u6001\u4FDD\u6301\u4E0D\u53D8\u3002"), /*#__PURE__*/React.createElement(ErrorBox, {
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
      "aria-label": "\u771F\u5B9E\u8D44\u6E90\u538B\u529B"
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u6B63\u5F0F\u8BA1\u5212\u8D44\u6E90\u538B\u529B"), data.plan && /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      reason: !canNavigate ? '对象导航尚未接入' : '',
      onClick: () => navigate({
        view: 'gantt',
        context: {
          plan_ref: data.plan.plan_ref
        },
        enabled: true
      })
    }, "\u8BA1\u5212\u7518\u7279")), /*#__PURE__*/React.createElement("div", {
      className: "dy-context"
    }, data.plan ? data.plan.display_name : data.categories.delivery.state === 'no_official_plan' ? '无正式计划' : '正式计划未能读取', " \xB7 ", p.time_scope ? p.time_scope.range_start.replace('T', ' ') + ' 至 ' + p.time_scope.range_end.replace('T', ' ') + ' · 工厂本地 · 左闭右开' : '时间范围未读取'), /*#__PURE__*/React.createElement(Issues, {
      issues: p.issues
    }), /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, "\u5360\u7528\u5C0F\u65F6\u4E0D\u662F\u6709\u6548\u52A0\u5DE5\u5DE5\u65F6\uFF1B\u53EF\u7528\u4EA7\u80FD\u672A\u77E5\u65F6\u5229\u7528\u7387\u4FDD\u6301\u672A\u77E5\u3002\u505C\u673A\u548C\u65E5\u5386\u6309\u540C\u4E00\u6B63\u5F0F\u8BA1\u5212\u6838\u5BF9\u3002"), !rows || !rows.length ? /*#__PURE__*/React.createElement("div", {
      className: "dy-empty"
    }, !rows ? '资源压力无法评估，未显示零负荷。' : '当前正式计划没有资源占用数据。') : /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "dy-resource"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u8D44\u6E90"), /*#__PURE__*/React.createElement("th", null, "\u5360\u7528 / \u5B89\u6392"), /*#__PURE__*/React.createElement("th", null, "\u53EF\u7528"), /*#__PURE__*/React.createElement("th", null, "\u5229\u7528\u7387"), /*#__PURE__*/React.createElement("th", null, "\u91CD\u53E0\u5360\u7528"), /*#__PURE__*/React.createElement("th", null, "\u65E5\u5386\u5916\u5360\u7528"), /*#__PURE__*/React.createElement("th", null, "\u5BB9\u91CF\u7F3A\u53E3"))), /*#__PURE__*/React.createElement("tbody", null, rows.map(r => /*#__PURE__*/React.createElement("tr", {
      key: r.kind + r.resource_ref,
      "data-resource-ref": r.resource_ref
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("b", null, r.label || '名称未提供'), /*#__PURE__*/React.createElement("div", {
      className: "dy-muted"
    }, r.kind === 'machine' ? '设备' : '人员', " \xB7 ", r.operation_count, " \u9053\u5DE5\u5E8F")), /*#__PURE__*/React.createElement("td", null, hours(r.occupied_hours), " / ", hours(r.arranged_hours)), /*#__PURE__*/React.createElement("td", null, hours(r.available_hours)), /*#__PURE__*/React.createElement("td", null, r.utilization === null ? '未知' : (r.utilization * 100).toFixed(1) + '%', r.utilization !== null && /*#__PURE__*/React.createElement("div", {
      className: 'dy-meter' + (r.capacity_insufficient || r.has_overlap ? ' hot' : '')
    }, /*#__PURE__*/React.createElement("i", {
      style: {
        width: r.utilization * 100 + '%'
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
      "aria-label": "\u771F\u5B9E\u5019\u9009\u76EE\u5F55"
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5019\u9009\u65B9\u6848\u76EE\u5F55"), /*#__PURE__*/React.createElement(Button, {
      icon: "history",
      reason: !canNavigate ? '候选导航尚未接入' : '',
      onClick: () => navigate({
        view: 'analysis',
        context: {
          source: 'run_history'
        },
        enabled: true
      })
    }, "\u5B8C\u6574\u8FD0\u884C\u76EE\u5F55")), /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, "\u5DF2\u4FDD\u5B58\u8FD0\u884C\u76EE\u5F55 \xB7 \u975E\u5F53\u524D\u6B63\u5F0F\u8BA1\u5212"), /*#__PURE__*/React.createElement(Issues, {
      issues: c.issues
    }), c.state === 'unavailable' ? /*#__PURE__*/React.createElement("div", {
      className: "dy-empty"
    }, "\u5019\u9009\u76EE\u5F55\u672A\u80FD\u8BFB\u53D6\u3002") : !c.runs.length ? /*#__PURE__*/React.createElement("div", {
      className: "dy-empty"
    }, "\u5C1A\u65E0\u6392\u4EA7\u8FD0\u884C\u8BB0\u5F55\u3002") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "dy-scroll"
    }, /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u8FD0\u884C\u53D7\u7406\u65F6\u95F4"), /*#__PURE__*/React.createElement("th", null, "\u8BA1\u7B97\u72B6\u6001"), /*#__PURE__*/React.createElement("th", null, "\u5019\u9009\u6570\u91CF"), /*#__PURE__*/React.createElement("th", null, "\u8303\u56F4"), /*#__PURE__*/React.createElement("th", null, "\u64CD\u4F5C"))), /*#__PURE__*/React.createElement("tbody", null, c.runs.map(r => /*#__PURE__*/React.createElement("tr", {
      key: r.run_ref,
      "data-run-ref": r.run_ref
    }, /*#__PURE__*/React.createElement("td", null, r.accepted_at.replace('T', ' ')), /*#__PURE__*/React.createElement("td", null, runStates[r.state] || '状态未知'), /*#__PURE__*/React.createElement("td", null, r.candidate_count), /*#__PURE__*/React.createElement("td", null, r.scope_summary ? value(r.scope_summary.batch_count) + ' 个批次' : '范围未知'), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      reason: !canNavigate ? '候选导航尚未接入' : '',
      onClick: () => navigate({
        view: 'analysis',
        context: {
          run_ref: r.run_ref
        },
        enabled: true
      })
    }, "\u67E5\u770B\u5019\u9009"))))))), /*#__PURE__*/React.createElement("div", {
      className: "dy-pager"
    }, "\u76EE\u5F55 ", c.page.total, " \u6B21 \xB7 \u5F53\u524D ", c.runs.length, " \u6B21", c.page.has_more ? ' · 还有更多，请进入完整运行目录' : '')));
  }
  function ExternalRegistration({
    summary,
    onUpdated
  }) {
    return /*#__PURE__*/React.createElement(React.Fragment, null, summary && /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5916\u534F\u771F\u5B9E\u6C47\u603B"
    }, /*#__PURE__*/React.createElement("dl", {
      className: "dy-facts"
    }, [['receipt_count', '保留登记'], ['current_receipt_count', '来源有效登记'], ['awaiting_return_count', '待回厂'], ['overdue_count', '超期未回'], ['returned_count', '已回厂'], ['awaiting_confirmation_count', '待确认'], ['unregistered_count', '未登记工序'], ['source_gap_count', '来源缺口']].map(([k, label]) => /*#__PURE__*/React.createElement("div", {
      key: k
    }, /*#__PURE__*/React.createElement("dt", null, label), /*#__PURE__*/React.createElement("dd", {
      "data-external-count": k
    }, summary[k] === null ? '未知' : summary[k])))), /*#__PURE__*/React.createElement("div", {
      className: "dy-context"
    }, "\u5DF2\u786E\u8BA4\u98CE\u9669 ", summary.known_risk_count, " \u9879", summary.risk_count === null ? ' · 总风险未知' : '', " \xB7 \u767B\u8BB0\u4E0E\u6838\u5B9E\u5386\u53F2\u72EC\u7ACB\u4FDD\u7559")), typeof window.OutsourcingWorkspace === 'function' ? /*#__PURE__*/React.createElement(window.OutsourcingWorkspace, {
      onUpdated: onUpdated
    }) : /*#__PURE__*/React.createElement("div", {
      className: "dy-note warning",
      role: "status"
    }, "\u5916\u534F\u767B\u8BB0\u6A21\u5757\u5C1A\u672A\u52A0\u8F7D\u3002"));
  }
  function ExternalHandlingState({
    summary
  }) {
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5916\u534F\u98CE\u9669\u5904\u7F6E"
    }, /*#__PURE__*/React.createElement("h3", null, "\u5916\u534F\u98CE\u9669\u5904\u7F6E"), summary.handling_supported ? /*#__PURE__*/React.createElement("div", {
      className: "dy-context"
    }, "\u5DF2\u767B\u8BB0\u5904\u7F6E ", summary.handling_count, " \u9879 \xB7 \u5DF2\u5173\u95ED\u5904\u7F6E ", summary.closed_count, " \u9879 \xB7 \u5173\u95ED\u4E0D\u6539\u53D8\u771F\u5B9E\u56DE\u5382\u72B6\u6001") : /*#__PURE__*/React.createElement("div", {
      className: "dy-note warning",
      role: "status"
    }, summary.handling_state === 'unavailable' ? '外协处置台账不可用' : '外协风险处置尚未接入', " \xB7 \u5904\u7F6E\u6570\u91CF\u672A\u77E5\uFF0C\u672A\u663E\u793A\u4E3A\u96F6\u3002"), /*#__PURE__*/React.createElement(Issues, {
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
