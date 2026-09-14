(function () {
  'use strict';

  const C = window.DashboardContract,
    S = window.DashboardSession,
    P = window.DashboardPanels,
    {
      Button,
      ErrorBox
    } = window.ResourceControls;
  function durableScope(query) {
    const result = {
      ...query
    };
    delete result.snapshot_ref;
    return result;
  }
  async function readList(api, query, signal) {
    if (query.page === 1 || query.snapshot_ref) return api.list(query, signal);
    const first = await api.list({
      ...query,
      page: 1
    }, signal);
    return api.list({
      ...query,
      snapshot_ref: first.meta.snapshot_ref
    }, signal);
  }
  function Content({
    start,
    onNavigate
  }) {
    const api = React.useMemo(() => C.create(), []),
      command = S.useCommand(api);
    const [q, setQuery] = React.useState(start.q),
      [tab, setTab] = React.useState(start.tab),
      [selected, setSelected] = React.useState(start.selected);
    const [historyPage, setHistoryPage] = React.useState(start.historyPage),
      [revision, refresh] = React.useReducer(n => n + 1, 0);
    const [dialog, setDialog] = React.useState(false),
      [navError, setNavError] = React.useState(null);
    const [navigationConfirmation, setNavigationConfirmation] = React.useState(null);
    const [outsourcing, setOutsourcing] = React.useState(null),
      [registrationChanged, setRegistrationChanged] = React.useState(false);
    const [analysisBatch, setAnalysisBatch] = React.useState(start.analysisBatch);
    const [comparisonState, setComparisonState] = React.useState({
      context: start.comparison,
      caption: null
    });
    const onComparisonState = React.useCallback(value => setComparisonState(previous => C.equal(previous, value) ? previous : value), []);
    const analysisApi = React.useMemo(() => window.DashboardAnalysisAPI.create(), []);
    const list = S.useRead(signal => readList(api, q, signal), [api, q, revision]);
    const result = list.result,
      data = result && result.data,
      snapshot = result && result.meta.snapshot_ref;
    const analysisRead = S.useRead(signal => analysisApi.read(data && data.plan ? data.plan.plan_ref : null, signal), [analysisApi, data && data.plan && data.plan.plan_ref, revision], !!data && !list.loading && !list.error && !outsourcing);
    const analysisData = analysisRead.result && analysisRead.result.data;
    const detailQuery = React.useMemo(() => ({
      ...q,
      snapshot_ref: snapshot
    }), [q, snapshot]);
    const handlingAvailable = q.category !== 'external' || !!data && data.categories.external.handling_supported === true;
    const detail = S.useRead(signal => api.detail(selected, detailQuery, undefined, signal), [api, selected, detailQuery], handlingAvailable && !!selected && !!snapshot);
    const history = S.useRead(signal => api.detail(selected, detailQuery, historyPage, signal), [api, selected, detailQuery, historyPage, tab], handlingAvailable && tab === 'records' && !!selected && !!snapshot);
    const item = detail.result && detail.result.data.item;
    function choose(ref) {
      setSelected(ref);
      setHistoryPage(1);
    }
    function change(patch, paging = false) {
      const next = {
        ...q,
        ...patch,
        page: paging ? patch.page : 1
      };
      delete next.snapshot_ref;
      if (paging) next.snapshot_ref = snapshot;
      setQuery(C.scope(next));
      if (!paging) {
        choose(null);
        setDialog(false);
      }
      refresh();
    }
    function reload() {
      const next = {
        ...q,
        page: 1
      };
      delete next.snapshot_ref;
      setQuery(next);
      setHistoryPage(1);
      setRegistrationChanged(false);
      refresh();
    }
    function category(k) {
      change({
        category: k
      });
      setAnalysisBatch(null);
      setComparisonState({
        context: {},
        caption: null
      });
      setTab(k === 'candidate' ? 'compare' : 'items');
    }
    function showAnalysis(k) {
      category(k);
      setTab('analysis');
    }
    function readContext() {
      return {
        scope: durableScope(q),
        tab,
        ...(selected ? {
          item_ref: selected,
          history_page: historyPage
        } : {}),
        ...(analysisBatch ? {
          analysis_batch_ref: analysisBatch
        } : {}),
        ...(Object.keys(comparisonState.context).length ? {
          comparison: comparisonState.context
        } : {})
      };
    }
    function openTarget(n, current, overview = false) {
      P.navigationTarget(n, onNavigate);
      const context = {
        ...(overview ? {} : n.context),
        return_to: {
          view: 'dashboard',
          context: current
        }
      };
      if (n.view === 'outsourcing') {
        setOutsourcing(context);
        return;
      }
      if (n.view === 'batches' && context.batch_ref) context.entity_ref = context.batch_ref;
      C.check(onNavigate(n.view, context) !== false, '目标页面没有打开，这条记录仍然保留。请刷新后重试。');
    }
    function navigate(n, origin) {
      try {
        setNavError(null);
        const label = P.navigationTarget(n, onNavigate),
          current = readContext();
        if (!n.enabled) {
          C.check(origin && origin === item && origin.item_ref === selected && origin.navigation.includes(n), '这条记录的来源和详情对不上，页面没有跳转。请刷新后重试。');
          setNavigationConfirmation({
            navigation: n,
            item: origin,
            current,
            label
          });
        } else openTarget(n, current);
      } catch (error) {
        setNavError(error);
      }
    }
    function confirmNavigation() {
      try {
        openTarget(navigationConfirmation.navigation, navigationConfirmation.current, true);
        setNavigationConfirmation(null);
      } catch (error) {
        setNavError(error);
      }
    }
    function finish() {
      if (command.finish()) {
        setDialog(false);
        reload();
      }
    }
    const currentSummary = data && q.category !== 'all' && data.categories[q.category];
    const external = q.category === 'external',
      activeTabs = external ? handlingAvailable ? {
        items: '处置清单',
        records: '处置历史'
      } : {
        items: '登记与更正历史'
      } : S.tabs;
    const activeTab = Object.prototype.hasOwnProperty.call(activeTabs, tab) ? tab : 'items',
      tabKeys = Object.keys(activeTabs);
    window.WorkbenchPageContext.useSnapshot(readContext(), !!data && !list.loading && !list.error && !detail.error);
    const comparing = !external && activeTab === 'compare',
      showingAnalysis = !external && activeTab === 'analysis';
    const plan = !list.loading && !list.error && !outsourcing && !comparing && (showingAnalysis ? !analysisRead.loading && !analysisRead.error && analysisData && analysisData.plan : data && data.plan);
    const caption = comparing ? !list.loading && !list.error && !outsourcing ? comparisonState.caption : null : plan && plan.kind === 'official' && plan.is_current_official === true ? {
      reference: plan.plan_ref,
      label: '正式计划',
      name: plan.display_name,
      status: '当前正式',
      ...(Number.isSafeInteger(plan.version) && plan.version > 0 ? {
        version: '正式 v' + plan.version
      } : {})
    } : null;
    window.WorkbenchCaption.useCaption(caption);
    if (outsourcing) return /*#__PURE__*/React.createElement("div", {
      className: "plana dashboard-live",
      "data-dashboard-outsourcing": true,
      "data-return-item": outsourcing.return_to.context.item_ref
    }, /*#__PURE__*/React.createElement(window.DashboardStyles, null), /*#__PURE__*/React.createElement("header", {
      className: "dy-heading"
    }, /*#__PURE__*/React.createElement("h2", null, "\u5916\u534F\u7269\u6D41\u767B\u8BB0"), /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-left",
      onClick: () => setOutsourcing(null)
    }, "\u8FD4\u56DE\u503C\u73ED\u53F0\u6761\u76EE")), /*#__PURE__*/React.createElement("div", {
      className: "dy-note"
    }, "\u5916\u534F\u7269\u6D41\u767B\u8BB0\u6982\u89C8 \xB7 \u7269\u6D41\u767B\u8BB0\u4E0D\u66FF\u4EE3\u98CE\u9669\u5904\u7F6E\u3002"), /*#__PURE__*/React.createElement(window.WorkbenchReference, {
      entries: {
        '登记编号': outsourcing.outsourcing_ref
      }
    }), typeof window.OutsourcingWorkspace === 'function' ? /*#__PURE__*/React.createElement(window.OutsourcingWorkspace, {
      outsourcingRef: outsourcing.outsourcing_ref,
      onUpdated: () => setRegistrationChanged(true)
    }) : /*#__PURE__*/React.createElement("div", {
      className: "dy-note warning",
      role: "status"
    }, window.WorkbenchTerms.outcomes.unavailable));
    return /*#__PURE__*/React.createElement("div", {
      className: "plana dashboard-live",
      "data-dashboard-workspace": true,
      "data-ready": !!data,
      "data-analysis-ready": !!analysisData && !analysisRead.loading && !analysisRead.error,
      "aria-busy": list.loading
    }, /*#__PURE__*/React.createElement(window.DashboardStyles, null), /*#__PURE__*/React.createElement("header", {
      className: "dy-heading"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", {
      className: "wb-page-title"
    }, "\u8BA1\u5212\u5458\u503C\u73ED\u53F0"), /*#__PURE__*/React.createElement("div", {
      className: "dy-context wb-page-context"
    }, /*#__PURE__*/React.createElement("span", null, comparing ? comparisonState.caption ? comparisonState.caption.name + ' · ' + comparisonState.caption.status : '尚未确认所选候选方案' : data ? data.plan ? data.plan.display_name + ' · 当前正式' : data.categories.delivery.state === 'no_official_plan' ? '当前无正式计划' : '正式计划未能读取' : '正式计划未读取'), /*#__PURE__*/React.createElement("span", null, data ? '数据截至 ' + window.WorkbenchFormat.dateTime(data.as_of) : '数据尚未读取'))), /*#__PURE__*/React.createElement("div", {
      className: "dy-tools"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u503C\u73ED\u53F0",
      busy: list.loading,
      disabled: command.busy,
      onClick: reload
    }), command.saved && /*#__PURE__*/React.createElement(Button, {
      icon: "history",
      onClick: () => setDialog(true)
    }, command.saved.phase === 'confirmed' ? '查看已确认的结果' : '查询上次处置结果'))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: command.storageError
    }), command.storageError && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: command.sync
    }, "\u5237\u65B0\u4E0A\u6B21\u64CD\u4F5C\u8BB0\u5F55"), registrationChanged && /*#__PURE__*/React.createElement("div", {
      className: "dy-note warning",
      role: "status"
    }, "\u5916\u534F\u7269\u6D41\u767B\u8BB0\u5DF2\u66F4\u65B0\u3002\u5F53\u524D\u4ECD\u663E\u793A\u79BB\u5F00\u524D\u7684\u7B5B\u9009\u548C\u6761\u76EE\uFF0C\u8BF7\u70B9\u300C\u5237\u65B0\u503C\u73ED\u53F0\u300D\u66F4\u65B0\u98CE\u9669\u4E0E\u5904\u7F6E\u3002"), !dialog && command.saved && /*#__PURE__*/React.createElement("div", {
      className: 'dy-note ' + (command.saved.phase === 'confirmed' ? 'success' : 'warning')
    }, command.saved.phase === 'confirmed' ? '上次处置结果已确认，点「完成」后更新风险与处置。' : '上次处置还没确认结果，确认前不能新增处置。'), /*#__PURE__*/React.createElement(P.Overview, {
      data: data,
      analysis: analysisData,
      onCategory: category,
      onAnalysis: showAnalysis
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: analysisRead.error
    }), /*#__PURE__*/React.createElement("div", {
      className: "dy-work"
    }, /*#__PURE__*/React.createElement(P.Rail, {
      data: data,
      category: q.category,
      onCategory: category
    }), /*#__PURE__*/React.createElement("div", {
      className: "dy-main"
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-section-head"
    }, /*#__PURE__*/React.createElement("h3", null, C.categories[q.category]), currentSummary && q.category !== 'candidate' && /*#__PURE__*/React.createElement(P.CategoryState, {
      summary: currentSummary
    }), /*#__PURE__*/React.createElement("label", {
      className: "dy-category-picker"
    }, "\u5F02\u5E38\u7C7B\u522B", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5F02\u5E38\u7C7B\u522B",
      value: q.category,
      onChange: event => category(event.target.value)
    }, Object.entries(C.categories).map(([key, label]) => /*#__PURE__*/React.createElement("option", {
      key: key,
      value: key
    }, label))))), /*#__PURE__*/React.createElement("div", {
      className: "dy-tabs",
      role: "tablist",
      "aria-label": "\u95EE\u9898\u8BE6\u60C5\u89C6\u56FE"
    }, Object.entries(activeTabs).map(([key, label], index) => /*#__PURE__*/React.createElement("button", {
      type: "button",
      key: key,
      id: 'dy-tab-' + key,
      role: "tab",
      className: "dy-tab",
      "aria-controls": "dy-content",
      "aria-selected": activeTab === key,
      tabIndex: activeTab === key ? 0 : -1,
      onClick: () => setTab(key),
      onKeyDown: e => {
        if (e.altKey || e.ctrlKey || e.metaKey) return;
        let next;
        if (e.key === 'ArrowRight') next = (index + 1) % tabKeys.length;
        if (e.key === 'ArrowLeft') next = (index + tabKeys.length - 1) % tabKeys.length;
        if (e.key === 'Home') next = 0;
        if (e.key === 'End') next = tabKeys.length - 1;
        if (next !== undefined) {
          e.preventDefault();
          setTab(tabKeys[next]);
          document.getElementById('dy-tab-' + tabKeys[next]).focus();
        }
      }
    }, label))), /*#__PURE__*/React.createElement("div", {
      className: "dy-panel",
      role: "tabpanel",
      id: "dy-content",
      "aria-labelledby": 'dy-tab-' + activeTab
    }, /*#__PURE__*/React.createElement(ErrorBox, {
      error: list.error || navError
    }), list.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: reload
    }, "\u5237\u65B0\u5F53\u524D\u7B5B\u9009"), list.loading && /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "loading",
      title: "\u6B63\u5728\u8BFB\u53D6\u98CE\u9669\u3001\u8D44\u6E90\u4E0E\u5019\u9009\u65B9\u6848\u5217\u8868"
    }), external && /*#__PURE__*/React.createElement(P.ExternalRegistration, {
      summary: currentSummary,
      onUpdated: reload
    }), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(P.Gaps, {
      categories: data.categories,
      selected: q.category
    }), external && /*#__PURE__*/React.createElement(P.ExternalHandlingState, {
      summary: currentSummary
    }), handlingAvailable && activeTab === 'items' && /*#__PURE__*/React.createElement("div", {
      className: item ? 'wb-detail-layout dy-detail-layout' : ''
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement(P.Filters, {
      query: q,
      busy: list.loading,
      onChange: change
    }), /*#__PURE__*/React.createElement(P.List, {
      data: data,
      selected: selected,
      onSelect: choose,
      query: q,
      onClear: () => change({
        query: '',
        status: 'all'
      })
    }), /*#__PURE__*/React.createElement(P.Pager, {
      page: data.page,
      busy: list.loading,
      onPage: page => change({
        page
      }, true),
      onSize: size => change({
        size
      })
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: detail.error
    }), detail.loading && /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "loading",
      title: "\u6B63\u5728\u8BFB\u53D6\u8FD9\u6761\u8BB0\u5F55\u7684\u8BE6\u60C5"
    })), item && /*#__PURE__*/React.createElement(P.Detail, {
      item: item,
      onClose: () => choose(null),
      onHandle: () => setDialog(true),
      onHistory: () => setTab('records'),
      navigate: navigate,
      canNavigate: typeof onNavigate === 'function'
    })), !external && tab === 'analysis' && /*#__PURE__*/React.createElement(React.Fragment, null, analysisRead.loading && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u540C\u4E00\u6B63\u5F0F\u8BA1\u5212\u7684\u5206\u6790\u4F9D\u636E\u3002"), analysisRead.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: reload
    }, "\u5237\u65B0\u5206\u6790"), analysisData && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(ErrorBox, {
      error: analysisRead.error
    }), /*#__PURE__*/React.createElement(window.ResourceControls.Issues, {
      issues: analysisData.issues
    }), q.category === 'material' ? /*#__PURE__*/React.createElement(window.DashboardAnalysisPanels.Material, {
      data: analysisData
    }) : analysisData.plan && (q.category === 'downtime' ? /*#__PURE__*/React.createElement(window.DashboardAnalysisPanels.Downtime, {
      data: analysisData,
      selected: analysisBatch,
      onSelect: setAnalysisBatch
    }) : q.category === 'actual' ? /*#__PURE__*/React.createElement(window.DashboardAnalysisPanels.Actual, {
      data: analysisData,
      navigate: navigate
    }) : /*#__PURE__*/React.createElement(window.DashboardAnalysisPanels.Delivery, {
      data: analysisData,
      selected: analysisBatch,
      onSelect: setAnalysisBatch,
      onCompare: () => setTab('compare')
    })), !['material', 'actual'].includes(q.category) && /*#__PURE__*/React.createElement(P.Pressure, {
      data: data,
      navigate: navigate,
      canNavigate: typeof onNavigate === 'function'
    }))), !external && tab === 'compare' && (['candidate', 'delivery', 'all'].includes(q.category) ? /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.DashboardCandidates, {
      key: q.category,
      catalog: data.candidate_catalog,
      initialContext: comparisonState.context,
      onState: onComparisonState,
      selectedBatch: analysisBatch,
      onSelectBatch: setAnalysisBatch,
      issueBatchRef: q.category === 'delivery' ? analysisBatch || item && item.source.batch_ref || null : null
    }), /*#__PURE__*/React.createElement(P.Candidates, {
      data: data,
      navigate: navigate,
      canNavigate: typeof onNavigate === 'function'
    })) : /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u672C\u95EE\u9898\u5019\u9009\u72B6\u6001"
    }, /*#__PURE__*/React.createElement("h3", null, "\u8FD9\u4E2A\u95EE\u9898\u8FD8\u6CA1\u6709\u5355\u72EC\u7684\u5019\u9009\u65B9\u6848"), /*#__PURE__*/React.createElement("p", null, "\u8FD9\u91CC\u4E0D\u4F1A\u62FF\u5176\u4ED6\u95EE\u9898\u7684\u5019\u9009\u65B9\u6848\u5F53\u6210\u672C\u95EE\u9898\u7684\u7ED3\u8BBA\u3002"), /*#__PURE__*/React.createElement(Button, {
      icon: "git-compare-arrows",
      onClick: () => category('candidate')
    }, "\u67E5\u770B\u73B0\u6709\u5019\u9009\u65B9\u6848"))), handlingAvailable && activeTab === 'records' && /*#__PURE__*/React.createElement(window.DashboardHistory, {
      read: history,
      selected: selected,
      rows: data.items,
      historyPage: historyPage,
      onPage: setHistoryPage,
      onSelect: choose,
      onHandle: () => setDialog(true)
    }))))), /*#__PURE__*/React.createElement("footer", {
      className: "dy-footer"
    }, /*#__PURE__*/React.createElement("span", null, "\u6B63\u5F0F\u8BA1\u5212 / \u62A5\u5DE5\u8BB0\u5F55 / \u8D44\u6E90\u73ED\u8868 / \u9F50\u5957\u8BB0\u5F55 / \u5916\u534F\u767B\u8BB0"), /*#__PURE__*/React.createElement("span", null, "\u98CE\u9669\u4E0E\u5904\u7F6E\u72EC\u7ACB \xB7 \u5916\u534F\u56DE\u5382\u4E0D\u7B49\u4E8E\u5DE5\u5E8F\u5B8C\u5DE5")), dialog && (command.saved || item) && /*#__PURE__*/React.createElement(window.DashboardHandling, {
      key: command.saved ? command.saved.request_key : item.item_ref,
      item: item,
      command: command,
      onClose: () => setDialog(false),
      onFinish: finish
    }), navigationConfirmation && /*#__PURE__*/React.createElement(P.NavigationConfirmation, {
      entry: navigationConfirmation,
      error: navError,
      onClose: () => setNavigationConfirmation(null),
      onConfirm: confirmNavigation
    }));
  }
  function WorkbenchDashboardWorkspace({
    initialContext = {},
    onNavigate
  }) {
    let start;
    try {
      C.check(C.object(initialContext));
      const {
        analysis_batch_ref,
        comparison,
        ...base
      } = initialContext;
      C.check(analysis_batch_ref === undefined || C.ref(analysis_batch_ref));
      start = {
        ...S.context(base),
        analysisBatch: analysis_batch_ref || null,
        comparison: window.DashboardCandidateComparisonAPI.context(comparison === undefined ? {} : comparison)
      };
      start.q = durableScope(start.q);
    } catch (error) {
      return /*#__PURE__*/React.createElement("div", {
        className: "plana dashboard-live"
      }, /*#__PURE__*/React.createElement(window.DashboardStyles, null), /*#__PURE__*/React.createElement("h2", {
        className: "wb-page-title"
      }, "\u8BA1\u5212\u5458\u503C\u73ED\u53F0"), /*#__PURE__*/React.createElement(ErrorBox, {
        error: error
      }));
    }
    return /*#__PURE__*/React.createElement(Content, {
      key: JSON.stringify(start),
      start: start,
      onNavigate: onNavigate
    });
  }
  window.WorkbenchDashboardWorkspace = WorkbenchDashboardWorkspace;
})();
