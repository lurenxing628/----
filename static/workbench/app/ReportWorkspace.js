(function () {
  'use strict';

  let pendingViewFocus = null;
  function Workspace({
    adapter,
    mode = 'reports',
    initialContext = {},
    onNav,
    onOpenOperation
  }) {
    const {
      Scope,
      Tabs,
      Sort,
      Page,
      Button,
      ErrorBox,
      useRead,
      Styles
    } = window.ReportControls;
    const {
      Table,
      Metrics
    } = window.ReportTable;
    const api = React.useMemo(() => adapter || window.ReportAPI.create(), [adapter]);
    const initialTopic = mode === 'review' ? 'delivery' : window.ReportAPI.topics.includes(initialContext.topic) ? initialContext.topic : 'delivery';
    const [scope, setScope] = React.useState(() => window.ReportAPI.scope(initialContext.scope || {}));
    const [state, setState] = React.useState(() => window.ReportAPI.table(initialContext.table, initialTopic));
    const [revision, refresh] = React.useReducer(value => value + 1, 0),
      [selected, setSelected] = React.useState(initialContext.selected || null),
      [notice, setNotice] = React.useState(''),
      [error, setError] = React.useState(null),
      [downloading, setDownloading] = React.useState(false),
      [format, setFormat] = React.useState('csv'),
      [catalog, setCatalog] = React.useState(!!initialContext.catalogOpen),
      [chartsOpen, setChartsOpen] = React.useState(!!initialContext.chartsOpen);
    const root = React.useRef(null),
      restored = React.useRef(false);
    const [scroll, setScroll] = React.useState(initialContext.scroll || {});
    const [resourceView, setResourceView] = React.useState(initialContext.resourceView || {
      kind: 'machine',
      page: 1
    });
    const [detailView, setDetailView] = React.useState(initialContext.detailView || {
      page: 1,
      size: 10
    });
    const [lastChoices, setLastChoices] = React.useState({});
    const input = {
      ...scope,
      ...state
    };
    const request = useRead(signal => window.ReportAPI.readView(api, input, signal), JSON.stringify(input) + revision);
    const response = request.result,
      data = response && response.data;
    const captionPlan = !request.busy && !request.error && data && data.plan;
    const captionStatus = captionPlan && {
      official: captionPlan.is_current_official ? '当前正式采用' : '历史正式计划',
      candidate: window.WorkbenchTerms.candidate,
      scenario: window.WorkbenchTerms.trial_scenario
    }[captionPlan.kind];
    window.WorkbenchCaption.useCaption(captionStatus ? {
      reference: captionPlan.plan_ref,
      label: mode === 'review' ? '复盘计划' : '报表计划',
      name: captionPlan.display_name,
      status: captionStatus,
      version: captionPlan.kind === 'official' && Number.isSafeInteger(captionPlan.version) ? '正式 v' + captionPlan.version : undefined,
      range: data.scope.plan_finish_date_from && data.scope.plan_finish_date_to ? '计划完工 ' + data.scope.plan_finish_date_from + ' 至 ' + data.scope.plan_finish_date_to : undefined
    } : null);
    window.WorkbenchPageContext.useSnapshot(data ? {
      scope: window.ReportAPI.scope(data.scope),
      topic: data.topic,
      table: {
        topic: data.topic,
        page: data.page.number,
        size: data.page.size,
        sort: data.page.sort[0].field,
        direction: data.page.sort[0].direction
      },
      selected,
      chartsOpen,
      catalogOpen: catalog,
      scroll,
      resourceView,
      detailView,
      returnTo: initialContext.returnTo
    } : null, !!data && !request.busy && !request.error);
    React.useEffect(() => {
      let frame = 0;
      const remember = event => {
        const node = root.current,
          table = node && node.querySelector('.rw-primary-table'),
          main = node && node.closest('.main-content');
        if (!node || ![table, main, document, window].includes(event.target)) return;
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(() => setScroll({
          tableLeft: table ? table.scrollLeft : 0,
          tableTop: table ? table.scrollTop : 0,
          mainTop: main ? main.scrollTop : 0,
          windowTop: window.pageYOffset
        }));
      };
      document.addEventListener('scroll', remember, true);
      return () => {
        cancelAnimationFrame(frame);
        document.removeEventListener('scroll', remember, true);
      };
    }, []);
    React.useEffect(() => {
      if (data) setLastChoices(data.choices);
    }, [response]);
    React.useEffect(() => {
      if (!data || restored.current) return;
      restored.current = true;
      if (!initialContext.scroll) return;
      const frame = requestAnimationFrame(() => {
        const table = root.current.querySelector('.rw-table-scroll'),
          main = root.current.closest('.main-content');
        if (table) {
          table.scrollLeft = initialContext.scroll.tableLeft || 0;
          table.scrollTop = initialContext.scroll.tableTop || 0;
        }
        if (main) main.scrollTop = initialContext.scroll.mainTop || 0;
        window.scrollTo(0, initialContext.scroll.windowTop || 0);
      });
      return () => cancelAnimationFrame(frame);
    }, [response]);
    const changeScope = next => {
      setScope(next);
      setState(old => ({
        ...old,
        page: 1,
        snapshot_ref: undefined
      }));
      setSelected(null);
      setCatalog(false);
      setNotice('');
      setError(null);
    };
    const changePage = patch => {
      setState(old => ({
        ...old,
        ...patch,
        snapshot_ref: response ? response.meta.snapshot_ref : old.snapshot_ref
      }));
      setSelected(null);
    };
    const changeTopic = topic => changePage({
      topic,
      sort: window.ReportAPI.sorts[topic][0],
      page: 1
    });
    function reload() {
      if (data) setScope(window.ReportAPI.scope(data.scope));
      setState(old => ({
        ...old,
        snapshot_ref: undefined
      }));
      setNotice('');
      setError(null);
      refresh();
    }
    async function download() {
      setDownloading(true);
      setError(null);
      try {
        await api.download(data.exports.url, {
          ...window.ReportAPI.scope(data.scope),
          ...window.ReportAPI.table(state, data.topic),
          snapshot_ref: response.meta.snapshot_ref,
          format
        });
        setNotice('已导出当前筛选全部 ' + data.page.total + ' 项，文件已交给浏览器下载。');
      } catch (failure) {
        setError(failure);
      } finally {
        setDownloading(false);
      }
    }
    const title = mode === 'review' ? '执行复盘' : '报表中心';
    React.useLayoutEffect(() => {
      if (pendingViewFocus !== mode) return;
      const tab = document.getElementById('analytics-view-' + mode);
      if (tab && !tab.disabled) {
        tab.focus();
        pendingViewFocus = null;
      }
    }, [mode, !!data]);
    function currentContext() {
      const table = root.current.querySelector('.rw-primary-table'),
        main = root.current.closest('.main-content');
      return {
        scope: window.ReportAPI.scope(data.scope),
        topic: data.topic,
        table: window.ReportAPI.table(state, data.topic),
        selected,
        chartsOpen,
        resourceView,
        detailView,
        catalogOpen: catalog,
        returnTo: initialContext.returnTo,
        scroll: {
          tableLeft: table ? table.scrollLeft : 0,
          tableTop: table ? table.scrollTop : 0,
          mainTop: main ? main.scrollTop : 0,
          windowTop: window.pageYOffset
        }
      };
    }
    const go = (target, resume = false) => {
      if (!resume && initialContext.returnTo && initialContext.returnTo.view === target) return onNav(target, initialContext.returnTo.context);
      const context = {
        scope: window.ReportAPI.scope(data.scope),
        topic: state.topic
      };
      onNav(target, {
        ...context,
        returnTo: {
          view: mode,
          context: currentContext()
        }
      }, resume);
    };
    function drill(topic, patch) {
      onNav('reports', {
        topic,
        scope: window.ReportAPI.scope({
          ...data.scope,
          ...patch
        }),
        returnTo: {
          view: mode,
          context: currentContext()
        }
      });
    }
    function navigateOperation(operationRef, original, row, target = 'field', reportRef = null) {
      if (!row || row.operation_ref !== operationRef || !window.FieldContract.ref(row.task_ref) || !data.plan.is_current_official || data.scope.source !== 'production' || original.snapshot_ref !== response.meta.snapshot_ref || !['field', 'fieldgantt'].includes(target) || reportRef !== null && !window.FieldContract.ref(reportRef)) {
        setError(window.APSResourceContract.failure('来源任务、记录或计划没有通过核对，没有改指其他工序。'));
        return;
      }
      const targetScope = {
        plan_ref: data.plan.plan_ref
      };
      for (const key of ['plan_finish_date_from', 'plan_finish_date_to']) if (data.scope[key]) targetScope[key] = data.scope[key];
      onNav(target, {
        plan_ref: data.plan.plan_ref,
        task_ref: row.task_ref,
        operation_ref: operationRef,
        scope: targetScope,
        ...(reportRef ? {
          report_ref: reportRef
        } : {}),
        return_to: {
          view: mode,
          context: currentContext()
        }
      });
    }
    return /*#__PURE__*/React.createElement("section", {
      ref: root,
      className: mode === 'review' ? 'er-workbench rw-workbench' : 'rw-workbench',
      "aria-label": title,
      "data-source": "production",
      "data-ready": !!data
    }, /*#__PURE__*/React.createElement(Styles, null), /*#__PURE__*/React.createElement("header", {
      className: "rw-header"
    }, /*#__PURE__*/React.createElement("div", null, /*#__PURE__*/React.createElement("h2", {
      className: "wb-page-title"
    }, title), /*#__PURE__*/React.createElement("p", {
      className: "wb-page-context"
    }, data ? data.plan.display_name + ' · 当前正式计划与报工记录' : '当前正式计划', response && /*#__PURE__*/React.createElement("span", {
      className: "rw-asof"
    }, "\u6570\u636E\u622A\u81F3 ", window.WorkbenchFormat.dateTime(response.meta.as_of)))), /*#__PURE__*/React.createElement("div", {
      className: "rw-actions"
    }, initialContext.returnTo && initialContext.returnTo.view === 'calib' && /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-left",
      disabled: typeof onNav !== 'function',
      onClick: () => go('calib')
    }, "\u8FD4\u56DE\u5DE5\u65F6\u6821\u51C6"), initialContext.returnTo && ['reports', 'review'].includes(initialContext.returnTo.view) && /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-left",
      disabled: typeof onNav !== 'function',
      onClick: () => go(initialContext.returnTo.view)
    }, "\u8FD4\u56DE\u6765\u6E90"), /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u62A5\u8868",
      busy: request.busy,
      onClick: reload
    }))), /*#__PURE__*/React.createElement("div", {
      className: "wb-view-tabs",
      role: "tablist",
      "aria-label": "\u7EDF\u8BA1\u5206\u6790\u89C6\u56FE"
    }, [['reports', '报表中心'], ['review', '执行复盘']].map(([target, label], index) => /*#__PURE__*/React.createElement("button", {
      type: "button",
      key: target,
      role: "tab",
      id: 'analytics-view-' + target,
      "aria-selected": mode === target,
      "aria-controls": "analytics-view-panel",
      tabIndex: mode === target ? 0 : -1,
      disabled: !data || typeof onNav !== 'function',
      onClick: () => target !== mode && go(target, true),
      onKeyDown: event => {
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === 'Home' ? 'reports' : event.key === 'End' ? 'review' : index === 0 ? 'review' : 'reports';
        const button = document.getElementById('analytics-view-' + next);
        if (button && !button.disabled) {
          button.focus();
          if (next !== mode) {
            pendingViewFocus = next;
            go(next, true);
          }
        }
      }
    }, label))), /*#__PURE__*/React.createElement("div", {
      id: "analytics-view-panel",
      role: "tabpanel",
      "aria-labelledby": 'analytics-view-' + mode
    }, /*#__PURE__*/React.createElement(Scope, {
      value: scope,
      onChange: changeScope,
      choices: lastChoices,
      busy: request.busy
    }), /*#__PURE__*/React.createElement(ErrorBox, {
      error: request.error || error
    }), request.error && /*#__PURE__*/React.createElement(Button, {
      icon: "refresh-cw",
      onClick: reload
    }, "\u5237\u65B0\u62A5\u8868\u6570\u636E"), notice && /*#__PURE__*/React.createElement("p", {
      className: "rw-notice",
      role: "status"
    }, notice), mode !== 'review' && /*#__PURE__*/React.createElement(Tabs, {
      topic: state.topic,
      onChange: changeTopic
    }), request.busy && /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "loading",
      title: "\u6B63\u5728\u8BFB\u53D6\u5F53\u524D\u8303\u56F4"
    }), data && /*#__PURE__*/React.createElement("div", {
      id: "report-topic-panel",
      role: mode === 'review' ? undefined : 'tabpanel',
      "aria-labelledby": mode === 'review' ? undefined : 'report-tab-' + state.topic
    }, /*#__PURE__*/React.createElement(Metrics, {
      summary: data.summary,
      topic: state.topic
    }), /*#__PURE__*/React.createElement(window.ReportEvidence.NoFeedback, {
      summary: data.summary
    }), /*#__PURE__*/React.createElement("p", {
      className: "rw-basis"
    }, "\u6309\u8BA1\u5212\u5B8C\u5DE5\u65E5\u6311\u5DE5\u5E8F \xB7 \u665A 10 \u5206\u949F\u4EE5\u4E0A\u624D\u7B97\u665A\u5B8C\u6210 \xB7 \u672A\u786E\u8BA4\u5B8C\u6210\u4E0D\u7B49\u4E8E\u6CA1\u751F\u4EA7\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "rw-table-heading"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rw-table-title"
    }, /*#__PURE__*/React.createElement("h3", null, state.topic === 'records' ? '逐次报工与旧现场事件' : ['machines', 'people'].includes(state.topic) ? '实际资源记录' : '范围内工序'), /*#__PURE__*/React.createElement("span", null, data.page.total, " \u9879")), /*#__PURE__*/React.createElement("div", {
      className: "rw-filters"
    }, /*#__PURE__*/React.createElement(Sort, {
      topic: state.topic,
      state: state,
      onChange: changePage
    }), /*#__PURE__*/React.createElement("label", null, "\u683C\u5F0F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5BFC\u51FA\u683C\u5F0F",
      value: format,
      onChange: event => setFormat(event.target.value)
    }, /*#__PURE__*/React.createElement("option", {
      value: "csv"
    }, "CSV"), /*#__PURE__*/React.createElement("option", {
      value: "xlsx"
    }, "XLSX"))), /*#__PURE__*/React.createElement(Button, {
      transfer: "export",
      busy: downloading,
      disabled: request.busy,
      reasonDisplay: "inline",
      reason: !data.page.total ? '当前范围没有可导出的结果。' : '',
      onClick: download
    }, "\u5BFC\u51FA\u8303\u56F4"))), /*#__PURE__*/React.createElement("div", {
      className: selected ? 'wb-detail-layout' : ''
    }, /*#__PURE__*/React.createElement("div", {
      className: "rw-list-pane"
    }, /*#__PURE__*/React.createElement(Table, {
      data: data,
      onDetail: ref => {
        setSelected(ref);
        setDetailView({
          page: 1,
          size: 10
        });
      },
      busy: request.busy,
      primary: true
    }), /*#__PURE__*/React.createElement(Page, {
      page: data.page,
      onChange: changePage,
      busy: request.busy
    })), selected && /*#__PURE__*/React.createElement(window.ReportDetail, {
      api: api,
      operationRef: selected,
      input: {
        ...window.ReportAPI.scope(data.scope),
        ...window.ReportAPI.table(state, data.topic),
        snapshot_ref: response.meta.snapshot_ref
      },
      onClose: () => setSelected(null),
      initialView: detailView,
      onView: setDetailView,
      onOpenOperation: onOpenOperation || (typeof onNav === 'function' ? navigateOperation : undefined)
    })), /*#__PURE__*/React.createElement(window.ReviewCharts, {
      data: data,
      open: chartsOpen,
      onChange: setChartsOpen,
      resourceView: resourceView,
      onResourceView: setResourceView,
      onDrill: typeof onNav === 'function' ? drill : undefined
    }), /*#__PURE__*/React.createElement("details", {
      className: "rw-limitations"
    }, /*#__PURE__*/React.createElement("summary", null, "\u6570\u636E\u8303\u56F4\u4E0E\u7F3A\u53E3"), /*#__PURE__*/React.createElement("ul", null, data.data_gaps.map(text => /*#__PURE__*/React.createElement("li", {
      key: text
    }, text)))), /*#__PURE__*/React.createElement("details", {
      className: "rw-catalog",
      open: catalog,
      onToggle: event => setCatalog(event.currentTarget.open)
    }, /*#__PURE__*/React.createElement("summary", null, "\u5176\u4ED6\u62A5\u8868"), catalog && /*#__PURE__*/React.createElement(window.ReportCatalog, {
      api: api,
      scope: data.scope,
      snapshot: response.meta.snapshot_ref
    })))));
  }
  function GuardedWorkspace(props) {
    try {
      window.ReportAPI.scope(props.initialContext && props.initialContext.scope || {});
      const context = props.initialContext || {},
        topic = props.mode === 'review' ? 'delivery' : context.topic || 'delivery';
      if (!window.ReportAPI.topics.includes(topic)) throw window.APSResourceContract.failure('原报表专题无效，未改用默认专题。');
      window.ReportAPI.table(context.table, topic);
      if (context.selected !== undefined && context.selected !== null && !/^[0-9a-f]{48}$/.test(context.selected)) throw window.APSResourceContract.failure('原工序编号无效，没有改选其他工序。');
      const value = props.initialContext && props.initialContext.resourceView;
      if (value !== undefined && (!value || !['machine', 'operator'].includes(value.kind) || !Number.isSafeInteger(value.page) || value.page < 1)) throw window.APSResourceContract.failure('资源工时查看状态无效，未改选其他资源。');
      const detail = props.initialContext && props.initialContext.detailView;
      if (detail !== undefined && (!detail || !Number.isSafeInteger(detail.page) || detail.page < 1 || ![10, 20, 50].includes(detail.size))) throw window.APSResourceContract.failure('报表记录详情分页无效，未改选其他记录。');
    } catch (error) {
      return /*#__PURE__*/React.createElement("section", {
        className: "rw-workbench"
      }, /*#__PURE__*/React.createElement("h2", {
        className: "wb-page-title"
      }, props.mode === 'review' ? '执行复盘' : '报表中心'), /*#__PURE__*/React.createElement(window.ResourceControls.ErrorBox, {
        error: error
      }));
    }
    return /*#__PURE__*/React.createElement(Workspace, {
      ...props
    });
  }
  window.ReportWorkspace = GuardedWorkspace;
})();
