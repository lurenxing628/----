// Small real upload fixtures, independent of product serializers.
import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
const require = createRequire(import.meta.url);
const {Workbook, SpreadsheetFile} = await import(pathToFileURL(require.resolve('@oai/artifact-tool')));
const root = process.argv[2];
await fs.mkdir(root + '/uploads', {recursive: true});
async function xlsx(name, rows) {
  const book = Workbook.create(), sheet = book.worksheets.add('Sheet1');
  sheet.getRange('A1:' + String.fromCharCode(64 + rows[0].length) + rows.length).values = rows;
  await (await SpreadsheetFile.exportXlsx(book)).save(root + '/uploads/' + name + '.xlsx');
}
const headers = ['批次号', '图号', '数量', '交期', '优先级', '齐套', '齐套日期', '备注'];
await fs.writeFile(root + '/uploads/recovery-route.csv', '\ufeff图号,名称,工艺路线字符串,备注\r\nAN-RECOVERY,原请求回执验证,10车削,保留原请求\r\n');
for (const state of ['1920-light', '1920-dark', '1392-light', '1392-dark']) {
  await fs.writeFile(root + '/uploads/route-' + state + '.csv', '\ufeff图号,名称,工艺路线字符串,备注\r\n' +
    Array.from({length: 23}, (_, i) => 'AN-FILE-' + state + '-' + String(i + 1).padStart(3, '0') + ',文件导入零件,10车削20检验,原备注保留\r\n').join(''));
  await xlsx('hours-' + state, [['图号', '工序', '换型时间(h)', '单件工时(h)'], ['AN-P-' + state, 10, null, .375]]);
  await xlsx('bad-hours-' + state, [['图号', '工序', '单件工时(h)'], ['AN-P-' + state, 10, -1]]);
}
await xlsx('batch-overwrite', [headers, ...Array.from({length: 43}, (_, i) => ['AN-MULTI-' + String(i + 1).padStart(3, '0'), 'PROC-001', i + 1, '2026-10-20', 'normal', 'yes', null, 'AN import original'])]);
await xlsx('batch-append', [headers, ['AN-MULTI-001', 'PROC-001', 999, '2026-10-21', 'urgent', 'yes', null, 'must be skipped'], ['AN-APPEND-001', 'PROC-001', 2, '2026-10-21', 'normal', 'yes', null, 'appended']]);
await xlsx('batch-replace', [headers, ['AN-REPLACE-001', 'PROC-001', 3, '2026-10-21', 'normal', 'yes', null, 'replace must reject protected history']]);
console.log('AN_UPLOAD_FIXTURES_READY ' + root);
