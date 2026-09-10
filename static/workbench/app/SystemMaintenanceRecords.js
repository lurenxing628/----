(function () {
  'use strict';

  const A = window.SystemMaintenanceAPI,
    C = window.SystemMaintenanceControls;
  const emptyFilters = {
    query: '',
    type: '',
    status: '',
    level: '',
    file: '',
    start: '',
    end: ''
  };
  const types = {
    manual: '手动备份',
    auto: '自动备份',
    before_restore: '恢复前保护副本',
    unknown: '类型未知',
    restore: '恢复',
    cleanup: '清理',
    runtime: '运行日志',
    operation: '操作记录'
  };
  const states = {
    unverified: '未校验',
    unknown: '结果未知',
    accepted: '已受理',
    checking: '检查中',
    protecting: '创建保护副本',
    restoring: '恢复中',
    verifying: '校验中',
    rolling_back: '回滚中',
    succeeded: '已完成',
    failed: '失败',
    rolled_back: '已回滚',
    rollback_failed: '回滚失败',
    recovery_required: '需人工核查'
  };
  function Filters({
    kind,
    value,
    onChange,
    onSubmit,
    onReset,
    loading
  }) {
    const select = (key, label, choices) => /*#__PURE__*/React.createElement("label", {
      className: "sm-field",
      key: key
    }, /*#__PURE__*/React.createElement("span", null, label), /*#__PURE__*/React.createElement("select", {
      "aria-label": label,
      value: value[key],
      onChange: event => onChange({
        ...value,
        [key]: event.target.value
      })
    }, /*#__PURE__*/React.createElement("option", {
      value: ""
    }, "\u5168\u90E8"), choices.map(([key, label]) => /*#__PURE__*/React.createElement("option", {
      key: key,
      value: key
    }, label))));
    return /*#__PURE__*/React.createElement("form", {
      className: "sm-filters",
      onSubmit: event => {
        event.preventDefault();
        onSubmit();
      }
    }, /*#__PURE__*/React.createElement("label", {
      className: "sm-field sm-search"
    }, /*#__PURE__*/React.createElement("span", null, "\u641C\u7D22"), /*#__PURE__*/React.createElement("span", {
      className: "sm-search-input"
    }, /*#__PURE__*/React.createElement(SMIcon, {
      name: "search"
    }), /*#__PURE__*/React.createElement("input", {
      type: "search",
      "aria-label": "\u641C\u7D22\u7EF4\u62A4\u8BB0\u5F55",
      maxLength: 200,
      value: value.query,
      onChange: event => onChange({
        ...value,
        query: event.target.value
      }),
      placeholder: kind === 'logs' ? '摘要、已读取详情、来源' : '备份文件名'
    }))), select('type', '记录类型', Object.entries(types).filter(([key]) => kind === 'logs' ? ['runtime', 'operation'].includes(key) : !['runtime', 'operation'].includes(key))), select('status', '记录状态', kind === 'logs' ? [['recorded', '已记录']] : Object.entries(states)), kind === 'logs' && /*#__PURE__*/React.createElement(React.Fragment, null, select('file', '日志来源', ['aps.log', 'aps_error.log', 'launcher.log', 'OperationLogs'].map(key => [key, key === 'OperationLogs' ? '操作记录' : key])), select('level', '日志级别', ['INFO', 'WARNING', 'WARN', 'ERROR', 'DEBUG', 'CRITICAL', 'UNKNOWN'].map(key => [key, key]))), ['start', 'end'].map(key => /*#__PURE__*/React.createElement("label", {
      className: "sm-field",
      key: key
    }, /*#__PURE__*/React.createElement("span", null, key === 'start' ? '开始日期' : '结束日期'), /*#__PURE__*/React.createElement("input", {
      type: "date",
      "aria-label": key === 'start' ? '开始日期' : '结束日期',
      value: value[key],
      onChange: event => onChange({
        ...value,
        [key]: event.target.value
      })
    }))), /*#__PURE__*/React.createElement("div", {
      className: "sm-actions",
      style: {
        gridColumn: '1 / -1',
        justifyContent: 'flex-end'
      }
    }, /*#__PURE__*/React.createElement(C.Button, {
      icon: "x",
      "aria-label": "\u6E05\u9664\u7B5B\u9009",
      onClick: onReset
    }), /*#__PURE__*/React.createElement(C.Button, {
      icon: "search",
      type: "submit",
      busy: loading
    }, "\u67E5\u8BE2")));
  }
  function Sources({
    data,
    kind
  }) {
    if (kind === 'backups') return data.sources.map((item, index) => /*#__PURE__*/React.createElement("p", {
      className: "sm-note",
      key: index
    }, item.message, " \xB7 ", item.code));
    const labels = {
      available: '可读取',
      empty: '窗口内暂无记录',
      missing: '来源不存在',
      error: '来源读取失败'
    };
    return /*#__PURE__*/React.createElement("div", {
      className: "sm-log-sources",
      "aria-label": "\u65E5\u5FD7\u8BFB\u53D6\u7A97\u53E3",
      style: {
        borderBottom: '1px solid var(--ui-border)',
        paddingBottom: 12,
        marginBottom: 12
      }
    }, /*#__PURE__*/React.createElement("p", {
      className: "sm-note"
    }, "\u5148\u8BFB\u53D6\u5404\u6765\u6E90\u6700\u8FD1\u7A97\u53E3\uFF0C\u518D\u6309\u6761\u4EF6\u7B5B\u9009\uFF1B\u4E0D\u662F\u5168\u5386\u53F2\u65E5\u5FD7\u3002\u8BB0\u5F55\u72B6\u6001\u4E0D\u4EE3\u8868\u4E1A\u52A1\u6267\u884C\u6210\u529F\u3002"), /*#__PURE__*/React.createElement("div", {
      style: {
        display: 'flex',
        flexWrap: 'wrap',
        gap: '8px 24px'
      }
    }, data.sources.map(item => /*#__PURE__*/React.createElement("div", {
      key: item.source,
      style: {
        flex: '1 1 210px',
        minWidth: 0,
        overflowWrap: 'anywhere',
        fontSize: 13
      }
    }, /*#__PURE__*/React.createElement("strong", null, item.source === 'OperationLogs' ? '操作记录' : item.source), /*#__PURE__*/React.createElement("span", {
      className: ['error', 'missing'].includes(item.state) ? 'sm-tone-warning' : 'sm-meta'
    }, " \xB7 ", labels[item.state]), /*#__PURE__*/React.createElement("div", null, "\u6700\u8FD1 ", item.window, " \u6761 \xB7 ", item.count === null ? '数量未知' : '读取 ' + item.count + ' 条', item.truncated ? ' · 窗口已截断' : ' · 未报告窗口截断'), item.boundary_unknown && /*#__PURE__*/React.createElement("div", {
      className: "sm-tone-warning"
    }, "\u8BFB\u53D6\u8FB9\u754C\u672A\u80FD\u5B8C\u6574\u786E\u8BA4"), item.message && /*#__PURE__*/React.createElement("div", {
      className: "sm-tone-warning"
    }, item.message)))));
  }
  function Detail({
    row,
    kind,
    data,
    reason,
    onAction,
    onDownload,
    downloadBusy,
    onClose
  }) {
    const ref = React.useRef(null);
    const file = kind === 'backups' && row.record_kind === 'backup_file',
      event = kind === 'backups' && !file;
    React.useEffect(() => {
      const previous = document.activeElement;
      ref.current.focus();
      return () => {
        if (previous && previous.isConnected) previous.focus();
      };
    }, []);
    return /*#__PURE__*/React.createElement("section", {
      className: "sm-detail",
      role: "region",
      "aria-label": kind === 'logs' ? '日志详情' : file ? '备份详情' : '维护事件详情',
      tabIndex: -1,
      ref: ref,
      onKeyDown: event => {
        if (event.key === 'Escape') onClose();
      }
    }, /*#__PURE__*/React.createElement("div", {
      className: "sm-section-head"
    }, /*#__PURE__*/React.createElement("h3", {
      style: {
        overflowWrap: 'anywhere',
        minWidth: 0
      }
    }, kind === 'logs' ? '日志详情' : file ? row.filename : row.summary), /*#__PURE__*/React.createElement(C.Button, {
      icon: "x",
      "aria-label": "\u5173\u95ED\u8BE6\u60C5",
      onClick: onClose
    })), /*#__PURE__*/React.createElement("div", {
      className: "sm-detail-meta"
    }, /*#__PURE__*/React.createElement("time", null, row.time ? row.time.replace('T', ' ') : '时间未识别'), /*#__PURE__*/React.createElement("span", null, types[row.type]), /*#__PURE__*/React.createElement("span", null, kind === 'logs' ? row.file + ' · ' + row.level + ' · 已记录' : file ? '未校验 · ' + row.size_bytes + ' 字节' : states[row.status])), event && /*#__PURE__*/React.createElement("p", {
      className: "sm-note"
    }, {
      external_maintenance_journal: '外置维护记录',
      operation_audit: '操作审计',
      latest_job_state_only: '仅最近任务状态'
    }[row.event_source], " \xB7 ", row.event_ref), /*#__PURE__*/React.createElement("p", {
      style: {
        overflowWrap: 'anywhere'
      }
    }, row.summary), /*#__PURE__*/React.createElement("pre", {
      style: {
        fontSize: 13
      }
    }, row.body), row.content_truncated && /*#__PURE__*/React.createElement("p", {
      className: "sm-tone-warning"
    }, "\u672C\u6761\u8BE6\u60C5\u5DF2\u622A\u65AD\uFF0C\u4E0D\u662F\u5B8C\u6574\u539F\u59CB\u5185\u5BB9\u3002"), file && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement("p", {
      className: "sm-note"
    }, "\u5907\u4EFD\u6587\u4EF6\u5B58\u5728\u4E0D\u4EE3\u8868\u5DF2\u6821\u9A8C\u901A\u8FC7\u6216\u53EF\u4EE5\u6062\u590D\u3002"), /*#__PURE__*/React.createElement("div", {
      className: "sm-actions"
    }, /*#__PURE__*/React.createElement(C.Button, {
      transfer: "export",
      disabled: !!reason,
      busy: downloadBusy,
      onClick: () => onDownload(row)
    }, "\u4E0B\u8F7D\u5907\u4EFD"), /*#__PURE__*/React.createElement(C.Button, {
      icon: "rotate-ccw",
      reason: reason || A.blocked(data, 'restore'),
      onClick: () => onAction('restore', row)
    }, "\u6062\u590D\u5907\u4EFD"), /*#__PURE__*/React.createElement(C.Button, {
      icon: "trash-2",
      reason: reason || A.blocked(data, 'delete'),
      onClick: () => onAction('delete', row)
    }, "\u5220\u9664\u5907\u4EFD")), A.blocked(data, 'restore') && /*#__PURE__*/React.createElement("p", {
      className: "sm-note"
    }, "\u6062\u590D\u7981\u7528\uFF1A", A.blocked(data, 'restore')), A.blocked(data, 'delete') && /*#__PURE__*/React.createElement("p", {
      className: "sm-note"
    }, "\u5220\u9664\u7981\u7528\uFF1A", A.blocked(data, 'delete'))));
  }
  function Records({
    api,
    kind,
    pageSize,
    onPageSize,
    revision,
    command,
    active = true,
    initialContext,
    onReadContext
  }) {
    const [start] = React.useState(() => A.recordContext(initialContext, kind));
    const [draft, setDraft] = React.useState(start.filters),
      [filters, setFilters] = React.useState(start.filters);
    const [page, setPage] = React.useState(start.page),
      [snapshot, setSnapshot] = React.useState(''),
      [refresh, reload] = React.useReducer(value => value + 1, 0);
    const [selection, setSelection] = React.useState(start.selection),
      [confirm, setConfirm] = React.useState(null),
      [downloadBusy, setDownloadBusy] = React.useState(false);
    const [error, setError] = React.useState(null),
      [notice, setNotice] = React.useState('');
    const request = C.useRead(api, kind, {
      ...filters,
      page,
      page_size: pageSize,
      snapshot_ref: snapshot
    }, revision + ':' + refresh, active);
    const payload = request.data,
      data = payload && payload.data;
    const stableSelection = selection && (kind !== 'backups' || /^[a-f0-9]{64}$/.test(selection.key) && ['backup_file', 'restore_event', 'cleanup_event'].includes(selection.record_kind));
    const matches = stableSelection && data ? data.rows.filter(row => row.key === selection.key && (kind !== 'backups' || row.record_kind === selection.record_kind && (row.record_kind !== 'backup_file' || !selection.backup_ref || row.backup_ref === selection.backup_ref))) : [];
    const selected = matches.length === 1 ? matches[0] : null;
    function setSelected(row) {
      setSelection(row ? {
        key: row.key,
        ...(kind === 'backups' ? {
          record_kind: row.record_kind,
          ...(row.record_kind === 'backup_file' ? {
            backup_ref: row.backup_ref
          } : {})
        } : {})
      } : null);
    }
    React.useEffect(() => {
      if (selected && kind === 'backups' && selected.record_kind === 'backup_file' && !selection.backup_ref) setSelected(selected);
    }, [selected, selection, kind]);
    const previousVersion = React.useRef(revision + ':' + pageSize);
    React.useEffect(() => {
      const next = revision + ':' + pageSize;
      if (previousVersion.current === next) return;
      previousVersion.current = next;
      setPage(1);
      setSnapshot('');
      setSelected(null);
      setConfirm(null);
    }, [revision, pageSize]);
    const savedScope = JSON.stringify(A.recordContext({
      filters,
      page,
      selection
    }, kind));
    React.useLayoutEffect(() => {
      if (onReadContext && active && data && !request.loading && !request.error) onReadContext(kind, JSON.parse(savedScope));
    }, [onReadContext, kind, active, !!data, request.loading, request.error, savedScope]);
    React.useEffect(() => {
      if (!active || command.locked) setConfirm(null);
    }, [active, command.locked]);
    function apply(value) {
      if (value.start && value.end && value.start > value.end) {
        setError(new Error('开始日期不能晚于结束日期。'));
        return;
      }
      setError(null);
      setNotice('');
      setFilters({
        ...value
      });
      setPage(1);
      setSnapshot('');
      setSelected(null);
      reload();
    }
    function changePage(next) {
      setPage(next);
      setSnapshot(payload.meta.snapshot_ref);
      setSelected(null);
      setError(null);
      setNotice('');
    }
    async function download(format) {
      setError(null);
      setNotice('');
      setDownloadBusy(true);
      try {
        const file = await api.download(format, {
          ...filters,
          page: 1,
          page_size: pageSize,
          snapshot_ref: payload.meta.snapshot_ref
        });
        setNotice('已生成并交给浏览器下载：' + file.filename + '（' + file.bytes + ' 字节）。');
      } catch (problem) {
        setError(problem);
      } finally {
        setDownloadBusy(false);
      }
    }
    async function downloadBackup(row) {
      setError(null);
      setNotice('');
      setDownloadBusy(true);
      try {
        const file = await api.downloadBackup(row, {
          ...filters,
          page: 1,
          page_size: pageSize,
          snapshot_ref: payload.meta.snapshot_ref
        });
        setNotice('已生成并交给浏览器下载：' + file.filename + '（' + file.bytes + ' 字节）。');
      } catch (problem) {
        setError(problem);
      } finally {
        setDownloadBusy(false);
      }
    }
    const writeReason = command.locked ? '原维护请求尚未确认，请先核实结果。' : request.loading || !data ? '请先读取有效的备份清单。' : '';
    const ask = (action, row) => {
      if (action !== 'create' && (!row || row.record_kind !== 'backup_file')) {
        setError(new Error('维护事件不是可操作的备份文件。'));
        return;
      }
      setConfirm({
        action,
        row
      });
    };
    return /*#__PURE__*/React.createElement("section", {
      className: "sm-section",
      "aria-label": kind === 'logs' ? '运行日志与操作记录' : '备份与恢复记录'
    }, /*#__PURE__*/React.createElement("div", {
      className: "sm-section-head"
    }, /*#__PURE__*/React.createElement("h3", null, kind === 'logs' ? '运行日志与操作记录' : '备份与恢复记录'), /*#__PURE__*/React.createElement(C.Button, {
      icon: "refresh-cw",
      "aria-label": "\u91CD\u65B0\u8BFB\u53D6\u6E05\u5355",
      busy: request.loading,
      onClick: () => {
        setPage(1);
        setSnapshot('');
        setSelected(null);
        reload();
      }
    })), /*#__PURE__*/React.createElement("div", {
      className: "sm-toolbar"
    }, /*#__PURE__*/React.createElement(Filters, {
      kind: kind,
      value: draft,
      onChange: setDraft,
      onSubmit: () => apply(draft),
      loading: request.loading,
      onReset: () => {
        setDraft({
          ...emptyFilters
        });
        apply(emptyFilters);
      }
    }), /*#__PURE__*/React.createElement("div", {
      className: "sm-actions sm-record-actions"
    }, kind === 'backups' ? /*#__PURE__*/React.createElement(C.Button, {
      icon: "plus",
      reason: writeReason || A.blocked(data, 'create'),
      onClick: () => ask('create', null)
    }, "\u521B\u5EFA\u5907\u4EFD") : /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(C.Button, {
      transfer: "export",
      disabled: !data || request.loading,
      busy: downloadBusy,
      onClick: () => download('csv')
    }, "\u5BFC\u51FA\u7A97\u53E3 CSV"), /*#__PURE__*/React.createElement(C.Button, {
      transfer: "export",
      disabled: !data || request.loading,
      busy: downloadBusy,
      onClick: () => download('zip')
    }, "\u8131\u654F\u8BCA\u65AD ZIP")))), /*#__PURE__*/React.createElement(C.ErrorBox, {
      error: request.error || error
    }), notice && /*#__PURE__*/React.createElement("p", {
      className: "sm-notice",
      role: "status"
    }, notice), selection && data && !selected && /*#__PURE__*/React.createElement("p", {
      className: "sm-notice",
      role: "status"
    }, !stableSelection ? '原选择缺少可信的稳定记录标识或记录类型，未按旧令牌、同名文件或第一条记录定位。' : '原选择记录未通过当前返回页的唯一身份核对，未自动替换为其他记录。', /*#__PURE__*/React.createElement(C.Button, {
      icon: "x",
      onClick: () => setSelected(null)
    }, "\u6E05\u9664\u539F\u9009\u62E9")), kind === 'backups' && data && A.blocked(data, 'create') && /*#__PURE__*/React.createElement("p", {
      className: "sm-note"
    }, "\u6587\u4EF6\u52A8\u4F5C\u7981\u7528\uFF1A", A.blocked(data, 'create')), request.loading && /*#__PURE__*/React.createElement("p", {
      className: "sm-note",
      role: "status"
    }, "\u6B63\u5728\u8BFB\u53D6", kind === 'logs' ? '日志窗口' : '备份清单', "\u2026"), data && /*#__PURE__*/React.createElement(React.Fragment, null, /*#__PURE__*/React.createElement(Sources, {
      data: data,
      kind: kind
    }), /*#__PURE__*/React.createElement("div", {
      className: "sm-meta"
    }, "\u5DE5\u5382\u672C\u5730\u65F6\u95F4 \xB7 \u6570\u636E\u622A\u81F3 ", payload.meta.as_of.replace('T', ' ')), data.rows.length ? /*#__PURE__*/React.createElement("div", {
      className: "wb-table-shell",
      style: {
        overflowX: 'auto'
      }
    }, /*#__PURE__*/React.createElement("table", {
      className: 'wb-table sm-table sm-record-table sm-' + kind + '-table'
    }, /*#__PURE__*/React.createElement("thead", null, /*#__PURE__*/React.createElement("tr", null, /*#__PURE__*/React.createElement("th", null, "\u5DE5\u5382\u672C\u5730\u65F6\u95F4"), /*#__PURE__*/React.createElement("th", null, "\u7C7B\u578B"), /*#__PURE__*/React.createElement("th", null, "\u72B6\u6001"), kind === 'logs' && /*#__PURE__*/React.createElement("th", null, "\u7EA7\u522B"), /*#__PURE__*/React.createElement("th", null, kind === 'logs' ? '摘要 / 来源' : '文件'), kind === 'backups' && /*#__PURE__*/React.createElement("th", null, "\u5927\u5C0F"), /*#__PURE__*/React.createElement("th", null, "\u8BE6\u60C5"))), /*#__PURE__*/React.createElement("tbody", null, data.rows.map(row => /*#__PURE__*/React.createElement("tr", {
      key: row.key,
      "data-record-kind": row.record_kind,
      tabIndex: 0,
      "aria-label": '查看详情 ' + row.summary,
      "aria-expanded": !!selected && selected.key === row.key,
      style: {
        cursor: 'pointer'
      },
      onClick: () => setSelected(row),
      onKeyDown: event => {
        if (event.target === event.currentTarget && ['Enter', ' '].includes(event.key)) {
          event.preventDefault();
          setSelected(row);
        }
      }
    }, /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("time", {
      className: "sm-time"
    }, row.time ? row.time.replace('T', ' ') : '时间未识别')), /*#__PURE__*/React.createElement("td", null, types[row.type]), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("span", {
      className: "sm-status sm-tone-neutral"
    }, kind === 'logs' ? '已记录' : states[row.status])), kind === 'logs' && /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("span", {
      className: 'sm-level sm-level-' + row.level
    }, row.level)), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement("div", {
      className: "sm-summary"
    }, /*#__PURE__*/React.createElement("strong", {
      style: {
        fontSize: 14
      }
    }, row.summary), kind === 'logs' && /*#__PURE__*/React.createElement("small", null, row.file, row.content_truncated ? ' · 详情已截断' : ''))), kind === 'backups' && /*#__PURE__*/React.createElement("td", {
      style: {
        textAlign: 'right'
      }
    }, row.record_kind === 'backup_file' ? (row.size_bytes / 1024).toFixed(1) + ' KB' : '事件记录'), /*#__PURE__*/React.createElement("td", null, /*#__PURE__*/React.createElement(C.Button, {
      icon: "chevron-right",
      className: "mini",
      "aria-label": '查看详情 ' + row.summary,
      onClick: event => {
        event.stopPropagation();
        setSelected(row);
      }
    }))))))) : /*#__PURE__*/React.createElement(SMUnavailable, {
      title: "\u5F53\u524D\u7B5B\u9009\u4E0B\u6682\u65E0\u8BB0\u5F55"
    }, kind === 'logs' ? '仅限已读取的日志窗口；来源缺失和读取失败另行列出。' : '仅限已读取的备份文件、恢复事件和清理记录。'), /*#__PURE__*/React.createElement("div", {
      className: "sm-pager"
    }, /*#__PURE__*/React.createElement("span", {
      className: "sm-meta"
    }, "\u5F53\u524D\u8303\u56F4\u5171 ", data.page.total, " \u6761"), /*#__PURE__*/React.createElement("div", {
      className: "sm-actions"
    }, /*#__PURE__*/React.createElement("label", {
      className: "sm-inline-label"
    }, "\u6BCF\u9875", /*#__PURE__*/React.createElement("select", {
      "aria-label": "\u6BCF\u9875\u6570\u91CF",
      value: pageSize,
      onChange: event => onPageSize(Number(event.target.value))
    }, [10, 25, 50].map(size => /*#__PURE__*/React.createElement("option", {
      key: size,
      value: size
    }, size, " \u6761")))), /*#__PURE__*/React.createElement(C.Button, {
      icon: "chevron-left",
      "aria-label": "\u4E0A\u4E00\u9875",
      disabled: data.page.number <= 1,
      onClick: () => changePage(page - 1)
    }), /*#__PURE__*/React.createElement("span", {
      className: "sm-page-number"
    }, data.page.number, " / ", data.page.pages), /*#__PURE__*/React.createElement(C.Button, {
      icon: "chevron-right",
      "aria-label": "\u4E0B\u4E00\u9875",
      disabled: data.page.number >= data.page.pages,
      onClick: () => changePage(page + 1)
    }))), selected && /*#__PURE__*/React.createElement(Detail, {
      key: selected.key,
      row: selected,
      kind: kind,
      data: data,
      reason: writeReason,
      onAction: ask,
      onDownload: downloadBackup,
      downloadBusy: downloadBusy,
      onClose: () => setSelected(null)
    })), confirm && /*#__PURE__*/React.createElement(C.Confirm, {
      ...confirm,
      reason: writeReason || A.blocked(data, confirm.action),
      onClose: () => setConfirm(null),
      onConfirm: () => {
        const {
            action,
            row
          } = confirm,
          reason = writeReason || A.blocked(data, action);
        if (reason) {
          setError(new Error(reason));
          return;
        }
        setConfirm(null);
        command.execute(action, row ? row.write_context.write_token : data.create_context.write_token, row ? {
          backup_ref: row.backup_ref
        } : {}, row ? {
          filename: row.filename
        } : null);
      }
    }));
  }
  window.SystemMaintenanceRecords = Records;
})();
