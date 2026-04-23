# web层与web_new_test深度审查
- Date: 2026-04-02
- Overview: 对web/和web_new_test/目录进行全面深度审查，聚焦BUG、静默回退和不必要兜底
- Status: completed
- Overall decision: conditionally_accepted

## Review Scope
# Web 层与 web_new_test 深度审查

**日期**: 2026-04-02  
**范围**: `web/` 全部模块 + `web_new_test/`  
**审查目标**: 
1. 真实 BUG（逻辑错误、数据丢失、安全漏洞）
2. 会隐藏 BUG 的静默回退（bare except、默认值吞异常）
3. 不必要的兜底代码

**审查方法**: 三轮审查
- 第一轮：bootstrap 层（factory/launcher/security/paths/plugins/runtime_probe/static_versioning）
- 第二轮：routes 层全部路由模块
- 第三轮：viewmodels 层 + error_handlers + ui_mode + web_new_test

## Review Summary
<!-- LIMCODE_REVIEW_SUMMARY_START -->
- Current status: completed
- Reviewed modules: web/bootstrap/, web/error_handlers.py, web/ui_mode.py, web/routes/normalizers.py, web/routes/pagination.py, web/routes/excel_utils.py, web/routes/dashboard.py, web/routes/ (全部43个文件), web/viewmodels/ (全13个文件), web_new_test/ (全部9个文件), web/bootstrap/ (8文件), web/routes/ (43文件), web/viewmodels/ (13文件), web_new_test/ (9文件)
- Current progress: 3 milestones recorded; latest: M3
- Total milestones: 3
- Completed milestones: 3
- Total findings: 11
- Findings by severity: high 0 / medium 4 / low 7
- Latest conclusion: ## 审查结论 对 `web/` 全部 84 个 Python 文件和 `web_new_test/` 全部 9 个文件进行了三轮深度审查。 ### 整体质量评价 **代码质量较高**，未发现严重 BUG（High severity 为 0）。架构分层清晰，模块拆分合理： - Bootstrap 层对 Win7/PyInstaller 场景有细致考虑，运行时锁/契约文件/进程管理实现稳健 - Routes 层的 Excel 导入采用 preview-confirm 双阶段 + SHA256 baseline 签名防并发方案，设计严谨 - V1/V2 UI 模式切换通过 Jinja overlay env + cookie + DB 三级配置，渐进发布策略合理 - `safe_url_for` + `<details>` 排查信息的降级模式，是很好的生产级可用性实践 ### 发现汇总（11 条） | 等级 | 数量 | 核心模式 | |------|------|----------| | Medium | 4 | 静默回退无可观测信号、批量操作吞异常 | | Low | 7 | 配置回退无日志、不必要的兜底、风格不一致 | **最需优先修复的 4 个 Medium 问题**： 1. **F001** - `before_request` 中维护任务持续失败无冷却机制 → 建议增加失败计数器 2. **F002** - V2 Jinja env 回退 V1 无日志 → 加一行 warning 3. **F005** - 停机ID/排产摘要读取失败静默返回空 → 加 warning 日志 4. **F006** - 批量 set_status/delete 吞掉异常信息 → 加 `logger.exception` ### 无需修复的合理设计 - `safe_url_for` 吞 BuildError → 正确的渐进发布策略 - `scheduler_analysis_vm` 的 safe_float/safe_int → 展示层容错优先于报错 - 数据库恢复流程的 maintenance_window + ensure_schema → 事务安全设计合理 - shutdown endpoint 的 `secrets.compare_digest` + 127.0.0.1 限制 → 安全措施到位
- Recommended next action: 优先修复 4 个 Medium 问题（F001/F002/F005/F006），均为增加日志可观测性，改动量小且风险极低。Low 问题可在后续迭代中逐步处理。
- Overall decision: conditionally_accepted
<!-- LIMCODE_REVIEW_SUMMARY_END -->

## Review Findings
<!-- LIMCODE_REVIEW_FINDINGS_START -->
- [medium] performance: before_request 中维护任务持续失败被静默吞掉
  - ID: F001
  - Description: factory.py L293-294: SystemMaintenanceService.run_if_due() 在每个请求的 before_request 中执行，任何异常被 except Exception 吞掉仅打日志。如果维护任务持续失败（如磁盘满），每个请求都会尝试执行并失败，造成性能开销且用户无感知。
  - Evidence Files:
    - `web/bootstrap/factory.py`
  - Related Milestones: M1
  - Recommendation: 增加失败计数器或冷却机制，连续失败N次后暂停一段时间不再尝试。

- [medium] maintainability: V2 Jinja env为None时静默回退V1无可观测信号
  - ID: F002
  - Description: ui_mode.py L306: render_ui_template 中，当 mode=='v2' 但 V2 Jinja env 为 None 时，静默回退到 V1 env。用户以为切到了V2，实际渲染V1，没有日志/提示。
  - Evidence Files:
    - `web/ui_mode.py`
  - Related Milestones: M1
  - Recommendation: 在回退时至少记录一条 warning 日志，标明 V2 env 不可用已回退 V1。

- [low] javascript: 首页result_summary解析失败静默返回overdue=0
  - ID: F003
  - Description: dashboard.py L37-38: result_summary JSON 解析失败时静默设为 None，overdue_count 将显示 0，用户无感知。
  - Evidence Files:
    - `web/routes/dashboard.py`
  - Related Milestones: M1
  - Recommendation: 解析失败时至少记录warning日志。

- [low] other: hmac.compare_digest 异常时回退普通字符串比较
  - ID: F004
  - Description: excel_utils.py L72-73: hmac.compare_digest 失败时回退到 provided == expected。虽然实际触发概率极低，但设计上不应有此安全降级。
  - Evidence Files:
    - `web/routes/excel_utils.py`
  - Related Milestones: M1
  - Recommendation: 移除 try/except，直接使用 hmac.compare_digest。

- [medium] other: 多处数据读取失败静默返回空值无日志
  - ID: F005
  - Description: equipment_pages.py L61-67, scheduler_batches.py L71-73: _load_active_downtime_machine_ids() 和 latest_history/latest_summary 获取失败时静默返回空集/None。停机ID列表获取失败意味着设备停机状态在列表页不显示，用户无感知。scheduler_batches.py 的 latest_history 解析失败则排产首页丢失最近排产摘要。
  - Evidence Files:
    - `web/routes/equipment_pages.py`
    - `web/routes/scheduler_batches.py`
  - Related Milestones: M2
  - Recommendation: 至少记录 warning 日志，让运维能通过日志发现数据读取异常。

- [medium] other: 批量操作单条失败吞掉异常信息
  - ID: F006
  - Description: equipment_pages.py L297-302, L325-330, personnel_pages.py L207-212, L235-240, scheduler_batches.py L203-208: 批量操作（set_status/delete）中，单条失败被 except Exception 吞掉，仅将ID加入failed列表。异常信息完全丢失，失败原因不可追溯（除了 scheduler_batches.py 的 bulk_copy/bulk_update 正确记录了 logger.exception）。
  - Evidence Files:
    - `web/routes/equipment_pages.py`
    - `web/routes/personnel_pages.py`
    - `web/routes/scheduler_batches.py`
  - Related Milestones: M2
  - Recommendation: 在 except Exception 中增加 current_app.logger.exception 或至少 logger.warning，记录具体失败原因。

- [low] other: holiday_default_efficiency配置读取失败静默回退
  - ID: F007
  - Description: scheduler_excel_calendar.py L124-129: holiday_default_efficiency 配置读取失败时静默回退到0.8，这可能掩盖数据库配置损坏或服务层BUG。类似模式在 scheduler_calendar_pages.py L18-24 也存在。
  - Evidence Files:
    - `web/routes/scheduler_excel_calendar.py`
    - `web/routes/scheduler_calendar_pages.py`
  - Related Milestones: M2
  - Recommendation: 在 except 分支记录 warning 日志标明使用了回退值。

- [low] other: time_range校验异常被静默吞掉
  - ID: F008
  - Description: system_utils.py L99-104: _normalize_time_range 中 start > end 的校验失败时（非 ValidationError 类型），被 except Exception: _ = None 完全吞掉。这意味着如果 strptime 出现意外异常（理论上不应该因为 start_norm 和 end_norm 已经是标准格式），start>end的校验逻辑就不生效。
  - Evidence Files:
    - `web/routes/system_utils.py`
  - Related Milestones: M2
  - Recommendation: 移除多余的 except Exception 分支，因为此处 start_norm/end_norm 已经是标准化后的格式，strptime 不应失败。如果确需兜底，应至少打日志。

- [low] other: 部分服务实例缺少op_logger参数
  - ID: F009
  - Description: process_parts.py L98: SupplierService(g.db) 构造时没有传 op_logger 参数，而同文件其他服务（如 PartService）都传了 op_logger。这虽不是BUG（op_logger 通常是可选参数），但与项目其他代码风格不一致，可能导致供应商相关操作缺少操作日志。同样 process_suppliers.py L29 中 OpTypeService(g.db) 也缺少 op_logger。
  - Evidence Files:
    - `web/routes/process_parts.py`
    - `web/routes/process_suppliers.py`
  - Related Milestones: M2
  - Recommendation: 补充 op_logger=getattr(g, 'op_logger', None) 参数以保持一致性。

- [low] maintainability: 分析页影响层safe_float/safe_int静默回退0可能掩盖数据结构变化
  - ID: F010
  - Description: scheduler_analysis_vm.py 中大量使用 safe_float/safe_int 将任意值非法静默回退为 0。对于一个分析仪表板页面，这意味着如果后端数据结构变化（如字段改名），指标全部显示为0而不是报错，用户可能误认为排产效果很好。这是一个典型的“会隐藏BUG的静默回退”。但考虑到分析页只是展示层，它的容错优先于报错是合理的设计选择，影响度 low。
  - Evidence Files:
    - `web/viewmodels/scheduler_analysis_vm.py`
  - Related Milestones: M3
  - Recommendation: 可保持现状，但建议在 build_trend_rows 中对关键字段缺失时至少记录一次 warning 日志。

- [low] css: CSS :has()伪类兼容性风险
  - ID: F011
  - Description: web_new_test/static/css/style.css L160-167: 使用了 CSS :has() 伪类（.card:not(:has(.card-header)):not(:has(.card-body))）。这个伪类在Chrome 105+才支持，而项目目标环境是Win7+Chrome 109，所以刚好兼容。但如果有其他旧浏览器场景（如内部IE11测试），这些规则会完全失效，导致旧V1模板在V2布局中缺少padding。
  - Evidence Files:
    - `web_new_test/static/css/style.css`
  - Related Milestones: M3
  - Recommendation: 确认目标浏览器范围，如仅Chrome 109+则安全。否则需增加回退规则。
<!-- LIMCODE_REVIEW_FINDINGS_END -->

## Review Milestones
<!-- LIMCODE_REVIEW_MILESTONES_START -->
### M1 · Bootstrap层 + 基础工具模块审查
- Status: completed
- Recorded At: 2026-04-02T06:52:28.462Z
- Reviewed Modules: web/bootstrap/, web/error_handlers.py, web/ui_mode.py, web/routes/normalizers.py, web/routes/pagination.py, web/routes/excel_utils.py, web/routes/dashboard.py
- Summary:
审查了 `web/bootstrap/` 全部8个文件（factory.py, launcher.py, paths.py, plugins.py, runtime_probe.py, security.py, static_versioning.py）以及 `web/error_handlers.py`, `web/ui_mode.py`, `web/routes/normalizers.py`, `web/routes/pagination.py`, `web/routes/excel_utils.py`, `web/routes/dashboard.py`。

**整体评价**: Bootstrap层实现稳健，异常处理层次分明，对Win7/PyInstaller场景有细致考虑。

**发现问题**:

1. **factory.py L293-294 (Medium)**: `SystemMaintenanceService.run_if_due()` 在 `before_request` 中执行，任何异常被 `except Exception` 吞掉仅打日志。如果维护任务持续失败（如磁盘满），每个请求都会尝试执行并失败，造成不必要的性能开销，且用户完全无感知。

2. **ui_mode.py L306 (Medium)**: `render_ui_template` 中，当 `mode == "v2"` 但 V2 Jinja env 为 None 时，静默回退到 V1 env (`app.jinja_env`)。用户以为切到了V2，实际渲染的是V1，没有任何可观测信号（无日志/无提示）。

3. **dashboard.py L37-38 (Low)**: `latest.result_summary` JSON 解析失败时静默设为 None，首页 overdue_count 将显示 0。对用户而言看不到任何错误提示。

4. **excel_utils.py L72-73 (Low)**: `hmac.compare_digest` 失败时回退到普通字符串比较 `provided == expected`。这是安全降级，虽然实际场景中 SHA256 hex 字符串不太可能触发 hmac 异常，但设计上不应有这个回退。
- Conclusion: 审查了 `web/bootstrap/` 全部8个文件（factory.py, launcher.py, paths.py, plugins.py, runtime_probe.py, security.py, static_versioning.py）以及 `web/error_handlers.py`, `web/ui_mode.py`, `web/routes/normalizers.py`, `web/routes/pagination.py`, `web/routes/excel_utils.py`, `web/routes/dashboard.py`。 **整体评价**: Bootstrap层实现稳健，异常处理层次分明，对Win7/PyInstaller场景有细致考虑。 **发现问题**: 1. **factory.py L293-294 (Medium)**: `SystemMaintenanceService.run_if_due()` 在 `before_request` 中执行，任何异常被 `except Exception` 吞掉仅打日志。如果维护任务持续失败（如磁盘满），每个请求都会尝试执行并失败，造成不必要的性能开销，且用户完全无感知。 2. **ui_mode.py L306 (Medium)**: `render_ui_template` 中，当 `mode == "v2"` 但 V2 Jinja env 为 None 时，静默回退到 V1 env (`app.jinja_env`)。用户以为切到了V2，实际渲染的是V1，没有任何可观测信号（无日志/无提示）。 3. **dashboard.py L37-38 (Low)**: `latest.result_summary` JSON 解析失败时静默设为 None，首页 overdue_count 将显示 0。对用户而言看不到任何错误提示。 4. **excel_utils.py L72-73 (Low)**: `hmac.compare_digest` 失败时回退到普通字符串比较 `provided == expected`。这是安全降级，虽然实际场景中 SHA256 hex 字符串不太可能触发 hmac 异常，但设计上不应有这个回退。
- Findings:
  - [medium] performance: before_request 中维护任务持续失败被静默吞掉
  - [medium] maintainability: V2 Jinja env为None时静默回退V1无可观测信号
  - [low] javascript: 首页result_summary解析失败静默返回overdue=0
  - [low] other: hmac.compare_digest 异常时回退普通字符串比较

### M2 · Routes层全量审查
- Status: completed
- Recorded At: 2026-04-02T06:54:14.157Z
- Reviewed Modules: web/routes/ (全部43个文件)
- Summary:
审查了 `web/routes/` 全部43个路由文件，覆盖设备(6)、人员(7)、工艺(9)、排产(16)、系统(8)、报表(1)、物料(1)、其他(6)。

**整体评价**: 路由层代码质量较高，模块拆分合理，各Excel导入流程的preview-confirm双阶段 + baseline签名防并发方案设计严谨。

**发现问题**:

1. **(Medium) 多处数据读取失败静默返回空值无日志**: 
   - `_load_active_downtime_machine_ids()` 失败返回空set，列表页不显示停机状态
   - `scheduler_batches.py` 排产首页 latest_history 解析失败静默设为 None

2. **(Medium) 批量操作单条失败吞掉异常信息**: 设备/人员/批次的批量 set_status/delete 中 `except Exception` 只记录ID不记录原因，无法追溯失败根因。

3. **(Low) holiday_default_efficiency 配置读取失败静默回退0.8**: 两处相同模式，可能掩盖配置损坏。

4. **(Low) time_range校验异常被静默吞掉**: `_normalize_time_range` 中 start>end 校验的外层 except 完全静默。

5. **(Low) 部分服务实例缺少op_logger参数**: `process_parts.py` 和 `process_suppliers.py` 中部分服务构造缺失 op_logger，导致操作日志不完整。
- Conclusion: 审查了 `web/routes/` 全部43个路由文件，覆盖设备(6)、人员(7)、工艺(9)、排产(16)、系统(8)、报表(1)、物料(1)、其他(6)。 **整体评价**: 路由层代码质量较高，模块拆分合理，各Excel导入流程的preview-confirm双阶段 + baseline签名防并发方案设计严谨。 **发现问题**: 1. **(Medium) 多处数据读取失败静默返回空值无日志**: - `_load_active_downtime_machine_ids()` 失败返回空set，列表页不显示停机状态 - `scheduler_batches.py` 排产首页 latest_history 解析失败静默设为 None 2. **(Medium) 批量操作单条失败吞掉异常信息**: 设备/人员/批次的批量 set_status/delete 中 `except Exception` 只记录ID不记录原因，无法追溯失败根因。 3. **(Low) holiday_default_efficiency 配置读取失败静默回退0.8**: 两处相同模式，可能掩盖配置损坏。 4. **(Low) time_range校验异常被静默吞掉**: `_normalize_time_range` 中 start>end 校验的外层 except 完全静默。 5. **(Low) 部分服务实例缺少op_logger参数**: `process_parts.py` 和 `process_suppliers.py` 中部分服务构造缺失 op_logger，导致操作日志不完整。
- Findings:
  - [medium] other: 多处数据读取失败静默返回空值无日志
  - [medium] other: 批量操作单条失败吞掉异常信息
  - [low] other: holiday_default_efficiency配置读取失败静默回退
  - [low] other: time_range校验异常被静默吞掉
  - [low] other: 部分服务实例缺少op_logger参数

### M3 · ViewModels层 + web_new_test审查
- Status: completed
- Recorded At: 2026-04-02T06:55:18.330Z
- Reviewed Modules: web/viewmodels/ (全13个文件), web_new_test/ (全部9个文件)
- Summary:
审查了 `web/viewmodels/` 全部13个文件和 `web_new_test/` 全部9个文件。

**ViewModels层**:
- `scheduler_analysis_vm.py`：排产分析页的数据构建逻辑，SVG折线图生成、趋势提取、attempts排序等。代码结构清晰，纯计算函数无副作用，易测试。大量使用 safe_float/safe_int 做容错是合理的展示层设计。
- `system_logs_vm.py`：简单的日志数据展开，无问题。
- `page_manuals*.py`（11个文件）：静态帮助文档的内容注册与构建系统。纯数据驱动，无逻辑风险。

**web_new_test层**:
- V2 UI 的模板和CSS。CSS 使用了现代 CSS 特性（:has() 伪类），但项目明确锁定 Chrome 109+，所以兼容性风险可控。
- 模板结构与V1保持了良好的分离，通过 `safe_url_for` 做 endpoint 降级，模式正确。
- 发现了大量使用 `safe_url_for` + fallback `<details>` 排查信息的模式，这是一个良好的渐进发布实践。

**总体发现**:
1. (Low) `scheduler_analysis_vm.py` 的 safe_float/safe_int 可能掩盖数据结构变化
2. (Low) CSS :has() 伪类在非 Chrome 109+ 环境下完全失效
- Conclusion: 审查了 `web/viewmodels/` 全部13个文件和 `web_new_test/` 全部9个文件。 **ViewModels层**: - `scheduler_analysis_vm.py`：排产分析页的数据构建逻辑，SVG折线图生成、趋势提取、attempts排序等。代码结构清晰，纯计算函数无副作用，易测试。大量使用 safe_float/safe_int 做容错是合理的展示层设计。 - `system_logs_vm.py`：简单的日志数据展开，无问题。 - `page_manuals*.py`（11个文件）：静态帮助文档的内容注册与构建系统。纯数据驱动，无逻辑风险。 **web_new_test层**: - V2 UI 的模板和CSS。CSS 使用了现代 CSS 特性（:has() 伪类），但项目明确锁定 Chrome 109+，所以兼容性风险可控。 - 模板结构与V1保持了良好的分离，通过 `safe_url_for` 做 endpoint 降级，模式正确。 - 发现了大量使用 `safe_url_for` + fallback `<details>` 排查信息的模式，这是一个良好的渐进发布实践。 **总体发现**: 1. (Low) `scheduler_analysis_vm.py` 的 safe_float/safe_int 可能掩盖数据结构变化 2. (Low) CSS :has() 伪类在非 Chrome 109+ 环境下完全失效
- Findings:
  - [low] maintainability: 分析页影响层safe_float/safe_int静默回退0可能掩盖数据结构变化
  - [low] css: CSS :has()伪类兼容性风险
<!-- LIMCODE_REVIEW_MILESTONES_END -->

<!-- LIMCODE_REVIEW_METADATA_START -->
{
  "formatVersion": 3,
  "reviewRunId": "review-mnh49j7q-qgivk4",
  "createdAt": "2026-04-02T00:00:00.000Z",
  "finalizedAt": "2026-04-02T06:55:42.379Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "latestConclusion": "## 审查结论 对 `web/` 全部 84 个 Python 文件和 `web_new_test/` 全部 9 个文件进行了三轮深度审查。 ### 整体质量评价 **代码质量较高**，未发现严重 BUG（High severity 为 0）。架构分层清晰，模块拆分合理： - Bootstrap 层对 Win7/PyInstaller 场景有细致考虑，运行时锁/契约文件/进程管理实现稳健 - Routes 层的 Excel 导入采用 preview-confirm 双阶段 + SHA256 baseline 签名防并发方案，设计严谨 - V1/V2 UI 模式切换通过 Jinja overlay env + cookie + DB 三级配置，渐进发布策略合理 - `safe_url_for` + `<details>` 排查信息的降级模式，是很好的生产级可用性实践 ### 发现汇总（11 条） | 等级 | 数量 | 核心模式 | |------|------|----------| | Medium | 4 | 静默回退无可观测信号、批量操作吞异常 | | Low | 7 | 配置回退无日志、不必要的兜底、风格不一致 | **最需优先修复的 4 个 Medium 问题**： 1. **F001** - `before_request` 中维护任务持续失败无冷却机制 → 建议增加失败计数器 2. **F002** - V2 Jinja env 回退 V1 无日志 → 加一行 warning 3. **F005** - 停机ID/排产摘要读取失败静默返回空 → 加 warning 日志 4. **F006** - 批量 set_status/delete 吞掉异常信息 → 加 `logger.exception` ### 无需修复的合理设计 - `safe_url_for` 吞 BuildError → 正确的渐进发布策略 - `scheduler_analysis_vm` 的 safe_float/safe_int → 展示层容错优先于报错 - 数据库恢复流程的 maintenance_window + ensure_schema → 事务安全设计合理 - shutdown endpoint 的 `secrets.compare_digest` + 127.0.0.1 限制 → 安全措施到位",
  "recommendedNextAction": "优先修复 4 个 Medium 问题（F001/F002/F005/F006），均为增加日志可观测性，改动量小且风险极低。Low 问题可在后续迭代中逐步处理。",
  "reviewedModules": [
    "web/bootstrap/",
    "web/error_handlers.py",
    "web/ui_mode.py",
    "web/routes/normalizers.py",
    "web/routes/pagination.py",
    "web/routes/excel_utils.py",
    "web/routes/dashboard.py",
    "web/routes/ (全部43个文件)",
    "web/viewmodels/ (全13个文件)",
    "web_new_test/ (全部9个文件)",
    "web/bootstrap/ (8文件)",
    "web/routes/ (43文件)",
    "web/viewmodels/ (13文件)",
    "web_new_test/ (9文件)"
  ],
  "milestones": [
    {
      "id": "M1",
      "title": "Bootstrap层 + 基础工具模块审查",
      "summary": "审查了 `web/bootstrap/` 全部8个文件（factory.py, launcher.py, paths.py, plugins.py, runtime_probe.py, security.py, static_versioning.py）以及 `web/error_handlers.py`, `web/ui_mode.py`, `web/routes/normalizers.py`, `web/routes/pagination.py`, `web/routes/excel_utils.py`, `web/routes/dashboard.py`。\n\n**整体评价**: Bootstrap层实现稳健，异常处理层次分明，对Win7/PyInstaller场景有细致考虑。\n\n**发现问题**:\n\n1. **factory.py L293-294 (Medium)**: `SystemMaintenanceService.run_if_due()` 在 `before_request` 中执行，任何异常被 `except Exception` 吞掉仅打日志。如果维护任务持续失败（如磁盘满），每个请求都会尝试执行并失败，造成不必要的性能开销，且用户完全无感知。\n\n2. **ui_mode.py L306 (Medium)**: `render_ui_template` 中，当 `mode == \"v2\"` 但 V2 Jinja env 为 None 时，静默回退到 V1 env (`app.jinja_env`)。用户以为切到了V2，实际渲染的是V1，没有任何可观测信号（无日志/无提示）。\n\n3. **dashboard.py L37-38 (Low)**: `latest.result_summary` JSON 解析失败时静默设为 None，首页 overdue_count 将显示 0。对用户而言看不到任何错误提示。\n\n4. **excel_utils.py L72-73 (Low)**: `hmac.compare_digest` 失败时回退到普通字符串比较 `provided == expected`。这是安全降级，虽然实际场景中 SHA256 hex 字符串不太可能触发 hmac 异常，但设计上不应有这个回退。",
      "status": "completed",
      "conclusion": "审查了 `web/bootstrap/` 全部8个文件（factory.py, launcher.py, paths.py, plugins.py, runtime_probe.py, security.py, static_versioning.py）以及 `web/error_handlers.py`, `web/ui_mode.py`, `web/routes/normalizers.py`, `web/routes/pagination.py`, `web/routes/excel_utils.py`, `web/routes/dashboard.py`。 **整体评价**: Bootstrap层实现稳健，异常处理层次分明，对Win7/PyInstaller场景有细致考虑。 **发现问题**: 1. **factory.py L293-294 (Medium)**: `SystemMaintenanceService.run_if_due()` 在 `before_request` 中执行，任何异常被 `except Exception` 吞掉仅打日志。如果维护任务持续失败（如磁盘满），每个请求都会尝试执行并失败，造成不必要的性能开销，且用户完全无感知。 2. **ui_mode.py L306 (Medium)**: `render_ui_template` 中，当 `mode == \"v2\"` 但 V2 Jinja env 为 None 时，静默回退到 V1 env (`app.jinja_env`)。用户以为切到了V2，实际渲染的是V1，没有任何可观测信号（无日志/无提示）。 3. **dashboard.py L37-38 (Low)**: `latest.result_summary` JSON 解析失败时静默设为 None，首页 overdue_count 将显示 0。对用户而言看不到任何错误提示。 4. **excel_utils.py L72-73 (Low)**: `hmac.compare_digest` 失败时回退到普通字符串比较 `provided == expected`。这是安全降级，虽然实际场景中 SHA256 hex 字符串不太可能触发 hmac 异常，但设计上不应有这个回退。",
      "evidenceFiles": [],
      "reviewedModules": [
        "web/bootstrap/",
        "web/error_handlers.py",
        "web/ui_mode.py",
        "web/routes/normalizers.py",
        "web/routes/pagination.py",
        "web/routes/excel_utils.py",
        "web/routes/dashboard.py"
      ],
      "recommendedNextAction": null,
      "recordedAt": "2026-04-02T06:52:28.462Z",
      "findingIds": [
        "F001",
        "F002",
        "F003",
        "F004"
      ]
    },
    {
      "id": "M2",
      "title": "Routes层全量审查",
      "summary": "审查了 `web/routes/` 全部43个路由文件，覆盖设备(6)、人员(7)、工艺(9)、排产(16)、系统(8)、报表(1)、物料(1)、其他(6)。\n\n**整体评价**: 路由层代码质量较高，模块拆分合理，各Excel导入流程的preview-confirm双阶段 + baseline签名防并发方案设计严谨。\n\n**发现问题**:\n\n1. **(Medium) 多处数据读取失败静默返回空值无日志**: \n   - `_load_active_downtime_machine_ids()` 失败返回空set，列表页不显示停机状态\n   - `scheduler_batches.py` 排产首页 latest_history 解析失败静默设为 None\n\n2. **(Medium) 批量操作单条失败吞掉异常信息**: 设备/人员/批次的批量 set_status/delete 中 `except Exception` 只记录ID不记录原因，无法追溯失败根因。\n\n3. **(Low) holiday_default_efficiency 配置读取失败静默回退0.8**: 两处相同模式，可能掩盖配置损坏。\n\n4. **(Low) time_range校验异常被静默吞掉**: `_normalize_time_range` 中 start>end 校验的外层 except 完全静默。\n\n5. **(Low) 部分服务实例缺少op_logger参数**: `process_parts.py` 和 `process_suppliers.py` 中部分服务构造缺失 op_logger，导致操作日志不完整。",
      "status": "completed",
      "conclusion": "审查了 `web/routes/` 全部43个路由文件，覆盖设备(6)、人员(7)、工艺(9)、排产(16)、系统(8)、报表(1)、物料(1)、其他(6)。 **整体评价**: 路由层代码质量较高，模块拆分合理，各Excel导入流程的preview-confirm双阶段 + baseline签名防并发方案设计严谨。 **发现问题**: 1. **(Medium) 多处数据读取失败静默返回空值无日志**: - `_load_active_downtime_machine_ids()` 失败返回空set，列表页不显示停机状态 - `scheduler_batches.py` 排产首页 latest_history 解析失败静默设为 None 2. **(Medium) 批量操作单条失败吞掉异常信息**: 设备/人员/批次的批量 set_status/delete 中 `except Exception` 只记录ID不记录原因，无法追溯失败根因。 3. **(Low) holiday_default_efficiency 配置读取失败静默回退0.8**: 两处相同模式，可能掩盖配置损坏。 4. **(Low) time_range校验异常被静默吞掉**: `_normalize_time_range` 中 start>end 校验的外层 except 完全静默。 5. **(Low) 部分服务实例缺少op_logger参数**: `process_parts.py` 和 `process_suppliers.py` 中部分服务构造缺失 op_logger，导致操作日志不完整。",
      "evidenceFiles": [],
      "reviewedModules": [
        "web/routes/ (全部43个文件)"
      ],
      "recommendedNextAction": null,
      "recordedAt": "2026-04-02T06:54:14.157Z",
      "findingIds": [
        "F005",
        "F006",
        "F007",
        "F008",
        "F009"
      ]
    },
    {
      "id": "M3",
      "title": "ViewModels层 + web_new_test审查",
      "summary": "审查了 `web/viewmodels/` 全部13个文件和 `web_new_test/` 全部9个文件。\n\n**ViewModels层**:\n- `scheduler_analysis_vm.py`：排产分析页的数据构建逻辑，SVG折线图生成、趋势提取、attempts排序等。代码结构清晰，纯计算函数无副作用，易测试。大量使用 safe_float/safe_int 做容错是合理的展示层设计。\n- `system_logs_vm.py`：简单的日志数据展开，无问题。\n- `page_manuals*.py`（11个文件）：静态帮助文档的内容注册与构建系统。纯数据驱动，无逻辑风险。\n\n**web_new_test层**:\n- V2 UI 的模板和CSS。CSS 使用了现代 CSS 特性（:has() 伪类），但项目明确锁定 Chrome 109+，所以兼容性风险可控。\n- 模板结构与V1保持了良好的分离，通过 `safe_url_for` 做 endpoint 降级，模式正确。\n- 发现了大量使用 `safe_url_for` + fallback `<details>` 排查信息的模式，这是一个良好的渐进发布实践。\n\n**总体发现**:\n1. (Low) `scheduler_analysis_vm.py` 的 safe_float/safe_int 可能掩盖数据结构变化\n2. (Low) CSS :has() 伪类在非 Chrome 109+ 环境下完全失效",
      "status": "completed",
      "conclusion": "审查了 `web/viewmodels/` 全部13个文件和 `web_new_test/` 全部9个文件。 **ViewModels层**: - `scheduler_analysis_vm.py`：排产分析页的数据构建逻辑，SVG折线图生成、趋势提取、attempts排序等。代码结构清晰，纯计算函数无副作用，易测试。大量使用 safe_float/safe_int 做容错是合理的展示层设计。 - `system_logs_vm.py`：简单的日志数据展开，无问题。 - `page_manuals*.py`（11个文件）：静态帮助文档的内容注册与构建系统。纯数据驱动，无逻辑风险。 **web_new_test层**: - V2 UI 的模板和CSS。CSS 使用了现代 CSS 特性（:has() 伪类），但项目明确锁定 Chrome 109+，所以兼容性风险可控。 - 模板结构与V1保持了良好的分离，通过 `safe_url_for` 做 endpoint 降级，模式正确。 - 发现了大量使用 `safe_url_for` + fallback `<details>` 排查信息的模式，这是一个良好的渐进发布实践。 **总体发现**: 1. (Low) `scheduler_analysis_vm.py` 的 safe_float/safe_int 可能掩盖数据结构变化 2. (Low) CSS :has() 伪类在非 Chrome 109+ 环境下完全失效",
      "evidenceFiles": [],
      "reviewedModules": [
        "web/viewmodels/ (全13个文件)",
        "web_new_test/ (全部9个文件)"
      ],
      "recommendedNextAction": null,
      "recordedAt": "2026-04-02T06:55:18.330Z",
      "findingIds": [
        "F010",
        "F011"
      ]
    }
  ],
  "findings": [
    {
      "id": "F001",
      "severity": "medium",
      "category": "performance",
      "title": "before_request 中维护任务持续失败被静默吞掉",
      "description": "factory.py L293-294: SystemMaintenanceService.run_if_due() 在每个请求的 before_request 中执行，任何异常被 except Exception 吞掉仅打日志。如果维护任务持续失败（如磁盘满），每个请求都会尝试执行并失败，造成性能开销且用户无感知。",
      "evidenceFiles": [
        "web/bootstrap/factory.py"
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "recommendation": "增加失败计数器或冷却机制，连续失败N次后暂停一段时间不再尝试。"
    },
    {
      "id": "F002",
      "severity": "medium",
      "category": "maintainability",
      "title": "V2 Jinja env为None时静默回退V1无可观测信号",
      "description": "ui_mode.py L306: render_ui_template 中，当 mode=='v2' 但 V2 Jinja env 为 None 时，静默回退到 V1 env。用户以为切到了V2，实际渲染V1，没有日志/提示。",
      "evidenceFiles": [
        "web/ui_mode.py"
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "recommendation": "在回退时至少记录一条 warning 日志，标明 V2 env 不可用已回退 V1。"
    },
    {
      "id": "F003",
      "severity": "low",
      "category": "javascript",
      "title": "首页result_summary解析失败静默返回overdue=0",
      "description": "dashboard.py L37-38: result_summary JSON 解析失败时静默设为 None，overdue_count 将显示 0，用户无感知。",
      "evidenceFiles": [
        "web/routes/dashboard.py"
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "recommendation": "解析失败时至少记录warning日志。"
    },
    {
      "id": "F004",
      "severity": "low",
      "category": "other",
      "title": "hmac.compare_digest 异常时回退普通字符串比较",
      "description": "excel_utils.py L72-73: hmac.compare_digest 失败时回退到 provided == expected。虽然实际触发概率极低，但设计上不应有此安全降级。",
      "evidenceFiles": [
        "web/routes/excel_utils.py"
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "recommendation": "移除 try/except，直接使用 hmac.compare_digest。"
    },
    {
      "id": "F005",
      "severity": "medium",
      "category": "other",
      "title": "多处数据读取失败静默返回空值无日志",
      "description": "equipment_pages.py L61-67, scheduler_batches.py L71-73: _load_active_downtime_machine_ids() 和 latest_history/latest_summary 获取失败时静默返回空集/None。停机ID列表获取失败意味着设备停机状态在列表页不显示，用户无感知。scheduler_batches.py 的 latest_history 解析失败则排产首页丢失最近排产摘要。",
      "evidenceFiles": [
        "web/routes/equipment_pages.py",
        "web/routes/scheduler_batches.py"
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "recommendation": "至少记录 warning 日志，让运维能通过日志发现数据读取异常。"
    },
    {
      "id": "F006",
      "severity": "medium",
      "category": "other",
      "title": "批量操作单条失败吞掉异常信息",
      "description": "equipment_pages.py L297-302, L325-330, personnel_pages.py L207-212, L235-240, scheduler_batches.py L203-208: 批量操作（set_status/delete）中，单条失败被 except Exception 吞掉，仅将ID加入failed列表。异常信息完全丢失，失败原因不可追溯（除了 scheduler_batches.py 的 bulk_copy/bulk_update 正确记录了 logger.exception）。",
      "evidenceFiles": [
        "web/routes/equipment_pages.py",
        "web/routes/personnel_pages.py",
        "web/routes/scheduler_batches.py"
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "recommendation": "在 except Exception 中增加 current_app.logger.exception 或至少 logger.warning，记录具体失败原因。"
    },
    {
      "id": "F007",
      "severity": "low",
      "category": "other",
      "title": "holiday_default_efficiency配置读取失败静默回退",
      "description": "scheduler_excel_calendar.py L124-129: holiday_default_efficiency 配置读取失败时静默回退到0.8，这可能掩盖数据库配置损坏或服务层BUG。类似模式在 scheduler_calendar_pages.py L18-24 也存在。",
      "evidenceFiles": [
        "web/routes/scheduler_excel_calendar.py",
        "web/routes/scheduler_calendar_pages.py"
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "recommendation": "在 except 分支记录 warning 日志标明使用了回退值。"
    },
    {
      "id": "F008",
      "severity": "low",
      "category": "other",
      "title": "time_range校验异常被静默吞掉",
      "description": "system_utils.py L99-104: _normalize_time_range 中 start > end 的校验失败时（非 ValidationError 类型），被 except Exception: _ = None 完全吞掉。这意味着如果 strptime 出现意外异常（理论上不应该因为 start_norm 和 end_norm 已经是标准格式），start>end的校验逻辑就不生效。",
      "evidenceFiles": [
        "web/routes/system_utils.py"
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "recommendation": "移除多余的 except Exception 分支，因为此处 start_norm/end_norm 已经是标准化后的格式，strptime 不应失败。如果确需兜底，应至少打日志。"
    },
    {
      "id": "F009",
      "severity": "low",
      "category": "other",
      "title": "部分服务实例缺少op_logger参数",
      "description": "process_parts.py L98: SupplierService(g.db) 构造时没有传 op_logger 参数，而同文件其他服务（如 PartService）都传了 op_logger。这虽不是BUG（op_logger 通常是可选参数），但与项目其他代码风格不一致，可能导致供应商相关操作缺少操作日志。同样 process_suppliers.py L29 中 OpTypeService(g.db) 也缺少 op_logger。",
      "evidenceFiles": [
        "web/routes/process_parts.py",
        "web/routes/process_suppliers.py"
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "recommendation": "补充 op_logger=getattr(g, 'op_logger', None) 参数以保持一致性。"
    },
    {
      "id": "F010",
      "severity": "low",
      "category": "maintainability",
      "title": "分析页影响层safe_float/safe_int静默回退0可能掩盖数据结构变化",
      "description": "scheduler_analysis_vm.py 中大量使用 safe_float/safe_int 将任意值非法静默回退为 0。对于一个分析仪表板页面，这意味着如果后端数据结构变化（如字段改名），指标全部显示为0而不是报错，用户可能误认为排产效果很好。这是一个典型的“会隐藏BUG的静默回退”。但考虑到分析页只是展示层，它的容错优先于报错是合理的设计选择，影响度 low。",
      "evidenceFiles": [
        "web/viewmodels/scheduler_analysis_vm.py"
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "recommendation": "可保持现状，但建议在 build_trend_rows 中对关键字段缺失时至少记录一次 warning 日志。"
    },
    {
      "id": "F011",
      "severity": "low",
      "category": "css",
      "title": "CSS :has()伪类兼容性风险",
      "description": "web_new_test/static/css/style.css L160-167: 使用了 CSS :has() 伪类（.card:not(:has(.card-header)):not(:has(.card-body))）。这个伪类在Chrome 105+才支持，而项目目标环境是Win7+Chrome 109，所以刚好兼容。但如果有其他旧浏览器场景（如内部IE11测试），这些规则会完全失效，导致旧V1模板在V2布局中缺少padding。",
      "evidenceFiles": [
        "web_new_test/static/css/style.css"
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "recommendation": "确认目标浏览器范围，如仅Chrome 109+则安全。否则需增加回退规则。"
    }
  ]
}
<!-- LIMCODE_REVIEW_METADATA_END -->
