---
doc_type: issue-fix
issue: 2026-05-28-equipment-excel-machine-header-aliases
path: fast-track
fix_date: 2026-05-28
status: completed
severity: P1
tags:
  - equipment
  - excel
  - import
---

# Equipment Excel Machine Header Aliases Fix Note

## 问题

设备信息 Excel 页面说明里写明旧列名 `机器编号`、`机器名称` 也能识别。

实际导入时，后端只按 `设备编号`、`设备名称` 读取。用户如果上传旧表头，会在预览里看到 `“设备编号”不能为空`，页面说明和真实行为不一致。

## 根因

`equipment_excel_machines.py` 在读取 Excel 后，直接用 `设备编号` 做唯一性检查和预览主键。

同类的工种、供应商、人员设备关联已经有旧列名标准化逻辑；设备信息导入链路漏掉了这一步。

## 修复

- 设备信息导入预览阶段先把 `机器编号` 标准化为 `设备编号`，把 `机器名称` 标准化为 `设备名称`。
- 设备信息确认写入阶段再次做同样标准化，保证确认阶段只处理标准列名。
- 如果同一行同时填写标准列和旧列，而且两个值不一致，预览和确认都会拒绝写入，并提示用户保留一个列名或把两个值改成一致。
- 旧表头被识别时，页面提示用户本次会按标准列处理，并建议下载新模板维护。

## 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/test_excel_renamed_column_conflicts.py -q`
- 当前浏览器所连本地服务 `http://127.0.0.1:61731` 重启后，用只包含 `机器编号`、`机器名称`、`状态` 的 Excel 做预览：HTTP 200，页面出现旧列识别提示，不再出现 `“设备编号”不能为空`。

## 结果

- 上传只包含 `机器编号`、`机器名称`、`状态` 的旧设备信息 Excel，可以正常预览并确认写入。
- 新旧设备编号同时存在且值不一致时，系统不会猜测，会拒绝导入并给出清楚提示。
