(function () {
  'use strict';

  // Axis numbers encode factory-local wall-clock fields; UTC extraction must not shift them to the browser timezone.
  const U = window.TrialControls,
    wall = value => Date.parse(value + 'Z');
  const pieceLabel = t => t.piece_id === null ? '共同工序' : '分件 ' + t.piece_id;
  const taskLabel = t => t.batch_id + ' · ' + t.sequence + ' ' + t.process_label + ' · ' + pieceLabel(t);
  function resourceNames(data) {
    const names = new Map();
    ['machines', 'operators'].forEach(k => data.resources[k].forEach(r => names.set(r.ref, r.business_code + ' · ' + (r.label || '名称未填写'))));
    return ref => ref === null ? '无内部资源' : names.get(ref) || '原资源名称不可读';
  }
  function matching(data, scope, query, changed) {
    const name = resourceNames(data),
      needle = query.trim().toLowerCase();
    return data.tasks.filter(t => (!changed || t.changed) && (!scope.range_start || window.PointContract.overlaps(t, scope.range_start, scope.range_end)) && (!scope.batch_refs || scope.batch_refs.includes(t.batch_ref)) && (!scope.resource_ref || (scope.resource_type === 'batch' ? t.batch_ref : t[scope.resource_type + '_ref']) === scope.resource_ref) && (!needle || [t.batch_id, t.part_no, t.part_name, t.process_label, t.piece_id, name(t.machine_ref), name(t.operator_ref)].join(' ').toLowerCase().includes(needle)));
  }
  function Gantt({
    data,
    selected,
    onSelect
  }) {
    const V = window.TrialViewState,
      preferences = V.useView(data),
      values = preferences.value || V.defaults(data);
    const view = values.mode,
      baseline = values.baseline,
      changed = values.only_changed,
      query = values.query;
    const setView = mode => preferences.change({
        mode
      }),
      setBaseline = baseline => preferences.change({
        baseline
      });
    const setChanged = only_changed => preferences.change({
        only_changed
      }),
      setQuery = query => preferences.change({
        query
      });
    const [limit, setLimit] = React.useState(true);
    const [page, setPage] = React.useState(1),
      [zoom, setZoom] = React.useState(1),
      [expanded, setExpanded] = React.useState(false);
    const [hover, setHover] = React.useState(null);
    const scope = limit ? data.scope : {},
      filtered = React.useMemo(() => matching(data, scope, query, changed), [data, scope, query, changed]);
    const name = resourceNames(data),
      key = view === 'batch' ? 'batch_ref' : view + '_ref',
      board = React.useRef(null);
    const rows = React.useMemo(() => {
      const entries = [];
      filtered.forEach(t => {
        entries.push({
          t,
          group: t[key],
          ghost: false
        });
        if (baseline && view !== 'batch' && t.original[key] !== t[key]) entries.push({
          t,
          group: t.original[key],
          ghost: true
        });
      });
      return entries.sort((a, b) => String(a.group).localeCompare(String(b.group)) || a.t.start.localeCompare(b.t.start) || a.t.task_ref.localeCompare(b.t.task_ref));
    }, [filtered, view, baseline]);
    const current = Math.min(page, Math.max(1, Math.ceil(rows.length / 30))),
      visible = rows.slice((current - 1) * 30, current * 30);
    const bounds = React.useMemo(() => {
      let start = Infinity,
        end = -Infinity;
      data.tasks.forEach(t => {
        start = Math.min(start, wall(t.start), wall(t.original.start));
        end = Math.max(end, wall(t.end), wall(t.original.end));
      });
      const pad = Math.max(60000, (end - start) * .025);
      return {
        start: start - pad,
        end: end + pad
      };
    }, [data]);
    const position = t => ({
      left: (wall(t.start) - bounds.start) / (bounds.end - bounds.start) * 100 + '%',
      width: (wall(t.end) - wall(t.start)) / (bounds.end - bounds.start) * 100 + '%'
    });
    const pointTitle = (t, original) => (original ? '原安排 · ' : '') + taskLabel(t) + '\n' + U.timeLabel((original ? t.original : t).start) + '\n零工时工序 · 0 小时 · 不占设备人员';
    function pointMarker(t, original) {
      const value = original ? t.original : t,
        title = pointTitle(t, original);
      return /*#__PURE__*/React.createElement(window.PointGantt.Marker, {
        task: original ? {
          ...t,
          start: value.start,
          end: value.end
        } : t,
        "data-task-ref": original ? undefined : t.task_ref,
        "data-baseline-ref": original ? t.task_ref : undefined,
        title: title,
        x: position(value).left,
        top: original ? 36 : 10,
        tone: original ? 'before' : t.issues.length ? 'critical' : t.locked ? 'success' : '',
        selected: selected === t.task_ref,
        onSelect: () => {
          setHover(null);
          onSelect(t.task_ref);
        },
        onHover: event => setHover(event ? {
          title,
          x: event.clientX,
          y: event.clientY
        } : null)
      });
    }
    React.useEffect(() => {
      if (!selected) return;
      const index = rows.findIndex(r => !r.ghost && r.t.task_ref === selected);
      if (index >= 0) setPage(Math.floor(index / 30) + 1);
    }, [selected]);
    React.useEffect(() => {
      if (expanded) {
        const handler = e => {
          if (e.key === 'Escape') setExpanded(false);
        };
        document.addEventListener('keydown', handler);
        return () => document.removeEventListener('keydown', handler);
      }
    }, [expanded]);
    if (!preferences.value) return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u8BD5\u8C03\u7518\u7279"
    }, /*#__PURE__*/React.createElement(V.Notice, {
      state: preferences,
      label: "\u8BD5\u8C03\u7518\u7279\u67E5\u770B\u504F\u597D"
    }));
    return /*#__PURE__*/React.createElement("section", {
      className: 'tt-gantt' + (expanded ? ' tt-expanded' : ''),
      "aria-label": "\u8BD5\u8C03\u7518\u7279"
    }, /*#__PURE__*/React.createElement(window.PointGantt.Styles, null), /*#__PURE__*/React.createElement(V.Notice, {
      state: preferences,
      label: "\u8BD5\u8C03\u7518\u7279\u67E5\u770B\u504F\u597D"
    }), /*#__PURE__*/React.createElement("div", {
      className: "tt-heading"
    }, /*#__PURE__*/React.createElement("h3", null, "\u8BD5\u8C03\u6392\u7A0B\u56FE"), /*#__PURE__*/React.createElement("span", {
      className: "tt-muted"
    }, "\u542B\u591C\u95F4")), /*#__PURE__*/React.createElement("div", {
      className: "tt-tools tt-gantt-tools"
    }, /*#__PURE__*/React.createElement(U.Tabs, {
      value: view,
      label: "\u7518\u7279\u5206\u7EC4",
      options: [["machine", '设备'], ['operator', '人员'], ['batch', '批次']],
      onChange: v => {
        setView(v);
        setPage(1);
      }
    }), /*#__PURE__*/React.createElement("label", {
      className: "tt-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: baseline,
      onChange: e => setBaseline(e.target.checked)
    }), "\u539F\u5B89\u6392"), /*#__PURE__*/React.createElement("label", {
      className: "tt-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: changed,
      onChange: e => {
        setChanged(e.target.checked);
        setPage(1);
      }
    }), "\u4EC5\u53D8\u66F4"), !!Object.keys(data.scope).length && /*#__PURE__*/React.createElement("label", {
      className: "tt-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: limit,
      onChange: e => {
        setLimit(e.target.checked);
        setPage(1);
      }
    }), "\u539F\u663E\u793A\u8303\u56F4"), /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u8BD5\u8C03\u5DE5\u5E8F",
      placeholder: "\u6279\u6B21 / \u5DE5\u5E8F / \u8D44\u6E90",
      maxLength: 200,
      value: query,
      onChange: e => {
        setQuery(e.target.value);
        setPage(1);
      }
    }), /*#__PURE__*/React.createElement(U.Button, {
      icon: "minus",
      "aria-label": "\u7F29\u5C0F\u7518\u7279",
      disabled: zoom <= 1,
      onClick: () => setZoom(z => z / 2)
    }), /*#__PURE__*/React.createElement(U.Button, {
      icon: "plus",
      "aria-label": "\u653E\u5927\u7518\u7279",
      disabled: zoom >= 8,
      onClick: () => setZoom(z => z * 2)
    }), /*#__PURE__*/React.createElement(U.Button, {
      icon: "chart-gantt",
      "aria-label": expanded ? '收起甘特' : '展开甘特',
      onClick: () => setExpanded(!expanded)
    })), /*#__PURE__*/React.createElement("div", {
      className: "tt-board",
      ref: board,
      onScroll: () => setHover(null)
    }, /*#__PURE__*/React.createElement("div", {
      className: "tt-timeline",
      style: {
        width: zoom === 1 ? '100%' : zoom * 100 + '%'
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "tt-axis"
    }, /*#__PURE__*/React.createElement("div", {
      className: "tt-corner"
    }, "\u5DE5\u5E8F / \u8D44\u6E90"), /*#__PURE__*/React.createElement("div", {
      className: "tt-ticks"
    }, [0, 1, 2, 3].map(i => /*#__PURE__*/React.createElement("span", {
      key: i
    }, U.timeLabel(new Date(bounds.start + (bounds.end - bounds.start) * i / 3).toISOString().slice(0, 19)).slice(5, 16))))), visible.map((r, i) => /*#__PURE__*/React.createElement(React.Fragment, {
      key: r.t.task_ref + ':' + r.ghost
    }, (i === 0 || visible[i - 1].group !== r.group) && /*#__PURE__*/React.createElement("div", {
      className: "tt-group"
    }, view === 'batch' ? r.t.batch_id + ' · ' + (r.t.part_name || '零件名称未填写') : name(r.group)), /*#__PURE__*/React.createElement("div", {
      className: 'tt-gantt-row' + (selected === r.t.task_ref ? ' selected' : ''),
      "data-trial-task": r.t.task_ref
    }, /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: "tt-task-label",
      onClick: () => onSelect(r.t.task_ref),
      "aria-pressed": selected === r.t.task_ref,
      "aria-label": '选择工序 ' + taskLabel(r.t),
      title: taskLabel(r.t) + '\n本工序目标量 ' + U.number(r.t.quantity) + ' · 整批量 ' + U.number(r.t.batch_quantity)
    }, /*#__PURE__*/React.createElement("strong", null, pieceLabel(r.t), " \xB7 ", r.t.sequence), /*#__PURE__*/React.createElement("small", null, r.t.batch_id, " \xB7 ", r.t.process_label, " \xB7 ", r.ghost ? '原资源' : U.number(r.t.quantity) + ' 件')), /*#__PURE__*/React.createElement("div", {
      className: "tt-track"
    }, !r.ghost && (window.PointContract.isPoint(r.t) ? pointMarker(r.t, false) : /*#__PURE__*/React.createElement("button", {
      type: "button",
      className: 'tt-bar' + (r.t.issues.length ? ' conflict' : '') + (r.t.locked ? ' locked' : ''),
      "data-task-ref": r.t.task_ref,
      "aria-label": '安排时段 ' + taskLabel(r.t),
      "aria-pressed": selected === r.t.task_ref,
      title: taskLabel(r.t) + '\n本工序目标量 ' + U.number(r.t.quantity) + ' · 整批量 ' + U.number(r.t.batch_quantity) + '\n' + U.timeLabel(r.t.start) + ' 至 ' + U.timeLabel(r.t.end),
      style: position(r.t),
      onClick: () => onSelect(r.t.task_ref)
    })), baseline && (view === 'batch' || r.ghost || r.t.original[key] === r.group) && (window.PointContract.isPoint(r.t) ? pointMarker(r.t, true) : /*#__PURE__*/React.createElement("span", {
      className: "tt-baseline",
      "data-baseline-ref": r.t.task_ref,
      style: position(r.t.original),
      title: '原安排 ' + taskLabel(r.t) + '\n' + U.timeLabel(r.t.original.start) + ' 至 ' + U.timeLabel(r.t.original.end)
    })))))), !visible.length && /*#__PURE__*/React.createElement("div", {
      className: "tt-empty"
    }, "\u5F53\u524D\u663E\u793A\u8303\u56F4\u6CA1\u6709\u5339\u914D\u5DE5\u5E8F"))), /*#__PURE__*/React.createElement("div", {
      className: "tt-heading"
    }, /*#__PURE__*/React.createElement("div", {
      className: "tt-legend"
    }, /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("i", null), "\u8BD5\u8C03\u5B89\u6392"), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("i", {
      className: "baseline"
    }), "\u539F\u8BD5\u8C03\u57FA\u7840"), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("i", {
      className: "conflict"
    }), "\u7EA6\u675F\u95EE\u9898"), /*#__PURE__*/React.createElement("span", null, /*#__PURE__*/React.createElement("i", {
      className: "locked"
    }), "\u5DF2\u9501\u5B9A\uFF0C\u4E0D\u80FD\u8C03\u6574")), /*#__PURE__*/React.createElement("span", {
      className: "tt-muted"
    }, "\u5339\u914D ", filtered.length, " / \u5B8C\u6574 ", data.task_count, " \u9053 \xB7 ", zoom, "\xD7")), /*#__PURE__*/React.createElement(U.Pager, {
      page: {
        number: current,
        size: 30,
        total: rows.length
      },
      label: "\u7518\u7279",
      onPage: setPage
    }), hover && /*#__PURE__*/React.createElement("div", {
      role: "tooltip",
      className: "tt-point-tooltip",
      style: {
        left: Math.max(8, Math.min(innerWidth - 335, hover.x + 12)),
        top: Math.max(8, Math.min(innerHeight - 160, hover.y + 14))
      }
    }, hover.title));
  }
  window.TrialGantt = Gantt;
  window.TrialGantt.resourceNames = resourceNames;
})();
