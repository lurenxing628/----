import C from './resource-contract.js';
import M from './ResourceMaterialContract.js';
import { failure, object, token32, isDate } from './shared/contract/kit.js';

// 日历文件的导出范围都以日期区间为准，不是列表筛选。个人日历在日期之外还能只导某几个人。
const labels = { work_calendar: '工作日历', operator_calendar: '个人日历' };
// 个人日历在日期之外多一维人员范围；全局日历没有这一维。
const PEOPLE_KIND = 'operator_calendar';
const hints = {
  work_calendar: {
    scopeLabel: '日期范围',
    confirmationHint: '这一天的安排和日历页上看到的不完全一样，请核对修改前后内容。',
    acknowledgeHint: '已核对这些日期的修改前后内容，确认这些更新。',
    importHint: '按日期增量更新：文件里列出的日期会被改写，没列出的日期完全不动。'
      + '空格子表示这一项保持原样；备注要清除请填 \\N（大写）。类型填工作日或假期，'
      + '允许普通件和允许急件填是或否，效率按百分比填。'
      + '这张表只管已经单独设置过的日期；要把某一天恢复成默认规则，请在日历页用批量维护里的清除。'
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
// 日期范围的错误带上项路径，弹窗里对应的日期项会标红；总错误框只保留这一句话。一次能导出多少天由后端校验。
// 路径与后端导出预检的 400 同一口径：范围在请求体的 range 下（range.start_date / range.end_date）。
function checkRange(value) {
  if (!object(value) || !isDate(value.start_date) || !isDate(value.end_date))
    throw failure('请先选好开始和结束日期，没有开始下载。',
      { fields: [{ path: !object(value) || !isDate(value.start_date) ? 'range.start_date' : 'range.end_date', message: '请按 2026-09-13 这样填写日期。' }] });
  if (value.start_date > value.end_date) throw failure('结束日期不能早于开始日期，没有开始下载。', { fields: [{ path: 'range.end_date', message: '结束日期不能早于开始日期。' }] });
  return { start_date: value.start_date, end_date: value.end_date };
}
// 导出请求体只在这里拼一次，导出预检回来也拿它对账，免得两边各写一份人员范围的判断。
function exportBody(kind, shared, request, selected) {
  const range = checkRange(selected), body = { range };
  if (kind === PEOPLE_KIND) {
    if (!object(selected) || !['all', 'selected'].includes(selected.people))
      throw failure('请先选好要导出哪些人员，没有开始下载。');
    if (selected.people === 'selected') {
      const refs = shared.selection(request);
      if (!refs.length) throw failure('还没有勾选人员，没有开始下载。请先在人员列表里勾选，或者改成导出全部人员。');
      body.scope = { operator_refs: refs };
    }
  } else if (object(selected) && C.own(selected, 'people')) {
    throw failure('这类日历没有人员范围，没有开始下载。');
  }
  const snapshot = request && request.snapshot_ref;
  if (token32(snapshot)) body.snapshot_ref = snapshot;
  return body;
}
function create(kind) {
  if (!C.own(labels, kind)) throw failure('不支持这类日历的文件操作。');
  const label = labels[kind];
  const shared = M.create(kind, label);
  return {
    ...shared, ...hints[kind],
    paths: {
      import: 'calendar-files/' + kind + '/preview', export: 'calendar-files/' + kind + '/export-preview',
      download: 'calendar-files/' + kind + '/export', template: 'calendar-files/' + kind + '/template'
    },
    templateHint: '空白表头模板，只有列名，没有示例数据。',
    requestBody(mode, request, selected) {
      if (mode !== 'export') throw failure('日历文件只支持导入和按日期范围导出。');
      return exportBody(kind, shared, request, selected);
    },
    // 导出范围是日期区间，不是勾选；初始值由弹窗按当前月份给。
    exportPreview(result, _selected, body) {
      const data = result.data;
      if (!token32(data.export_ref) || !object(data.range)
          || data.range.start_date !== body.range.start_date || data.range.end_date !== body.range.end_date)
        throw failure('导出预检内容不完整，没有开始下载。');
      // 服务端把这次导出的人员范围原样回显在 range 里，对不上就不下载，免得导出的是别人的日历。
      const echoed = C.own(data.range, 'selected_refs') ? data.range.selected_refs : null;
      const wanted = body.scope ? body.scope.operator_refs : null;
      if (JSON.stringify(echoed) !== JSON.stringify(wanted))
        throw failure('导出预检的人员范围和选择的不一致，没有开始下载。');
      return result;
    }
  };
}
const APSCalendarFile = { create, labels, peopleKind: PEOPLE_KIND };
export { APSCalendarFile, create, labels, PEOPLE_KIND as peopleKind };
export default APSCalendarFile;
