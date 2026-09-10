"""Batch XLSX uses the existing eight-column template, without advanced switches."""

TEMPLATE_FILENAME = "批次信息.xlsx"
HEADERS = ("批次号", "图号", "数量", "交期", "优先级", "齐套", "齐套日期", "备注")
COLUMNS = ("business_code", "part_no", "quantity", "due_date", "priority", "ready_status", "ready_date", "remark")
HEADER_FIELDS = dict(zip(HEADERS, COLUMNS))
MAX_ROWS = 5000
MAX_BYTES = 10 * 1024 * 1024
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
