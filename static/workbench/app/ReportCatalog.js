(function () {
  'use strict';

  const options = [['overdue', '超期批次'], ['utilization', '资源负荷 / 利用率'], ['downtime', '停机影响'], ['official-review', '正式执行复盘 / Excel']];
  function Catalog({
    api,
    scope,
    snapshot
  }) {
    const {
      Button,
      ErrorBox,
      useRead,
      Page
    } = window.ReportControls;
    const [kind, setKind] = React.useState('overdue'),
      [draft, setDraft] = React.useState({}),
      [filter, setFilter] = React.useState({}),
      [table, setTable] = React.useState({
        page: 1,
        size: 10
      }),
      [notice, setNotice] = React.useState(''),
      [error, setError] = React.useState(null),
      [downloading, setDownloading] = React.useState(false);
    const base = kind === 'official-review' ? {
      ...window.ReportAPI.scope(scope),
      snapshot_ref: snapshot,
      topic: 'delivery'
    } : {
      source: 'production',
      plan_ref: scope.plan_ref,
      ...filter
    };
    const input = {
      ...base,
      ...table
    };
    const request = useRead(signal => api.catalog(kind, input, signal), kind + JSON.stringify(input));
    const response = request.result;
    function choose(next) {
      setKind(next);
      setFilter({});
      setDraft({});
      setTable({
        page: 1,
        size: 10
      });
      setError(null);
      setNotice('');
    }
    async function download() {
      setDownloading(true);
      setError(null);
      try {
        await api.download('/api/workbench/v1/reports/' + kind + '/export', {
          ...input,
          snapshot_ref: response.meta.snapshot_ref,
          format: 'xlsx'
        });
        setNotice('完整范围 XLSX 已交给浏览器下载。');
      } catch (failure) {
        setError(failure);
      } finally {
        setDownloading(false);
      }
    }
    return /*#__PURE__*/React.createElement("section", {
      "aria-label": "\u5176\u4ED6\u62A5\u8868\u76EE\u5F55"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rw-table-heading"
    }, /*#__PURE__*/React.createElement("div", {
      className: "rw-filters",
      style: {
        marginLeft: 0
      }
    }, /*#__PURE__*/React.createElement("label", null, "\u62A5\u8868", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u5176\u4ED6\u62A5\u8868",
      value: kind,
      onChange: event => choose(event.target.value)
    }, options.map(([key, label]) => /*#__PURE__*/React.createElement("option", {
      value: key,
      key: key
    }, label)))), ['utilization', 'downtime'].includes(kind) && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("label", null, "\u7EDF\u8BA1\u7A97\u53E3\u8D77\u65E5", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u7EDF\u8BA1\u7A97\u53E3\u8D77\u65E5",
      value: draft.window_date_from || '',
      onChange: event => setDraft(old => ({
        ...old,
        window_date_from: event.target.value
      }))
    })), /*#__PURE__*/React.createElement("label", null, "\u6B62\u65E5", /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": "\u7EDF\u8BA1\u7A97\u53E3\u6B62\u65E5",
      value: draft.window_date_to || '',
      onChange: event => setDraft(old => ({
        ...old,
        window_date_to: event.target.value
      }))
    })), /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      "aria-label": "\u8BFB\u53D6\u76EE\u5F55\u8303\u56F4",
      onClick: () => {
        setFilter(draft);
        setTable({
          page: 1,
          size: 10
        });
      }
    })), kind !== 'official-review' && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("label", null, "\u641C\u7D22", /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u76EE\u5F55\u62A5\u8868",
      value: draft.query || '',
      onChange: event => setDraft(old => ({
        ...old,
        query: event.target.value
      })),
      onKeyDown: event => {
        if (event.key === 'Enter') {
          setFilter(draft);
          setTable({
            page: 1,
            size: 10
          });
        }
      }
    })), /*#__PURE__*/React.createElement(Button, {
      icon: "search",
      "aria-label": "\u641C\u7D22\u76EE\u5F55\u7ED3\u679C",
      onClick: () => {
        setFilter(draft);
        setTable({
          page: 1,
          size: 10
        });
      }
    }), response && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("label", null, "\u6392\u5E8F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u76EE\u5F55\u6392\u5E8F\u5B57\u6BB5",
      value: table.sort || response.data.page.sort[0].field,
      onChange: event => setTable(old => ({
        ...old,
        page: 1,
        sort: event.target.value,
        snapshot_ref: response.meta.snapshot_ref
      }))
    }, response.data.columns.map(column => /*#__PURE__*/React.createElement("option", {
      key: column.key,
      value: column.key
    }, column.label)))), /*#__PURE__*/React.createElement("label", null, "\u987A\u5E8F", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u76EE\u5F55\u6392\u5E8F\u65B9\u5411",
      value: table.direction || 'asc',
      onChange: event => setTable(old => ({
        ...old,
        page: 1,
        direction: event.target.value,
        snapshot_ref: response.meta.snapshot_ref
      }))
    }, /*#__PURE__*/React.createElement("option", {
      value: "asc"
    }, "\u5347\u5E8F"), /*#__PURE__*/React.createElement("option", {
      value: "desc"
    }, "\u964D\u5E8F"))))), /*#__PURE__*/React.createElement(Button, {
      transfer: "export",
      busy: downloading,
      disabled: !response || request.busy,
      reason: response && !response.data.page.total ? '当前范围没有可导出的结果。' : '',
      onClick: download
    }, "\u5BFC\u51FA XLSX"))), /*#__PURE__*/React.createElement(ErrorBox, {
      error: request.error || error
    }), notice && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, notice), request.busy && /*#__PURE__*/React.createElement("p", {
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6\u76EE\u5F55\u62A5\u8868..."), response && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", null, response.data.data_gaps.join(' '), response.data.scope.window_date_from ? ' 统计窗口：' + response.data.scope.window_date_from + ' 至 ' + response.data.scope.window_date_to : ''), /*#__PURE__*/React.createElement(window.ReportTable.Table, {
      data: kind === 'official-review' ? {
        ...response.data,
        topic: 'delivery'
      } : response.data
    }), /*#__PURE__*/React.createElement(Page, {
      page: response.data.page,
      onChange: patch => setTable(old => ({
        ...old,
        ...patch,
        snapshot_ref: response.meta.snapshot_ref
      })),
      busy: request.busy
    })));
  }
  window.ReportCatalog = Catalog;
})();
