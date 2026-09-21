"""报工记录文件的列目录。两种格式版本：旧的 10 列，带任务编号的 13 列。

和其余 11 张表一样，列目录放在 models 里，字节层只管读写。
"""

from core.models.workbench_command import WorkbenchCommandRejected

HEADERS = ('报工编号', '批次号', '工序', '本次完成数量', '实际开工', '本次实际完工',
           '有效加工工时(h)', '实际设备', '实际人员', '备注')
FIELDS = ('report_no', 'batch_id', 'operation_label', 'completed_quantity', 'actual_start', 'actual_end',
          'effective_processing_hours', 'machine_label', 'operator_label', 'remark')
TASK_HEADERS = HEADERS + ('任务编号', '工序范围', '单件编号')
TASK_FIELDS = FIELDS + ('task_ref', 'operation_scope', 'piece_id')
ROW_LIMIT = 5000
_VALUE_HINTS = {
    'report_no': '系统预填的报工编号，请原样保留',
    'batch_id': '批次号，例如 B001',
    'operation_label': '工序，例如 10 车削',
    'completed_quantity': '本次完成数量，填数字；确实是零就填 0，没做就留空',
    'actual_start': '实际开工时刻，填成 2026-09-13 08:30',
    'actual_end': '本次实际完工时刻，填成 2026-09-13 16:30',
    'effective_processing_hours': '有效加工工时，单位小时，填数字',
    'machine_label': '实际设备，按现场核对后填，不要照抄计划',
    'operator_label': '实际人员，按现场核对后填，不要照抄计划',
    'remark': '随便写',
    'task_ref': '系统预填的任务编号，请原样保留，不用手抄',
    'operation_scope': '系统预填的工序范围，请原样保留',
    'piece_id': '工序范围是单件时必须和预填值一致；共同工序必须留空',
}
_ERROR_HINTS = {
    'report_no': '改动了预填的编号',
    'batch_id': '留空，或者这个批次号在系统里找不到',
    'operation_label': '留空，或者这道工序在这个批次里找不到；重名分不清也会被拒绝',
    'completed_quantity': '不是数字、填了「是/否」、或者填了公式',
    'actual_start': '不是时刻，或者只填了日期没填时分',
    'actual_end': '不是时刻，或者早于实际开工',
    'effective_processing_hours': '不是数字，或者填了「是/否」',
    'machine_label': '这台设备在系统里找不到',
    'operator_label': '这个人在系统里找不到',
    'remark': '填了公式或 Excel 的错误值',
    'task_ref': '改动了预填的任务编号',
    'operation_scope': '改动了预填的工序范围',
    'piece_id': '单件工序留空，或者共同工序填了值，又或者和预填值对不上',
}
_GENERAL_RULES = (
    '一次最多导入 ' + str(ROW_LIMIT) + ' 行；预检只看不保存。',
    '本次完成数量和有效加工工时都没填的行不算报工；确实是零请填 0，不要留空。',
    '报工编号请保留；任务编号、工序范围和单件编号由当前范围预填，不要改，也不用手抄。',
    '工序范围是单件时，单件编号必须和预填值一致；共同工序的单件编号必须留空。',
    '原来的 10 列格式只支持批次和工序都唯一的情况，重名分不清会被拒绝。',
    '实际设备和人员要按现场核对后填，不能拿计划里的当实际。',
    '重复导入只补空着的项；要改已经填过的内容请走更正并写明原因。',
    '时间填成 2026-09-13 08:30 这样的年月日加时分。',
    '实际甘特里的目标数量按报工统计；计划应做数量、计划批次数量和依据另外列出，不知道就留空。',
)
_SAMPLE_ROWS = (
    ('R-0001', 'B001', '10 车削', '20', '2026-09-13 08:30', '2026-09-13 12:00', '3.5', 'M001', 'OP001', ''),
    ('R-0002', 'B001', '20 钻孔', '0', '', '', '', '', '', '当天未开工'),
)
_TASK_SAMPLE_EXTRA = (('T-0001', '单件', 'P-0001'), ('T-0002', '共同', ''))


def table_descriptor(format_version=1):
    """模板与填写说明生成器的唯一入口，12 张表统一形状。

    两个版本同名同表，只是列数不同；文件名和说明表标题都按「报工记录」走，
    要分清是哪一版看列数，总表会在同名时自动把列数标出来。
    """
    if format_version not in (1, 2):
        raise WorkbenchCommandRejected('invalid_input', '这个报工文件的格式版本不支持。', 422)
    headers, fields = (HEADERS, FIELDS) if format_version == 1 else (TASK_HEADERS, TASK_FIELDS)
    columns = [{
        'key': field,
        'label': headers[index],
        # 一行至少要有一项实际数据，单看某一列都不是必填，所以这里不给必填标记。
        'required': False,
        'readonly': False,
        'value_hint': _VALUE_HINTS[field],
        'error_hint': _ERROR_HINTS[field],
        'enum': None,
        'nullable': False,
    } for index, field in enumerate(fields)]
    samples = _SAMPLE_ROWS if format_version == 1 else tuple(
        row + extra for row, extra in zip(_SAMPLE_ROWS, _TASK_SAMPLE_EXTRA))
    return {
        'table_id': 'field_report_v' + str(format_version),
        'display_name': '报工记录',
        'sheet_name': '报工记录',
        'file_stem': '报工记录',
        'columns': columns,
        'general_rules': _GENERAL_RULES,
        'sample_rows': samples,
        'row_limit': ROW_LIMIT,
    }
