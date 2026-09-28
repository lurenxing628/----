'use strict';
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
function fromCsv(text) {
  const python=process.env.WIN7_HOST_PYTHON;assert(python);
  return execFileSync(python,['-B','-c',
    'import csv,io,sys,openpyxl\nw=openpyxl.Workbook()\nrows=list(csv.reader(io.StringIO(sys.stdin.buffer.read().decode("utf-8-sig"))))\n'
    + 'numeric={"stock_qty","default_days","default_hours","库存数量","可排工时（小时）","效率（%）"}\n'
    + 'for number,row in enumerate(rows):\n'
    + ' if number:\n'
    + '  row=[float(value) if rows[0][i] in numeric and value not in ("", "\\\\N") else value for i,value in enumerate(row)]\n'
    + ' w.active.append(row)\nb=io.BytesIO();w.save(b);sys.stdout.buffer.write(b.getvalue())'],
    {input:Buffer.from(text),maxBuffer:32*1024*1024});
}
module.exports={fromCsv};
