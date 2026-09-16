"""Public issue vocabulary shared by every capacity projection."""

_MESSAGES = {
    "calendar_invalid": "工作日历或人员班表有误，这部分产能算不出来。请到工作日历核对。",
    "calendar_range_limit": "查询的日期范围太大，班表读不完。请缩小时间范围后重试。",
    "calendar_cell_limit": "设备人员和日期的组合太多，算不完。请缩小时间范围后重试。",
    "calendar_fact_limit": "要读的班表或设备人员记录超过上限。请缩小时间范围后重试。",
    "calendar_window_limit": "班次时长超过 24 小时，这部分产能算不出来。请到工作日历核对班次。",
    "resource_missing": "这条安排关联的设备或人员记录找不到，产能算不出来。请到资料总览核对。",
    "resource_status_unknown": "设备或人员状态无效，请到资料总览核对。",
    "downtime_invalid": "设备停机时间或状态有误，产能算不出来。请到资料总览核对设备停机。",
    "calendar_unavailable": "工作日历产能算不出来；工时和时间冲突还是照常显示。",
    "assignment_source_unknown": "这条安排是自制还是外协分不清，系统不猜设备人员占用。请到基础资料核对工序归属。",
    "assignment_resource_missing": "自制安排没有填设备或人员，确认不了会不会冲突。请到基础资料补齐。",
    "assignment_priority_unknown": "这条安排的优先级读不出来，分不清按普通还是急件的班表算。请到批次管理核对优先级。",
    "assignment_resource_inactive": "这条安排用到了未启用的设备或人员。请改派，或到资料总览把它启用。",
    "assignment_work_type_unknown": "这条安排或设备的工种资料缺失，确认不了工种对不对得上。请到资料总览补齐工种。",
    "assignment_work_type_mismatch": "这条安排的自制工种和设备的工种对不上。请改派设备，或到资料总览核对工种。",
    "assignment_qualification_invalid": "人员的技能或设备授权资料有误，确认不了能不能干这道工序。请到资料总览核对。",
    "assignment_not_authorized": "这个人员没有该设备的操作授权。请改派人员，或到资料总览补授权。",
    "assignment_not_qualified": "这个人员没有登记该自制工种的资格。请改派人员，或到资料总览补资格。",
    "assignment_calendar_unavailable": "无法计算此安排的班表产能，请到工作日历核对。",
    "assignment_outside_calendar": "这条安排有时段落在设备人员的班表外，或者撞上设备停机。请到工作日历和资料总览核对。",
    "assignment_machine_downtime": "这条安排和设备的停机时段重叠。请改期，或到资料总览核对设备停机。",
}


def issue(code, **fields):
    return dict(code=code, message=_MESSAGES[code], **fields)
