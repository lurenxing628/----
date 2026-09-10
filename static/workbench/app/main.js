(function () {
  'use strict';

  const root = document.getElementById('root');
  const fail = message => {
    root.setAttribute('data-workbench-boot', 'failed');
    const alert = document.createElement('p');
    alert.setAttribute('role', 'alert');
    alert.textContent = message;
    const retry = document.createElement('a');
    retry.href = location.href;
    retry.textContent = '重新加载';
    root.replaceChildren(alert, retry);
  };
  let boot;
  try {
    boot = JSON.parse(document.getElementById('workbench-boot').textContent);
    if (!boot || typeof boot !== 'object' || Array.isArray(boot)) throw new Error('Invalid boot object');
  } catch (_) {
    fail('工作台启动信息无法读取，请重新打开本机应用。');
    return;
  }
  if (boot.messages !== undefined && (!Array.isArray(boot.messages) || boot.messages.some(value => !value || typeof value.category !== 'string' || typeof value.message !== 'string'))) {
    fail('工作台返回消息格式不正确，请重新加载后核对原操作结果。');
    return;
  }
  if (boot.schema_version !== 1 || !window.React || !window.ReactDOM || !window.APSWorkbenchUI || !window.APSWorkbenchTheme || !window.APSWorkbenchTransport || !window.APSWorkbenchSystemContract || typeof SystemLive !== 'function' || typeof window.ResourceLive !== 'function' || typeof window.WorkbenchControls !== 'function' || typeof window.WorkbenchControlStyles !== 'function' || typeof window.WorkbenchNumberControls !== 'function' || typeof window.PlanWorkspace !== 'function' || typeof window.ReportWorkspace !== 'function' || typeof window.ReviewWorkspace !== 'function' || typeof window.BatchWorkspace !== 'function' || typeof window.MasterOverviewWorkspace !== 'function' || typeof window.SystemMaintenanceWorkspace !== 'function' || typeof window.FieldWorkspace !== 'function' || typeof window.ActualGanttWorkspace !== 'function' || typeof window.PreflightWorkspace !== 'function' || typeof window.RunWorkspace !== 'function' || typeof window.PlanCenterWorkspace !== 'function' || typeof window.RunCandidateWorkspace !== 'function' || typeof window.RunHistoryWorkspace !== 'function' || typeof window.CalibrationWorkspace !== 'function' || typeof window.RunAdoptionAction !== 'function' || typeof window.WorkbenchTrialWorkspace !== 'function' || typeof window.TrialAdoptionAction !== 'function' || typeof window.WorkbenchDashboardWorkspace !== 'function' || !window.WorkbenchNavigation || !window.WorkbenchCaption || !window.WorkbenchPageContext || !window.WorkbenchBoundary) {
    fail('工作台资源未完整加载，请检查本机安装文件。');
    return;
  }
  function href(view) {
    return window.WorkbenchNavigation.href(boot, view);
  }
  function WorkbenchShell({
    view,
    theme,
    navigate,
    messages,
    dismissMessage,
    children
  }) {
    const active = view === 'delay' ? 'analysis' : view;
    return /*#__PURE__*/React.createElement("div", {
      className: "app-container operations-shell"
    }, /*#__PURE__*/React.createElement("aside", {
      className: "sidebar"
    }, /*#__PURE__*/React.createElement("div", {
      className: "sidebar-header"
    }, /*#__PURE__*/React.createElement("span", {
      className: "brand-tile",
      "aria-label": "APS \u667A\u80FD\u6392\u4EA7"
    }, /*#__PURE__*/React.createElement("svg", {
      viewBox: "0 0 24 24",
      width: "18",
      height: "18",
      fill: "#fff",
      "aria-hidden": "true"
    }, /*#__PURE__*/React.createElement("rect", {
      x: "4",
      y: "6",
      width: "10",
      height: "3.2",
      rx: "1.6"
    }), /*#__PURE__*/React.createElement("rect", {
      x: "7",
      y: "10.4",
      width: "12",
      height: "3.2",
      rx: "1.6",
      fillOpacity: "0.92"
    }), /*#__PURE__*/React.createElement("rect", {
      x: "4",
      y: "14.8",
      width: "8",
      height: "3.2",
      rx: "1.6",
      fillOpacity: "0.78"
    }))), /*#__PURE__*/React.createElement("span", {
      className: "brand-word"
    }, "APS \u667A\u80FD\u6392\u4EA7")), /*#__PURE__*/React.createElement("nav", {
      className: "sidebar-nav"
    }, NAV_GROUPS.map(group => /*#__PURE__*/React.createElement("div", {
      className: "nav-group",
      key: group.title
    }, /*#__PURE__*/React.createElement("div", {
      className: "nav-group-title"
    }, group.title), group.items.map(item => /*#__PURE__*/React.createElement("a", {
      key: item.id,
      href: href(item.id),
      title: item.label,
      className: 'nav-item' + (active === item.id ? ' active' : ''),
      "aria-current": active === item.id ? 'page' : undefined,
      onClick: event => {
        if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        navigate(item.id);
      }
    }, /*#__PURE__*/React.createElement(Ico, {
      name: item.icon
    }), /*#__PURE__*/React.createElement("span", {
      className: "nav-label"
    }, item.label))))))), /*#__PURE__*/React.createElement("div", {
      className: "main-content"
    }, /*#__PURE__*/React.createElement("header", {
      className: "top-header"
    }, /*#__PURE__*/React.createElement("h2", {
      className: "top-title"
    }, boot.titles[view] || '工作区不存在'), /*#__PURE__*/React.createElement(window.WorkbenchCaption.Caption, null), /*#__PURE__*/React.createElement("div", {
      className: "header-controls"
    }, /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "hdr-pill",
      onClick: () => window.APSWorkbenchTheme.set(theme === 'dark' ? 'light' : 'dark')
    }, "\u6DF1\u8272\uFF1A", theme === 'dark' ? '开' : '关'))), /*#__PURE__*/React.createElement("main", {
      className: "page-content"
    }, /*#__PURE__*/React.createElement("style", null, `.wb-server-messages { display: grid; gap: 8px; margin-bottom: 16px; }
          .wb-server-message { display: flex; align-items: flex-start; gap: 12px; padding: 10px 12px; border: 1px solid var(--ui-border); border-left: 3px solid var(--ui-primary); border-radius: 4px; background: var(--ui-surface); color: var(--ui-text); }
          .wb-server-message[data-kind="error"],.wb-server-message[data-kind="danger"] { border-left-color: #dc3545; }
          .wb-server-message[data-kind="warning"] { border-left-color: #b77900; }
          .wb-server-message[data-kind="success"] { border-left-color: #15803d; }
          .wb-server-message p { flex: 1; min-width: 0; margin: 0; overflow-wrap: anywhere; }
          .wb-server-message button { flex: 0 0 28px; width: 28px; height: 28px; display: grid; place-items: center; padding: 0; color: inherit; background: transparent; border: 0; border-radius: 4px; cursor: pointer; }
          .wb-server-message button:focus-visible { outline: 2px solid var(--ui-primary); outline-offset: 2px; }`), messages.length > 0 && /*#__PURE__*/React.createElement("section", {
      className: "wb-server-messages",
      "aria-label": "\u64CD\u4F5C\u7ED3\u679C"
    }, messages.map((value, index) => /*#__PURE__*/React.createElement("div", {
      className: "wb-server-message",
      "data-kind": value.category,
      key: index,
      role: ['error', 'danger', 'warning'].includes(value.category) ? 'alert' : 'status'
    }, /*#__PURE__*/React.createElement("p", null, value.message), /*#__PURE__*/React.createElement("button", {
      type: "button",
      "aria-label": "\u5173\u95ED\u6D88\u606F",
      title: "\u5173\u95ED\u6D88\u606F",
      onClick: () => dismissMessage(index)
    }, /*#__PURE__*/React.createElement(Ico, {
      name: "x"
    }))))), children)));
  }
  function App() {
    function currentPage() {
      try {
        return window.WorkbenchNavigation.read(boot);
      } catch (error) {
        return {
          view: boot.view,
          context: {},
          key: 0,
          error: error.message
        };
      }
    }
    const [page, setPage] = React.useState(currentPage);
    const [messages, setMessages] = React.useState(boot.messages || []);
    const activePage = React.useRef(page),
      restoring = React.useRef(true);
    activePage.current = page;
    const {
      view,
      context
    } = page;
    const initialContext = Object.keys(context).length ? context : undefined;
    const batchAdapter = React.useMemo(() => window.APSBatchAPI.create(), []);
    const [preference, setPreference] = React.useState(window.APSWorkbenchTheme.get());
    React.useEffect(() => {
      root.setAttribute('data-workbench-boot', 'ready');
      window.dispatchEvent(new Event('aps-workbench-ready'));
    }, []);
    React.useEffect(() => window.APSWorkbenchTheme.subscribe(setPreference), []);
    React.useEffect(() => {
      const previous = history.scrollRestoration;
      history.scrollRestoration = 'manual';
      let frame = 0;
      const save = () => {
        if (restoring.current || activePage.current.error) return;
        try {
          window.WorkbenchNavigation.remember(boot, activePage.current);
        } catch (error) {
          setPage(old => ({
            ...old,
            error: error.message
          }));
        }
      };
      const scroll = () => {
        cancelAnimationFrame(frame);
        frame = requestAnimationFrame(save);
      };
      const restore = () => {
        restoring.current = true;
        cancelAnimationFrame(frame);
        setMessages([]);
        setPage(currentPage());
      };
      window.addEventListener('popstate', restore);
      window.addEventListener('pagehide', save);
      document.addEventListener('scroll', scroll, true);
      return () => {
        cancelAnimationFrame(frame);
        history.scrollRestoration = previous;
        window.removeEventListener('popstate', restore);
        window.removeEventListener('pagehide', save);
        document.removeEventListener('scroll', scroll, true);
      };
    }, []);
    React.useEffect(() => {
      restoring.current = true;
      if (page.error) {
        restoring.current = false;
        return undefined;
      }
      return window.WorkbenchNavigation.restore(page, () => {
        restoring.current = false;
      });
    }, [page.view, page.key, page.error]);
    React.useEffect(() => {
      document.title = (boot.titles[view] || '工作区不存在') + ' · APS 智能排产';
    }, [view]);
    const navigate = (target, nextContext) => {
      if (target === view && nextContext === undefined && !page.error) return;
      try {
        if (page.error) {
          location.assign(href(target));
          return;
        }
        const next = window.WorkbenchNavigation.navigate(boot, page, target, nextContext);
        restoring.current = true;
        setMessages([]);
        setPage(next);
      } catch (error) {
        setPage(old => ({
          ...old,
          error: error.message
        }));
      }
    };
    const rememberTrialTarget = nextContext => {
      window.TrialContract.target(nextContext);
      const entry = currentPage();
      if (entry.view !== 'trial' || entry.key !== page.key) throw new Error('当前页面已变化，未覆盖其他页面的恢复记录。');
      window.WorkbenchNavigation.replaceContext(boot, entry, nextContext);
    };
    const rememberPage = React.useCallback(nextContext => {
      if (activePage.current.view !== view || activePage.current.key !== page.key) return;
      try {
        window.WorkbenchNavigation.replaceContext(boot, activePage.current, nextContext);
      } catch (error) {
        setPage(old => ({
          ...old,
          error: error.message
        }));
      }
    }, [view, page.key]);
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.WorkbenchControlStyles, null), /*#__PURE__*/React.createElement(window.WorkbenchControls, null), /*#__PURE__*/React.createElement(window.WorkbenchNumberControls, null), /*#__PURE__*/React.createElement(window.WorkbenchCaption.Styles, null), /*#__PURE__*/React.createElement(window.WorkbenchPageContext.Provider, {
      key: view + ':' + page.key,
      remember: rememberPage
    }, /*#__PURE__*/React.createElement(window.WorkbenchCaption.Provider, {
      key: view + ':' + page.key
    }, /*#__PURE__*/React.createElement(WorkbenchShell, {
      view: view,
      theme: preference.theme,
      navigate: navigate,
      messages: messages,
      dismissMessage: index => setMessages(items => items.filter((_value, current) => current !== index))
    }, preference.error && /*#__PURE__*/React.createElement("p", {
      role: "alert",
      className: "sm-error"
    }, preference.error), /*#__PURE__*/React.createElement(window.WorkbenchBoundary, {
      key: view + ':' + page.key
    }, page.error ? /*#__PURE__*/React.createElement("p", {
      role: "alert",
      className: "sm-error"
    }, page.error) : view === 'dashboard' ? /*#__PURE__*/React.createElement(window.WorkbenchDashboardWorkspace, {
      key: view + ':' + page.key,
      onNavigate: navigate,
      initialContext: initialContext
    }) : view === 'system' ? /*#__PURE__*/React.createElement(SystemLive, {
      boot: boot,
      theme: preference.theme,
      initialContext: initialContext
    }) : view === 'process' ? /*#__PURE__*/React.createElement(window.ResourceLive, {
      key: view + ':' + page.key,
      onNavigate: navigate,
      initialContext: initialContext
    }) : view === 'batches' ? /*#__PURE__*/React.createElement(window.BatchWorkspace, {
      key: view + ':' + page.key,
      adapter: batchAdapter,
      onNav: navigate,
      initialContext: initialContext
    }) : view === 'analysis' || view === 'gantt' || view === 'delay' ? /*#__PURE__*/React.createElement(window.PlanCenterWorkspace, {
      key: view + ':' + page.key,
      view: view,
      onNavigate: navigate,
      initialContext: initialContext
    }) : view === 'reports' ? /*#__PURE__*/React.createElement(window.ReportWorkspace, {
      key: view + ':' + page.key,
      onNav: navigate,
      initialContext: initialContext
    }) : view === 'review' ? /*#__PURE__*/React.createElement(window.ReviewWorkspace, {
      key: view + ':' + page.key,
      onNav: navigate,
      initialContext: initialContext
    }) : view === 'calib' ? /*#__PURE__*/React.createElement(window.CalibrationWorkspace, {
      key: view + ':' + page.key,
      onNavigate: navigate,
      initialContext: initialContext
    }) : view === 'basedata' ? /*#__PURE__*/React.createElement(window.MasterOverviewWorkspace, {
      key: view + ':' + page.key,
      onNavigate: navigate,
      initialContext: initialContext
    }) : view === 'field' ? /*#__PURE__*/React.createElement(window.FieldWorkspace, {
      key: view + ':' + page.key,
      onNavigate: navigate,
      initialContext: initialContext
    }) : view === 'fieldgantt' ? /*#__PURE__*/React.createElement(window.ActualGanttWorkspace, {
      key: view + ':' + page.key,
      onNavigate: navigate,
      initialContext: initialContext
    }) : view === 'run' ? /*#__PURE__*/React.createElement(window.RunWorkspace, {
      key: view + ':' + page.key,
      onNavigate: navigate,
      initialContext: initialContext
    }) : view === 'trial' ? /*#__PURE__*/React.createElement(window.WorkbenchTrialWorkspace, {
      key: view + ':' + page.key,
      onNavigate: navigate,
      initialTarget: initialContext,
      onTargetChange: rememberTrialTarget,
      renderAdoption: props => /*#__PURE__*/React.createElement(window.TrialAdoptionAction, {
        ...props
      })
    }) : /*#__PURE__*/React.createElement("section", {
      className: "wb-page-panel",
      "aria-label": boot.titles[view] || '工作区不存在'
    }, /*#__PURE__*/React.createElement("h2", null, boot.titles[view] || '工作区不存在'), /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u8BE5\u5DE5\u4F5C\u533A\u5C1A\u672A\u63A5\u5165\u771F\u5B9E\u6570\u636E\uFF0C\u6682\u4E0D\u63D0\u4F9B\u4E1A\u52A1\u64CD\u4F5C\u3002")))))));
  }
  ReactDOM.createRoot(root).render(/*#__PURE__*/React.createElement(App, null));
})();
