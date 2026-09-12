(function () {
  'use strict';

  const {
      Button,
      Icon
    } = window.ResourceControls,
    M = window.ActualGanttModel;
  function describe(item, labels, report) {
    const wording = {
      '执行投影不可用': '执行记录不可用',
      '完成依据：逐次执行投影': '完成依据：逐次报工记录'
    };
    return M.describe(item, labels, report).map(line => wording[line] || line);
  }
  function Styles() {
    return /*#__PURE__*/React.createElement(window.PointGantt.Styles, null);
  }
  function Toolbar({
    view,
    patch,
    model,
    data,
    zoom,
    width,
    onZoom,
    onFit,
    onLocate,
    onExport,
    busy
  }) {
    const allCollapsed = model.groups.length > 0 && model.groups.every(g => view.collapsed[g.id]);
    const counts = Object.fromEntries(Object.keys(M.lateLabels).map(key => [key, key === 'all' ? data.items.length : data.items.filter(item => M.deadlines(item, M.wire(model.asOf))[key]).length]));
    return /*#__PURE__*/React.createElement("div", {
      className: "gb-toolbar fg-toolbar"
    }, /*#__PURE__*/React.createElement("div", {
      className: "fg-toolbar-main"
    }, /*#__PURE__*/React.createElement("div", {
      className: "seg",
      role: "group",
      "aria-label": "\u7518\u7279\u89C6\u56FE"
    }, Object.entries(M.views).map(([key, label]) => /*#__PURE__*/React.createElement("button", {
      key: key,
      className: 'seg-btn' + (view.mode === key ? ' on' : ''),
      "aria-pressed": view.mode === key,
      onClick: () => patch({
        mode: key,
        collapsed: {}
      })
    }, label))), /*#__PURE__*/React.createElement("label", {
      className: "fg-search"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "search"
    }), /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u73B0\u573A\u7518\u7279",
      placeholder: "\u6279\u6B21 / \u5DE5\u5E8F / \u8BBE\u5907 / \u4EBA\u5458",
      maxLength: 200,
      value: view.query,
      onChange: e => patch({
        query: e.target.value
      })
    })), /*#__PURE__*/React.createElement("span", {
      className: "fg-muted",
      "data-actual-count": true
    }, model.groups.length, " \u7EC4 \xB7 ", model.items.length, " / ", data.task_count, " \u9053\u5DE5\u5E8F"), /*#__PURE__*/React.createElement("label", {
      className: "fg-late-filter"
    }, "\u665A\u671F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u665A\u671F\u7B5B\u9009",
      value: view.late,
      onChange: e => patch({
        late: e.target.value
      })
    }, Object.entries(M.lateLabels).map(([key, label]) => /*#__PURE__*/React.createElement("option", {
      key: key,
      value: key
    }, label, " (", counts[key], ")")))), /*#__PURE__*/React.createElement(Button, {
      transfer: "export",
      busy: busy,
      disabled: !model.items.length || data.availability.state !== 'available',
      onClick: onExport
    }, "\u5BFC\u51FA CSV")), /*#__PURE__*/React.createElement("div", {
      className: "fg-toolbar-chart"
    }, /*#__PURE__*/React.createElement("div", {
      className: "fg-legend"
    }, /*#__PURE__*/React.createElement("span", {
      className: "fg-lg"
    }, /*#__PURE__*/React.createElement("i", {
      className: "fg-sw-plan"
    }), "\u539F\u8BA1\u5212\u57FA\u7EBF"), /*#__PURE__*/React.createElement("span", {
      className: "fg-lg"
    }, /*#__PURE__*/React.createElement("i", {
      className: "fg-sw-act"
    }), "\u5B9E\u9645\u62A5\u5DE5"), /*#__PURE__*/React.createElement("span", {
      className: "fg-lg"
    }, /*#__PURE__*/React.createElement("i", {
      className: "fg-sw-remaining"
    }), "\u5DF2\u6709\u5269\u4F59\u5B89\u6392"), data.critical_chain.state === 'available' && /*#__PURE__*/React.createElement("label", {
      className: "fg-chain-toggle"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: view.chain,
      onChange: e => patch({
        chain: e.target.checked
      })
    }), "\u5173\u952E\u94FE")), /*#__PURE__*/React.createElement("div", {
      className: "fg-toolbar-chart-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "fg-icon-button",
      icon: allCollapsed ? 'unfold-vertical' : 'fold-vertical',
      "aria-label": allCollapsed ? '全部展开' : '全部折叠',
      disabled: !model.groups.length,
      onClick: () => patch({
        collapsed: allCollapsed ? {} : Object.fromEntries(model.groups.map(g => [g.id, true]))
      })
    }), /*#__PURE__*/React.createElement("label", {
      className: "fg-chain-toggle"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: view.onlySelected,
      disabled: !view.selected && !view.onlySelected,
      onChange: e => patch({
        onlySelected: e.target.checked
      })
    }), "\u53EA\u770B\u9009\u4E2D"), /*#__PURE__*/React.createElement("label", {
      className: "fg-chain-toggle"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: view.details,
      onChange: e => patch({
        details: e.target.checked
      })
    }), "\u8BE6\u60C5"), view.chain && data.critical_chain.state === 'available' && /*#__PURE__*/React.createElement("label", {
      className: "fg-chain-toggle"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: view.chainLines !== false,
      disabled: !data.critical_chain.edges.length,
      onChange: e => patch({
        chainLines: e.target.checked
      })
    }), "\u5173\u952E\u94FE\u8FDE\u7EBF"), /*#__PURE__*/React.createElement(Button, {
      className: "fg-icon-button",
      icon: "minus",
      "aria-label": "\u7F29\u5C0F\u65F6\u95F4\u8F74",
      disabled: zoom <= 1,
      onClick: () => onZoom(zoom / 2)
    }), /*#__PURE__*/React.createElement("span", {
      className: "fg-zoom-value",
      "aria-label": "\u65F6\u95F4\u8F74\u7F29\u653E\u6A21\u5F0F"
    }, zoom === 1 ? '自动' : '手动'), /*#__PURE__*/React.createElement(Button, {
      className: "fg-icon-button",
      icon: "plus",
      "aria-label": "\u653E\u5927\u65F6\u95F4\u8F74",
      disabled: zoom >= 1024,
      onClick: () => onZoom(zoom * 2)
    }), /*#__PURE__*/React.createElement("span", {
      className: "fg-muted",
      "aria-label": "\u65F6\u95F4\u8F74\u523B\u5EA6",
      "data-tick-step": M.tickStep(model, width)
    }, "\u523B\u5EA6 ", M.tickLabel(M.tickStep(model, width))), /*#__PURE__*/React.createElement(Button, {
      className: "fg-icon-button",
      icon: "chart-gantt",
      "aria-label": "\u9002\u5E94\u5168\u90E8",
      onClick: onFit
    }), /*#__PURE__*/React.createElement(Button, {
      className: "fg-icon-button",
      icon: "search",
      "aria-label": "\u5B9A\u4F4D\u9009\u4E2D\u5DE5\u5E8F",
      disabled: !model.items.some(i => i.task.task_ref === view.selected),
      onClick: onLocate
    }))));
  }
  function Chain({
    chain,
    model,
    onLocate
  }) {
    const visible = new Set(model.items.map(item => item.task.task_ref));
    return /*#__PURE__*/React.createElement("div", {
      className: "fg-chain-strip",
      "aria-label": "\u6240\u9009\u8BA1\u5212\u5173\u952E\u94FE",
      "data-chain-context": chain.mode,
      "data-chain-target": chain.target_task_ref || ''
    }, /*#__PURE__*/React.createElement("div", {
      className: "fg-chain-heading"
    }, /*#__PURE__*/React.createElement("strong", null, chain.mode === 'related' ? '当前对象目标的控制前驱链' : '整版计划控制前驱链'), " \xB7 \u539F\u7B97\u6CD5\u8FD1\u4F3C \xB7 ", chain.mode === 'related' ? '目标计划结束' : '计划最晚结束', " ", M.time(chain.makespan_end), chain.partial && /*#__PURE__*/React.createElement("span", {
      role: "status"
    }, " \xB7 \u90E8\u5206\u7ED3\u679C\uFF1A\u539F\u7B97\u6CD5\u4E0D\u542B ", chain.omitted_point_count, " \u4E2A\u96F6\u65F6\u957F\u70B9")), chain.state === 'unavailable' ? /*#__PURE__*/React.createElement("span", {
      role: "status"
    }, "\u5173\u8054\u94FE\u4E0D\u53EF\u7528\uFF1A", chain.reason) : chain.nodes.map((node, index) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: node.task_ref
    }, index > 0 && /*#__PURE__*/React.createElement("span", {
      className: "fg-chain-edge-label",
      title: chain.edges[index - 1].reason,
      "data-chain-edge-reason": true
    }, chain.edges[index - 1].reason, " \xB7 \u95F4\u9694 ", chain.edges[index - 1].gap_minutes, " \u5206\u949F"), /*#__PURE__*/React.createElement(Button, {
      className: "fg-chain-node",
      icon: "search",
      disabled: !visible.has(node.task_ref),
      "data-chain-node": node.task_ref,
      title: M.taskLabel(node),
      onClick: () => onLocate(node.task_ref)
    }, node.batch_id, " \xB7 ", node.sequence, " ", node.process_label))), /*#__PURE__*/React.createElement("span", {
      className: "fg-muted"
    }, "\u7B5B\u9009\u5185 ", chain.task_refs.filter(ref => visible.has(ref)).length, " / ", chain.task_refs.length, " \u4E2A\u8282\u70B9 \xB7 \u5DE5\u827A\u5B9E\u7EBF\uFF0C\u8D44\u6E90\u865A\u7EBF \xB7 \u4E0D\u662F\u5B9E\u9645\u5DE5\u65F6\u6216\u5269\u4F59\u9884\u6D4B"));
  }
  function Range({
    scope,
    resources,
    onApply,
    busy
  }) {
    const [draft, setDraft] = React.useState(scope),
      [batches, setBatches] = React.useState((scope.batch_ids || []).join(','));
    React.useEffect(() => {
      setDraft(scope);
      setBatches((scope.batch_ids || []).join(','));
    }, [scope]);
    const patch = value => setDraft(previous => ({
      ...previous,
      ...value
    }));
    return /*#__PURE__*/React.createElement("form", {
      className: "fg-range",
      onSubmit: event => {
        event.preventDefault();
        const next = {
          ...draft
        };
        Object.keys(next).forEach(key => {
          if (next[key] === '' || next[key] === null) delete next[key];
        });
        if (!next.resource_ref) delete next.resource_type;
        if (batches.trim()) next.batch_ids = batches.split(',').map(v => v.trim());else delete next.batch_ids;
        delete next.snapshot_ref;
        onApply(next);
      }
    }, scope.range_start && /*#__PURE__*/React.createElement("span", {
      className: "fg-muted",
      title: "\u6309\u539F\u8BA1\u5212\u65F6\u6BB5\u76F8\u4EA4\u9009\u62E9\u5DE5\u5E8F\uFF1B\u5165\u9009\u5DE5\u5E8F\u4FDD\u7559\u5168\u90E8\u6709\u6548\u62A5\u5DE5"
    }, "\u539F\u8BA1\u5212\u65F6\u6BB5 ", M.time(scope.range_start), " \u81F3 ", M.time(scope.range_end)), /*#__PURE__*/React.createElement("label", null, "\u8BA1\u5212\u5B8C\u5DE5\u65E5", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u8BA1\u5212\u5B8C\u5DE5\u5F00\u59CB\u65E5",
      value: draft.plan_finish_date_from || '',
      onChange: e => patch({
        plan_finish_date_from: e.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u81F3", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u8BA1\u5212\u5B8C\u5DE5\u7ED3\u675F\u65E5",
      value: draft.plan_finish_date_to || '',
      onChange: e => patch({
        plan_finish_date_to: e.target.value
      })
    })), /*#__PURE__*/React.createElement("label", null, "\u8D44\u6E90", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u8D44\u6E90\u8303\u56F4",
      value: draft.resource_ref || '',
      onChange: e => {
        const row = resources.find(r => r.ref === e.target.value);
        patch({
          resource_ref: e.target.value,
          resource_type: row ? row.kind : ''
        });
      }
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u5168\u90E8\u8BA1\u5212\u6216\u5B9E\u9645\u8D44\u6E90"), resources.filter(r => r.kind !== 'supplier').map(r => /*#__PURE__*/React.createElement("option", {
      key: r.ref,
      value: r.ref
    }, M.views[r.kind], " \xB7 ", r.label || r.business_code)))), /*#__PURE__*/React.createElement("label", null, "\u6279\u6B21", /*#__PURE__*/React.createElement("input", {
      className: "fg-batches",
      "aria-label": "\u6279\u6B21\u8303\u56F4",
      value: batches,
      onChange: e => setBatches(e.target.value)
    })), /*#__PURE__*/React.createElement(Button, {
      type: "submit",
      icon: "search",
      busy: busy
    }, "\u5E94\u7528\u8303\u56F4"), /*#__PURE__*/React.createElement(Button, {
      icon: "x",
      "aria-label": "\u6E05\u9664\u6765\u6E90\u8303\u56F4",
      disabled: busy,
      onClick: () => onApply({
        plan_ref: scope.plan_ref
      })
    }));
  }
  window.ActualGanttControls = {
    Styles,
    Toolbar,
    Range,
    Chain,
    describe
  };
})();
