(function () {
  'use strict';

  const {
    Button,
    Icon,
    Modal
  } = window.ResourceControls;
  const timeLabel = v => v ? String(v).replace('T', ' ') : '未记录';
  const number = v => v === null || v === undefined ? '不可评估' : typeof v === 'number' ? v.toLocaleString('zh-CN', {
    maximumFractionDigits: 2
  }) : String(v);
  const sourceLabel = identity => (identity.display_name || '原排产候选') + (identity.plan_ref && identity.version ? ' · v' + identity.version : '');
  const statusLabel = v => ({
    editing: '可继续试调',
    saved: '已保存',
    discarded: '已放弃',
    valid: '通过',
    warning: '有提示',
    blocked: '有阻断',
    complete: '已完成',
    partial: '部分完成',
    failed: '失败',
    running: '计算中',
    queued: '待计算',
    interrupted: '已中断',
    active: '启用',
    inactive: '停用'
  })[v] || v;
  function ErrorBox({
    error
  }) {
    return error ? /*#__PURE__*/React.createElement("div", {
      className: "tt-error",
      role: "alert"
    }, error.message || String(error), Array.isArray(error.fields) && error.fields.map((r, i) => /*#__PURE__*/React.createElement("div", {
      key: i
    }, r.message))) : null;
  }
  function Pager({
    page,
    onPage,
    busy,
    label = '记录'
  }) {
    const pages = page.pages === undefined ? Math.ceil(page.total / page.size) : page.pages;
    const input = React.useRef(null),
      [jump, setJump] = React.useState(page.number);
    React.useEffect(() => {
      setJump(page.number);
    }, [page.number]);
    function apply() {
      if (input.current.reportValidity()) onPage(Number(jump));
    }
    return /*#__PURE__*/React.createElement("div", {
      className: "tt-pager"
    }, /*#__PURE__*/React.createElement("span", null, page.total, " \u9879 \xB7 \u7B2C ", page.number, " / ", Math.max(pages, 1), " \u9875"), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": label + '上一页',
      disabled: busy || page.number <= 1,
      onClick: () => onPage(page.number - 1)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": label + '下一页',
      disabled: busy || page.number >= pages,
      onClick: () => onPage(page.number + 1)
    }), pages > 2 && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("input", {
      ref: input,
      type: "number",
      required: true,
      min: "1",
      max: pages,
      step: "1",
      value: jump,
      "aria-label": label + '页码',
      disabled: busy,
      style: {
        width: 66
      },
      onChange: e => setJump(e.target.value),
      onKeyDown: e => {
        if (e.key === 'Enter') {
          e.preventDefault();
          apply();
        }
      }
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "arrow-right",
      "aria-label": '跳转' + label + '页',
      disabled: busy,
      onClick: apply
    })));
  }
  function Tabs({
    value,
    options,
    onChange,
    label
  }) {
    return /*#__PURE__*/React.createElement("div", {
      role: "tablist",
      "aria-label": label,
      className: "tt-tabs"
    }, options.map(([key, text]) => /*#__PURE__*/React.createElement("button", {
      type: "button",
      key: key,
      role: "tab",
      tabIndex: value === key ? 0 : -1,
      "aria-selected": value === key,
      onClick: () => onChange(key),
      onKeyDown: event => {
        const index = options.findIndex(o => o[0] === value),
          offset = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
        if (!offset && !['Home', 'End'].includes(event.key)) return;
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? options.length - 1 : (index + offset + options.length) % options.length;
        onChange(options[next][0]);
        event.currentTarget.parentElement.children[next].focus();
      }
    }, text)));
  }
  function Table({
    rows,
    columns,
    label,
    size = 20
  }) {
    const [number, set] = React.useState(1),
      page = Math.min(number, Math.max(1, Math.ceil(rows.length / size)));
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", {
      className: "tt-table-scroll"
    }, /*#__PURE__*/React.createElement("table", {
      className: "tt-table",
      "aria-label": label
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, columns.map(c => /*#__PURE__*/React.createElement("th", {
      key: c[0]
    }, c[0])))), /*#__PURE__*/React.createElement("tbody", null, rows.slice((page - 1) * size, page * size).map((row, i) => /*#__PURE__*/React.createElement("tr", {
      key: row.change_ref || row.row_ref || row.resource_ref || i
    }, columns.map(c => /*#__PURE__*/React.createElement("td", {
      key: c[0]
    }, c[1](row))))))), !rows.length && /*#__PURE__*/React.createElement("div", {
      className: "tt-empty"
    }, "\u6682\u65E0\u8BB0\u5F55")), rows.length > size && /*#__PURE__*/React.createElement(Pager, {
      page: {
        number: page,
        size,
        total: rows.length
      },
      onPage: set,
      label: label
    }));
  }
  function Issues({
    rows,
    onSelect
  }) {
    if (!rows.length) return null;
    return /*#__PURE__*/React.createElement(Table, {
      rows: rows,
      size: 10,
      label: "\u7EA6\u675F\u95EE\u9898",
      columns: [['级别', r => r.severity === 'warning' ? '提示' : '阻断'], ['问题', r => r.message], ['关联', r => r.task_ref && onSelect ? /*#__PURE__*/React.createElement(Button, {
        icon: "arrow-right",
        "aria-label": '定位问题工序 ' + r.code,
        onClick: () => onSelect(r.task_ref)
      }, "\u5DE5\u5E8F") : '整体']]
    });
  }
  function Download({
    data
  }) {
    const [error, setError] = React.useState(null);
    function save(raw = false) {
      let url, a;
      try {
        const output = raw ? window.TrialExport.raw(data) : window.TrialExport.csv(data);
        const blob = new Blob([output.text], {
          type: output.mime
        });
        url = URL.createObjectURL(blob);
        a = document.createElement('a');
        a.href = url;
        a.download = output.filename;
        document.body.appendChild(a);
        a.click();
        setError(null);
      } catch (e) {
        setError(e);
      } finally {
        if (a) a.remove();
        if (url) setTimeout(() => URL.revokeObjectURL(url), 1000);
      }
    }
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("span", {
      className: "tt-tools"
    }, /*#__PURE__*/React.createElement(Button, {
      icon: "download",
      onClick: () => save()
    }, "\u5BFC\u51FA\u5BF9\u6BD4"), /*#__PURE__*/React.createElement(Button, {
      icon: "file-down",
      onClick: () => save(true)
    }, "\u5BFC\u51FA\u539F\u59CB\u6570\u636E")), /*#__PURE__*/React.createElement(ErrorBox, {
      error: error
    }));
  }
  window.TrialControls = {
    Button,
    Icon,
    Modal,
    ErrorBox,
    Pager,
    Tabs,
    Table,
    Issues,
    Download,
    timeLabel,
    number,
    statusLabel,
    sourceLabel
  };
})();
