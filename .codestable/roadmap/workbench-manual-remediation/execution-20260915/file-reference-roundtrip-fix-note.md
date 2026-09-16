# 导出清单回导：参考列契约修复

## 现场问题与根因

5001 手动验收：新增 `RESTORE-0915-CHECK`，名称“隔离恢复校验物料”、单位“件”、库存 7；导出 `物料清单.xlsx`，恢复到新增前备份，再上传刚导出的原文件。预检因导出列“创建时间”拒绝新增。

现场原文件：`/Users/lurenxing/Downloads/物料清单.xlsx`，5308 字节，SHA-256 `94f6904cc115a2ed930cb5fd9ca996c9213b2512d4d3ce97ba084127a5f648c7`（主代理现场记录，本子任务未重写文件）。

代码查明三处同类契约冲突：

- `material_files.py`：`_check_created_at` 要求文件创建时间与现存行相同，新记录必拒。
- `resource_file_input.py`：工种、设备、人员、供应商的已声明只读列均作为现存事实断言，导出清单内任一非空只读值都会阻止新增。
- `batch_file_codec.py`：导出九列（含状态），导入只接受八列，原导出文件在表头校验即被拒。

## 修改契约

- 仅接受现有文件 schema 已声明的参考列；未知列、缺失必要列、重复列、公式和错误单元格规则保持拒绝。
- 物料创建时间、资源原始只读列只供阅读，均不进入可写 DTO；时间由数据库生成，现有时间或原始关系不被覆盖。
- 物料/资源预检返回 `reference_fields`，共享预检界面按中文列名列出本次不会导入的内容。涉及原设备授权时明确提示在人员详情设置，不增加复选框。
- 批次兼容原八列模板及九列系统清单；“状态”不进入导入字段，预检给出明确说明，已有批次保持当前状态、新批次从待排开始。
- 原子确认、绑定原文件指纹、并发资料变化检查、幂等回执继续执行。已存在记录的完整文件回导仍可判为不变。
- 工种归属、供应商周期、有效关联等可编辑字段继续按原业务规则检查；此修复不使 Excel 变成数据库备份，也不通过参考列恢复设备权限。

## 产品文件

- `core/services/workbench/material_files.py`
- `core/services/workbench/material_file_codec.py`
- `web/routes/workbench/material_actions_context.py`
- `core/services/workbench/resource_file_input.py`
- `core/services/workbench/resource_files.py`
- `core/models/workbench_resource_file.py`
- `core/services/workbench/batch_file_codec.py`
- `frontend/workbench/app/ResourceMaterialContract.js`
- `frontend/workbench/app/ResourceFileContract.js`
- `frontend/workbench/app/ResourceMaterialPreview.jsx`

## 定向验证

新增 `tests/workbench/test_file_reference_roundtrip.py`，20 个参数化场景：物料与五类资源分 CSV/XLSX 执行“备份前无该记录 → 新增 → 导出 → 回导旧备份”；确认时间不被回填旧值、参考列不进入写 DTO，原设备权限完全不变。另覆盖实际 Flask 预检字段、批次实际导出回导、伪装“已完成”的参考状态不影响新批次、未知列与直接写系统字段拒绝。

按新契约调整三个既有测试文件中的参考列语义/公开行字段断言；没有删除原子性、并发、权限、旧值保留等断言。

执行：

```text
.venv/bin/python -m pytest -q tests/workbench/test_file_reference_roundtrip.py tests/workbench/test_material_files.py tests/workbench/test_resource_files.py tests/workbench/test_resource_file_codec.py tests/workbench/test_batch_files.py tests/workbench/test_resource_file_api.py tests/workbench/test_material_actions_api.py -k 'not 10000 and not 2000 and not snapshot_while and not one_pass'
282 passed, 21 deselected in 37.37s
```

两个共享 JS 契约 `node --check` 通过；修改范围 `git diff --check` 通过。首轮 8 个失败为新增测试误判既有空 `relationships` DTO 和 HTTP 422 状态，修正测试后以上验证通过，未为适应断言改产品行为。

本子任务没有启动浏览器、构建、服务或写入任何业务数据库。测试只写 pytest 临时库及内存备份；未跑全门禁或整仓测试。最新源码的真实 UI 回导由主代理统一构建并重启 5001 后完成。

新测试文件需加入测试登记，由主代理统一安排。当前工作区有大量先前改动，本记录不构成 clean-worktree proof。

## 回导时间复核与预检显示

主代理已通过真实 UI 回导原 `物料清单.xlsx`：新增 1、拒绝 0，参考列说明正确，确认并刷新后库存为 7，现场记录见 `manual-run-field.md`。回导后的数据库 `created_at=2026-09-15 14:27:42` 是 UTC，按既有导出转换对应北京时间 `22:27:42`，比原文件 `22:10:51` 晚 16 分 51 秒，确为本次新建，未倒退。`schema.sql:484` 采用 `CURRENT_TIMESTAMP`；普通 UI 与文件导入复用同一 `WorkbenchMaterialService.apply → MaterialRepository.create`，没有生成时间分叉。本次复核未改时间存储、原文件或已写事实。

随后主代理在批删预检中真实确认显示问题：23:16 新增的物料被显示为 15:16，且无 UTC 标记。定向修复 `web/routes/workbench/material_actions_context.py:128–129`，只把公开 `before` 副本的创建时间按现有 `messages.stored_utc_text` 转为北京时间，`after` 从该副本复制；服务器原始预检、事实指纹及数据库继续保留 UTC。没有修改前端或其他时间表面。

在既有 `test_material_actions_api.py` 增加 8 个参数化场景，覆盖批删与导入的同日、跨日、NULL 创建时间、与实际 CSV 导出一致、公开转换不改变原始预检及整库数据、确认后保留原始 UTC，以及坏存储时间明确报错。与现有相关原子确认/并发/私有字段保护用例一起定向执行：`19 passed, 39 deselected in 8.81s`；Ruff 和差异检查通过。没有构建、启动浏览器、写业务库或运行全门禁；主代理重启服务后验证 UI。
