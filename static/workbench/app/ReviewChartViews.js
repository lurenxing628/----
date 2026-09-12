(function () {
  'use strict';

  function DistributionChart({
    items,
    label
  }) {
    const id = React.useId(),
      maximum = Math.max(1, ...items.map(row => row.count || 0));
    return /*#__PURE__*/React.createElement("figure", {
      className: "aw-chart aw-distribution",
      "aria-labelledby": id
    }, /*#__PURE__*/React.createElement("figcaption", {
      className: "aw-caption",
      id: id
    }, label), /*#__PURE__*/React.createElement("ul", {
      className: "aw-bars"
    }, items.map(row => /*#__PURE__*/React.createElement("li", {
      key: row.id
    }, /*#__PURE__*/React.createElement("div", {
      className: "aw-bar-row"
    }, /*#__PURE__*/React.createElement("span", {
      className: "aw-bar-label"
    }, row.label), /*#__PURE__*/React.createElement("span", {
      className: "aw-bar-track",
      "aria-hidden": "true"
    }, /*#__PURE__*/React.createElement("i", {
      "data-tone": row.tone,
      style: {
        width: row.count / maximum * 100 + '%'
      }
    })), /*#__PURE__*/React.createElement("strong", null, row.count))))));
  }
  function TrendChart({
    points,
    label
  }) {
    const id = React.useId();
    if (!points.length) return /*#__PURE__*/React.createElement(window.WorkbenchListControls.EmptyState, {
      kind: "empty",
      title: "\u5F53\u524D\u8303\u56F4\u65E0\u53EF\u6BD4\u8F83\u8D8B\u52BF"
    });
    const max = Math.max(1, ...points.flatMap(row => [row.planned, row.actual || 0]));
    const start = points[0].time,
      span = points[points.length - 1].time - start || 1;
    const x = row => 10 + (row.time - start) / span * 580,
      y = value => 190 - value / max * 180;
    const series = [['planned', '计划累计完工'], ['actual', '已确认整道完工']];
    return /*#__PURE__*/React.createElement("figure", {
      className: "aw-chart aw-trend",
      "aria-labelledby": id
    }, /*#__PURE__*/React.createElement("figcaption", {
      id: id,
      className: "aw-caption"
    }, label), /*#__PURE__*/React.createElement("div", {
      className: "aw-legend"
    }, series.map(([key, title]) => /*#__PURE__*/React.createElement("span", {
      key: key
    }, /*#__PURE__*/React.createElement("i", {
      className: 'aw-swatch aw-' + key
    }), title))), /*#__PURE__*/React.createElement("div", {
      className: "aw-chart-body"
    }, /*#__PURE__*/React.createElement("div", {
      className: "aw-y-axis"
    }, /*#__PURE__*/React.createElement("span", {
      style: {
        top: 0
      }
    }, max), /*#__PURE__*/React.createElement("span", {
      style: {
        bottom: 0
      }
    }, "0")), /*#__PURE__*/React.createElement("div", {
      className: "aw-plot"
    }, /*#__PURE__*/React.createElement("svg", {
      className: "aw-plot-svg",
      viewBox: "0 0 600 200",
      preserveAspectRatio: "none",
      role: "img",
      "aria-label": label
    }, [0, max / 2, max].map(value => /*#__PURE__*/React.createElement("line", {
      key: value,
      className: "aw-gridline",
      x1: 0,
      x2: 600,
      y1: y(value),
      y2: y(value)
    })), series.map(([key, title]) => {
      const known = points.filter(row => row[key] !== null);
      return /*#__PURE__*/React.createElement("g", {
        key: key,
        className: 'aw-series aw-' + key
      }, /*#__PURE__*/React.createElement("path", {
        d: known.map((row, index) => (index ? 'L' : 'M') + x(row) + ' ' + y(row[key])).join(' '),
        fill: "none",
        vectorEffect: "non-scaling-stroke"
      }), known.map(row => /*#__PURE__*/React.createElement("circle", {
        key: row.time,
        cx: x(row),
        cy: y(row[key]),
        r: 3,
        vectorEffect: "non-scaling-stroke"
      }, /*#__PURE__*/React.createElement("title", null, row.label, " \xB7 ", title, " ", row[key], " \u9053"))));
    })))), /*#__PURE__*/React.createElement("div", {
      className: "aw-x-axis"
    }, /*#__PURE__*/React.createElement("span", null, points[0].label), /*#__PURE__*/React.createElement("span", null, points[points.length - 1].label)), /*#__PURE__*/React.createElement("details", {
      className: "aw-data"
    }, /*#__PURE__*/React.createElement("summary", null, "\u56FE\u8868\u6570\u636E"), /*#__PURE__*/React.createElement("div", {
      className: "aw-data-scroll wb-table-frame",
      tabIndex: 0,
      role: "region",
      "aria-label": "\u7D2F\u8BA1\u5B8C\u5DE5\u8D8B\u52BF\u6570\u636E"
    }, /*#__PURE__*/React.createElement("table", null, /*#__PURE__*/React.createElement("caption", {
      className: "wb-visually-hidden"
    }, label), /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u65E5\u671F"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u8BA1\u5212\u7D2F\u8BA1\u5B8C\u5DE5"), /*#__PURE__*/React.createElement("th", {
      scope: "col"
    }, "\u5DF2\u786E\u8BA4\u6574\u9053\u5B8C\u5DE5"))), /*#__PURE__*/React.createElement("tbody", null, points.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.time
    }, /*#__PURE__*/React.createElement("th", {
      scope: "row"
    }, window.WorkbenchFormat.date(row.label)), /*#__PURE__*/React.createElement("td", null, row.planned), /*#__PURE__*/React.createElement("td", null, row.actual == null ? '未知' : row.actual))))))));
  }
  const resourceColumns = [['resource_label', '实际资源'], ['operations', '涉及工序'], ['events', '旧现场事件数'], ['production_reports', '逐次报工数'], ['records', '全部记录数'], ['effective_processing_hours', '有效加工工时(h)'], ['known_effective_processing_hours', '已知工时小计(h)'], ['unknown_hour_events', '工时未知记录数']].map(([key, label]) => ({
    key,
    label
  }));
  window.ReviewChartViews = {
    DistributionChart,
    TrendChart,
    resourceColumns
  };
})();
