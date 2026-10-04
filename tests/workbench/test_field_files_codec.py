"""Ten-column bytes, numeric/null/date preservation, and strict bounds."""

from datetime import datetime
from io import BytesIO

import pytest
from openpyxl import load_workbook

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.execution.field_report_files_codec import HEADERS, decode_reports, encode_reports
from tests.workbench.execution_ledger_support import all_rows
from tests.workbench.field_workspace_support import BASE, _ledger_fixture, success  # noqa: F401
from tests.workbench.field_workspace_support import field_api as _field_api  # noqa: F401


def test_ten_columns_null_zero_and_excel_datetime():
    content = encode_reports([{'report_no': 'BG1', 'batch_id': 'B1', 'operation_label': '1 Turning', 'completed_quantity': 0,
        'actual_start': datetime(2026, 9, 1, 8), 'effective_processing_hours': None}])
    row = decode_reports(content)[0]
    assert row['errors'] == []
    assert row['values']['completed_quantity'] == 0 and row['values']['effective_processing_hours'] is None
    assert row['values']['actual_start'] == '2026-09-01T08:00:00'
    book = load_workbook(BytesIO(content))
    assert tuple(cell.value for cell in book.active[1]) == HEADERS and book.active.max_column == 10
    book.close()


def test_formula_is_text_on_export_but_formula_input_rejected():
    content = encode_reports([{'remark': '=1+1'}])
    assert decode_reports(content)[0]['values']['remark'] == '=1+1'
    book = load_workbook(BytesIO(content)); book.active['D2'] = '=1+1'
    out = BytesIO(); book.save(out); book.close()
    assert decode_reports(out.getvalue())[0]['errors']


def test_capacity_exact_and_extra_column():
    content = encode_reports([{'report_no': 'BG' + str(index)} for index in range(5000)])
    assert len(decode_reports(content)) == 5000
    with pytest.raises(WorkbenchCommandRejected, match='5000'):
        encode_reports([{} for _ in range(5001)])
    book = load_workbook(BytesIO(encode_reports([{}]))); book.active['K2'] = 'hidden extra'
    out = BytesIO(); book.save(out); book.close()
    with pytest.raises(WorkbenchCommandRejected, match='单元格超出表头范围'):
        decode_reports(out.getvalue())


def test_invalid_date_and_boolean_remain_errors():
    content = encode_reports([{'actual_start': '2026-02-30T10:00', 'completed_quantity': True}])
    assert len(decode_reports(content)[0]['errors']) == 2


def test_merged_cells_are_rejected_not_normalized():
    book = load_workbook(BytesIO(encode_reports([{'report_no': 'BG'}])))
    book.active.merge_cells('D2:E2')
    output = BytesIO(); book.save(output); book.close()
    with pytest.raises(WorkbenchCommandRejected, match='合并'):
        decode_reports(output.getvalue())


def test_seconds_are_kept_like_page_reports_but_subsecond_is_rejected():
    # 页面新增报工默认填带秒的当前时间；导出和分次报工模板原样带出秒，回导要认。
    content = encode_reports([{'actual_start': '2026-09-09T08:00:15', 'actual_end': datetime(2026, 9, 9, 10, 0, 45)}])
    row = decode_reports(content)[0]
    assert row['errors'] == []
    assert (row['values']['actual_start'], row['values']['actual_end']) == ('2026-09-09T08:00:15', '2026-09-09T10:00:45')
    for value in ('2026-09-09T08:00:15.5', datetime(2026, 9, 9, 8, 0, 15, 500000)):
        assert [error['field'] for error in decode_reports(encode_reports([{'actual_start': value}]))[0]['errors']] == ['actual_start']


@pytest.mark.parametrize('hours,text', [(5 / 3, '1.6666666666666667'), (0.1 + 0.2, '0.30000000000000004'),
                                        (1e-07, '0.0000001'), (7.0, '7')])
def test_quantity_and_hours_are_exact_text_cells_that_decode_back(hours, text):
    content = encode_reports([{'completed_quantity': 12, 'effective_processing_hours': hours}])
    book = load_workbook(BytesIO(content))
    cells = [(cell.value, cell.data_type, cell.number_format) for cell in (book.active['D2'], book.active['G2'])]
    book.close()
    assert cells == [('12', 's', '@'), (text, 's', '@')]
    values = decode_reports(content)[0]['values']
    assert values['completed_quantity'] == 12 and values['effective_processing_hours'] == hours


def test_page_report_with_seconds_and_long_hours_reimports_unchanged(field_api):
    api, case = field_api, field_api.case
    case.plan(2, [case.op_id])
    case.command('create', case.task(2, case.op_id), case.values(
        1, actual_start='2026-09-09T08:00:15', actual_end='2026-09-09T09:40:15', effective_processing_hours=5 / 3))
    reading = api.read()
    exported = api.client.get(BASE + '/files/export', query_string={
        **reading['data']['scope'], 'snapshot_ref': reading['meta']['snapshot_ref'], 'page': 1, 'size': 50})
    assert exported.status_code == 200, exported.get_data(as_text=True)
    before = all_rows(case.conn)
    preview = success(api.upload(exported.data))['data']
    assert preview['can_confirm'] and preview['summary']['unchanged'] == 1, preview['rows']
    assert all_rows(case.conn) == before
