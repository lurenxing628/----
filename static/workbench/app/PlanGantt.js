(function () {
  'use strict';

  const M = window.PlanGanttModel,
    {
      Button,
      Icon
    } = window.ResourceControls;
  const {
    DenseRow,
    Overview
  } = window.PlanGanttCanvas;
  function Segment({
    value,
    options,
    onChange,
    label,
    disabled = false
  }) {
    return /*#__PURE__*/React.createElement("div", {
      className: "plan-segment",
      role: "group",
      "aria-label": label,
      onKeyDown: event => {
        if (disabled || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const index = options.findIndex(([id]) => id === value);
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : (index + (event.key === 'ArrowLeft' ? -1 : 1) + options.length) % options.length;
        onChange(options[next][0]);
        event.currentTarget.querySelectorAll('button')[next].focus();
      }
    }, options.map(([id, text]) => /*#__PURE__*/React.createElement(Button, {
      key: id,
      className: "plan-segment-button",
      disabled: disabled,
      "aria-pressed": value === id,
      tabIndex: value === id ? 0 : -1,
      onClick: () => onChange(id)
    }, text)));
  }
  function Bar({
    item,
    model,
    width,
    selectedRef,
    risks,
    onSelect,
    onHover
  }) {
    const task = item.task,
      size = (item.end - item.start) / (model.end - model.start) * width;
    const title = (item.baseline ? '初始基线\n' : '') + M.taskTitle(task, model.labels, !item.baseline && model.conflicts.has(task.task_ref));
    if (window.PointContract.isPoint(task)) return /*#__PURE__*/React.createElement(window.PointGantt.Marker, {
      task: task,
      "data-plan-task": task.task_ref,
      "data-before": item.baseline || undefined,
      title: title,
      x: (item.start - model.start) / (model.end - model.start) * width,
      top: item.baseline ? 1 : 15,
      selected: selectedRef === task.task_ref,
      tone: item.baseline ? 'before' : M.tone(task, model.conflicts, risks),
      onSelect: () => onSelect(task, item.baseline),
      onHover: event => onHover(event ? {
        task,
        before: item.baseline,
        x: event.clientX,
        y: event.clientY
      } : null)
    });
    return /*#__PURE__*/React.createElement("button", {
      type: "button",
      "data-plan-task": task.task_ref,
      "data-before": item.baseline || undefined,
      className: 'plan-bar ' + (item.baseline ? 'before' : M.tone(task, model.conflicts, risks)) + (model.conflicts.has(task.task_ref) && !item.baseline ? ' conflict' : ''),
      "aria-label": title,
      "aria-pressed": selectedRef === task.task_ref,
      title: title,
      style: {
        left: (item.start - model.start) / (model.end - model.start) * width,
        width: size
      },
      onClick: () => onSelect(task, item.baseline),
      onMouseEnter: event => onHover({
        task,
        before: item.baseline,
        x: event.clientX,
        y: event.clientY
      }),
      onMouseLeave: () => onHover(null)
    }, /*#__PURE__*/React.createElement("span", {
      className: "plan-bar-face",
      style: {
        padding: !item.baseline && size >= 28 ? 2 : 0,
        borderWidth: size < 4 ? 0 : 1
      }
    }, !item.baseline && size >= 28 && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("strong", null, M.pieceLabel(task)), size >= 75 && /*#__PURE__*/React.createElement("small", null, task.batch_id, " \xB7 ", task.sequence, " ", task.process_label))));
  }
  function PlanGantt({
    data,
    selected,
    onSelect,
    query,
    onQuery,
    disabled = false
  }) {
    const [mode, setMode] = React.useState('machine'),
      [baseline, setBaseline] = React.useState(false),
      [zoom, setZoom] = React.useState(1);
    const [changedOnly, setChangedOnly] = React.useState(false),
      [expanded, setExpanded] = React.useState(false);
    const [position, setPosition] = React.useState({
        left: 0,
        top: 0,
        width: 1000,
        height: 440
      }),
      [hover, setHover] = React.useState(null);
    const board = React.useRef(null),
      search = React.useRef(null),
      pending = React.useRef(null),
      frame = React.useRef(null),
      expandButton = React.useRef(null);
    const labelWidth = position.width < 550 ? 125 : 170,
      viewport = Math.max(100, position.width - labelWidth);
    const width = viewport * zoom,
      selectedRef = selected && selected.task.task_ref;
    const model = React.useMemo(() => M.layout(data, mode, query, baseline, width, changedOnly), [data, mode, query, baseline, width, changedOnly]);
    const risks = React.useMemo(() => new Map((data.projections.delivery_risks.items || []).map(row => [row.batch_id, row.risk])), [data]);
    const before = data.projections.baseline,
      showBaseline = before.state === 'available';
    const ticks = M.ticks(model.start, model.end, width, position.left, viewport);
    const visibleRows = M.visibleRows(model.rows, Math.max(0, position.top - 90), position.top + position.height + 90);
    const rangeStart = model.start + position.left / width * (model.end - model.start);
    const rangeEnd = model.start + (position.left + viewport) / width * (model.end - model.start);
    const measure = () => {
      const el = board.current;
      if (el) setPosition({
        left: el.scrollLeft,
        top: el.scrollTop,
        width: el.clientWidth,
        height: el.clientHeight
      });
    };
    React.useLayoutEffect(() => {
      measure();
      const resize = new ResizeObserver(measure);
      resize.observe(board.current);
      return () => {
        resize.disconnect();
        cancelAnimationFrame(frame.current);
      };
    }, []);
    React.useLayoutEffect(() => {
      if (pending.current !== null) {
        board.current.scrollLeft = pending.current * width - viewport / 2;
        pending.current = null;
      }
      measure();
    }, [width, model]);
    React.useEffect(() => {
      setHover(null);
    }, [query, mode, baseline, changedOnly, expanded]);
    React.useEffect(() => {
      setHover(current => {
        if (!current) return null;
        const node = document.elementFromPoint(current.x, current.y),
          task = node && node.closest('[data-plan-task]');
        return task && task.dataset.planTask === current.task.task_ref && task.hasAttribute('data-before') === !!current.before ? current : null;
      });
    }, [position.top, position.left]);
    React.useEffect(() => {
      if (!expanded) return undefined;
      const overflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      board.current.focus();
      const close = event => {
        if (event.key === 'Escape') {
          event.preventDefault();
          setExpanded(false);
        }
      };
      document.addEventListener('keydown', close);
      return () => {
        document.body.style.overflow = overflow;
        document.removeEventListener('keydown', close);
        if (expandButton.current) expandButton.current.focus();
      };
    }, [expanded]);
    function changeZoom(next) {
      pending.current = (position.left + viewport / 2) / width;
      setZoom(Math.max(1, Math.min(1024, next)));
    }
    function locate(taskRef = selectedRef) {
      const location = model.locations.get(taskRef);
      if (!location) return;
      const {
          item,
          top
        } = location,
        el = board.current;
      el.scrollTop = Math.max(0, top - el.clientHeight / 3);
      el.scrollLeft = (item.start + item.end - 2 * model.start) / 2 / (model.end - model.start) * width - viewport / 2;
      measure();
    }
    const located = React.useRef(null);
    React.useEffect(() => {
      if (selected && selected.locate && located.current !== selected && model.locations.has(selectedRef)) {
        located.current = selected;
        locate(selectedRef);
      }
    }, [selected, model]);
    function select(task, beforeTask) {
      setHover(null);
      onSelect(task, beforeTask);
    }
    function move(direction) {
      const tasks = model.tasks,
        index = tasks.findIndex(task => task.task_ref === selectedRef);
      const next = tasks[Math.max(0, Math.min(tasks.length - 1, index < 0 ? 0 : index + direction))];
      if (next) {
        onSelect(next, false);
        locate(next.task_ref);
      }
    }
    const currentIndex = model.tasks.findIndex(task => task.task_ref === selectedRef);
    return /*#__PURE__*/React.createElement("div", {
      className: 'plan-gantt' + (expanded ? ' plan-expanded' : ''),
      "data-plan-gantt": true,
      onKeyDown: event => {
        if (disabled || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || event.target.closest('input,textarea,select,[role=dialog]')) return;
        if (event.key === '/') {
          event.preventDefault();
          search.current.focus();
        }
        if (event.key === '+' || event.key === '=') {
          event.preventDefault();
          changeZoom(zoom * 2);
        }
        if (event.key === '-') {
          event.preventDefault();
          changeZoom(zoom / 2);
        }
        if (event.key.toLowerCase() === 'f') {
          event.preventDefault();
          pending.current = 0.5;
          setZoom(1);
          board.current.scrollLeft = 0;
        }
        if (event.key.toLowerCase() === 'l') {
          event.preventDefault();
          locate();
        }
      }
    }, /*#__PURE__*/React.createElement(window.PointGantt.Styles, null), /*#__PURE__*/React.createElement("div", {
      className: "plan-toolbar"
    }, /*#__PURE__*/React.createElement(Segment, {
      value: mode,
      options: Object.entries(M.kindLabels),
      onChange: setMode,
      label: "\u7518\u7279\u5206\u7EC4",
      disabled: disabled
    }), /*#__PURE__*/React.createElement("label", {
      className: "plan-check",
      title: showBaseline ? '持久基础计划对照' : before.reason || '初始基线无法核实'
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      "aria-label": "\u663E\u793A\u521D\u59CB\u57FA\u7EBF",
      checked: baseline && showBaseline,
      disabled: !showBaseline || disabled,
      onChange: event => setBaseline(event.target.checked)
    }), "\u521D\u59CB\u57FA\u7EBF"), /*#__PURE__*/React.createElement("label", {
      className: "plan-check",
      title: showBaseline ? '按已核实的初始计划对照筛选' : before.reason || '初始基线无法核实'
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      "aria-label": "\u4EC5\u53D8\u66F4",
      checked: changedOnly && showBaseline,
      disabled: !showBaseline || disabled,
      onChange: event => setChangedOnly(event.target.checked)
    }), "\u4EC5\u53D8\u66F4"), /*#__PURE__*/React.createElement("label", {
      className: "search plan-search"
    }, /*#__PURE__*/React.createElement("span", {
      className: "ic"
    }, /*#__PURE__*/React.createElement(Icon, {
      name: "search"
    })), /*#__PURE__*/React.createElement("input", {
      ref: search,
      type: "search",
      "aria-label": "\u641C\u7D22\u6279\u6B21\u3001\u5DE5\u5E8F\u3001\u8BBE\u5907\u3001\u4EBA\u5458",
      placeholder: "\u6279\u6B21\u3001\u5DE5\u5E8F\u3001\u8D44\u6E90",
      value: query,
      onChange: event => onQuery(event.target.value),
      onKeyDown: event => {
        if (event.key === 'Enter') {
          event.preventDefault();
          move(event.shiftKey ? -1 : 1);
        }
        if (event.key === 'Escape') onQuery('');
      }
    })), /*#__PURE__*/React.createElement("div", {
      className: "plan-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "minus",
      className: "btn plan-icon",
      "aria-label": "\u7F29\u5C0F\u65F6\u95F4\u8F74",
      disabled: zoom <= 1 || disabled,
      onClick: () => changeZoom(zoom / 2)
    }), /*#__PURE__*/React.createElement("span", {
      className: "plan-muted",
      style: {
        minWidth: 34,
        textAlign: 'center'
      }
    }, zoom, "\xD7"), /*#__PURE__*/React.createElement(Button, {
      icon: "plus",
      className: "btn plan-icon",
      "aria-label": "\u653E\u5927\u65F6\u95F4\u8F74",
      disabled: zoom >= 1024 || disabled,
      onClick: () => changeZoom(zoom * 2)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "unfold-vertical",
      className: "btn plan-icon plan-fit",
      "aria-label": "\u9002\u5408\u5B8C\u6574\u8DE8\u5EA6",
      title: "\u9002\u5408\u5B8C\u6574\u8DE8\u5EA6 (F)",
      onClick: () => {
        pending.current = 0.5;
        setZoom(1);
        board.current.scrollLeft = 0;
        measure();
      }
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      className: "btn plan-icon",
      "aria-label": "\u5B9A\u4F4D\u9009\u4E2D\u4EFB\u52A1",
      title: "\u5B9A\u4F4D\u9009\u4E2D\u4EFB\u52A1 (L)",
      disabled: !model.locations.has(selectedRef),
      onClick: () => locate()
    }), /*#__PURE__*/React.createElement(Button, {
      icon: expanded ? 'x' : 'chart-gantt',
      className: "btn plan-icon",
      "aria-label": expanded ? '收起甘特' : '展开甘特',
      title: expanded ? '返回完整工作区' : '展开甘特工作区',
      "aria-expanded": expanded,
      disabled: disabled,
      onClick: event => {
        expandButton.current = event.currentTarget;
        setExpanded(!expanded);
      }
    }))), !showBaseline && /*#__PURE__*/React.createElement("div", {
      className: "plan-note"
    }, "\u521D\u59CB\u57FA\u7EBF\uFF1A", before.reason || '无法核实'), /*#__PURE__*/React.createElement("div", {
      className: "plan-board-frame"
    }, /*#__PURE__*/React.createElement(Overview, {
      model: model,
      tasks: data.tasks,
      width: width,
      viewport: viewport,
      left: position.left,
      onPan: left => {
        board.current.scrollLeft = Math.max(0, left);
        measure();
      }
    }), /*#__PURE__*/React.createElement("div", {
      ref: board,
      className: "plan-board",
      "data-plan-scroll": true,
      tabIndex: 0,
      "aria-label": M.kindLabels[mode] + '甘特时间轴',
      onScroll: () => {
        if (frame.current) cancelAnimationFrame(frame.current);
        frame.current = requestAnimationFrame(measure);
      },
      style: {
        '--plan-label': labelWidth + 'px'
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "plan-board-inner",
      style: {
        width: labelWidth + width,
        height: model.height + 52
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "plan-axis"
    }, /*#__PURE__*/React.createElement("div", {
      className: "plan-corner"
    }, M.kindLabels[mode], " / \u5DE5\u5E8F", /*#__PURE__*/React.createElement("small", {
      className: "plan-muted",
      style: {
        display: 'block'
      }
    }, model.groupCount, "\u7EC4 \xB7 \u5DE5\u5382\u672C\u5730\u65F6\u95F4")), /*#__PURE__*/React.createElement("div", {
      className: "plan-ticks",
      style: {
        width
      }
    }, ticks.map(tick => /*#__PURE__*/React.createElement("div", {
      className: "plan-tick",
      key: tick.at,
      style: {
        left: tick.x
      }
    }, tick.label.slice(0, 10), /*#__PURE__*/React.createElement("small", null, tick.label.slice(11)))))), visibleRows.map(row => {
      const items = row.point ? window.PointGanttModel.visible(row.items, rangeStart, rangeEnd, width / (model.end - model.start)) : M.visibleItems(row.items, rangeStart, rangeEnd);
      return /*#__PURE__*/React.createElement("div", {
        key: row.key,
        className: 'plan-lane' + (row.before ? ' baseline' : ''),
        style: {
          top: row.top + 52,
          height: row.height,
          width: labelWidth + width
        }
      }, /*#__PURE__*/React.createElement("div", {
        className: "plan-resource",
        title: row.label + ' · ' + (row.before ? '初始基线' : row.tasks.length + '道安排 · 子轨 ' + (row.track + 1) + '/' + row.trackCount + (row.overlap ? ' · 存在重叠' : ''))
      }, /*#__PURE__*/React.createElement("strong", null, row.label), !row.before && /*#__PURE__*/React.createElement("small", null, row.tasks.length, "\u9053\u5B89\u6392", row.trackCount > 1 ? ' · 子轨 ' + (row.track + 1) + '/' + row.trackCount : '', row.overlap ? ' · 重叠' : ''), row.before && /*#__PURE__*/React.createElement("small", null, "\u521D\u59CB\u57FA\u7EBF")), /*#__PURE__*/React.createElement("div", {
        className: "plan-track",
        style: {
          width
        }
      }, ticks.map(tick => /*#__PURE__*/React.createElement("i", {
        key: tick.at,
        className: "plan-gridline",
        style: {
          left: tick.x
        }
      })), items.length > 70 ? /*#__PURE__*/React.createElement(DenseRow, {
        row: row,
        model: model,
        width: width,
        viewport: viewport,
        left: position.left,
        selectedRef: selectedRef,
        risks: risks,
        onSelect: select,
        onHover: setHover
      }) : items.map(item => /*#__PURE__*/React.createElement(Bar, {
        key: item.task.task_ref,
        item: item,
        model: model,
        width: width,
        selectedRef: selectedRef,
        risks: risks,
        onSelect: select,
        onHover: setHover
      }))));
    }), !model.rows.length && /*#__PURE__*/React.createElement("div", {
      className: "plan-empty",
      style: {
        position: 'sticky',
        left: 0,
        width: position.width
      }
    }, changedOnly ? '当前范围没有匹配的变更安排。' : query ? '没有匹配安排，完整计划跨度保持不变。' : '该读取范围没有安排。'))), /*#__PURE__*/React.createElement("div", {
      className: "plan-footer"
    }, /*#__PURE__*/React.createElement("span", {
      "data-plan-search-count": true
    }, model.tasks.length, " / ", data.task_count, " \u9053\u5B89\u6392"), /*#__PURE__*/React.createElement("span", {
      className: "plan-legend"
    }, /*#__PURE__*/React.createElement("i", {
      className: "plan-swatch"
    }), "\u5B89\u6392"), /*#__PURE__*/React.createElement("span", {
      className: "plan-legend"
    }, /*#__PURE__*/React.createElement("i", {
      className: "plan-swatch critical"
    }), "\u8D85\u671F / \u8D44\u6E90\u91CD\u53E0"), baseline && /*#__PURE__*/React.createElement("span", {
      className: "plan-legend"
    }, /*#__PURE__*/React.createElement("i", {
      className: "plan-swatch before"
    }), "\u521D\u59CB\u57FA\u7EBF"), /*#__PURE__*/React.createElement("span", {
      className: "plan-actions"
    }, /*#__PURE__*/React.createElement(Button, {
      className: "btn plan-icon",
      icon: "chevron-left",
      "aria-label": "\u4E0A\u4E00\u5339\u914D\u4EFB\u52A1",
      disabled: currentIndex <= 0,
      onClick: () => move(-1)
    }), /*#__PURE__*/React.createElement("span", null, currentIndex < 0 ? '未选任务' : '第 ' + (currentIndex + 1) + ' 道匹配'), /*#__PURE__*/React.createElement(Button, {
      className: "btn plan-icon",
      icon: "chevron-right",
      "aria-label": "\u4E0B\u4E00\u5339\u914D\u4EFB\u52A1",
      disabled: !model.tasks.length || currentIndex >= model.tasks.length - 1,
      onClick: () => move(1)
    })))), hover && /*#__PURE__*/React.createElement("div", {
      role: "tooltip",
      className: "plan-tooltip",
      style: {
        left: Math.max(8, Math.min(hover.x + 12, window.innerWidth - 335)),
        top: Math.max(8, Math.min(hover.y + 16, window.innerHeight - 300)),
        maxHeight: 'calc(100vh - 16px)',
        overflow: 'auto',
        overflowWrap: 'anywhere'
      }
    }, (hover.before ? '初始基线\n' : '') + M.taskTitle(hover.task, model.labels, !hover.before && model.conflicts.has(hover.task.task_ref))));
  }
  window.PlanGantt = PlanGantt;
  window.PlanSegmentUI = Segment;
})();
