(function () {
  'use strict';
  const api = window.APSTrialSample;
  const nodes = Object.assign({}, window.APSDashboard.iconNodes, window.APSFieldReports.iconNodes);
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const icon = name => {
    if (!nodes[name]) throw new Error('样板图标未加载：' + name);
    return '<svg class="tr-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + nodes[name].map(([tag, attrs]) => '<' + tag + ' ' + Object.entries(attrs).map(([key, value]) => key + '="' + esc(value) + '"').join(' ') + '></' + tag + '>').join('') + '</svg>';
  };
  const badge = (text, tone = '') => '<span class="tr-status ' + tone + '">' + esc(text) + '</span>';
  const button = (label, action, name, extra = '') => '<button type="button" class="tr-button" data-action="' + action + '" ' + extra + '>' + (name ? icon(name) : '') + esc(label) + '</button>';
  const time = value => esc(api.formatTime(value));
  const number = value => Number(value.toFixed(1));
  const base = () => api.scenarios.find(s => s.id === 'base');
  const sameTask = (a, b) => a.resource === b.resource && a.person === b.person && a.start === b.start && a.end === b.end;
  const slot = iso => (Number(iso.slice(8, 10)) - 8) * 10 + Number(iso.slice(11, 13)) - 8 + Number(iso.slice(14, 16)) / 60;
  const barStyle = task => {
    const left = Math.max(0, Math.min(100, slot(task.start) / 20 * 100));
    const right = Math.max(left, Math.min(100, slot(task.end) / 20 * 100));
    return 'left:' + left + '%;width:' + (right - left) + '%';
  };
  function revealTask(target) {
    const bar = target.closest('.tr-bar');
    if (!bar) return;
    const board = bar.closest('.tr-board'), frame = board.getBoundingClientRect();
    const resource = bar.closest('.tr-lane').querySelector('.tr-resource').getBoundingClientRect();
    const axis = board.querySelector('.tr-axis').getBoundingClientRect(), bounds = bar.getBoundingClientRect();
    const right = frame.left + board.clientWidth, bottom = frame.top + board.clientHeight;
    // Native focus scrolling does not account for frozen row/column headers.
    if (bounds.left < resource.right) board.scrollLeft += bounds.left - resource.right;
    else if (bounds.right > right) board.scrollLeft += Math.min(bounds.left - resource.right, bounds.right - right);
    if (bounds.top < axis.bottom) board.scrollTop += bounds.top - axis.bottom;
    else if (bounds.bottom > bottom) board.scrollTop += Math.min(bounds.top - axis.bottom, bounds.bottom - bottom);
  }
  function focusTask(root, id, position) {
    const bar = Array.from(root.querySelectorAll('.tr-bar')).find(node => node.dataset.task === id);
    if (!bar) return;
    const board = bar.closest('.tr-board');
    if (position) { board.scrollLeft = position.left; board.scrollTop = position.top; }
    bar.focus({ preventScroll: true });
    revealTask(bar);
  }
  function sidebar() {
    const groups = [
      ['① 数据准备', [['process', '基础资料', 'database'], ['batches', '批次管理', 'boxes']]],
      ['② 执行排产', [['run', '执行排产', 'calendar-clock'], ['analysis', '选择排产方案', 'git-compare-arrows'], ['trial', '方案试调', 'square-pen'], ['gantt', '设备 / 人员 / 批次甘特', 'chart-gantt']]],
      ['③ 现场', [['field', '现场记录', 'clipboard-list'], ['fieldgantt', '现场实际甘特', 'chart-gantt']]],
      ['④ 统计分析', [['review', '执行复盘', 'history'], ['reports', '报表中心', 'file-down'], ['calib', '工时定额校准', 'clock-3']]],
      ['基础数据 · 系统', [['dashboard', '值班台', 'clipboard-list'], ['basedata', '主数据总览', 'database'], ['system', '系统管理', 'wrench']]]
    ];
    return '<aside class="tr-sidebar"><a class="tr-brand" href="index.html"><img src="../../assets/logo-mark.svg" alt=""><strong>APS 智能排产</strong></a><nav class="tr-nav" aria-label="主导航">' + groups.map(([title, items]) => '<div class="tr-nav-group"><div class="tr-nav-title">' + title + '</div>' + items.map(([id, label, image]) => '<a href="' + (id === 'trial' ? 'trial-sample.html' : 'index.html?view=' + id) + '" title="' + label + '"' + (id === 'trial' ? ' class="active" aria-current="page"' : '') + '>' + icon(image) + '<span class="tr-nav-label">' + label + '</span>' + (id === 'trial' ? '<span class="tr-nav-tag">样板</span>' : '') + '</a>').join('') + '</div>').join('') + '</nav></aside>';
  }
  function comparison(state, vm) {
    const choices = api.scenarios.concat(state.draft ? [state.draft] : []);
    if (!choices.some(s => vm.samePlan(s, state.adopted))) choices.push(Object.assign({}, state.adopted, { id: 'adopted' }));
    return '<section class="tr-comparison" aria-label="候选方案对比"><div class="tr-table-wrap"><table class="tr-table"><thead><tr><th>排产方案</th><th class="num">预计晚交</th><th class="num">总拖期</th><th class="num">调整工序</th><th class="num">换设备</th><th class="num">换型次数¹</th><th>方案状态</th></tr></thead><tbody>' + choices.map(s => {
      const inspection = api.inspect(s, base()), m = inspection.report;
      const adopted = vm.samePlan(s, state.adopted), blocked = inspection.issues.length > 0;
      const label = adopted ? '正式采用 v' + state.version : blocked ? '存在冲突' : s.id === 'base' ? '初始基线 v15' : s.id === 'draft' ? '试调草稿' : '候选';
      return '<tr class="' + (s.id === state.selected ? 'selected' : '') + '"><td><label class="tr-scheme-label"><input type="radio" name="scheme" value="' + esc(s.id) + '" ' + (s.id === state.selected ? 'checked' : '') + '><strong>' + esc(s.name) + '</strong>' + (s.recommended ? badge('建议', 'notice') : '') + '</label></td>'
        + '<td class="num ' + (blocked ? '' : m.lateCount ? 'tr-negative' : 'tr-positive') + '">' + (blocked ? '不可评估' : '<strong>' + m.lateCount + '</strong> 批') + '</td>'
        + '<td class="num">' + (blocked ? '不可评估' : number(m.totalDelayHours) + ' h') + '</td><td class="num">' + m.changedOperations + ' 道</td><td class="num">' + m.movedOperations + ' 道</td>'
        + '<td class="num">' + (s.changeovers == null ? '未评估' : s.changeovers + ' 次') + '</td><td>' + badge(label, adopted ? 'ok' : blocked ? 'danger' : s.id === 'draft' ? 'warning' : '') + '</td></tr>';
    }).join('') + '</tbody></table></div><aside class="tr-choice-note">' + badge(vm.isAdopted ? '当前正式方案' : '正在预览 · 未改变正式计划', vm.isAdopted ? 'ok' : 'notice') + '<h2>' + esc(vm.scenario.name) + '</h2><p>' + esc(vm.scenario.summary) + '</p><p class="tr-cost">' + icon('info') + ' ' + esc(vm.scenario.tradeoff) + '</p></aside></section>';
  }
  function timeline(state, vm) {
    const originals = base().tasks;
    const visible = vm.scenario.tasks.filter(t => {
      const b = api.batches.find(x => x.id === t.batch);
      return (!state.changedOnly || !sameTask(t, originals.find(x => x.id === t.id))) && (!state.search || [t.batch, t.op, t.resource, t.person, b.name].join(' ').toLowerCase().includes(state.search.toLowerCase()));
    });
    const resourceView = state.view !== 'batch';
    const keys = resourceView ? api.resources.map(r => state.view === 'person' ? r.person : r.id) : api.batches.map(b => b.id);
    const group = t => state.view === 'person' ? t.person : state.view === 'resource' ? t.resource : t.batch;
    const rows = keys.map(key => {
      const tasks = visible.filter(t => group(t) === key);
      const ghosts = originals.filter(t => group(t) === key && visible.some(v => v.id === t.id));
      if (!tasks.length && !ghosts.length) return '';
      const r = resourceView ? api.resources.find(x => state.view === 'person' ? x.person === key : x.id === key) : api.batches.find(x => x.id === key);
      const load = resourceView && vm.report.loads.find(x => x.id === r.id);
      const layout = api.layoutIntervals(tasks), baselineTop = 12 + layout.count * 48;
      const label = '<strong>' + esc(state.view === 'person' ? r.person : r.id) + '</strong><small>' + esc(r.name) + '</small><small>' + (load ? number(load.hours) + ' / ' + load.capacityHours + ' h · 本范围' : r.qty + ' 件 · ' + esc(r.priority)) + '</small>' + (layout.overlaps.length ? '<small class="tr-negative">时段冲突 · ' + layout.overlaps.length + ' 处</small>' : '');
      return '<div class="tr-lane" data-resource="' + esc(key) + '"><div class="tr-resource">' + label + '</div><div class="tr-track" style="min-height:' + (baselineTop + (state.showBaseline ? 16 : 4)) + 'px"><span class="tr-day-line"></span>' + layout.overlaps.map(overlap => '<span class="tr-overlap" style="' + barStyle(overlap) + ';height:' + (layout.count * 48 - 4) + 'px" title="资源时段冲突：' + time(overlap.start) + ' 至 ' + time(overlap.end) + '"></span>').join('') + (state.showBaseline ? ghosts.map(t => '<span class="tr-baseline" style="' + barStyle(t) + ';top:' + baselineTop + 'px" title="初始计划 ' + time(t.start) + ' 至 ' + time(t.end) + '"></span>').join('') : '') + tasks.map(t => {
        const b = vm.report.rows.find(x => x.id === t.batch);
        const conflict = vm.issues.some(issue => issue.taskIds.includes(t.id));
        const cls = t.locked ? ' locked' : b.lateHours > 0 ? ' late' : b.priority === '特急' ? ' urgent' : '';
        const text = t.batch + ' · ' + t.op + ' · ' + api.formatTime(t.start) + ' 至 ' + api.formatTime(t.end) + (t.locked ? ' · 固定工序' : '');
        return '<button type="button" class="tr-bar' + cls + (state.taskId === t.id ? ' selected' : '') + (conflict ? ' conflict' : '') + '" data-task="' + esc(t.id) + '" style="' + barStyle(t) + ';top:' + (12 + layout.tracks[t.id] * 48) + 'px" title="' + esc(text) + '" aria-label="' + esc(text) + '" aria-pressed="' + (state.taskId === t.id) + '"><span class="tr-bar-face"><strong>' + esc(t.op) + '</strong><small>' + esc(resourceView ? t.batch.slice(-3) : t.resource) + '</small></span></button>';
      }).join('') + '</div></div>';
    }).join('');
    const days = ['09-08 周二', '09-09 周三'].map(day => '<div class="tr-day"><strong>' + day + '</strong><div class="tr-ticks"><span>08:00</span><span>10:00</span><span>12:00</span><span>14:00</span><span>16:00</span><span>18:00</span></div></div>').join('');
    return '<section aria-label="排程预览"><div class="tr-section-head"><h2>排程预览 <small>· ' + esc(vm.scenario.name) + '</small></h2><small>09-08 至 09-09 · 日班 08:00–18:00</small></div><div class="tr-board-shell"><div class="tr-toolbar"><div class="tr-control-group"><span>视图</span><div class="tr-segment" aria-label="甘特分组">' + (state.allowPerson ? [['resource', '设备'], ['person', '人员'], ['batch', '批次']] : [['resource', '设备'], ['batch', '批次']]).map(([value, label]) => '<button type="button" data-view="' + value + '" aria-pressed="' + (state.view === value) + '">' + label + '</button>').join('') + '</div></div><label class="tr-check"><input type="checkbox" name="baseline" ' + (state.showBaseline ? 'checked' : '') + '>初始基线</label><label class="tr-check"><input type="checkbox" name="changed" ' + (state.changedOnly ? 'checked' : '') + '>仅变更</label><div class="tr-toolbar-end"><label class="tr-search">' + icon('search') + '<input type="search" name="search" aria-label="搜索批次、工序或资源" placeholder="批次 / 工序 / 资源" value="' + esc(state.search) + '"></label>' + button(state.expanded ? '收起' : '展开', 'expand', 'chart-gantt', 'title="' + (state.expanded ? '返回完整工作区' : '展开甘特工作区') + '"') + '</div></div><div class="tr-board"><div class="tr-gantt"><div class="tr-axis"><div class="tr-corner">' + (state.view === 'person' ? '人员 / 设备' : state.view === 'resource' ? '设备 / 人员' : '批次 / 工序') + '<small>仅显示日班，夜间折叠</small></div><div class="tr-days">' + days + '</div></div>' + (rows || '<div class="tr-empty">当前筛选没有匹配工序。</div>') + '</div></div><div class="tr-legend"><span><i class="tr-swatch"></i>预览安排</span><span><i class="tr-swatch late"></i>交期风险</span><span><i class="tr-swatch locked"></i>固定工序</span><span><i class="tr-swatch baseline"></i>初始计划 v15</span><span>金边：选中工序</span></div></div></section>';
  }
  function impact(state, vm) {
    const deliveryBadge = row => vm.issues.length ? badge('冲突待处理', 'warning') : badge(row.lateHours > 0 ? '晚 ' + number(row.lateHours) + ' h' : '可按期', row.lateHours > 0 ? 'danger' : 'ok');
    let body;
    if (state.tab === 'history') {
      body = state.history.length ? '<ol class="tr-history">' + state.history.slice().reverse().map(r => '<li><strong>v' + r.version + ' · ' + esc(r.name) + '</strong> ' + badge('示例采用记录', 'ok') + '<p>' + esc(r.person) + ' · ' + esc(r.reason) + '</p><time>' + esc(r.at) + ' · 从 ' + esc(r.previous) + ' 切换 · 调整 ' + r.changed + ' 道工序</time></li>').join('') + '</ol>' : '<div class="tr-empty">尚未采用新方案；初始正式计划为 v15。</div>';
    } else {
      const rows = vm.report.rows.filter(r => !state.changedOnly || r.changed);
      body = '<div class="tr-table-wrap"><table class="tr-table"><thead><tr><th>批次 / 零件</th><th>交付截至</th><th>初始计划完工</th><th>预览完工</th><th class="num">完工变化</th><th>预计交付</th></tr></thead><tbody>' + rows.map(r => '<tr class="' + (vm.task && r.id === vm.task.batch ? 'selected' : '') + '"><td><button type="button" class="tr-batch-button" data-batch="' + esc(r.id) + '">' + esc(r.id) + '<small>' + esc(r.name) + ' · ' + r.qty + ' 件</small></button></td><td>' + time(r.due) + '</td><td>' + time(r.baselineFinish) + '</td><td>' + time(r.finish) + '</td><td class="num ' + (r.improvementHours > 0 ? 'tr-positive' : r.improvementHours < 0 ? 'tr-negative' : '') + '">' + (r.improvementHours ? (r.improvementHours > 0 ? '提前 ' : '后移 ') + number(Math.abs(r.improvementHours)) + ' h' : '不变') + '</td><td>' + deliveryBadge(r) + '</td></tr>').join('') + '</tbody></table>' + (!rows.length ? '<div class="tr-empty">本方案相对初始计划没有变更。</div>' : '') + '</div>';
    }
    return '<section class="tr-lower"><div class="tr-tabs" role="tablist" aria-label="方案结果"><button type="button" role="tab" id="tr-impact-tab" aria-controls="tr-result-panel" data-tab="impact" aria-selected="' + (state.tab === 'impact') + '">批次交付<small>' + vm.report.rows.length + '</small></button><button type="button" role="tab" id="tr-history-tab" aria-controls="tr-result-panel" data-tab="history" aria-selected="' + (state.tab === 'history') + '">采用记录<small>' + state.history.length + '</small></button></div><div id="tr-result-panel" role="tabpanel" aria-labelledby="tr-' + state.tab + '-tab">' + body + '</div></section>';
  }
  function inspector(state, vm) {
    const t = vm.task, r = api.resources.find(x => x.id === t.resource), batch = api.batches.find(x => x.id === t.batch);
    const previous = t.predecessor && vm.scenario.tasks.find(x => x.id === t.predecessor);
    const kinds = [['resource', '设备与人员时段'], ['predecessor', '工艺前后序'], ['calendar', '日班工作日历'], ['locked', '固定工序保护']];
    const checks = vm.issues.length ? vm.issues.map(issue => '<li class="bad">' + icon('circle-alert') + '<span>' + esc(issue.message) + '</span></li>').join('') : kinds.map(([, label]) => '<li>' + icon('circle-check') + '<span>' + label + '通过</span></li>').join('');
    const editing = state.editor && state.editor.taskId === t.id;
    const form = editing ? '<form class="tr-editor" id="tr-edit-form"><label>调整设备<select name="resource" aria-label="调整设备">' + api.resources.map(resource => '<option value="' + esc(resource.id) + '" ' + (resource.id === state.editor.resource ? 'selected' : '') + '>' + esc(resource.id + ' · ' + resource.name) + '</option>').join('') + '</select></label><label>调整开工<input name="start" aria-label="调整开工" type="datetime-local" required value="' + esc(state.editor.start) + '"></label><p class="tr-inline-note">本工序时长保持不变；前后序不自动移动。</p><div class="tr-actions"><button type="submit" class="tr-button">' + icon('check') + '保存试调</button>' + button('取消', 'cancel-edit', 'x') + '</div></form>' : button(t.locked ? '固定工序不可调整' : '调整此工序', 'edit', 'square-pen', t.locked ? 'disabled' : '');
    return '<aside class="tr-inspector" aria-label="工序详情与约束"><h2>工序详情</h2><div class="tr-task-head">' + badge(t.locked ? '已固定' : batch.priority, t.locked ? 'ok' : batch.priority === '特急' ? 'danger' : 'notice') + '<h3>' + esc(t.batch) + '</h3><p>' + esc(batch.name) + ' · ' + batch.qty + ' 件</p></div><dl class="tr-facts"><dt>当前工序</dt><dd>' + esc(t.op) + '</dd><dt>安排资源</dt><dd>' + esc(r.id + ' / ' + t.person) + '</dd><dt>预览开工</dt><dd>' + time(t.start) + '</dd><dt>预览完工</dt><dd>' + time(t.end) + '</dd><dt>前置工序</dt><dd>' + (previous ? esc(previous.op) + '<br><small>' + time(previous.end) + ' 完工</small>' : '本样例无前置工序') + '</dd><dt>交付截至</dt><dd>' + time(batch.due) + '</dd></dl>' + form + '<section class="tr-inspector-section" style="margin-top:14px"><div class="tr-section-head"><h3>约束检查</h3>' + badge(vm.issues.length ? vm.issues.length + ' 项冲突' : '已通过', vm.issues.length ? 'danger' : 'ok') + '</div><ul class="tr-checks">' + checks + '</ul></section><section class="tr-inspector-section"><h3>资源时段占用</h3><p>本范围 2 个日班，不代表全厂负荷。</p>' + vm.report.loads.map(load => '<div class="tr-load-row"><div class="tr-load-title"><span>' + esc(load.id) + '</span><small>' + number(load.hours) + ' / ' + load.capacityHours + ' h · ' + number(load.percent) + '%</small></div><div class="tr-load-track"><i style="width:' + Math.min(100, load.percent) + '%"></i></div></div>').join('') + '</section></aside>';
  }
  function render(state, vm) {
    const decision = vm.issues.length ? '存在 ' + vm.issues.length + ' 项冲突，暂不能采用' : vm.isAdopted ? '当前查看的就是正式采用方案' : '预览预计晚交 ' + vm.report.lateCount + ' 批 · 总拖期 ' + number(vm.report.totalDelayHours) + ' h';
    return '<div class="tr-shell' + (state.expanded ? ' tr-fullscreen' : '') + '">' + sidebar()
      + '<div class="tr-main"><header class="tr-header"><strong class="tr-header-title">方案试调</strong><div class="tr-context">' + badge('正式采用 v' + state.version, 'ok') + '<strong>' + esc(state.adopted.name) + '</strong><span>·</span><span>09-08 至 09-09</span></div>'
      + '<div class="tr-header-tools"><a href="index.html?view=analysis">返回原型</a>' + button('深色：' + (state.theme === 'dark' ? '开' : '关'), 'theme', '') + '</div></header>'
      + '<main class="tr-content"><div class="tr-heading"><div><div class="tr-heading-line"><h1>排产方案试调</h1>' + badge('交互样板') + '</div><p class="tr-subtitle">回转壳体单元 · 4 个批次 / 8 道工序 · 对照初始计划 v15</p></div>'
      + '<div class="tr-actions">' + button('导出对比', 'export', 'file-output', vm.issues.length ? 'disabled title="先处理草稿冲突再导出"' : '') + button('重置样板', 'reset', 'history') + '</div></div>'
      + (state.error ? '<div class="tr-error" role="alert">' + esc(state.error) + '</div>' : '') + (state.notice ? '<div class="tr-notice" role="status">' + esc(state.notice) + '</div>' : '')
      + comparison(state, vm) + '<div class="tr-workspace"><div class="tr-workbody">' + timeline(state, vm) + impact(state, vm) + '</div>' + inspector(state, vm) + '</div>'
      + '<div class="tr-decision-bar"><div><strong>' + decision + '</strong><small>正式计划 v' + state.version + ' 保持不变，确认采用后才替换本地示例。</small></div>'
      + '<div class="tr-actions">' + (state.draft ? button('放弃试调', 'discard', 'x') : '') + '<button type="button" class="tr-button primary" data-action="adopt" ' + (vm.issues.length || vm.isAdopted || state.editor ? 'disabled' : '') + '>' + icon('check-check') + '采用此方案</button></div></div>'
      + '<footer class="tr-footer"><span>预置候选与本地试调 · 未调用排产引擎 · 不写入生产计划</span><span>¹ 换型次数为预置示例值；手工试调后不推断。</span></footer></main></div></div>';
  }
  function modal(kind, state, vm) {
    const adoption = kind === 'adopt';
    const delta = adoption ? api.evaluate(vm.scenario, state.adopted) : null;
    return '<div class="tr-modal-layer"><form class="tr-modal" id="tr-confirm-form" role="dialog" aria-modal="true" aria-labelledby="tr-modal-title"><div class="tr-modal-head"><h2 id="tr-modal-title">' + (adoption ? '确认采用方案' : kind === 'reset' ? '重置本地样板' : '放弃试调草稿') + '</h2>' + button('', 'close-modal', 'x', 'aria-label="关闭确认窗口" title="关闭"') + '</div><div class="tr-modal-body">' + (adoption ? '<p>将 <strong>' + esc(vm.scenario.name) + '</strong> 设为本地正式计划 <strong>v' + (state.version + 1) + '</strong>。</p><div class="tr-modal-summary"><div>相对当前正式计划<strong>' + delta.changedOperations + ' 道调整</strong></div><div>采用后预计晚交<strong>' + delta.lateCount + ' 批</strong></div></div><label>确认人<input name="person" required maxlength="40" placeholder="填写确认人"></label><label>采用说明<textarea name="reason" required maxlength="300" placeholder="记录本次取舍与需跟进事项"></textarea></label><p class="tr-inline-note">保留初始基线和采用记录，仅影响本浏览器的样板。</p>' : '<p>' + (kind === 'reset' ? '将清除本样板的草稿和采用记录，恢复初始计划 v15。原有原型和生产数据不受影响。' : '将删除未保留的试调草稿。已采用的计划快照不会改变。') + '</p>') + '<div id="tr-modal-error" class="tr-error" role="alert" hidden></div></div><div class="tr-modal-foot">' + button('取消', 'close-modal', '') + '<button type="submit" class="tr-button primary">' + (adoption ? '确认采用' : '确认') + '</button></div></form></div>';
  }
  window.APSTrialViews = { render, modal, esc, icon, sameTask, timeline, impact, comparison, revealTask, focusTask };
})();
