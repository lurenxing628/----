# 示例：如何调用“APS 开发文档回填”

> 说明：以下是“真实项目常见改动”的调用示例。调用后，默认会**直接回填** `开发文档/`（忽略清单中的文件不读不改），并输出“逐文件检查结果 + 回填摘要 + 未决问题”。

## 示例 1：路由拆分 + 页面文案/参数变更

**用户输入：**
“我把排产模块的路由拆分到了多个文件，并新增了批次筛选参数和一些 flash 文案。请回填开发文档，尤其是接口清单和面板文案。”

**期望行为（Agent）：**
- 读取 `git status`/`git diff`，列出变更文件（例如 `web/routes/scheduler_*.py`、`templates/scheduler/*.html`）。
- 并行 subagent 抽取：
  - 新增/变更 URL、endpoint、query/form 字段、默认值
  - 新增/变更 flash 文案、确认弹窗文案、空数据提示
  - v1/v2 模板映射（如存在 UI 模式）
- 回填到：
  - `开发文档/面板与接口清单.md`（逐页面更新 URL/参数/文案/模板路径/路由文件）
  - `开发文档/系统速查表.md`（同步新增/变更的关键接口与参数默认值）
- 输出：按变更文件逐条写“做了什么→影响章节→验证方式”。

## 示例 2：人员专属日历（OperatorCalendar）+ day_type 口径归一

**用户输入：**
“我新增了人员专属工作日历（OperatorCalendar），并把日历 day_type 的 weekend/holiday 口径统一为 holiday。请对齐开发文档。”

**期望行为（Agent）：**
- 读取变更文件（常见：`schema.sql`、`core/models/calendar.py`、`data/repositories/operator_calendar_repo.py`、`core/services/scheduler/calendar_service.py`、`web/routes/personnel_calendar_pages.py`，以及对应 Excel 路由/模板）。
- 并行 subagent 抽取事实：
  - DB：新增表/索引/字段、兼容迁移口径（weekend→holiday）
  - 服务：个人日历覆盖语义（优先级、回退规则）
  - 页面/Excel：入口 URL、字段、导入/导出模板名、用户提示文案
- 回填到：
  - `开发文档/开发文档.md`（数据模型与日历章节；口径统一说明）
  - `开发文档/系统速查表.md`（术语/枚举、接口清单、模板清单、字段字典）
  - `开发文档/面板与接口清单.md`（人员详情入口、个人日历页面与 Excel 页的 URL/文案）
  - `开发文档/实现计划表.md`（若计划表仍将其标为“后续阶段”，需改为“已落地/已接入”）

## 示例 3：排产入口新增参数（齐套约束/排产窗口）+ 留痕字段扩展

**用户输入：**
“排产入口新增了 enforce_ready（齐套约束开关）和 end_date（排产截止日期），并扩展了 ScheduleHistory 的 result_summary 字段。请把这些改动回填到开发文档。”

**期望行为（Agent）：**
- 读取变更文件（常见：`web/routes/scheduler_run.py`、`core/services/scheduler/schedule_service.py`、`core/services/scheduler/config_service.py`、`templates/scheduler/*.html`、`core/services/common/excel_audit.py`）。
- 核对并回填：
  - `开发文档/面板与接口清单.md`：排产/模拟排产表单字段、默认值、flash 文案（成功/失败/未选中）
  - `开发文档/系统速查表.md`：排产相关接口参数与默认值、ScheduleConfig 新增键（如 `enforce_ready_default`）
  - `开发文档/开发文档.md`：排产增强能力与开关（10.5.x）、留痕字段规范（12.2.x）
- 输出：列出“用户可感知行为变化”（启用齐套约束时未齐套如何被拒绝；截止窗口如何影响排产结果）。

