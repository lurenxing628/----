(function () {
  'use strict';

  const M = window.DashboardTimelineModel,
    {
      Button
    } = window.ResourceControls;
  function Timeline({
    data,
    mode = 'delivery',
    selectedBatch,
    onSelect
  }) {
    const board = React.useRef(null),
      [zoom, setZoom] = React.useState(1),
      [hover, setHover] = React.useState(null);
    const [position, setPosition] = React.useState({
      left: 0,
      top: 0,
      width: 900,
      height: 330
    });
    const labelWidth = 150,
      viewport = Math.max(200, position.width - labelWidth),
      width = Math.max(640, viewport) * zoom;
    const model = React.useMemo(() => M.layout(data, mode, width), [data, mode, width]);
    const measure = () => {
      const node = board.current;
      if (node) setPosition({
        left: node.scrollLeft,
        top: node.scrollTop,
        width: node.clientWidth,
        height: node.clientHeight
      });
    };
    React.useLayoutEffect(() => {
      measure();
      const observer = new ResizeObserver(measure);
      observer.observe(board.current);
      return () => observer.disconnect();
    }, []);
    React.useEffect(() => {
      setHover(null);
    }, [position.left, position.top, mode]);
    React.useEffect(() => {
      const task = model.tasks.find(row => row.batch_ref === selectedBatch),
        location = task && model.locations.get(task.task_ref);
      if (!location || !board.current) return;
      board.current.scrollTop = Math.max(0, location.top - 60);
      const left = (location.item.start - model.start) / (model.end - model.start) * width;
      if (left < position.left || left > position.left + viewport) board.current.scrollLeft = Math.max(0, left - viewport / 3);
    }, [selectedBatch, model]);
    const ticks = M.ticks(model.start, model.end, width, position.left, viewport);
    const rows = M.visibleRows(model.rows, Math.max(0, position.top - 60), position.top + position.height + 60);
    const rangeStart = model.start + position.left / width * (model.end - model.start),
      rangeEnd = model.start + (position.left + viewport) / width * (model.end - model.start);
    function show(event, text) {
      const rect = event.currentTarget.getBoundingClientRect();
      setHover({
        text,
        x: rect.left,
        y: rect.bottom
      });
    }
    return /*#__PURE__*/React.createElement("section", {
      className: "dy-timeline",
      "aria-label": mode === 'downtime' ? '检修窗口与原计划时间轴' : '关联资源关键时段',
      "data-dashboard-timeline": mode
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-heading"
    }, /*#__PURE__*/React.createElement("h3", null, mode === 'downtime' ? '检修窗口与原计划' : '关联资源的关键时段'), /*#__PURE__*/React.createElement("div", {
      className: "dy-tools"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "minus",
      "aria-label": "\u7F29\u5C0F\u5206\u6790\u65F6\u95F4\u8F74",
      disabled: zoom <= 1,
      onClick: () => setZoom(Math.max(1, zoom / 2))
    }), /*#__PURE__*/React.createElement("span", null, zoom, "\xD7"), /*#__PURE__*/React.createElement(Button, {
      icon: "plus",
      "aria-label": "\u653E\u5927\u5206\u6790\u65F6\u95F4\u8F74",
      disabled: zoom >= 64,
      onClick: () => setZoom(Math.min(64, zoom * 2))
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "unfold-vertical",
      "aria-label": "\u663E\u793A\u5B8C\u6574\u5206\u6790\u65F6\u95F4\u8F74",
      onClick: () => {
        setZoom(1);
        board.current.scrollLeft = 0;
      }
    }))), /*#__PURE__*/React.createElement("div", {
      className: "dy-timeline-board",
      ref: board,
      onScroll: measure,
      tabIndex: 0,
      style: {
        '--dy-label-width': labelWidth + 'px',
        height: Math.max(120, Math.min(330, model.height + 48))
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-timeline-inner",
      style: {
        width: labelWidth + width,
        height: Math.max(110, model.height + 48)
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-timeline-axis"
    }, /*#__PURE__*/React.createElement("div", {
      className: "dy-timeline-corner"
    }, "\u8BBE\u5907 / \u5DE5\u5E8F"), /*#__PURE__*/React.createElement("div", {
      className: "dy-timeline-ticks",
      style: {
        width
      }
    }, ticks.map(tick => /*#__PURE__*/React.createElement("div", {
      key: tick.at,
      style: {
        left: tick.x
      }
    }, tick.label.slice(0, 10), /*#__PURE__*/React.createElement("small", null, tick.label.slice(11)))))), rows.map(row => {
      const items = row.point ? window.PointGanttModel.visible(row.items, rangeStart, rangeEnd, width / (model.end - model.start)) : M.visibleItems(row.items, rangeStart, rangeEnd);
      return /*#__PURE__*/React.createElement("div", {
        key: row.key,
        className: "dy-timeline-row",
        style: {
          top: row.top + 48,
          height: row.height,
          width: labelWidth + width
        }
      }, /*#__PURE__*/React.createElement("div", {
        className: "dy-timeline-label"
      }, /*#__PURE__*/React.createElement("b", null, row.label), /*#__PURE__*/React.createElement("small", null, row.tasks.length, " \u9053\u5B89\u6392", row.trackCount > 1 ? ' · 子轨 ' + (row.track + 1) : '')), /*#__PURE__*/React.createElement("div", {
        className: "dy-timeline-track",
        style: {
          width
        }
      }, ticks.map(tick => /*#__PURE__*/React.createElement("i", {
        className: "dy-timeline-grid",
        key: tick.at,
        style: {
          left: tick.x
        }
      })), mode === 'downtime' && (model.windows.get(row.id) || []).map(stop => {
        const low = Math.max(model.start, M.instant(stop.start)),
          high = Math.min(model.end, M.instant(stop.end));
        const text = ['检修：' + (stop.reason || '原因未记录'), M.timeLabel(stop.start) + ' 至 ' + M.timeLabel(stop.end), '登记时间（原存值）：' + M.timeLabel(stop.recorded_at)].join('\n');
        return high > low ? /*#__PURE__*/React.createElement("span", {
          key: stop.downtime_ref,
          role: "img",
          tabIndex: 0,
          "aria-label": text,
          title: text,
          "data-downtime-ref": stop.downtime_ref,
          className: "dy-downtime-window",
          style: {
            left: (low - model.start) / (model.end - model.start) * width,
            width: (high - low) / (model.end - model.start) * width
          },
          onMouseEnter: event => show(event, text),
          onMouseLeave: () => setHover(null),
          onFocus: event => show(event, text),
          onBlur: () => setHover(null)
        }) : null;
      }), items.map(item => {
        const task = item.task,
          point = task.start === task.end,
          title = M.title(task),
          pixels = Math.max(point ? 10 : 2, (item.end - item.start) / (model.end - model.start) * width);
        return /*#__PURE__*/React.createElement("button", {
          type: "button",
          key: task.task_ref,
          "data-analysis-task": task.task_ref,
          "data-analysis-batch": task.batch_ref,
          "aria-label": title,
          title: title,
          "aria-pressed": selectedBatch === task.batch_ref,
          className: 'dy-analysis-bar' + (point ? ' point' : '') + (selectedBatch === task.batch_ref ? ' selected' : ''),
          style: {
            left: (item.start - model.start) / (model.end - model.start) * width - (point ? 5 : 0),
            width: pixels
          },
          onMouseEnter: event => show(event, title),
          onMouseLeave: () => setHover(null),
          onFocus: event => show(event, title),
          onBlur: () => setHover(null),
          onClick: () => {
            setHover(null);
            onSelect(task.batch_ref);
          }
        }, pixels >= 65 && /*#__PURE__*/React.createElement("span", null, task.batch_id, " \xB7 ", task.process_label));
      })));
    }), !model.rows.length && /*#__PURE__*/React.createElement("p", {
      className: "dy-empty"
    }, "\u5F53\u524D\u8BFB\u53D6\u8303\u56F4\u6CA1\u6709\u53EF\u663E\u793A\u7684\u8BBE\u5907\u5B89\u6392\u3002"))), /*#__PURE__*/React.createElement("div", {
      className: "dy-context"
    }, /*#__PURE__*/React.createElement("span", null, M.timeLabel(M.wire(model.start)), " \u81F3 ", M.timeLabel(M.wire(model.end)), " \xB7 \u5DE5\u5382\u672C\u5730"), /*#__PURE__*/React.createElement("span", null, mode === 'downtime' ? '检修窗口 / 原计划工序' : '原计划工序', " \xB7 ", model.tasks.length, " \u9053")), hover && /*#__PURE__*/React.createElement("div", {
      role: "tooltip",
      className: "dy-analysis-tooltip",
      style: {
        left: Math.max(8, Math.min(hover.x, window.innerWidth - 368)),
        top: Math.max(8, Math.min(hover.y + 8, window.innerHeight - 220))
      }
    }, hover.text));
  }
  window.DashboardTimeline = Timeline;
})();
