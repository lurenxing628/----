(function () {
 "use strict";
function createPartialImportTools({ XLSX, tasks, validate, clock, isOperationComplete }) {
  const headers = ['报工编号', '批次号', '工序', '本次完成数量', '实际开工', '本次实际完工', '有效加工工时(h)', '实际设备', '实际人员', '备注'];
  const actualFields = ['qty', 'start', 'end', 'hours'];
  const factFields = actualFields.concat(['machine', 'person']);
  const copy = value => JSON.parse(JSON.stringify(value));
  const empty = value => value == null || (typeof value === 'string' && value.trim() === '');
  const complete = record => actualFields.every(key => !empty(record[key]));
  const scope = task => JSON.stringify([task.batch, task.op]);
  const fail = message => { throw new Error(message); };
  const reportCode = record => {
    if (!empty(record.reportNo)) return String(record.reportNo).trim();
    const seed = /^r(\d+)$/.exec(record.id);
    return seed ? 'BG-20260907-' + seed[1].padStart(4, '0') : '';
  };

  function currentTime() {
    const value = clock();
    if (typeof value !== 'number' || !Number.isFinite(value) || !Number.isFinite(new Date(value).getTime())) {
      fail('示例时钟无效。');
    }
    return value;
  }

  function codeAllocator(snapshot, now) {
    const used = new Set(snapshot.flatMap(task => task.reports.map(reportCode)).filter(Boolean));
    const prefix = 'BG-' + new Date(now).toISOString().slice(0, 10).replace(/-/g, '') + '-';
    let next = 1;
    return {
      reserve(code) { if (code) used.add(code); },
      next() {
        let code;
        do { code = prefix + String(next++).padStart(4, '0'); } while (used.has(code));
        used.add(code);
        return code;
      }
    };
  }

  function buildTemplate() {
    const allocate = codeAllocator(tasks, currentTime());
    const rows = [headers.slice()];
    tasks.filter(task => !isOperationComplete(task)).forEach(task => {
      const pending = task.reports.filter(record => !complete(record));
      (pending.length ? pending : [null]).forEach(record => {
        const known = record || {};
        rows.push([record && reportCode(record) || allocate.next(), task.batch, task.op,
          known.qty == null ? '' : known.qty, known.start || '', known.end || '',
          known.hours == null ? '' : known.hours, known.machine || task.machine,
          known.person || task.person, known.remark || '']);
      });
    });
    const descriptions = [
      '报工的唯一编号；补录保留原编号，重复导入不会累计数量。',
      '必须与当前任务批次号完全一致。',
      '必须与当前任务工序完全一致；以批次号和工序共同定位。',
      '本次新增完成件数，非负整数；不是累计数量，未知留空。',
      '实际发生时间；YYYY-MM-DD HH:mm 或 YYYY-MM-DDTHH:mm[:00]，也接受 Excel 日期时间单元格。',
      '本次作业实际结束时间，格式同实际开工；不是计划时间或整道工序计划完工。',
      '本次有效加工小时数，非负数；未知留空，不从计划或起止时间自动推算。',
      '实际使用设备；预填值须按现场核实。',
      '实际作业人员；预填值须按现场核实。',
      '本次作业备注；补录时可填写补录说明。'
    ];
    const help = [['填写说明（本页不导入）', '列含义与格式'],
      ['导入范围', '只读取第一张“报工记录”；最多 5000 行数据。不要把示例留在实际导入页。'],
      ['空模板', '只有预填参考信息或未变化的已知实际开工时跳过，不生成报工。'],
      ['实际数据', '数量、时间和工时必须来自实际记录；本模板不使用计划推算实际。'],
      ['工序完工', '累计数量达到应做数量且实际记录校验通过后，自动标记本工序完工，无需另填完工标志。'],
      ...headers.map((header, index) => [header, descriptions[index]]), [],
      ['示例（仅说明，不属于实际导入数据）'], headers.slice(),
      ['SAMPLE-001', '示例批次-非当前任务', '30 精加工', 3, '2026-09-07 08:00', '2026-09-07 10:00', 1.5, '示例设备', '示例人员', '部分完成'],
      ['SAMPLE-002', '示例批次-非当前任务', '30 精加工', 2, '2026-09-07T10:30', '2026-09-07T12:00', 1, '示例设备', '示例人员', '报齐剩余件数，自动完工']];
    const workbook = XLSX.utils.book_new();
    const sheet = XLSX.utils.aoa_to_sheet(rows);
    sheet['!cols'] = [25, 20, 18, 18, 23, 23, 23, 18, 18, 45].map(wch => ({ wch }));
    XLSX.utils.book_append_sheet(workbook, sheet, '报工记录');
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet(help), '填写说明与示例');
    return workbook;
  }

  function cellAt(sheet, row, column) {
    const dense = sheet['!data'] || (Array.isArray(sheet) ? sheet : null);
    return dense ? (dense[row] || [])[column] : sheet[XLSX.utils.encode_cell({ r: row, c: column })];
  }

  function cellValue(cell, name) {
    if (!cell) return '';
    if ((cell.f != null || cell.F != null) && (cell.v == null || cell.t === 'z')) {
      fail(name + '含没有缓存结果的公式，请先在 Excel 中计算并保存。');
    }
    if (cell.t === 'e') fail(name + '含 Excel 错误值。');
    if (cell.t === 'b' || typeof cell.v === 'boolean') fail(name + '不能是布尔值。');
    if (cell.t === 'd' || cell.v instanceof Date) fail(name + '请使用文本或 Excel 数值日期，不要转为 JavaScript Date。');
    return cell.v == null ? '' : cell.v;
  }

  function checkCellBounds(sheet, lastRow) {
    const populated = cell => cell && (!empty(cell.v) || cell.f != null || cell.F != null || cell.t === 'e');
    const dense = sheet['!data'] || (Array.isArray(sheet) ? sheet : null);
    if (dense) {
      Object.keys(dense).filter(key => /^\d+$/.test(key)).forEach(row => {
        Object.keys(dense[row] || {}).filter(key => /^\d+$/.test(key)).forEach(column => {
          if ((Number(row) >= lastRow || Number(column) >= headers.length) && populated(dense[row][column])) {
            fail('存在超出声明范围的数据单元格，不能截断导入。');
          }
        });
      });
      return;
    }
    Object.keys(sheet).filter(key => key[0] !== '!').forEach(address => {
      if (!populated(sheet[address])) return;
      const match = /^([A-J])([1-9]\d{0,3})$/.exec(address);
      if (!match || Number(match[2]) > lastRow) fail('数据单元格超出声明范围：' + address);
    });
  }

  function checkedSheet(workbook) {
    const name = workbook && workbook.SheetNames && workbook.SheetNames[0];
    const sheet = name && workbook.Sheets && workbook.Sheets[name];
    if (!sheet) fail('缺少第一张工作表。');
    // Bound both axes before SheetJS expands a range or allocates row arrays.
    const ref = sheet['!ref'];
    const match = typeof ref === 'string' && /^A1(?::([A-Z]{1,3})([1-9]\d{0,6}))?$/.exec(ref);
    if (!match) fail('工作表范围无效，表头必须从 A1 开始。');
    const lastRow = match[2] ? Number(match[2]) : 1;
    if (lastRow > 5001) fail('最多允许 5000 行数据。');
    if (match[1] !== 'J') fail('表头必须包含且仅包含指定的 10 列，请下载当前模板。');
    if (sheet['!fullref'] && sheet['!fullref'] !== ref) fail('工作表被截断，不能只导入部分数据。');
    if (sheet['!merges'] && sheet['!merges'].length) fail('导入表不能包含合并单元格。');
    checkCellBounds(sheet, lastRow);
    const range = XLSX.utils.decode_range(ref);
    const columns = headers.map(() => -1);
    const seen = new Set();
    for (let column = 0; column < headers.length; column++) {
      const value = cellValue(cellAt(sheet, 0, column), '表头');
      if (typeof value !== 'string' || !headers.includes(value.trim())) fail('表头缺失或含未知列：' + String(value));
      const header = value.trim();
      if (seen.has(header)) fail('表头重复：' + header);
      seen.add(header);
      columns[headers.indexOf(header)] = column;
    }
    return { sheet, range, columns };
  }

  function text(value, name) {
    if (empty(value)) return '';
    if (typeof value !== 'string') fail(name + '必须是文本。');
    return value.trim();
  }

  function numeric(value, name, integer) {
    if (empty(value)) return null;
    if (typeof value !== 'number' && (typeof value !== 'string' || !/^\d+(?:\.\d+)?$/.test(value.trim()))) {
      fail(name + (integer ? '必须是非负整数。' : '必须是非负数字。'));
    }
    const number = Number(value);
    if (!Number.isFinite(number) || number < 0 || (integer && !Number.isSafeInteger(number))) {
      fail(name + (integer ? '必须是非负安全整数。' : '必须是非负有限数字。'));
    }
    return number;
  }

  function calendarDate(year, month, day, hour, minute, name) {
    const value = String(year).padStart(4, '0') + '-' + String(month).padStart(2, '0') + '-' +
      String(day).padStart(2, '0') + 'T' + String(hour).padStart(2, '0') + ':' + String(minute).padStart(2, '0');
    const date = new Date(value + ':00Z');
    if (year < 1 || year > 9999 || !Number.isFinite(date.getTime()) || date.getUTCFullYear() !== year ||
        date.getUTCMonth() + 1 !== month || date.getUTCDate() !== day || date.getUTCHours() !== hour || date.getUTCMinutes() !== minute) {
      fail(name + '不是有效的日历日期时间。');
    }
    return value;
  }

  function datetime(value, name, date1904) {
    if (empty(value)) return '';
    if (typeof value === 'number') {
      const date = Number.isFinite(value) && XLSX.SSF.parse_date_code(value, { date1904 });
      if (!date) fail(name + '不是有效的 Excel 日期时间。');
      const seconds = date.S + (date.u || 0);
      // Excel's binary day fractions can land just below an exact minute.
      const carry = Math.abs(seconds - 60) < 0.0001;
      if (Math.abs(seconds) >= 0.0001 && !carry) fail(name + '只接受分钟精度，秒必须为 00。');
      const result = calendarDate(date.y, date.m, date.d, date.H, date.M, name);
      return carry ? new Date(Date.parse(result + ':00Z') + 60000).toISOString().slice(0, 16) : result;
    }
    const match = typeof value === 'string' && /^(\d{4})-(\d{2})-(\d{2})(T| )(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(value.trim());
    if (!match || (match[7] != null && (match[4] !== 'T' || match[7] !== '00'))) {
      fail(name + '格式应为 YYYY-MM-DD HH:mm 或 YYYY-MM-DDTHH:mm[:00]。');
    }
    return calendarDate(Number(match[1]), Number(match[2]), Number(match[3]), Number(match[5]), Number(match[6]), name);
  }

  function parseRow(sheet, row, columns, date1904) {
    const cells = columns.map((column, index) => cellValue(cellAt(sheet, row, column), headers[index]));
    return { reportNo: text(cells[0], headers[0]), batch: text(cells[1], headers[1]), op: text(cells[2], headers[2]),
      qty: numeric(cells[3], headers[3], true), start: datetime(cells[4], headers[4], date1904),
      end: datetime(cells[5], headers[5], date1904), hours: numeric(cells[6], headers[6], false),
      machine: text(cells[7], headers[7]), person: text(cells[8], headers[8]),
      remark: text(cells[9], headers[9]) };
  }

  function liveIndex(snapshot) {
    const byScope = new Map(), byCode = new Map(), ids = new Set();
    snapshot.forEach(task => {
      if (byScope.has(scope(task))) fail('当前任务存在重复的批次号与工序：' + task.batch + ' / ' + task.op);
      byScope.set(scope(task), task);
      task.reports.forEach(record => {
        const code = reportCode(record);
        if (ids.has(record.id)) fail('当前记录内部 ID 重复：' + record.id);
        ids.add(record.id);
        if (code && byCode.has(code)) fail('当前记录存在重复报工编号：' + code);
        if (code) byCode.set(code, { task, record });
      });
    });
    return { byScope, byCode, ids };
  }

  function findExisting(task, row, index) {
    const coded = row.reportNo && index.byCode.get(row.reportNo);
    if (coded && coded.task !== task) fail('报工编号已用于其他批次或工序：' + row.reportNo);
    if (coded) return coded.record;
    if (!row.start) return null;
    const matching = task.reports.filter(record => record.start === row.start);
    if (matching.length > 1) fail('同批次、工序和实际开工对应多条记录，无法确定补录目标。');
    return matching[0] || null;
  }

  function propose(task, row, existing, allocate, now) {
    const candidate = existing ? copy(existing) : {};
    factFields.forEach(key => {
      if (existing && !empty(existing[key]) && !empty(row[key]) && existing[key] !== row[key]) {
        fail('报工编号或实际时段与已有事实冲突：' + key + '，不能覆盖已有记录。');
      }
      candidate[key] = empty(row[key]) && existing ? existing[key] : row[key];
    });
    candidate.remark = row.remark || (existing ? existing.remark : '') || '';
    if (existing && complete(existing) && candidate.remark !== (existing.remark || '')) {
      fail('已完成报工的备注不同，请使用明确的更正流程。');
    }
    candidate.reportNo = existing && reportCode(existing) || row.reportNo || allocate.next();
    candidate.id = existing ? existing.id : 'import-' + encodeURIComponent(JSON.stringify([task.batch, task.op, candidate.start, candidate.reportNo]));
    candidate.revision = existing ? (existing.revision || 0) + 1 : 0;
    candidate.recorded = new Date(now).toISOString().slice(0, 16);
    return candidate;
  }

  function applyRow(row, context) {
    const { result, index, allocate, now } = context;
    const hasActual = actualFields.some(key => !empty(row[key]));
    if (!row.batch && !row.op && !row.reportNo && !hasActual) { result.blank++; return; }
    const task = index.byScope.get(scope(row));
    if (!task) fail('找不到唯一的批次与工序：' + row.batch + ' / ' + row.op);
    const existing = findExisting(task, row, index);
    const newActual = actualFields.some(key => !empty(row[key]) && (!existing || row[key] !== existing[key]));
    if (!hasActual || (existing && !complete(existing) && !newActual)) {
      result.blank++;
      return;
    }
    const candidate = propose(task, row, existing, allocate, now);
    const same = existing && factFields.concat(['remark']).every(key => candidate[key] === existing[key]);
    if (existing && complete(existing) && !same) fail('不能覆盖已完成报工。');
    if (same) { result.duplicates++; return; }
    if (isOperationComplete(task)) fail('本工序已完工，不能追加或补录。');
    const error = validate(task, candidate, existing ? existing.id : null, now);
    if (error) fail(error);
    if (existing) {
      result.revisions.push({ batch: task.batch, previous: copy(existing), next: copy(candidate), text: 'Excel 补录报工：' + candidate.reportNo + (row.remark ? '；' + row.remark : '') });
      task.reports[task.reports.indexOf(existing)] = candidate;
      result.supplemented++;
    } else {
      if (index.ids.has(candidate.id)) fail('导入记录 ID 冲突，请核对报工编号。');
      task.reports.push(candidate);
      index.ids.add(candidate.id);
      result.added++;
    }
    task.closed = isOperationComplete(task);
    allocate.reserve(candidate.reportNo);
    index.byCode.set(candidate.reportNo, { task, record: candidate });
  }

  function planImport(workbook) {
    const original = copy(tasks);
    const result = { tasks: copy(original), added: 0, supplemented: 0, duplicates: 0, blank: 0, errors: [], revisions: [] };
    try {
      const { sheet, range, columns } = checkedSheet(workbook);
      const props = workbook.Workbook && workbook.Workbook.WBProps;
      const flag = props && props.date1904;
      if (flag != null && ![true, false, 0, 1, '0', '1', 'true', 'false'].includes(flag)) fail('工作簿 date1904 标志无效。');
      const date1904 = flag === true || flag === 1 || flag === '1' || flag === 'true';
      const now = currentTime(), index = liveIndex(result.tasks), allocate = codeAllocator(result.tasks, now);
      const parsed = [], seen = new Map();
      // blankrows preserves physical Excel row numbers; raw keeps numeric date serials.
      const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, raw: true, defval: null, blankrows: true, range });
      for (let offset = 1; offset < rows.length; offset++) {
        try {
          const row = parseRow(sheet, offset, columns, date1904);
          if (row.reportNo) {
            const previous = seen.get(row.reportNo);
            if (previous && JSON.stringify(previous.data) !== JSON.stringify(row)) {
              fail('报工编号在本文件中重复且数据冲突：' + row.reportNo + '（首次位于第 ' + previous.row + ' 行）。');
            }
            seen.set(row.reportNo, { row: offset + 1, data: row });
            allocate.reserve(row.reportNo);
          }
          parsed.push({ row: offset + 1, data: row });
        } catch (error) { result.errors.push({ row: offset + 1, message: error.message }); }
      }
      parsed.forEach(item => {
        try { applyRow(item.data, { result, index, allocate, now }); }
        catch (error) { result.errors.push({ row: item.row, message: error.message }); }
      });
    } catch (error) { result.errors.push({ row: 1, message: error.message }); }
    if (result.errors.length) {
      result.tasks = original;
      result.added = 0;
      result.supplemented = 0;
      result.revisions = [];
      result.errors.sort((a, b) => a.row - b.row);
    }
    return result;
  }

  return { buildTemplate, planImport };
}

if (typeof module !== 'undefined' && module.exports) module.exports = { createPartialImportTools };

window.APSFieldReports.createImportTools=createPartialImportTools;
})();
