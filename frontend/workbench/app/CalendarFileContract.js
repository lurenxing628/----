(function () {
  'use strict';
  // Load after ResourceMaterialContract.js and CalendarContract.js。
  // 日历文件的导出范围都以日期区间为准，不是列表筛选。个人日历在日期之外还能只导某几个人。
  const C = window.APSResourceContract, M = window.APSResourceMaterial, K = window.APSCalendarContract;
  const labels = { work_calendar: '工作日历', operator_calendar: '个人日历' };
  // 个人日历在日期之外多一维人员范围；全局日历没有这一维。
  const PEOPLE_KIND = 'operator_calendar';
  const token = value => typeof value === 'string' && /^[A-Za-z0-9_-]{32}$/.test(value);
  const count = value => Number.isSafeInteger(value) && value >= 0;
  const scalar = value => value === null || typeof value === 'string';
  const MAX_RANGE_DAYS = 1096;
  const hints = {
    work_calendar: {
      scopeLabel: '日期范围',
      confirmationHint: '这一天的安排和日历页上看到的不完全一样，请核对修改前后内容。',
      acknowledgeHint: '已核对这些日期的修改前后内容，确认这些更新。',
      importHint: '按日期增量更新：文件里列出的日期会被改写，没列出的日期完全不动。'
        + '空格子表示这一项保持原样；备注要清除请填 \\N（大写）。类型填工作日或假期，'
        + '允许普通件和允许急件填是或否，效率按百分比填。'
        + '这张表只管已经单独配置过的日期；要把某一天恢复成默认规则，请在日历页用批量维护里的清除。'
    },
    operator_calendar: {
      scopeLabel: '人员和日期范围',
      confirmationHint: '这一天这个人会整天按文件里的安排排产，请核对修改前后内容。',
      acknowledgeHint: '已核对这些人员这些日期的修改前后内容，确认这些更新。',
      importHint: '按「工号 + 日期」增量更新：文件里列出的那个人那一天会被改写，其他人和其他日期完全不动。'
        + '空格子表示这一项保持原样；备注和班次结束要清除请填 \\N（大写）。'
        + '工时不用填，由班次起止算出来；类型填工作日或假期，填假期时不用填班次。'
        + '只填这个人有特殊安排的日期；要取消某几天的特殊安排，请在人员详情的「编辑个人日历」里按日期范围清除。'
    }
  };
  function days(range) {
    return Math.round((Date.parse(range.end_date + 'T00:00:00Z') - Date.parse(range.start_date + 'T00:00:00Z')) / 86400000) + 1;
  }
  function checkRange(value) {
    if (!C.object(value) || !K.isDate(value.start_date) || !K.isDate(value.end_date))
      throw C.failure('请先选好开始和结束日期，没有开始下载。');
    if (value.start_date > value.end_date) throw C.failure('结束日期不能早于开始日期，没有开始下载。');
    if (days(value) > MAX_RANGE_DAYS) throw C.failure('一次最多导出 ' + MAX_RANGE_DAYS + ' 天，没有开始下载。请把范围缩小后重试。');
    return { start_date: value.start_date, end_date: value.end_date };
  }
  // 导出请求体只在这里拼一次，导出预检回来也拿它对账，免得两边各写一份人员范围的判断。
  function exportBody(kind, shared, request, selected) {
    const range = checkRange(selected), body = { range };
    if (kind === PEOPLE_KIND) {
      if (!C.object(selected) || !['all', 'selected'].includes(selected.people))
        throw C.failure('请先选好要导出哪些人员，没有开始下载。');
      if (selected.people === 'selected') {
        const refs = shared.selection(request);
        if (!refs.length) throw C.failure('还没有勾选人员，没有开始下载。请先在人员列表里勾选，或者改成导出全部人员。');
        body.scope = { operator_refs: refs };
      }
    } else if (C.object(selected) && C.own(selected, 'people')) {
      throw C.failure('这类日历没有人员范围，没有开始下载。');
    }
    const snapshot = request && request.snapshot_ref;
    if (token(snapshot)) body.snapshot_ref = snapshot;
    return body;
  }
  function columns(data) {
    if (!Array.isArray(data.columns) || !data.columns.length || !data.columns.every(item => C.object(item)
        && typeof item.key === 'string' && /^[a-z][a-z0-9_]*$/.test(item.key)
        && typeof item.label === 'string' && item.label.trim() && item.label !== item.key)
        || new Set(data.columns.map(item => item.key)).size !== data.columns.length)
      throw C.failure('预检缺少完整的业务列名，本批没有提交。');
    const keys = new Set(data.columns.map(item => item.key));
    const facts = value => value === null || C.object(value) && Object.keys(value).every(key => keys.has(key) && scalar(value[key]));
    if (!data.rows.every(row => facts(row.before) && facts(row.after) && Object.keys(row.changes).every(key => keys.has(key)
        && C.object(row.changes[key]) && C.own(row.changes[key], 'before') && C.own(row.changes[key], 'after')
        && scalar(row.changes[key].before) && scalar(row.changes[key].after))))
      throw C.failure('预检明细里有未说明的列，本批没有提交。');
  }
  function notes(data) {
    if (!data.rows.every(row => Array.isArray(row.notes) && row.notes.every(note => typeof note === 'string' && note.trim())))
      throw C.failure('预检的逐行说明不完整，本批没有提交。');
    if (!data.rows.every(row => !row.requires_confirmation || row.notes.length))
      throw C.failure('预检里有需要核对的行却没有写明原因，本批没有提交。');
  }
  function create(kind) {
    if (!C.own(labels, kind)) throw C.failure('不支持这类日历的文件操作。');
    const label = labels[kind];
    const shared = M.create(kind, label);
    return {
      ...shared, ...hints[kind],
      paths: {
        import: 'calendar-files/' + kind + '/preview', export: 'calendar-files/' + kind + '/export-preview',
        download: 'calendar-files/' + kind + '/export', template: 'calendar-files/' + kind + '/template'
      },
      // 导出范围是日期区间，不是勾选；初始值由弹窗按当前月份给。
      rowsMatchSelection: false,
      templateHint: '空白表头模板，只有列名，没有示例数据。',
      checkRange,
      preview(raw, mode, expected, request) {
        const result = shared.preview(raw, mode, expected, request);
        columns(result.data);
        notes(result.data);
        return result;
      },
      requestBody(mode, request, selected) {
        if (mode !== 'export') throw C.failure('日历文件只支持导入和按日期范围导出。');
        return exportBody(kind, shared, request, selected);
      },
      exportPreview(raw, selected, request) {
        const result = shared.envelope(raw), data = result.data;
        const body = exportBody(kind, shared, request, selected);
        if (!token(data.export_ref) || !count(data.row_count) || !Array.isArray(data.formats)
            || !data.formats.every(value => ['csv', 'xlsx'].includes(value)) || !C.object(data.range)
            || data.range.start_date !== body.range.start_date || data.range.end_date !== body.range.end_date
            || !Number.isFinite(Date.parse(data.expires_at)))
          throw C.failure('导出预检内容不完整，没有开始下载。');
        // 服务端把这次导出的人员范围原样回显在 range 里，对不上就不下载，免得导出的是别人的日历。
        const echoed = C.own(data.range, 'selected_refs') ? data.range.selected_refs : null;
        const wanted = body.scope ? body.scope.operator_refs : null;
        if (JSON.stringify(echoed) !== JSON.stringify(wanted))
          throw C.failure('导出预检的人员范围和选择的不一致，没有开始下载。');
        return result;
      }
    };
  }
  window.APSCalendarFile = { create, labels, checkRange, peopleKind: PEOPLE_KIND };
})();
