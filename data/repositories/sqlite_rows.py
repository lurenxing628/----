"""Read SQLite storage classes independently of connection date converters."""


from typing import Any, Dict, Tuple

RAW_TABLE_SELECTS: Dict[str, str] = {
    "Batches": (
        'batch_id, part_no, part_name, quantity, +"due_date" AS "due_date", priority, '
        'ready_status, +"ready_date" AS "ready_date", status, remark, created_at, updated_at'
    ),
    "WorkCalendar": '+"date" AS "date", day_type, efficiency, allow_normal, allow_urgent, remark, periods_json',
}


def raw_table_select_sql(table: str) -> str:
    return 'SELECT ' + RAW_TABLE_SELECTS.get(table, "*") + ' FROM "' + table.replace('"', '""') + '"'


def sql_order(value: Any) -> Tuple[int, Any]:
    """SQLite ORDER BY 的存储类顺序：NULL < 数值 < 文本 < BLOB，同类再比原值。"""
    if value is None:
        return (0, "")
    if type(value) in (int, float):
        return (1, value)
    if isinstance(value, str):
        return (2, value)
    if isinstance(value, (bytes, bytearray)):
        return (3, bytes(value))
    raise TypeError("Unsupported SQLite storage value: " + type(value).__name__)


def raw_projection(table, column_info):
    names = [str(row[1]) for row in column_info]
    if not names:
        raise ValueError("Raw SQLite table has no columns: " + table)
    columns = ["+\"" + name.replace('"', '""') + '\" AS "wb_raw_' + str(index) + '"'
               for index, name in enumerate(names)]
    return names, ",".join(columns)
