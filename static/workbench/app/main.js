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
  if (boot.schema_version !== 1 || !window.React || !window.ReactDOM || !window.APSWorkbenchUI || !window.APSWorkbenchTheme || !window.APSWorkbenchTransport || !window.APSWorkbenchSystemContract || typeof SystemLive !== 'function' || typeof window.ResourceLive !== 'function' || typeof window.WorkbenchControls !== 'function' || typeof window.WorkbenchControlStyles !== 'function' || typeof window.WorkbenchNumberControls !== 'function' || typeof window.PlanWorkspace !== 'function' || typeof window.ReportWorkspace !== 'function' || typeof window.ReviewWorkspace !== 'function' || typeof window.BatchWorkspace !== 'function' || typeof window.MasterOverviewWorkspace !== 'function' || typeof window.SystemMaintenanceWorkspace !== 'function' || typeof window.FieldWorkspace !== 'function' || typeof window.ActualGanttWorkspace !== 'function' || typeof window.PreflightWorkspace !== 'function' || typeof window.RunWorkspace !== 'function' || typeof window.PlanCenterWorkspace !== 'function' || typeof window.RunCandidateWorkspace !== 'function' || typeof window.RunHistoryWorkspace !== 'function' || typeof window.CalibrationWorkspace !== 'function' || typeof window.RunAdoptionAction !== 'function' || typeof window.WorkbenchTrialWorkspace !== 'function' || typeof window.TrialAdoptionAction !== 'function' || typeof window.WorkbenchDashboardWorkspace !== 'function' || !window.WorkbenchNavigation || !window.WorkbenchCaption || !window.WorkbenchPageContext || !window.WorkbenchBoundary || !window.WorkbenchGuards || typeof window.WorkbenchGuardHost !== 'function' || !window.WorkbenchDensity || !window.WorkbenchScrollShadows) {
    fail('工作台资源未完整加载，请检查本机安装文件。');
    return;
  }
  try {
    window.WorkbenchNavigation.validateBoot(boot);
  } catch (_) {
    fail('工作台导航信息不完整，请检查本机安装文件。');
    return;
  }
  function href(view) {
    return window.WorkbenchNavigation.href(boot, view);
  }
  function WorkbenchShell({
    page,
    theme,
    density,
    navigate,
    switchTab,
    openHelp,
    messages,
    dismissMessage,
    navigationError,
    children
  }) {
    const view = page.view,
      active = boot.view_aliases[view] || view;
    // The plan-center tab strip only describes the plan views; inside 排产历史 it would contradict the header and content.
    const planTabs = ['analysis', 'gantt', 'delay'],
      showPlanTabs = planTabs.includes(view) && !window.WorkbenchNavigation.historyView(page);
    const content = React.useRef(null);
    React.useEffect(() => window.WorkbenchScrollShadows.attach(content.current), []);
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
      fill: "var(--ui-text-inverse)",
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
    }, boot.nav_groups.map(group => /*#__PURE__*/React.createElement("div", {
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
      className: "main-content",
      ref: content
    }, /*#__PURE__*/React.createElement("header", {
      className: "top-header"
    }, /*#__PURE__*/React.createElement("h2", {
      className: "top-title"
    }, window.WorkbenchNavigation.title(boot, page)), /*#__PURE__*/React.createElement(window.WorkbenchCaption.Caption, null), /*#__PURE__*/React.createElement("div", {
      className: "header-controls"
    }, /*#__PURE__*/React.createElement("span", {
      className: "wb-instance-label",
      title: boot.instance_label
    }, boot.instance_label), /*#__PURE__*/React.createElement("a", {
      className: "hdr-pill wb-help-link",
      href: window.WorkbenchNavigation.helpUrl(boot, page),
      onClick: event => {
        if (event.button || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        openHelp();
      }
    }, "\u5E2E\u52A9"), /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "hdr-pill",
      onClick: () => window.APSWorkbenchTheme.set(theme === 'dark' ? 'light' : 'dark')
    }, /*#__PURE__*/React.createElement("span", {
      "aria-hidden": "true"
    }, theme === 'dark' ? '☀' : '☾'), "\u5207\u6362", theme === 'dark' ? '浅色' : '深色'), /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "hdr-pill",
      "aria-pressed": density === 'compact',
      onClick: () => window.WorkbenchDensity.set(density === 'compact' ? 'comfortable' : 'compact')
    }, "\u7D27\u51D1\u8868\u683C"))), /*#__PURE__*/React.createElement("main", {
      className: "page-content"
    }, messages.length > 0 && /*#__PURE__*/React.createElement("section", {
      className: "wb-server-messages",
      "aria-label": "\u64CD\u4F5C\u7ED3\u679C"
    }, messages.map((value, index) => /*#__PURE__*/React.createElement("div", {
      className: "wb-server-message",
      "data-kind": value.category,
      key: index,
      role: ['error', 'danger', 'warning'].includes(value.category) ? 'alert' : 'status'
    }, /*#__PURE__*/React.createElement("span", {
      className: "wb-server-badge"
    }, {
      error: '失败',
      danger: '失败',
      warning: '注意',
      success: '成功'
    }[value.category] || '提示'), /*#__PURE__*/React.createElement("p", null, value.message), /*#__PURE__*/React.createElement("button", {
      type: "button",
      "aria-label": "\u5173\u95ED\u6D88\u606F",
      title: "\u5173\u95ED\u6D88\u606F",
      onClick: () => dismissMessage(index)
    }, /*#__PURE__*/React.createElement(Ico, {
      name: "x"
    }))))), navigationError && /*#__PURE__*/React.createElement("p", {
      className: "wb-navigation-error",
      role: "alert"
    }, navigationError), showPlanTabs && /*#__PURE__*/React.createElement("div", {
      className: "wb-view-tabs",
      role: "tablist",
      "aria-label": "\u8BA1\u5212\u4E2D\u5FC3\u89C6\u56FE",
      onKeyDown: event => {
        if (event.altKey || event.ctrlKey || event.metaKey) return;
        const tabs = Array.from(event.currentTarget.querySelectorAll('[role="tab"]')),
          index = tabs.indexOf(document.activeElement);
        const target = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : -1;
        if (target >= 0) {
          event.preventDefault();
          tabs[target].focus();
        }
      }
    }, planTabs.map(id => /*#__PURE__*/React.createElement("button", {
      type: "button",
      key: id,
      role: "tab",
      id: 'wb-view-tab-' + id,
      "aria-controls": "wb-view-panel",
      "aria-selected": id === view,
      tabIndex: id === view ? 0 : -1,
      onClick: () => switchTab(id)
    }, boot.titles[id]))), /*#__PURE__*/React.createElement("div", {
      id: "wb-view-panel",
      role: showPlanTabs ? 'tabpanel' : undefined,
      "aria-labelledby": showPlanTabs ? 'wb-view-tab-' + view : undefined
    }, children))));
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
    const [navigationError, setNavigationError] = React.useState('');
    const activePage = React.useRef(page),
      restoring = React.useRef(true),
      historyGuard = React.useRef(null);
    activePage.current = page;
    const {
      view,
      context
    } = page;
    const initialContext = Object.keys(context).length ? context : undefined;
    const batchAdapter = React.useMemo(() => window.APSBatchAPI.create(), []);
    const [preference, setPreference] = React.useState(window.APSWorkbenchTheme.get());
    const [density, setDensity] = React.useState(window.WorkbenchDensity.get());
    React.useEffect(() => {
      root.setAttribute('data-workbench-boot', 'ready');
      window.dispatchEvent(new Event('aps-workbench-ready'));
    }, []);
    React.useEffect(() => window.APSWorkbenchTheme.subscribe(setPreference), []);
    React.useEffect(() => window.WorkbenchDensity.subscribe(setDensity), []);
    React.useEffect(() => {
      const previous = history.scrollRestoration;
      history.scrollRestoration = 'manual';
      let frame = 0;
      const save = () => {
        if (restoring.current || activePage.current.error || historyGuard.current && historyGuard.current.busy()) return;
        try {
          window.WorkbenchNavigation.remember(boot, activePage.current);
          if (historyGuard.current) historyGuard.current.sync();
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
        setNavigationError('');
        const next = currentPage();
        activePage.current = next;
        setPage(next);
      };
      if (!activePage.current.error) historyGuard.current = window.WorkbenchNavigation.guardHistory(boot, {
        hasDirty: () => window.WorkbenchGuards.hasDirty(),
        confirmLeave: () => window.WorkbenchGuards.confirmLeave(),
        onRestore: restore,
        onError: error => setNavigationError(error.message)
      });
      window.addEventListener('pagehide', save);
      document.addEventListener('scroll', scroll, true);
      return () => {
        cancelAnimationFrame(frame);
        history.scrollRestoration = previous;
        if (historyGuard.current) historyGuard.current.dispose();
        historyGuard.current = null;
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
      document.title = window.WorkbenchNavigation.title(boot, page) + ' · APS 智能排产';
    }, [view, page.key]);
    const navigate = async (target, nextContext, preferSaved = false) => {
      if (target === view && nextContext === undefined && !page.error) return;
      if (historyGuard.current && historyGuard.current.busy()) return;
      const origin = activePage.current;
      try {
        if (page.error) {
          await window.WorkbenchGuards.leaveExternal(() => {
            if (activePage.current === origin) location.assign(href(target));
          });
          return;
        }
        if (!(await window.WorkbenchGuards.confirmLeave()) || activePage.current !== origin) return;
        const next = window.WorkbenchNavigation.navigate(boot, page, target, nextContext, preferSaved);
        if (historyGuard.current) historyGuard.current.sync();
        restoring.current = true;
        activePage.current = next;
        setMessages([]);
        setNavigationError('');
        setPage(next);
      } catch (error) {
        setNavigationError(error.message);
      }
    };
    const switchTab = target => {
      if (target === view) return;
      try {
        navigate(target, window.WorkbenchNavigation.read(boot).context);
      } catch (error) {
        setNavigationError(error.message);
      }
    };
    const openHelp = async () => {
      const origin = activePage.current;
      try {
        await window.WorkbenchGuards.leaveExternal(() => {
          if (activePage.current === origin) location.assign(window.WorkbenchNavigation.helpUrl(boot, origin));
        });
      } catch (error) {
        setNavigationError(error.message);
      }
    };
    const rememberTrialTarget = nextContext => {
      window.TrialContract.target(nextContext);
      const entry = currentPage();
      if (entry.view !== 'trial' || entry.key !== page.key) throw new Error('当前页面已变化，未覆盖其他页面的恢复记录。');
      window.WorkbenchNavigation.replaceContext(boot, entry, nextContext);
      if (historyGuard.current) historyGuard.current.sync();
    };
    const rememberPage = React.useCallback(nextContext => {
      if (activePage.current.view !== view || activePage.current.key !== page.key) return;
      if (historyGuard.current && historyGuard.current.busy()) return;
      try {
        window.WorkbenchNavigation.replaceContext(boot, activePage.current, nextContext);
        if (historyGuard.current) historyGuard.current.sync();
      } catch (error) {
        setPage(old => ({
          ...old,
          error: error.message
        }));
      }
    }, [view, page.key]);
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.WorkbenchControlStyles, null), /*#__PURE__*/React.createElement(window.WorkbenchControls, null), /*#__PURE__*/React.createElement(window.WorkbenchNumberControls, null), /*#__PURE__*/React.createElement(window.WorkbenchCaption.Styles, null), /*#__PURE__*/React.createElement(window.WorkbenchGuardHost, null), /*#__PURE__*/React.createElement(window.WorkbenchPageContext.Provider, {
      key: view + ':' + page.key,
      remember: rememberPage
    }, /*#__PURE__*/React.createElement(window.WorkbenchCaption.Provider, {
      key: view + ':' + page.key
    }, /*#__PURE__*/React.createElement(WorkbenchShell, {
      page: page,
      theme: preference.theme,
      density: density.density,
      navigate: navigate,
      switchTab: switchTab,
      openHelp: openHelp,
      messages: messages,
      navigationError: navigationError,
      dismissMessage: index => setMessages(items => items.filter((_value, current) => current !== index))
    }, preference.error && /*#__PURE__*/React.createElement("p", {
      role: "alert",
      className: "sm-error"
    }, preference.error), density.error && /*#__PURE__*/React.createElement("p", {
      role: "alert",
      className: "sm-error"
    }, density.error), /*#__PURE__*/React.createElement(window.WorkbenchBoundary, {
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
