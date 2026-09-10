(function () {
  'use strict';

  const {
    Button,
    Issues,
    Icon
  } = window.ResourceControls;
  function HoursFacts({
    value,
    fields,
    changes
  }) {
    if (value === null) return /*#__PURE__*/React.createElement("span", {
      className: "muted"
    }, "\u672A\u53D6\u5F97\u8BB0\u5F55");
    const keys = Object.keys(fields).filter(key => Object.prototype.hasOwnProperty.call(value, key) && !['business_code', 'sequence'].includes(key));
    return /*#__PURE__*/React.createElement("dl", {
      className: "rm-facts"
    }, keys.filter(key => value[key] !== null || Object.prototype.hasOwnProperty.call(changes, key)).map(key => /*#__PURE__*/React.createElement(React.Fragment, {
      key: key
    }, /*#__PURE__*/React.createElement("dt", null, fields[key]), /*#__PURE__*/React.createElement("dd", {
      className: Object.prototype.hasOwnProperty.call(changes, key) ? 'rm-changed' : undefined
    }, value[key] === null ? '未填写' : key === 'source' ? window.APSProcessContract.sourceLabel(value[key]) : String(value[key])))));
  }
  function HoursRows({
    data,
    receipt = false
  }) {
    const [filter, setFilter] = React.useState('all'),
      [page, setPage] = React.useState(1),
      [search, setSearch] = React.useState('');
    React.useEffect(() => {
      setPage(1);
      setFilter('all');
      setSearch('');
    }, [data]);
    const counts = window.APSProcessFiles.hoursCounts(data),
      skips = new Map(data.skipped_rows.map(row => [row.row, row]));
    const status = row => skips.has(row.row) ? 'skipped' : ['update', 'new', 'committed'].includes(row.result) ? 'changed' : row.result;
    const labels = {
      changed: receipt ? '已导入' : '待导入',
      skipped: '单件工时已锁定 · 本行跳过',
      unchanged: '原值相同 · 无需导入',
      rejected: '不能提交'
    };
    const rows = data.rows.filter(row => (filter === 'all' || status(row) === filter) && (String(row.business_code || '') + ' ' + String(row.sequence || '')).toLowerCase().includes(search.trim().toLowerCase()));
    const pages = Math.max(1, Math.ceil(rows.length / 20)),
      current = Math.min(page, pages);
    const fields = !receipt && Object.fromEntries(data.columns.map(row => [row.key, row.label]));
    return /*#__PURE__*/React.createElement("section", {
      className: "rm-preview",
      "aria-label": receipt ? '工时导入回执' : '工时导入预检'
    }, /*#__PURE__*/React.createElement("div", {
      className: "rm-summary",
      role: "status"
    }, /*#__PURE__*/React.createElement("span", null, receipt ? '已导入' : data.can_confirm ? '可导入' : '待处理更新', " ", /*#__PURE__*/React.createElement("b", null, counts.changed), " \u884C"), /*#__PURE__*/React.createElement("span", null, "\u9501\u5B9A\u8DF3\u8FC7 ", /*#__PURE__*/React.createElement("b", null, counts.skipped), " \u884C"), /*#__PURE__*/React.createElement("span", null, "\u539F\u503C\u76F8\u540C ", /*#__PURE__*/React.createElement("b", null, counts.unchanged), " \u884C"), counts.rejected > 0 && /*#__PURE__*/React.createElement("span", {
      className: "rm-danger"
    }, "\u4E0D\u80FD\u63D0\u4EA4 ", /*#__PURE__*/React.createElement("b", null, counts.rejected), " \u884C")), /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, receipt ? counts.changed ? '仅已导入行发生修改，其余行未修改。' : '本次没有导入任何工时，业务数据未变化。' : !data.can_confirm ? '本批存在不能提交的行，当前不能导入任何工时。' : counts.skipped === data.rows.length ? '全部行因单件工时已校准锁定而跳过；确认只记录结果，不修改工时。' : '尚未导入；确认后只写入可导入行。'), counts.skipped > 0 && /*#__PURE__*/React.createElement("p", null, "\u6821\u51C6\u9501\u53EA\u4FDD\u62A4\u5355\u4EF6\u5DE5\u65F6\u3002\u9501\u5B9A\u884C\u82E5\u8981\u4FEE\u6539\u5355\u4EF6\u5DE5\u65F6\uFF0C\u672C\u884C\u5168\u90E8\u8DF3\u8FC7\uFF0C\u6362\u578B\u65F6\u95F4\u4E5F\u4E0D\u4F1A\u968F\u672C\u884C\u5BFC\u5165\uFF1B\u4EC5\u6539\u6362\u578B\u65F6\u95F4\u65F6\uFF0C\u4FDD\u7559\u539F\u5355\u4EF6\u5DE5\u65F6\u6216\u5C06\u8BE5\u5217\u7559\u7A7A\u5373\u53EF\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "rm-preview-toolbar"
    }, /*#__PURE__*/React.createElement("h3", null, receipt ? '逐行导入结果' : '逐行核对'), /*#__PURE__*/React.createElement("label", null, "\u67E5\u627E ", /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u67E5\u627E\u56FE\u53F7\u6216\u5DE5\u5E8F",
      value: search,
      onChange: event => {
        setSearch(event.target.value);
        setPage(1);
      }
    })), /*#__PURE__*/React.createElement("label", null, "\u663E\u793A ", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5DE5\u65F6\u660E\u7EC6\u7B5B\u9009",
      value: filter,
      onChange: event => {
        setFilter(event.target.value);
        setPage(1);
      }
    }, /*#__PURE__*/React.createElement("option", {
      value: "all"
    }, "\u5168\u90E8 ", data.rows.length, " \u884C"), /*#__PURE__*/React.createElement("option", {
      value: "skipped"
    }, "\u9501\u5B9A\u8DF3\u8FC7 ", counts.skipped, " \u884C"), /*#__PURE__*/React.createElement("option", {
      value: "changed"
    }, receipt ? '已导入' : '待导入', " ", counts.changed, " \u884C"), /*#__PURE__*/React.createElement("option", {
      value: "unchanged"
    }, "\u539F\u503C\u76F8\u540C ", counts.unchanged, " \u884C"), !receipt && /*#__PURE__*/React.createElement("option", {
      value: "rejected"
    }, "\u4E0D\u80FD\u63D0\u4EA4 ", counts.rejected, " \u884C")))), /*#__PURE__*/React.createElement("div", {
      className: "rm-table-wrap",
      tabIndex: "0",
      role: "region",
      "aria-label": "\u5B8C\u6574\u5DE5\u65F6\u660E\u7EC6"
    }, /*#__PURE__*/React.createElement("table", {
      className: "rm-table",
      "aria-label": receipt ? '工时导入结果明细' : '工时导入预检明细'
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      style: {
        width: '8%'
      }
    }, "\u884C\u53F7"), /*#__PURE__*/React.createElement("th", {
      style: {
        width: receipt ? '28%' : '24%'
      }
    }, "\u96F6\u4EF6 / \u5DE5\u5E8F"), /*#__PURE__*/React.createElement("th", {
      style: {
        width: receipt ? '64%' : '24%'
      }
    }, "\u5904\u7406\u7ED3\u679C"), !receipt && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("th", {
      style: {
        width: '22%'
      }
    }, "\u539F\u8BB0\u5F55"), /*#__PURE__*/React.createElement("th", {
      style: {
        width: '22%'
      }
    }, "\u5BFC\u5165\u540E")))), /*#__PURE__*/React.createElement("tbody", null, rows.slice((current - 1) * 20, current * 20).map(row => {
      const skip = skips.get(row.row);
      return /*#__PURE__*/React.createElement("tr", {
        key: row.row,
        "data-quota-row": row.row,
        "data-quota-result": status(row)
      }, /*#__PURE__*/React.createElement("td", null, row.row), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("strong", null, row.business_code || '图号未识别'), /*#__PURE__*/React.createElement("div", null, "\u5DE5\u5E8F ", row.sequence === undefined ? '未识别' : row.sequence)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("div", null, skip && /*#__PURE__*/React.createElement(Icon, {
        name: "lock"
      }), " ", labels[status(row)]), skip && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("div", null, "\u5DF2\u91C7\u7EB3\u6821\u51C6\u7ED3\u679C\uFF0C\u5355\u4EF6\u5DE5\u65F6\u4E0D\u80FD\u88AB\u672C\u6587\u4EF6\u8986\u76D6\u3002"), /*#__PURE__*/React.createElement("div", {
        style: {
          whiteSpace: 'pre-wrap'
        }
      }, "\u91C7\u7EB3\u539F\u56E0\uFF1A", skip.reason)), !receipt && row.errors.map((error, index) => /*#__PURE__*/React.createElement("div", {
        className: "rm-danger",
        key: index
      }, error.message))), !receipt && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(HoursFacts, {
        value: row.before,
        fields: fields,
        changes: row.changes
      })), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(HoursFacts, {
        value: row.after,
        fields: fields,
        changes: row.changes
      }))));
    }), !rows.length && /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("td", {
      colSpan: receipt ? 3 : 5
    }, "\u6CA1\u6709\u5339\u914D\u7684\u5DE5\u65F6\u8BB0\u5F55\u3002"))))), /*#__PURE__*/React.createElement("div", {
      className: "rm-pagination"
    }, /*#__PURE__*/React.createElement("span", null, "\u5171 ", rows.length, " \u884C \xB7 \u7B2C ", current, " / ", pages, " \u9875"), /*#__PURE__*/React.createElement("span", null, "\u6BCF\u9875 20 \u884C"), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": "\u5DE5\u65F6\u660E\u7EC6\u4E0A\u4E00\u9875",
      disabled: current <= 1,
      onClick: () => setPage(current - 1)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": "\u5DE5\u65F6\u660E\u7EC6\u4E0B\u4E00\u9875",
      disabled: current >= pages,
      onClick: () => setPage(current + 1)
    })));
  }
  function RouteSummary({
    value
  }) {
    if (!value) return null;
    return /*#__PURE__*/React.createElement("details", null, /*#__PURE__*/React.createElement("summary", null, "\u8DEF\u7EBF\u8BC6\u522B\u7ED3\u679C"), /*#__PURE__*/React.createElement("p", null, "\u5DE5\u5E8F ", value.counts.operations, " \xB7 \u5DF2\u8BC6\u522B ", value.counts.recognized, " \xB7 \u672A\u8BC6\u522B ", value.counts.unknown), /*#__PURE__*/React.createElement("p", null, value.can_confirm_route ? '路线识别检查通过，尚未执行本次导入。' : '路线仍有待处理问题，本次不能确认。'), value.diagnostics.map((row, index) => /*#__PURE__*/React.createElement("div", {
      key: index,
      className: row.severity === 'error' ? 'rm-danger' : undefined
    }, row.sequence === undefined ? '' : '工序 ' + row.sequence + '：', row.message)));
  }
  function Groups({
    rows,
    selected,
    onChange,
    disabled
  }) {
    const [page, setPage] = React.useState(1),
      pages = Math.max(1, Math.ceil(rows.length / 50)),
      current = Math.min(page, pages);
    if (!rows.length) return null;
    const all = rows.every(row => selected.includes(row.ref));
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u53D7\u5F71\u54CD\u7684\u5916\u534F\u7EC4"
    }, /*#__PURE__*/React.createElement("h3", null, "\u9700\u660E\u786E\u89E3\u9664\u7684\u539F\u5916\u534F\u7EC4"), /*#__PURE__*/React.createElement("label", {
      className: "rm-check"
    }, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      checked: all,
      disabled: disabled,
      onChange: event => onChange(event.target.checked ? rows.map(row => row.ref) : [])
    }), "\u5DF2\u6838\u5BF9\u5168\u90E8 ", rows.length, " \u7EC4\uFF0C\u540C\u610F\u89E3\u9664\u8FD9\u4E9B\u539F\u5916\u534F\u7EC4\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "rm-table-wrap"
    }, /*#__PURE__*/React.createElement("table", {
      className: "rm-table",
      "aria-label": "\u539F\u5916\u534F\u7EC4\u89C4\u5219"
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", {
      style: {
        width: '8%'
      }
    }, "\u89E3\u9664"), /*#__PURE__*/React.createElement("th", null, "\u96F6\u4EF6"), /*#__PURE__*/React.createElement("th", null, "\u5DE5\u5E8F\u8303\u56F4"), /*#__PURE__*/React.createElement("th", null, "\u5468\u671F\u65B9\u5F0F"), /*#__PURE__*/React.createElement("th", null, "\u539F\u5468\u671F"), /*#__PURE__*/React.createElement("th", null, "\u4F9B\u5E94\u5546"), /*#__PURE__*/React.createElement("th", null, "\u539F\u5907\u6CE8"))), /*#__PURE__*/React.createElement("tbody", null, rows.slice((current - 1) * 50, current * 50).map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.ref
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("input", {
      type: "checkbox",
      "aria-label": '解除 ' + row.business_code + ' 工序 ' + row.start_sequence + ' 至 ' + row.end_sequence + ' 的外协组',
      checked: selected.includes(row.ref),
      disabled: disabled,
      onChange: event => onChange(event.target.checked ? selected.concat(row.ref) : selected.filter(ref => ref !== row.ref))
    })), /*#__PURE__*/React.createElement("td", null, row.business_code), /*#__PURE__*/React.createElement("td", null, row.start_sequence, " \u81F3 ", row.end_sequence), /*#__PURE__*/React.createElement("td", null, row.merge_mode === 'merged' ? '合并周期' : row.merge_mode === 'separate' ? '逐序周期' : row.merge_mode === null ? '未填写' : row.merge_mode), /*#__PURE__*/React.createElement("td", null, row.total_days === null ? '未填写' : row.total_days + ' 天'), /*#__PURE__*/React.createElement("td", null, row.supplier_label === null ? '未绑定' : row.supplier_label), /*#__PURE__*/React.createElement("td", null, row.remark === null ? '未填写' : row.remark, /*#__PURE__*/React.createElement(Issues, {
      issues: row.issues
    }))))))), /*#__PURE__*/React.createElement("div", {
      className: "rm-pagination"
    }, /*#__PURE__*/React.createElement("span", null, "\u5171 ", rows.length, " \u7EC4 \xB7 \u7B2C ", current, " / ", pages, " \u9875"), /*#__PURE__*/React.createElement("span", null, "\u6BCF\u9875 50 \u7EC4"), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-left",
      "aria-label": "\u5916\u534F\u7EC4\u4E0A\u4E00\u9875",
      disabled: current <= 1,
      onClick: () => setPage(current - 1)
    }), /*#__PURE__*/React.createElement(Button, {
      icon: "chevron-right",
      "aria-label": "\u5916\u534F\u7EC4\u4E0B\u4E00\u9875",
      disabled: current >= pages,
      onClick: () => setPage(current + 1)
    })));
  }
  function ProcessFilePreview({
    data,
    groups,
    onGroups,
    disabled
  }) {
    if (data.kind === 'hours') return /*#__PURE__*/React.createElement(HoursRows, {
      data: data
    });
    const fields = Object.fromEntries(data.columns.map(row => [row.key, row.label]));
    return /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(window.ProcessActionPreview, {
      data: data,
      fields: fields,
      renderDetails: row => /*#__PURE__*/React.createElement(RouteSummary, {
        value: row.route_summary
      })
    }), /*#__PURE__*/React.createElement(Groups, {
      rows: data.affected_groups,
      selected: groups,
      onChange: onGroups,
      disabled: disabled
    }));
  }
  window.ProcessFilePreview = ProcessFilePreview;
  window.ProcessFileReceipt = props => /*#__PURE__*/React.createElement(HoursRows, {
    ...props,
    receipt: true
  });
})();
