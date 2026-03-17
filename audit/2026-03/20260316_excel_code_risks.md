# Excel 导入代码层已知风险备忘

> 本文件在"Excel 导入说明书细化"改动中登记，仅记录发现的代码层风险，不包含修复。后续单独处理。

---

## R1 - 批次数量静默截断

**位置**：`core/services/common/excel_validators.py` 第 115 行

```python
q = int(qty)
```

**问题**：`int(100.5)` 在 Python 中返回 `100`，不抛异常。如果 openpyxl 返回 float 100.5（例如用户在数字格式单元格里填了 100.5），数量会被静默截断为 100。

**建议**：改为使用 `core/services/scheduler/number_utils.py` 中的 `parse_finite_int`，该函数会对非整数值（误差 > 1e-9）报错。

---

## R2 - yes/no 宽窄口径不一致

**位置**：
- 窄口径：`core/services/common/enum_normalizers.py` → `normalize_yesno_narrow`（日历的 允许普通件/允许急件）
- 宽口径：`core/services/personnel/operator_machine_normalizers.py` → `normalize_yes_no_optional`（人员关联的 主操设备）

**问题**：
- 日历的"允许普通件/允许急件"只接受 `yes/no/y/n/是/否`，不接受 `true/1/on`
- 人员关联的"主操设备"接受 `yes/no/true/false/1/0/on/off/是/否/主操/非主操/主/非主`

用户在不同模板中使用相同的填法（如 `1`/`0`），一个能导入一个不能，容易困惑。

**建议**：后续统一为宽口径，或在窄口径的错误提示中明确列出支持的值。

---

## R3 - 模板下载无格式/验证

**位置**：`core/services/common/excel_templates.py` → `_write_xlsx` 函数

```python
ws.append(list(headers))
for r in sample_rows:
    ws.append(list(r))
```

**问题**：所有模板下载时均未设置：
- 单元格 `number_format`（所有列都是 General 格式）
- `DataValidation`（无下拉选项）
- 列宽

用户拿到的是全 General 格式的空白模板，ID 列的前导零容易丢失。

**建议**：后续为 ID/编号列设置 `number_format = '@'`（文本格式），为枚举列添加 `DataValidation` 下拉，并设置合理列宽。
