(function () {
  'use strict';

  const U = window.TrialControls,
    A = window.TrialAdoptionHistoryAPI,
    S = window.TrialAdoptionHistoryState;
  const labels = {
    all: '全部采用',
    current: '当前正式',
    historical: '历史正式',
    unavailable: '计划不可用'
  };
  const text = value => value === null ? '暂无数据' : value;
  function Evidence({
    item,
    source
  }) {
    return /*#__PURE__*/React.createElement("details", {
      className: "wb-ref"
    }, /*#__PURE__*/React.createElement("summary", null, "\u6765\u6E90\u4E0E\u7F16\u53F7"), /*#__PURE__*/React.createElement("dl", {
      className: "tah-refs"
    }, /*#__PURE__*/React.createElement("dt", null, "\u539F\u6765\u6E90"), /*#__PURE__*/React.createElement("dd", null, U.sourceLabel(source.base_identity), /*#__PURE__*/React.createElement("br", null), Object.values(source.base)[0]), /*#__PURE__*/React.createElement("dt", null, "\u5F53\u65F6\u7684\u6B63\u5F0F\u8BA1\u5212"), /*#__PURE__*/React.createElement("dd", null, source.baseline.plan_ref ? '第 ' + source.baseline.version + ' 版 · ' + source.baseline.plan_ref : '当时还没有正式计划'), /*#__PURE__*/React.createElement("dt", null, "\u8BD5\u8C03\u65B9\u6848\u7F16\u53F7"), /*#__PURE__*/React.createElement("dd", null, source.scenario_ref), /*#__PURE__*/React.createElement("dt", null, "\u8BD5\u8C03\u8349\u7A3F\u7F16\u53F7"), /*#__PURE__*/React.createElement("dd", null, source.draft_ref), /*#__PURE__*/React.createElement("dt", null, "\u4FDD\u5B58\u6765\u6E90"), /*#__PURE__*/React.createElement("dd", null, source.saved_by, " \xB7 ", U.timeLabel(source.saved_at)), /*#__PURE__*/React.createElement("dt", null, "\u4FDD\u5B58\u64CD\u4F5C\u7F16\u53F7"), /*#__PURE__*/React.createElement("dd", null, source.save_request_key), /*#__PURE__*/React.createElement("dt", null, "\u65B0\u6B63\u5F0F\u8BA1\u5212\u7F16\u53F7"), /*#__PURE__*/React.createElement("dd", null, item.committed_plan.plan_ref), /*#__PURE__*/React.createElement("dt", null, "\u7ED3\u679C\u7F16\u53F7"), /*#__PURE__*/React.createElement("dd", null, item.receipt_ref), /*#__PURE__*/React.createElement("dt", null, "\u64CD\u4F5C\u7F16\u53F7"), /*#__PURE__*/React.createElement("dd", null, item.request_key), /*#__PURE__*/React.createElement("dt", null, "\u63D0\u4EA4\u65F6\u95F4"), /*#__PURE__*/React.createElement("dd", null, window.WorkbenchFormat.instant(item.committed_at_utc, {
      seconds: true
    })), /*#__PURE__*/React.createElement("dt", null, "\u6570\u636E\u6765\u6E90"), /*#__PURE__*/React.createElement("dd", null, "\u63D0\u4EA4\u65F6\u95F4\u6765\u81EA\u4FDD\u5B58\u4E0B\u6765\u7684\u64CD\u4F5C\u7ED3\u679C\uFF1B\u91C7\u7528\u539F\u56E0\u548C\u7ECF\u529E\u4EBA\u6765\u81EA\u63D0\u4EA4\u65F6\u6838\u5BF9\u7684\u5185\u5BB9\uFF1B\u91C7\u7528\u4EBA\u548C\u91C7\u7528\u65F6\u95F4\u6765\u81EA\u6B63\u5F0F\u8BA1\u5212\u7684\u5386\u53F2\u8BB0\u5F55\uFF1B\u5F53\u524D\u72B6\u6001\u662F\u8FD9\u6B21\u8BFB\u53D6\u5230\u7684\u3002")));
  }
  function History({
    data
  }) {
    const ref = data.scenario_ref;
    const [query, setQuery] = React.useState(() => {
      try {
        return S.restore(ref);
      } catch (error) {
        return {
          error
        };
      }
    });
    const [error, setError] = React.useState(null),
      [revision, refresh] = React.useReducer(n => n + 1, 0);
    const snapshot = React.useRef(query.snapshot_ref);
    const read = window.TrialSession.useRead(signal => A.read(ref, {
      page: query.page,
      size: query.size,
      status: query.status,
      ...(snapshot.current ? {
        snapshot_ref: snapshot.current
      } : {})
    }, signal), [ref, query.page, query.size, query.status, revision], !query.error);
    React.useEffect(() => {
      if (!read.result) return;
      snapshot.current = read.result.meta.snapshot_ref;
      try {
        S.remember(ref, {
          page: query.page,
          size: query.size,
          status: query.status,
          snapshot_ref: snapshot.current,
          tab: 'adoptions'
        });
      } catch (_) {
        setError(new Error('采用记录已读取，但查看状态保存失败；返回后筛选可能无法恢复。'));
      }
    }, [read.result]);
    function update(patch, reset = true) {
      if (reset) snapshot.current = null;
      const next = {
        ...query,
        ...patch,
        error: null,
        snapshot_ref: snapshot.current
      };
      try {
        S.remember(ref, next);
      } catch (_) {
        setError(new Error('采用记录的筛选没有存上，返回后可能要重新选。'));
        return;
      }
      setError(null);
      setQuery(next);
      refresh();
    }
    const result = read.result,
      d = result && result.data;
    return /*#__PURE__*/React.createElement("section", {
      className: "trial-adoption-history",
      "aria-label": "\u672C\u8BD5\u8C03\u65B9\u6848\u7684\u91C7\u7528\u8BB0\u5F55"
    }, /*#__PURE__*/React.createElement(window.TrialAdoptionHistoryStyles, null), /*#__PURE__*/React.createElement("div", {
      className: "tah-toolbar"
    }, /*#__PURE__*/React.createElement("label", null, "\u91C7\u7528\u72B6\u6001", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u91C7\u7528\u72B6\u6001",
      value: query.status || 'all',
      disabled: read.busy || !!query.error,
      onChange: e => update({
        status: e.target.value,
        page: 1
      })
    }, Object.keys(labels).map(key => /*#__PURE__*/React.createElement("option", {
      value: key,
      key: key
    }, labels[key])))), /*#__PURE__*/React.createElement("label", null, "\u6BCF\u9875", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u91C7\u7528\u8BB0\u5F55\u6BCF\u9875",
      value: query.size || 20,
      disabled: read.busy || !!query.error,
      onChange: e => update({
        size: Number(e.target.value),
        page: 1
      })
    }, [10, 20, 50].map(n => /*#__PURE__*/React.createElement("option", {
      value: n,
      key: n
    }, n, " \u6761")))), /*#__PURE__*/React.createElement(U.Button, {
      icon: "refresh-cw",
      "aria-label": "\u5237\u65B0\u91C7\u7528\u8BB0\u5F55",
      title: "\u5237\u65B0\u91C7\u7528\u8BB0\u5F55",
      busy: read.busy,
      onClick: () => {
        if (query.error) {
          history.replaceState({
            ...history.state,
            trialAdoptionHistory: null
          }, '', location.href);
        }
        update({
          page: 1,
          status: query.status || 'all',
          size: query.size || 20
        });
      }
    })), /*#__PURE__*/React.createElement(U.ErrorBox, {
      error: query.error || error || read.error
    }), read.busy && /*#__PURE__*/React.createElement("p", {
      role: "status",
      className: "tah-meta"
    }, "\u6B63\u5728\u8BFB\u53D6\u8FD9\u4E2A\u8BD5\u8C03\u65B9\u6848\u7684\u91C7\u7528\u8BB0\u5F55\u548C\u5F53\u524D\u6B63\u5F0F\u8BA1\u5212\u2026"), d && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "tah-meta"
    }, d.source.name, " \xB7 \u672C\u8BD5\u8C03\u65B9\u6848\u5171 ", d.total_adoptions, " \u6B21\u91C7\u7528 \xB7 \u6838\u5BF9\u65F6\u95F4 ", U.timeLabel(result.meta.as_of)), !d.items.length && /*#__PURE__*/React.createElement("p", {
      className: "tt-empty",
      role: "status"
    }, d.total_adoptions ? '当前筛选没有采用记录。' : '这个试调方案还没有正式采用记录。'), /*#__PURE__*/React.createElement("ol", {
      className: "tah-list"
    }, d.items.map(item => /*#__PURE__*/React.createElement("li", {
      key: item.receipt_ref,
      "data-adoption-receipt": item.receipt_ref
    }, /*#__PURE__*/React.createElement("div", {
      className: "tah-head"
    }, /*#__PURE__*/React.createElement("strong", null, "\u6B63\u5F0F\u8BA1\u5212\u7B2C ", item.committed_plan.version, " \u7248"), /*#__PURE__*/React.createElement("span", {
      className: 'tah-state tah-' + item.current_state
    }, labels[item.current_state]), /*#__PURE__*/React.createElement("span", null, item.committed_plan.row_count, " \u9053\u5DE5\u5E8F"), /*#__PURE__*/React.createElement(U.Button, {
      icon: "arrow-right",
      disabled: item.current_state === 'unavailable',
      onClick: () => {
        try {
          S.openPlan(ref, item.committed_plan.plan_ref);
        } catch (error) {
          setError(error);
        }
      }
    }, "\u67E5\u770B\u6B63\u5F0F\u8BA1\u5212")), /*#__PURE__*/React.createElement("p", null, "\u91C7\u7528\u4EBA\uFF1A", text(item.adoption.application_operator), " \xB7 \u7ECF\u529E\u4EBA\uFF1A", text(item.adoption.declared_operator)), /*#__PURE__*/React.createElement("p", null, "\u91C7\u7528\u539F\u56E0\uFF1A", text(item.adoption.reason)), /*#__PURE__*/React.createElement("p", {
      className: "tah-meta"
    }, U.timeLabel(item.adoption.adopted_at), " \xB7 \u5F53\u65F6\u7684\u6B63\u5F0F\u8BA1\u5212 ", d.source.baseline.plan_ref ? '第 ' + d.source.baseline.version + ' 版' : '无'), item.evidence_gaps.map((issue, index) => /*#__PURE__*/React.createElement("p", {
      className: "tah-gap",
      key: index
    }, issue.message)), /*#__PURE__*/React.createElement(Evidence, {
      item: item,
      source: d.source
    })))), /*#__PURE__*/React.createElement(U.Pager, {
      label: "\u91C7\u7528\u8BB0\u5F55",
      page: d.page,
      busy: read.busy,
      onPage: page => update({
        page
      }, false)
    })));
  }
  window.TrialAdoptionHistory = function TrialAdoptionHistory({
    data
  }) {
    return data.scenario_ref ? /*#__PURE__*/React.createElement(History, {
      key: data.scenario_ref,
      data: data
    }) : /*#__PURE__*/React.createElement("p", {
      className: "tt-empty"
    }, "\u5F53\u524D\u662F\u8BD5\u8C03\u8349\u7A3F\uFF0C\u8FD8\u6CA1\u6709\u5DF2\u4FDD\u5B58\u8BD5\u8C03\u65B9\u6848\u7684\u91C7\u7528\u8BB0\u5F55\u3002");
  };
})();
