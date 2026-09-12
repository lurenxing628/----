(function () {
  'use strict';

  const U = window.TrialControls,
    A = window.TrialAdoptionHistoryAPI,
    S = window.TrialAdoptionHistoryState;
  const labels = {
    all: '全部采用',
    current: '当前正式',
    historical: '历史正式',
    unavailable: '身份不可用'
  };
  const text = value => value === null ? '证据缺失' : value;
  function Evidence({
    item,
    source
  }) {
    return /*#__PURE__*/React.createElement("details", {
      className: "wb-ref"
    }, /*#__PURE__*/React.createElement("summary", null, "\u6765\u6E90\u4E0E\u7F16\u53F7"), /*#__PURE__*/React.createElement("dl", {
      className: "tah-refs"
    }, /*#__PURE__*/React.createElement("dt", null, "\u539F\u6765\u6E90"), /*#__PURE__*/React.createElement("dd", null, U.sourceLabel(source.base_identity), /*#__PURE__*/React.createElement("br", null), Object.values(source.base)[0]), /*#__PURE__*/React.createElement("dt", null, "\u539F\u6B63\u5F0F\u57FA\u7EBF"), /*#__PURE__*/React.createElement("dd", null, source.baseline.plan_ref ? 'v' + source.baseline.version + ' · ' + source.baseline.plan_ref : '当时无正式基线'), /*#__PURE__*/React.createElement("dt", null, "\u539F\u573A\u666F"), /*#__PURE__*/React.createElement("dd", null, source.scenario_ref), /*#__PURE__*/React.createElement("dt", null, "\u539F\u8349\u7A3F"), /*#__PURE__*/React.createElement("dd", null, source.draft_ref), /*#__PURE__*/React.createElement("dt", null, "\u4FDD\u5B58\u6765\u6E90"), /*#__PURE__*/React.createElement("dd", null, source.saved_by, " \xB7 ", U.timeLabel(source.saved_at), /*#__PURE__*/React.createElement("br", null), source.save_request_key), /*#__PURE__*/React.createElement("dt", null, "\u65B0\u6B63\u5F0F\u5F15\u7528"), /*#__PURE__*/React.createElement("dd", null, item.committed_plan.plan_ref), /*#__PURE__*/React.createElement("dt", null, "\u547D\u4EE4\u56DE\u6267"), /*#__PURE__*/React.createElement("dd", null, item.receipt_ref), /*#__PURE__*/React.createElement("dt", null, "\u539F\u8BF7\u6C42"), /*#__PURE__*/React.createElement("dd", null, item.request_key), /*#__PURE__*/React.createElement("dt", null, "\u63D0\u4EA4\u65F6\u95F4 UTC"), /*#__PURE__*/React.createElement("dd", null, item.committed_at_utc), /*#__PURE__*/React.createElement("dt", null, "\u5B57\u6BB5\u4F9D\u636E"), /*#__PURE__*/React.createElement("dd", null, "\u63D0\u4EA4\uFF1A\u6301\u4E45\u547D\u4EE4\u56DE\u6267\uFF1B\u539F\u56E0\u4E0E\u58F0\u660E\u4EBA\uFF1A\u56DE\u6267\u610F\u56FE\u6563\u5217\u6838\u5BF9\uFF1B\u91C7\u7528\u4EBA\u53CA\u672C\u5730\u65F6\u95F4\uFF1A\u6B63\u5F0F\u5386\u53F2\u5BA1\u8BA1\uFF1B\u5F53\u524D\u72B6\u6001\uFF1A\u672C\u6B21\u6B63\u5F0F\u8EAB\u4EFD\u8BFB\u53D6\u3002")));
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
        setError(new Error('采用记录筛选无法保存，请核对浏览器状态。'));
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
      "aria-label": "\u672C\u573A\u666F\u91C7\u7528\u8BB0\u5F55"
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
    }, "\u6B63\u5728\u8BFB\u53D6\u672C\u573A\u666F\u91C7\u7528\u8BB0\u5F55\u4E0E\u5F53\u524D\u6B63\u5F0F\u8EAB\u4EFD\u2026"), d && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "tah-meta"
    }, d.source.name, " \xB7 \u672C\u573A\u666F\u5171 ", d.total_adoptions, " \u6B21\u91C7\u7528 \xB7 \u6838\u5BF9\u4E8E ", U.timeLabel(result.meta.as_of)), !d.items.length && /*#__PURE__*/React.createElement("p", {
      className: "tt-empty",
      role: "status"
    }, d.total_adoptions ? '当前筛选没有采用记录。' : '尚无本场景的正式采用回执。'), /*#__PURE__*/React.createElement("ol", {
      className: "tah-list"
    }, d.items.map(item => /*#__PURE__*/React.createElement("li", {
      key: item.receipt_ref,
      "data-adoption-receipt": item.receipt_ref
    }, /*#__PURE__*/React.createElement("div", {
      className: "tah-head"
    }, /*#__PURE__*/React.createElement("strong", null, "\u6B63\u5F0F\u8BA1\u5212 v", item.committed_plan.version), /*#__PURE__*/React.createElement("span", {
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
    }, "\u67E5\u770B\u6B63\u5F0F\u65B9\u6848")), /*#__PURE__*/React.createElement("p", null, "\u91C7\u7528\u4EBA\uFF1A", text(item.adoption.application_operator), " \xB7 \u58F0\u660E\u4EBA\uFF1A", text(item.adoption.declared_operator)), /*#__PURE__*/React.createElement("p", null, "\u91C7\u7528\u539F\u56E0\uFF1A", text(item.adoption.reason)), /*#__PURE__*/React.createElement("p", {
      className: "tah-meta"
    }, U.timeLabel(item.adoption.adopted_at), " \xB7 \u539F\u57FA\u7EBF ", d.source.baseline.plan_ref ? 'v' + d.source.baseline.version : '无正式基线'), item.evidence_gaps.map((issue, index) => /*#__PURE__*/React.createElement("p", {
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
    }, "\u5F53\u524D\u4E3A\u8BD5\u8C03\u8349\u7A3F\uFF0C\u5C1A\u65E0\u5DF2\u4FDD\u5B58\u573A\u666F\u7684\u91C7\u7528\u8BB0\u5F55\u3002");
  };
})();
