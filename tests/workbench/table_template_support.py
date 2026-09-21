"""12 张导入表模板与导出文件的共同结构：第一张数据表，第二张固定叫「填写说明」。

这里只做结构断言，不复述说明文字——文字的唯一来源是各家族的 table_descriptor，
由 tests/workbench/test_table_descriptors.py 逐张校验协议。
"""

from core.models.workbench_table_descriptor import INSTRUCTION_SHEET, instruction_rows


def _norm(values):
    """Excel 读回来的空格子是 None，生成器给的是空字符串，比之前先抹平这一层。"""
    values = ["" if value is None else value for value in values]
    while values and values[-1] == "":
        values.pop()
    return values


def sheet_rows(wb, name):
    return [_norm([cell.value for cell in cells]) for cells in wb[name].iter_rows()]


def check_instruction_sheet(wb, descriptor):
    """第二张表必须在，而且逐行就是生成器给的内容，不允许各家族自己另写一份。"""
    assert wb.sheetnames == [descriptor["sheet_name"], INSTRUCTION_SHEET], wb.sheetnames
    assert sheet_rows(wb, INSTRUCTION_SHEET) == [_norm(list(row)) for row in instruction_rows(descriptor)]


def check_data_sheet_only(wb, descriptor):
    """CSV 之外的结构检查：数据表在第一张，枚举列该有下拉。"""
    check_instruction_sheet(wb, descriptor)
    data = wb[descriptor["sheet_name"]]
    ranges = {str(rule.sqref)[0] for rule in data.data_validations.dataValidation}
    return data, ranges
