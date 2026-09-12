(function () {
  'use strict';

  const C = window.APSMasterOverviewContract,
    {
      Button,
      ErrorBox
    } = window.ResourceControls;
  const {
    Table,
    Tabs,
    Pager
  } = window.MasterOverviewTable;
  const {
    useState,
    useEffect,
    useMemo,
    useRef
  } = React;
  async function readList(api, scope, page, token, signal) {
    if (page > 1 && !token) {
      const first = await api.list(scope, 1, undefined, signal);
      token = first.meta.snapshot_ref;
    }
    return api.list(scope, page, token, signal);
  }
  function readContext(context) {
    const empty = {
      scope: C.scope({}),
      page: 1,
      selected: null,
      section: 'issues',
      detailPage: 1
    };
    if (context == null) return empty;
    if (!C.canonical(context) || typeof context !== 'object' || Array.isArray(context) || Object.keys(context).some(key => !['domain', 'entity_ref', 'read_view'].includes(key))) C.fail('主数据导航含不支持的字段。');
    if (context.read_view === undefined) {
      if (!C.ref(context.entity_ref) || !C.domains.some(row => row[0] === context.domain)) C.fail('初始定位缺少数据域或永久引用。');
      return {
        ...empty,
        initial: {
          domain: context.domain,
          entity_ref: context.entity_ref
        }
      };
    }
    if (Object.keys(context).length !== 1) C.fail('主数据定位与恢复范围不能混用。');
    const view = context.read_view;
    if (!view || typeof view !== 'object' || Array.isArray(view) || Object.keys(view).some(key => !['scope', 'page', 'selected', 'section', 'detail_page'].includes(key))) C.fail('主数据恢复记录只能包含只读查看状态。');
    const scope = C.scope(view.scope);
    if (!Number.isSafeInteger(view.page) || view.page < 1 || !Number.isSafeInteger(view.detail_page) || view.detail_page < 1 || !['issues', 'relations', 'fields'].includes(view.section)) C.fail('主数据恢复页码或详情页签不正确。');
    const selected = view.selected;
    if (selected !== null && (!selected || typeof selected !== 'object' || Array.isArray(selected) || Object.keys(selected).some(key => !['domain', 'entity_ref', 'issue_ref'].includes(key)) || !C.ref(selected.entity_ref) || !C.domains.some(row => row[0] === selected.domain) || selected.issue_ref !== undefined && !C.ref(selected.issue_ref))) C.fail('主数据恢复实体引用不正确。');
    return {
      scope,
      page: view.page,
      selected,
      section: view.section,
      detailPage: view.detail_page
    };
  }
  function MasterOverviewWorkspace({
    onNavigate,
    initialContext
  }) {
    const api = useMemo(() => window.APSMasterOverviewAPI.create(), []);
    const contextKey = C.canonical(initialContext || null);
    const initial = useMemo(() => {
      try {
        return readContext(initialContext);
      } catch (error) {
        return {
          ...readContext(null),
          error
        };
      }
    }, [contextKey]);
    const contextSeen = useRef(contextKey);
    const [request, setRequest] = useState(() => ({
      scope: initial.scope,
      page: initial.page,
      initial: initial.initial,
      restore: initial
    }));
    const [result, setResult] = useState(null),
      [loading, setLoading] = useState(true),
      [error, setError] = useState(null);
    const [selected, setSelected] = useState(null),
      [section, setSection] = useState('issues'),
      [detailPage, setDetailPage] = useState(1);
    const [detail, setDetail] = useState(null),
      [detailLoading, setDetailLoading] = useState(false),
      [detailError, setDetailError] = useState(null);
    const [search, setSearch] = useState(initial.scope.query),
      [column, setColumn] = useState(null),
      [columnText, setColumnText] = useState('');
    const [message, setMessage] = useState(''),
      [actionError, setActionError] = useState(null),
      [exporting, setExporting] = useState(false);
    const opener = useRef(null),
      listRef = useRef(null),
      exportController = useRef(null),
      alive = useRef(true);
    const detailFocus = useRef(!!(initial.initial || initial.selected));
    const data = result && result.data,
      scope = data ? data.scope : request.scope;
    const currentScope = useRef(scope);
    currentScope.current = scope;
    const refresh = () => {
      detailFocus.current = false;
      setActionError(null);
      setMessage('');
      setRequest({
        scope: currentScope.current,
        page: 1
      });
    };
    useEffect(() => {
      alive.current = true;
      return () => {
        alive.current = false;
        if (exportController.current) exportController.current.abort();
      };
    }, []);
    useEffect(() => {
      const changed = () => setRequest({
        scope: currentScope.current,
        page: 1
      });
      window.addEventListener('focus', changed);
      window.addEventListener('aps:master-data-changed', changed);
      return () => {
        window.removeEventListener('focus', changed);
        window.removeEventListener('aps:master-data-changed', changed);
      };
    }, []);
    useEffect(() => {
      if (contextSeen.current === contextKey) return;
      contextSeen.current = contextKey;
      detailFocus.current = !!(initial.initial || initial.selected);
      opener.current = null;
      setRequest({
        scope: initial.scope,
        page: initial.page,
        initial: initial.initial,
        restore: initial
      });
      setSearch(initial.scope.query);
      setColumn(null);
    }, [contextKey, initial]);
    useEffect(() => {
      const controller = new AbortController();
      let active = true;
      setLoading(true);
      setError(null);
      setResult(null);
      setSelected(null);
      setDetail(null);
      setActionError(null);
      setMessage('');
      if (exportController.current) exportController.current.abort();
      async function read() {
        try {
          if (initial.error) throw initial.error;
          let next = request.locate ? await api.locate(request.scope, request.locate, request.token, controller.signal) : await readList(api, request.scope, request.page, request.token, controller.signal);
          if (request.initial) {
            if (!C.ref(request.initial.entity_ref) || !C.domains.some(row => row[0] === request.initial.domain)) C.fail('初始定位缺少数据域或永久引用。');
            next = await api.locate(next.data.scope, request.initial, next.meta.snapshot_ref, controller.signal);
          }
          if (!active) return;
          const focus = next.data.selected,
            restored = request.restore && request.restore.selected;
          const row = restored ? next.data.rows.find(item => (item.entity_ref || item.ref) === restored.entity_ref && item.domain === restored.domain && (!restored.issue_ref || item.issue_ref === restored.issue_ref)) : focus ? next.data.rows.find(item => item.ref === focus.entity_ref && item.domain === focus.domain) : next.data.rows[0];
          if (restored && !row) C.fail('原选中实体已不在当前范围，未自动替换成其他记录。');
          setResult(next);
          setSelected(row ? selection(row) : null);
          setSection(request.restore ? request.restore.section : 'issues');
          setDetailPage(request.restore ? request.restore.detailPage : 1);
        } catch (failure) {
          if (active && failure.name !== 'AbortError') setError(failure);
        } finally {
          if (active) setLoading(false);
        }
      }
      read();
      return () => {
        active = false;
        controller.abort();
      };
    }, [api, request]);
    useEffect(() => {
      if (!result || !selected) {
        setDetail(null);
        setDetailLoading(false);
        setDetailError(null);
        return undefined;
      }
      const controller = new AbortController();
      let active = true;
      setDetailLoading(true);
      setDetail(null);
      setDetailError(null);
      api.detail(result.data.scope, selected, section, detailPage, result.meta.snapshot_ref, controller.signal).then(value => {
        if (active) setDetail(value);
      }).catch(failure => {
        if (active && failure.name !== 'AbortError') setDetailError(failure);
      }).finally(() => {
        if (active) setDetailLoading(false);
      });
      return () => {
        active = false;
        controller.abort();
      };
    }, [api, result, selected, section, detailPage]);
    window.WorkbenchPageContext.useSnapshot({
      read_view: {
        scope,
        page: data ? data.page.number : 1,
        selected: selected ? {
          domain: selected.domain,
          entity_ref: selected.entity_ref,
          ...(selected.issue_ref ? {
            issue_ref: selected.issue_ref
          } : {})
        } : null,
        section,
        detail_page: detailPage
      }
    }, !!data && !loading && !error && !initial.error && !detailLoading && !detailError && (!selected || !!detail));
    function selection(row) {
      return {
        ...row,
        entity_ref: row.entity_ref || row.ref
      };
    }
    function filter(patch) {
      detailFocus.current = false;
      setRequest({
        scope: C.scope({
          ...scope,
          ...patch
        }),
        page: 1
      });
      setColumn(null);
    }
    function select(row, button) {
      detailFocus.current = true;
      opener.current = button;
      setSelected(selection(row));
      setSection('issues');
      setDetailPage(1);
    }
    function clearFilters() {
      setSearch('');
      filter({
        domain: 'all',
        status: 'all',
        query: '',
        column_filters: {}
      });
    }
    function closeDetail() {
      detailFocus.current = false;
      setSelected(null);
      const target = opener.current && opener.current.isConnected ? opener.current : listRef.current;
      opener.current = target;
      if (target) target.focus();
    }
    function locate(target) {
      if (result) {
        detailFocus.current = true;
        setSearch('');
        setColumn(null);
        setRequest({
          scope: data.scope,
          token: result.meta.snapshot_ref,
          locate: target,
          page: 1
        });
      }
    }
    async function navigate(target) {
      try {
        C.target(target);
        if (target.unavailable_reason) C.fail(target.unavailable_reason);
        if (typeof onNavigate !== 'function') C.fail('维护导航尚未接入。');
        await onNavigate(target.view, target.context);
      } catch (failure) {
        setActionError(failure);
      }
    }
    async function exportRows() {
      if (!result || !data.page.total || exporting) return;
      const controller = new AbortController();
      exportController.current = controller;
      setExporting(true);
      setMessage('');
      setActionError(null);
      try {
        const file = await api.export(data.scope, result.meta.snapshot_ref, data.page.total, controller.signal);
        if (alive.current && !controller.signal.aborted) {
          window.APSMasterOverviewAPI.save(file);
          setMessage('已发起下载：' + file.filename + '，共 ' + file.count + ' 条。');
        }
      } catch (failure) {
        if (alive.current && failure.name !== 'AbortError') setActionError(failure);
      } finally {
        if (alive.current) setExporting(false);
      }
    }
    const overview = data && data.overview,
      metrics = overview && overview.stats;
    const empty = {
      scope,
      rows: [],
      page: {
        number: 1,
        size: scope.size,
        total: 0,
        pages: 1
      }
    };
    return /*#__PURE__*/React.createElement("section", {
      className: "plana master-overview",
      "aria-label": "\u4E3B\u6570\u636E\u603B\u89C8"
    }, /*#__PURE__*/React.createElement(window.MasterOverviewStyles, null), /*#__PURE__*/React.createElement("header", {
      className: "mo-heading"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", {
      className: "wb-page-title"
    }, "\u4E3B\u6570\u636E\u603B\u89C8"), /*#__PURE__*/React.createElement("p", {
      className: "wb-page-context"
    }, result ? '基础资料 · 本机记录 · ' + window.WorkbenchFormat.dateTime(result.meta.as_of) : '基础资料 · 待读取')), /*#__PURE__*/React.createElement("div", {
      className: "mo-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      className: "btn mo-icon",
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u4E3B\u6570\u636E",
      onClick: refresh
    }), /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      transfer: "export",
      disabled: !data || !data.page.total || loading || exporting,
      onClick: exportRows
    }, "\u5BFC\u51FA\u7B5B\u9009\u7ED3\u679C"), /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      className: "btn primary",
      reason: typeof onNavigate !== 'function' ? '维护导航尚未接入。' : '',
      onClick: async () => {
        try {
          await onNavigate('process', {
            source: 'production'
          });
        } catch (failure) {
          setActionError(failure);
        }
      }
    }, "\u7EF4\u62A4\u57FA\u7840\u8D44\u6599"))), /*#__PURE__*/React.createElement("div", {
      className: "wb-metrics mo-metrics",
      "aria-label": "\u603B\u89C8\u72B6\u6001"
    }, [['entities', overview && !overview.complete ? '已读取实体' : '实体条目'], ['issues', '待维护项'], ['affected', '涉及实体'], ['relations', '已关联条目对']].map(([key, label]) => /*#__PURE__*/React.createElement("div", {
      className: "wb-metric",
      key: key,
      "data-tone": key === 'issues' ? 'warn' : undefined
    }, /*#__PURE__*/React.createElement("span", {
      className: "wb-metric-label"
    }, label), /*#__PURE__*/React.createElement("strong", {
      className: "wb-metric-value"
    }, metrics ? C.value(metrics[key]) : '未加载')))), /*#__PURE__*/React.createElement("div", {
      className: "wb-metrics mo-domains",
      "aria-label": "\u4E3B\u6570\u636E\u57DF\u6570\u91CF"
    }, C.domains.map(([id, label], index) => {
      const domain = overview && overview.domains[index];
      return /*#__PURE__*/React.createElement("button", {
        type: "button",
        className: "wb-metric mo-domain",
        key: id,
        "aria-pressed": scope.domain === id,
        "aria-label": '查看数据域 ' + label,
        onClick: () => filter({
          domain: scope.domain === id ? 'all' : id
        }),
        disabled: loading
      }, /*#__PURE__*/React.createElement("span", {
        className: "wb-metric-label"
      }, label), /*#__PURE__*/React.createElement("strong", {
        className: "wb-metric-value"
      }, domain && domain.loaded ? domain.count : '未加载'), /*#__PURE__*/React.createElement("span", {
        className: "wb-metric-helper"
      }, domain && domain.loaded ? domain.attention + ' 条需维护' + (domain.unknown ? ' · ' + domain.unknown + ' 条未核实' : '') : '来源未加载'));
    })), overview && /*#__PURE__*/React.createElement("p", {
      className: "mo-basis"
    }, overview.basis), overview && overview.gaps.length > 0 && /*#__PURE__*/React.createElement("details", {
      className: "mo-gaps",
      open: true
    }, /*#__PURE__*/React.createElement("summary", null, "\u539F\u59CB\u6570\u636E\u7F3A\u53E3 ", overview.gaps.length, " \u9879"), /*#__PURE__*/React.createElement("ul", null, overview.gaps.map((gap, index) => /*#__PURE__*/React.createElement("li", {
      key: index
    }, gap.message)))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error || actionError
    }), message && /*#__PURE__*/React.createElement("div", {
      className: "mo-message",
      role: "status"
    }, message), /*#__PURE__*/React.createElement(Tabs, {
      label: "\u6E05\u5355\u7C7B\u578B",
      value: scope.view,
      onChange: view => filter({
        view,
        status: 'all',
        column_filters: {}
      }),
      values: [["issues", "待维护项", metrics ? metrics.issues : '未加载'], ["entities", "实体清单", metrics ? metrics.entities : '未加载']]
    }), /*#__PURE__*/React.createElement("form", {
      className: "mo-tools",
      onSubmit: event => {
        event.preventDefault();
        filter({
          query: search
        });
      }
    }, /*#__PURE__*/React.createElement("label", null, "\u6570\u636E\u57DF", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u7B5B\u9009\u6570\u636E\u57DF",
      value: scope.domain,
      onChange: event => filter({
        domain: event.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "all"
    }, "\u5168\u90E8\u6570\u636E\u57DF"), C.domains.map(([id, label]) => /*#__PURE__*/React.createElement("option", {
      key: id,
      value: id
    }, label)))), /*#__PURE__*/React.createElement("label", null, "\u72B6\u6001", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u7B5B\u9009\u68C0\u67E5\u72B6\u6001",
      value: scope.status,
      onChange: event => filter({
        status: event.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "all"
    }, "\u5168\u90E8\u72B6\u6001"), Object.entries(C.statuses).map(([id, label]) => /*#__PURE__*/React.createElement("option", {
      key: id,
      value: id
    }, label)))), /*#__PURE__*/React.createElement("label", {
      className: "mo-search"
    }, /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u4E3B\u6570\u636E",
      placeholder: "\u7F16\u53F7\u3001\u540D\u79F0\u6216\u5F85\u7EF4\u62A4\u9879",
      value: search,
      maxLength: 1000,
      onChange: event => setSearch(event.target.value)
    })), /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      type: "submit",
      icon: "search",
      className: "btn mo-icon",
      "aria-label": "\u6267\u884C\u4E3B\u6570\u636E\u641C\u7D22"
    }), /*#__PURE__*/React.createElement("label", null, "\u6392\u5E8F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u4E3B\u6570\u636E\u6392\u5E8F",
      value: scope.sort,
      onChange: event => filter({
        sort: event.target.value,
        direction: ['label', 'business_code'].includes(event.target.value) ? 'asc' : 'desc'
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: "issue_count"
    }, "\u5F85\u7EF4\u62A4\u9879"), /*#__PURE__*/React.createElement("option", {
      value: "business_code"
    }, "\u7F16\u53F7"), /*#__PURE__*/React.createElement("option", {
      value: "label"
    }, "\u540D\u79F0"), /*#__PURE__*/React.createElement("option", {
      value: "relation_count"
    }, "\u5173\u8054\u9879"))), /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: "chevron-down",
      className: 'btn mo-icon' + (scope.direction === 'asc' ? ' mo-sort-asc' : ''),
      "aria-label": scope.direction === 'asc' ? '切换为降序' : '切换为升序',
      onClick: () => filter({
        direction: scope.direction === 'asc' ? 'desc' : 'asc'
      })
    }), /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      className: "btn mo-icon",
      icon: "x",
      "aria-label": "\u6E05\u9664\u4E3B\u6570\u636E\u7B5B\u9009",
      onClick: clearFilters
    })), column && /*#__PURE__*/React.createElement("form", {
      className: "mo-filter-band",
      onSubmit: event => {
        event.preventDefault();
        const filters = {
          ...scope.column_filters
        };
        if (columnText) filters[column] = columnText;else delete filters[column];
        filter({
          column_filters: filters
        });
      }
    }, /*#__PURE__*/React.createElement("label", null, C.columns[scope.view].find(row => row[0] === column)[1], /*#__PURE__*/React.createElement("input", {
      "aria-label": "\u5217\u5305\u542B\u6587\u5B57",
      autoFocus: true,
      value: columnText,
      maxLength: 1000,
      onChange: event => setColumnText(event.target.value)
    })), /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      type: "submit",
      icon: "search"
    }, "\u5E94\u7528\u5217\u7B5B\u9009"), /*#__PURE__*/React.createElement(Button, {
      reasonDisplay: "inline",
      icon: "x",
      "aria-label": "\u5173\u95ED\u5217\u7B5B\u9009",
      onClick: () => setColumn(null)
    })), Object.keys(scope.column_filters).length > 0 && /*#__PURE__*/React.createElement("p", {
      className: "mo-muted"
    }, "\u5DF2\u542F\u7528 ", Object.keys(scope.column_filters).length, " \u9879\u5217\u7B5B\u9009"), /*#__PURE__*/React.createElement("div", {
      className: selected ? 'mo-workspace wb-detail-layout' : 'mo-workspace'
    }, /*#__PURE__*/React.createElement("div", {
      className: "mo-list",
      ref: listRef,
      tabIndex: -1
    }, /*#__PURE__*/React.createElement(Table, {
      data: data || empty,
      selected: selected,
      onSelect: select,
      onMaintain: navigate,
      onClear: clearFilters,
      onRetry: refresh,
      navigation: typeof onNavigate === 'function',
      loading: loading,
      error: error,
      onFilter: key => {
        setColumn(key);
        setColumnText(scope.column_filters[key] || '');
      }
    }), data && /*#__PURE__*/React.createElement(Pager, {
      page: data.page,
      disabled: loading,
      onSize: size => filter({
        size
      }),
      onPage: page => setRequest({
        scope: data.scope,
        page,
        token: result.meta.snapshot_ref
      })
    })), /*#__PURE__*/React.createElement(window.MasterOverviewDetail, {
      result: detail,
      selected: selected,
      section: section,
      onSection: value => {
        setSection(value);
        setDetailPage(1);
      },
      onPage: setDetailPage,
      onLocate: locate,
      onMaintain: navigate,
      onBack: closeDetail,
      navigation: typeof onNavigate === 'function',
      loading: detailLoading,
      error: detailError,
      triggerRef: opener,
      autoFocus: detailFocus.current
    })));
  }
  window.MasterOverviewWorkspace = MasterOverviewWorkspace;
  MasterOverviewWorkspace.readContext = readContext;
  MasterOverviewWorkspace.readList = readList;
})();
