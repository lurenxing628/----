# web目录与web_new_test目录全面审查
- 日期: 2026-04-02
- 概述: 对web/和web_new_test/目录进行三轮深度审查，重点检查BUG、引用链完整性和影响使用的问题
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# web/ 与 web_new_test/ 全面审查

**审查日期**: 2026-04-01  
**审查范围**: `web/` 目录（启动引导、路由、视图模型）和 `web_new_test/` 目录  
**审查策略**: 三轮递进式审查

## 审查计划

### 第一轮：启动引导与基础设施
- `web/bootstrap/` — 应用工厂、启动器、安全、路径、插件
- `web/error_handlers.py`、`web/ui_mode.py`
- `web/__init__.py`

### 第二轮：路由层深度审查
- 各业务路由模块的引用链、数据校验、异常处理
- 跨模块依赖关系验证

### 第三轮：视图模型与 web_new_test
- `web/viewmodels/` 全部文件
- `web_new_test/` 与主 web 的差异和一致性

## 评审摘要

- 当前状态: 已完成
- 已审模块: web/bootstrap/, web/error_handlers.py, web/ui_mode.py, web/routes/dashboard.py, web/routes/scheduler_bp.py, web/routes/scheduler*.py, web/routes/equipment*.py, web/routes/system*.py, web/routes/reports.py, web/routes/excel_utils.py, web/routes/normalizers.py, web/routes/pagination.py, web/routes/enum_display.py, web/routes/process_excel_routes.py, web/viewmodels/, web_new_test/, app.py, app_new_ui.py, web/routes/
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 7
- 问题严重级别分布: 高 0 / 中 2 / 低 5
- 最新结论: ## 三轮审查总结 完成对 `web/` 和 `web_new_test/` 目录的三轮全面深度审查，涵盖启动引导（8个文件）、路由层（40+个文件）、视图模型（13个文件）和新UI测试环境（9个文件）。 ### 整体评价 系统整体工程质量较高，安全防护、异常处理和可观测性设计到位。未发现会导致崩溃或数据损坏的严重BUG。 ### 主要发现（共7项，0高/2中/5低） **中等严重度（2项）：** 1. **F1 - g.app_logger 始终为 None**：所有路由通过 `getattr(g, 'app_logger', None)` 传递 logger 参数给服务层，但 `g.app_logger` 从未被设置。追溯到数据仓库层的 `base_repo.py`，当出现数据库错误时，`self.logger.error()` 会因 logger 为 None 触发 `AttributeError`，然后被 `except Exception: pass` 静默吞掉。这导致数据库错误日志完全丢失——虽然不会崩溃，但会严重影响问题排查。 2. **F6 - V2 首页丢失统计数据**：V2 的 `dashboard.html` 只有静态导航卡片，丢失了V1首页的待排/已排/超期批次数量和最近排产版本信息。后端路由仍在查询这些数据但被浪费。用户切换到V2后看不到业务概览。 **低严重度（5项）：** - F2：6个文件中重复定义 `_strict_mode_enabled` - F3：排产列表页和管理页有约30行重复逻辑 - F4：路由层直接访问服务层内部仓库属性（`batch_svc.batch_repo`） - F5：路由层访问服务层私有方法（`CalendarService._normalize_date`） - F7：`app.py` 和 `app_new_ui.py` 启动流程约150行重复 ### 确认的设计亮点 - Excel导入的预览→确认二段式 + SHA256基线签名防篡改 - 运行时锁与契约文件机制确保单实例运行 - 安全头完整 + CSRF防护 + 安全重定向 + 路径穿越防护 - 备份恢复的维护窗口锁机制 - V1/V2 UI共存的overlay机制设计巧妙 - 慢请求可观测性（Server-Timing头） - 所有Excel操作有审计日志
- 下一步建议: 优先修复 F1（g.app_logger 始终为 None）和 F6（V2 首页统计数据缺失）；其余低优先级的可维护性问题可在后续重构中逐步处理
- 总体结论: 有条件通过

## 评审发现

### g.app_logger 始终为 None

- ID: F1
- 严重级别: 中
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  在 dashboard.py、scheduler_batches.py、scheduler_gantt.py 等多个路由中，广泛使用 getattr(g, 'app_logger', None) 来传递 logger 参数。但在 factory.py 的 _open_db before_request 钩子中，从未设置 g.app_logger。这意味着所有服务层收到的 logger 参数始终为 None，可能导致服务层内部日志静默丢失。
- 建议:

  在 _open_db 中添加 g.app_logger = current_app.logger，或者在路由中直接使用 current_app.logger
- 证据:
  - `web/bootstrap/factory.py:262-294#_open_db`
  - `web/routes/dashboard.py:19`
  - `web/bootstrap/factory.py`
  - `web/routes/dashboard.py`

### 多个路由中同一工具函数重复定义

- ID: F2
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  _strict_mode_enabled 函数在 6 个路由文件中各自定义了一份完全相同的副本（scheduler_run.py、scheduler_batches.py、scheduler_week_plan.py、scheduler_excel_batches.py、process_parts.py、process_excel_routes.py）。虽然功能一致不会造成BUG，但增加了维护风险——如果未来需要调整真值判定逻辑，容易遗漏某些副本。同样 _get_int_arg 在 gantt 和 week_plan 中重复。
- 建议:

  将 _strict_mode_enabled 和 _get_int_arg 提取到共享工具模块（如 excel_utils.py 或新建 route_utils.py），消除重复

### 批次列表页与批次管理页存在大量重复逻辑

- ID: F3
- 严重级别: 低
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  在 scheduler_batches.py 的 batches_page 和 batches_manage_page 两个路由中，存在几乎完全相同的批次列表查询和视图构建逻辑（重复约 30 行代码）。两者都执行 batch_svc.list(status=...) -> 遍历构建 view_rows -> paginate_rows，唯一区别是渲染的模板和额外的 part_options。这导致代码难以统一维护。
- 建议:

  提取公共的批次列表视图构建函数，两个路由共用

### 路由层直接访问服务层内部仓库属性

- ID: F4
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  在 scheduler_batches.py 第292行的 bulk_copy_batches 路由中，使用了 lambda 来检查批次是否存在：`exists_fn=lambda x: batch_svc.batch_repo.get(x) is not None`。这里直接访问了 batch_svc.batch_repo（仓库层的内部属性），破坏了分层封装。更好的做法是通过服务层的公共方法来查询。
- 建议:

  在 BatchService 上添加一个 exists(batch_id) 公共方法，替代直接访问 batch_repo
- 证据:
  - `web/routes/scheduler_batches.py:292#bulk_copy_batches`
  - `web/routes/scheduler_batches.py`

### 路由层访问服务层私有方法 _normalize_date

- ID: F5
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  在 scheduler_excel_calendar.py 第54行，直接访问了 CalendarService._normalize_date（私有方法，前缀带下划线），这属于访问内部实现细节。如果 CalendarService 的内部方法被重构或重命名，多处路由代码会受到影响。
- 建议:

  将 _normalize_date 提升为公共方法，或在路由层使用独立的日期标准化函数
- 证据:
  - `web/routes/scheduler_excel_calendar.py:52-56`
  - `web/routes/scheduler_excel_calendar.py`

### V2 首页丢失待排/已排/超期统计数据展示

- ID: F6
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  V2 的 dashboard.html 只是一个纯静态的导航卡片页面，没有使用路由传过来的 pending_count、scheduled_count、overdue_count、latest_history 等变量。这意味着用户切换到 V2 界面后，首页不再显示待排/已排/超期的统计数据，而这些数据在后端仍然被查询但被浪费。

  这是一个功能降级问题——用户在 V2 首页看不到关键的业务状态概览。
- 建议:

  为 V2 的 dashboard.html 补充统计数据展示区域，使用路由已传递的变量
- 证据:
  - `web_new_test/templates/dashboard.html:1-83`
  - `web/routes/dashboard.py:1-65`
  - `web_new_test/templates/dashboard.html`
  - `web/routes/dashboard.py`

### app.py 和 app_new_ui.py 启动流程大量重复

- ID: F7
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  app.py 和 app_new_ui.py 的 main() 函数、_configure_runtime_contract()、_parse_cli_args() 等几乎完全相同（约 150 行重复），唯一区别是 ui_mode 参数值。如果启动流程需要修改（如端口策略、运行时锁逻辑等），很容易只改一个文件而漏改另一个。
- 建议:

  将公共启动流程提取到 web/bootstrap/ 中的共享函数，两个入口文件只保留差异化配置
- 证据:
  - `app.py`
  - `app_new_ui.py`

## 评审里程碑

### M1 · 第一轮：启动引导与基础设施审查

- 状态: 已完成
- 记录时间: 2026-04-02T17:01:16.264Z
- 已审模块: web/bootstrap/, web/error_handlers.py, web/ui_mode.py, web/routes/dashboard.py, web/routes/scheduler_bp.py
- 摘要:

  完成对 web/bootstrap/（工厂、启动器、安全、路径、插件、运行时探测、静态版本化）、web/error_handlers.py、web/ui_mode.py 的全面审查。

  **已确认的良好实践：**
  - 退出备份做了去重保护（_EXIT_BACKUP_REGISTERED 标志）
  - 维护窗口检测有完整的 before_request 拦截
  - 安全头完整（X-Frame-Options、nosniff、Referrer-Policy）
  - 密钥持久化到文件，避免重启后 session 失效
  - 静态资源版本化使用 mtime 缓存，有固定版本环境变量覆盖
  - 慢请求可观测性（Server-Timing 头 + 日志预警）
  - safe_url_for 防止 BuildError 导致整页 500

  **初步发现的潜在问题：**
  1. scheduler_bp.py 注册了 _priority_zh / _ready_zh / _batch_status_zh / _day_type_zh 但从未被作为 Jinja 过滤器或上下文处理器注册到蓝图，只能通过 Python 调用——需要验证模板中是否有遗漏
  2. ui_mode.py 中 render_ui_template 每次渲染都会写入 env.globals，潜在的并发写入问题（虽然 GIL 保护了字典操作，但语义上是冗余的）
  3. dashboard.py 中 getattr(g, "app_logger", None) — g 上从未设置 app_logger，这个 getattr 总是返回 None
- 结论:

  启动引导和基础设施层整体设计严谨，防护措施完备。发现 g.app_logger 始终为 None 的问题需进一步确认影响范围。
- 问题:
  - [中] JavaScript: g.app_logger 始终为 None

### M2 · 第二轮：路由层深度审查

- 状态: 已完成
- 记录时间: 2026-04-02T17:03:31.076Z
- 已审模块: web/routes/scheduler*.py, web/routes/equipment*.py, web/routes/system*.py, web/routes/reports.py, web/routes/excel_utils.py, web/routes/normalizers.py, web/routes/pagination.py, web/routes/enum_display.py, web/routes/process_excel_routes.py
- 摘要:

  完成对 web/routes/ 目录下所有路由模块的全面审查，覆盖了：
  - 排产调度（批次管理、运行、配置、甘特图、分析、周计划、资源调度、Excel导入导出）
  - 设备管理（列表、详情、CRUD、停机、关联、Excel导入）
  - 人员管理（页面、日历、Excel导入）
  - 工艺管理（零件、工艺路线、供应商、工时Excel导入）
  - 报表中心（超期、利用率、停机影响、导出）
  - 系统管理（备份恢复、日志、历史、UI模式、插件、健康检查）
  - 公共工具（分页、枚举显示、标准化、Excel工具）

  **确认的良好实践：**
  1. Excel 导入采用预览→确认二段式，含 SHA256 基线签名防篡改
  2. 备份恢复操作前关闭当前 DB 连接，恢复后重新建立连接并执行 schema 检查
  3. 备份文件名校验防路径穿越攻击（basename 检查 + 前缀/后缀白名单）
  4. 安全重定向（_safe_next_url）阻止外站重定向
  5. 运行时关停接口仅允许本机访问 + token 验证 + 时序安全比较（secrets.compare_digest）
  6. 批量操作均有失败收集 + 限制展示条数 + 总结性提示
  7. 所有 Excel 导入/导出都有审计日志（log_excel_import/log_excel_export）
  8. ValidationError 被全局 error_handler 捕获，不会导致 500

  **发现的问题：**
  1. _strict_mode_enabled 在 6 个文件中重复定义
  2. 批次列表页和管理页有重复逻辑
  3. 路由层直接访问服务层内部仓库属性
  4. 路由层访问服务层私有方法
- 结论:

  路由层整体实现质量较高，Excel导入的预览-确认二段式设计含防篡改基线签名保护，路径穿越等安全问题已妥善处理。发现几个可维护性和低风险问题。
- 下一步建议:

  进入第三轮：审查 viewmodels 和 web_new_test 目录
- 问题:
  - [低] 可维护性: 多个路由中同一工具函数重复定义
  - [低] 性能: 批次列表页与批次管理页存在大量重复逻辑
  - [低] 其他: 路由层直接访问服务层内部仓库属性
  - [低] 其他: 路由层访问服务层私有方法 _normalize_date

### M3 · 第三轮：视图模型与 web_new_test 审查

- 状态: 已完成
- 记录时间: 2026-04-02T17:05:27.137Z
- 已审模块: web/viewmodels/, web_new_test/, app.py, app_new_ui.py
- 摘要:

  完成对 web/viewmodels/ 全部文件和 web_new_test/ 目录的审查。

  **视图模型层（web/viewmodels/）：**
  1. **page_manuals** 体系结构清晰：通过注册表（registry）、主题定义（topics）和公共构建器（common）三层解耦，支持多模块的页面说明系统
  2. **scheduler_analysis_vm** 实现了无依赖的SVG折线图生成，适合Win7离线环境
  3. **system_logs_vm** 安全地处理了JSON解析失败的回退

  **web_new_test/ 目录：**
  1. V2 的 base.html 实现了完整的侧边栏布局、暗色主题切换、表格密度调节
  2. V2 CSS（style.css 636行）包含了对V1旧模板的兼容层（legacy button、legacy form control、legacy table、legacy card），使得V1模板在V2布局中基本可用
  3. V2 覆盖了 7 个关键模板（base.html、dashboard.html、5个scheduler子页）
  4. 未覆盖的页面通过 ChoiceLoader overlay 机制回退到V1模板+V2基础布局

  **发现的问题：**
  1. V2 首页（dashboard.html）丢失了统计数据展示——V1有待排/已排/超期数量+最近版本信息，V2只有静态导航卡片
  2. app.py 和 app_new_ui.py 的 main() 函数几乎完全重复（~150行），仅 ui_mode 参数不同
- 结论:

  视图模型层设计良好，新旧UI共存机制完善。web_new_test 处于过渡阶段，大部分V1模板通过overlay机制回退可用。V2首页丢失了统计数据展示属于功能降级。两个入口文件高度重复需要重构。
- 问题:
  - [中] 其他: V2 首页丢失待排/已排/超期统计数据展示
  - [低] 可维护性: app.py 和 app_new_ui.py 启动流程大量重复

## 最终结论

## 三轮审查总结

完成对 `web/` 和 `web_new_test/` 目录的三轮全面深度审查，涵盖启动引导（8个文件）、路由层（40+个文件）、视图模型（13个文件）和新UI测试环境（9个文件）。

### 整体评价

系统整体工程质量较高，安全防护、异常处理和可观测性设计到位。未发现会导致崩溃或数据损坏的严重BUG。

### 主要发现（共7项，0高/2中/5低）

**中等严重度（2项）：**

1. **F1 - g.app_logger 始终为 None**：所有路由通过 `getattr(g, 'app_logger', None)` 传递 logger 参数给服务层，但 `g.app_logger` 从未被设置。追溯到数据仓库层的 `base_repo.py`，当出现数据库错误时，`self.logger.error()` 会因 logger 为 None 触发 `AttributeError`，然后被 `except Exception: pass` 静默吞掉。这导致数据库错误日志完全丢失——虽然不会崩溃，但会严重影响问题排查。

2. **F6 - V2 首页丢失统计数据**：V2 的 `dashboard.html` 只有静态导航卡片，丢失了V1首页的待排/已排/超期批次数量和最近排产版本信息。后端路由仍在查询这些数据但被浪费。用户切换到V2后看不到业务概览。

**低严重度（5项）：**
- F2：6个文件中重复定义 `_strict_mode_enabled`
- F3：排产列表页和管理页有约30行重复逻辑
- F4：路由层直接访问服务层内部仓库属性（`batch_svc.batch_repo`）
- F5：路由层访问服务层私有方法（`CalendarService._normalize_date`）
- F7：`app.py` 和 `app_new_ui.py` 启动流程约150行重复

### 确认的设计亮点

- Excel导入的预览→确认二段式 + SHA256基线签名防篡改
- 运行时锁与契约文件机制确保单实例运行
- 安全头完整 + CSRF防护 + 安全重定向 + 路径穿越防护
- 备份恢复的维护窗口锁机制
- V1/V2 UI共存的overlay机制设计巧妙
- 慢请求可观测性（Server-Timing头）
- 所有Excel操作有审计日志

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnhq0hbq-7nogmi",
  "createdAt": "2026-04-02T00:00:00.000Z",
  "updatedAt": "2026-04-02T17:05:52.324Z",
  "finalizedAt": "2026-04-02T17:05:52.324Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "web目录与web_new_test目录全面审查",
    "date": "2026-04-02",
    "overview": "对web/和web_new_test/目录进行三轮深度审查，重点检查BUG、引用链完整性和影响使用的问题"
  },
  "scope": {
    "markdown": "# web/ 与 web_new_test/ 全面审查\n\n**审查日期**: 2026-04-01  \n**审查范围**: `web/` 目录（启动引导、路由、视图模型）和 `web_new_test/` 目录  \n**审查策略**: 三轮递进式审查\n\n## 审查计划\n\n### 第一轮：启动引导与基础设施\n- `web/bootstrap/` — 应用工厂、启动器、安全、路径、插件\n- `web/error_handlers.py`、`web/ui_mode.py`\n- `web/__init__.py`\n\n### 第二轮：路由层深度审查\n- 各业务路由模块的引用链、数据校验、异常处理\n- 跨模块依赖关系验证\n\n### 第三轮：视图模型与 web_new_test\n- `web/viewmodels/` 全部文件\n- `web_new_test/` 与主 web 的差异和一致性"
  },
  "summary": {
    "latestConclusion": "## 三轮审查总结\n\n完成对 `web/` 和 `web_new_test/` 目录的三轮全面深度审查，涵盖启动引导（8个文件）、路由层（40+个文件）、视图模型（13个文件）和新UI测试环境（9个文件）。\n\n### 整体评价\n\n系统整体工程质量较高，安全防护、异常处理和可观测性设计到位。未发现会导致崩溃或数据损坏的严重BUG。\n\n### 主要发现（共7项，0高/2中/5低）\n\n**中等严重度（2项）：**\n\n1. **F1 - g.app_logger 始终为 None**：所有路由通过 `getattr(g, 'app_logger', None)` 传递 logger 参数给服务层，但 `g.app_logger` 从未被设置。追溯到数据仓库层的 `base_repo.py`，当出现数据库错误时，`self.logger.error()` 会因 logger 为 None 触发 `AttributeError`，然后被 `except Exception: pass` 静默吞掉。这导致数据库错误日志完全丢失——虽然不会崩溃，但会严重影响问题排查。\n\n2. **F6 - V2 首页丢失统计数据**：V2 的 `dashboard.html` 只有静态导航卡片，丢失了V1首页的待排/已排/超期批次数量和最近排产版本信息。后端路由仍在查询这些数据但被浪费。用户切换到V2后看不到业务概览。\n\n**低严重度（5项）：**\n- F2：6个文件中重复定义 `_strict_mode_enabled`\n- F3：排产列表页和管理页有约30行重复逻辑\n- F4：路由层直接访问服务层内部仓库属性（`batch_svc.batch_repo`）\n- F5：路由层访问服务层私有方法（`CalendarService._normalize_date`）\n- F7：`app.py` 和 `app_new_ui.py` 启动流程约150行重复\n\n### 确认的设计亮点\n\n- Excel导入的预览→确认二段式 + SHA256基线签名防篡改\n- 运行时锁与契约文件机制确保单实例运行\n- 安全头完整 + CSRF防护 + 安全重定向 + 路径穿越防护\n- 备份恢复的维护窗口锁机制\n- V1/V2 UI共存的overlay机制设计巧妙\n- 慢请求可观测性（Server-Timing头）\n- 所有Excel操作有审计日志",
    "recommendedNextAction": "优先修复 F1（g.app_logger 始终为 None）和 F6（V2 首页统计数据缺失）；其余低优先级的可维护性问题可在后续重构中逐步处理",
    "reviewedModules": [
      "web/bootstrap/",
      "web/error_handlers.py",
      "web/ui_mode.py",
      "web/routes/dashboard.py",
      "web/routes/scheduler_bp.py",
      "web/routes/scheduler*.py",
      "web/routes/equipment*.py",
      "web/routes/system*.py",
      "web/routes/reports.py",
      "web/routes/excel_utils.py",
      "web/routes/normalizers.py",
      "web/routes/pagination.py",
      "web/routes/enum_display.py",
      "web/routes/process_excel_routes.py",
      "web/viewmodels/",
      "web_new_test/",
      "app.py",
      "app_new_ui.py",
      "web/routes/"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 7,
    "severity": {
      "high": 0,
      "medium": 2,
      "low": 5
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：启动引导与基础设施审查",
      "status": "completed",
      "recordedAt": "2026-04-02T17:01:16.264Z",
      "summaryMarkdown": "完成对 web/bootstrap/（工厂、启动器、安全、路径、插件、运行时探测、静态版本化）、web/error_handlers.py、web/ui_mode.py 的全面审查。\n\n**已确认的良好实践：**\n- 退出备份做了去重保护（_EXIT_BACKUP_REGISTERED 标志）\n- 维护窗口检测有完整的 before_request 拦截\n- 安全头完整（X-Frame-Options、nosniff、Referrer-Policy）\n- 密钥持久化到文件，避免重启后 session 失效\n- 静态资源版本化使用 mtime 缓存，有固定版本环境变量覆盖\n- 慢请求可观测性（Server-Timing 头 + 日志预警）\n- safe_url_for 防止 BuildError 导致整页 500\n\n**初步发现的潜在问题：**\n1. scheduler_bp.py 注册了 _priority_zh / _ready_zh / _batch_status_zh / _day_type_zh 但从未被作为 Jinja 过滤器或上下文处理器注册到蓝图，只能通过 Python 调用——需要验证模板中是否有遗漏\n2. ui_mode.py 中 render_ui_template 每次渲染都会写入 env.globals，潜在的并发写入问题（虽然 GIL 保护了字典操作，但语义上是冗余的）\n3. dashboard.py 中 getattr(g, \"app_logger\", None) — g 上从未设置 app_logger，这个 getattr 总是返回 None",
      "conclusionMarkdown": "启动引导和基础设施层整体设计严谨，防护措施完备。发现 g.app_logger 始终为 None 的问题需进一步确认影响范围。",
      "evidence": [],
      "reviewedModules": [
        "web/bootstrap/",
        "web/error_handlers.py",
        "web/ui_mode.py",
        "web/routes/dashboard.py",
        "web/routes/scheduler_bp.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F1"
      ]
    },
    {
      "id": "M2",
      "title": "第二轮：路由层深度审查",
      "status": "completed",
      "recordedAt": "2026-04-02T17:03:31.076Z",
      "summaryMarkdown": "完成对 web/routes/ 目录下所有路由模块的全面审查，覆盖了：\n- 排产调度（批次管理、运行、配置、甘特图、分析、周计划、资源调度、Excel导入导出）\n- 设备管理（列表、详情、CRUD、停机、关联、Excel导入）\n- 人员管理（页面、日历、Excel导入）\n- 工艺管理（零件、工艺路线、供应商、工时Excel导入）\n- 报表中心（超期、利用率、停机影响、导出）\n- 系统管理（备份恢复、日志、历史、UI模式、插件、健康检查）\n- 公共工具（分页、枚举显示、标准化、Excel工具）\n\n**确认的良好实践：**\n1. Excel 导入采用预览→确认二段式，含 SHA256 基线签名防篡改\n2. 备份恢复操作前关闭当前 DB 连接，恢复后重新建立连接并执行 schema 检查\n3. 备份文件名校验防路径穿越攻击（basename 检查 + 前缀/后缀白名单）\n4. 安全重定向（_safe_next_url）阻止外站重定向\n5. 运行时关停接口仅允许本机访问 + token 验证 + 时序安全比较（secrets.compare_digest）\n6. 批量操作均有失败收集 + 限制展示条数 + 总结性提示\n7. 所有 Excel 导入/导出都有审计日志（log_excel_import/log_excel_export）\n8. ValidationError 被全局 error_handler 捕获，不会导致 500\n\n**发现的问题：**\n1. _strict_mode_enabled 在 6 个文件中重复定义\n2. 批次列表页和管理页有重复逻辑\n3. 路由层直接访问服务层内部仓库属性\n4. 路由层访问服务层私有方法",
      "conclusionMarkdown": "路由层整体实现质量较高，Excel导入的预览-确认二段式设计含防篡改基线签名保护，路径穿越等安全问题已妥善处理。发现几个可维护性和低风险问题。",
      "evidence": [],
      "reviewedModules": [
        "web/routes/scheduler*.py",
        "web/routes/equipment*.py",
        "web/routes/system*.py",
        "web/routes/reports.py",
        "web/routes/excel_utils.py",
        "web/routes/normalizers.py",
        "web/routes/pagination.py",
        "web/routes/enum_display.py",
        "web/routes/process_excel_routes.py"
      ],
      "recommendedNextAction": "进入第三轮：审查 viewmodels 和 web_new_test 目录",
      "findingIds": [
        "F2",
        "F3",
        "F4",
        "F5"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：视图模型与 web_new_test 审查",
      "status": "completed",
      "recordedAt": "2026-04-02T17:05:27.137Z",
      "summaryMarkdown": "完成对 web/viewmodels/ 全部文件和 web_new_test/ 目录的审查。\n\n**视图模型层（web/viewmodels/）：**\n1. **page_manuals** 体系结构清晰：通过注册表（registry）、主题定义（topics）和公共构建器（common）三层解耦，支持多模块的页面说明系统\n2. **scheduler_analysis_vm** 实现了无依赖的SVG折线图生成，适合Win7离线环境\n3. **system_logs_vm** 安全地处理了JSON解析失败的回退\n\n**web_new_test/ 目录：**\n1. V2 的 base.html 实现了完整的侧边栏布局、暗色主题切换、表格密度调节\n2. V2 CSS（style.css 636行）包含了对V1旧模板的兼容层（legacy button、legacy form control、legacy table、legacy card），使得V1模板在V2布局中基本可用\n3. V2 覆盖了 7 个关键模板（base.html、dashboard.html、5个scheduler子页）\n4. 未覆盖的页面通过 ChoiceLoader overlay 机制回退到V1模板+V2基础布局\n\n**发现的问题：**\n1. V2 首页（dashboard.html）丢失了统计数据展示——V1有待排/已排/超期数量+最近版本信息，V2只有静态导航卡片\n2. app.py 和 app_new_ui.py 的 main() 函数几乎完全重复（~150行），仅 ui_mode 参数不同",
      "conclusionMarkdown": "视图模型层设计良好，新旧UI共存机制完善。web_new_test 处于过渡阶段，大部分V1模板通过overlay机制回退可用。V2首页丢失了统计数据展示属于功能降级。两个入口文件高度重复需要重构。",
      "evidence": [],
      "reviewedModules": [
        "web/viewmodels/",
        "web_new_test/",
        "app.py",
        "app_new_ui.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F6",
        "F7"
      ]
    }
  ],
  "findings": [
    {
      "id": "F1",
      "severity": "medium",
      "category": "javascript",
      "title": "g.app_logger 始终为 None",
      "descriptionMarkdown": "在 dashboard.py、scheduler_batches.py、scheduler_gantt.py 等多个路由中，广泛使用 getattr(g, 'app_logger', None) 来传递 logger 参数。但在 factory.py 的 _open_db before_request 钩子中，从未设置 g.app_logger。这意味着所有服务层收到的 logger 参数始终为 None，可能导致服务层内部日志静默丢失。",
      "recommendationMarkdown": "在 _open_db 中添加 g.app_logger = current_app.logger，或者在路由中直接使用 current_app.logger",
      "evidence": [
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 262,
          "lineEnd": 294,
          "symbol": "_open_db"
        },
        {
          "path": "web/routes/dashboard.py",
          "lineStart": 19,
          "lineEnd": 19
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/routes/dashboard.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F2",
      "severity": "low",
      "category": "maintainability",
      "title": "多个路由中同一工具函数重复定义",
      "descriptionMarkdown": "_strict_mode_enabled 函数在 6 个路由文件中各自定义了一份完全相同的副本（scheduler_run.py、scheduler_batches.py、scheduler_week_plan.py、scheduler_excel_batches.py、process_parts.py、process_excel_routes.py）。虽然功能一致不会造成BUG，但增加了维护风险——如果未来需要调整真值判定逻辑，容易遗漏某些副本。同样 _get_int_arg 在 gantt 和 week_plan 中重复。",
      "recommendationMarkdown": "将 _strict_mode_enabled 和 _get_int_arg 提取到共享工具模块（如 excel_utils.py 或新建 route_utils.py），消除重复",
      "evidence": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F3",
      "severity": "low",
      "category": "performance",
      "title": "批次列表页与批次管理页存在大量重复逻辑",
      "descriptionMarkdown": "在 scheduler_batches.py 的 batches_page 和 batches_manage_page 两个路由中，存在几乎完全相同的批次列表查询和视图构建逻辑（重复约 30 行代码）。两者都执行 batch_svc.list(status=...) -> 遍历构建 view_rows -> paginate_rows，唯一区别是渲染的模板和额外的 part_options。这导致代码难以统一维护。",
      "recommendationMarkdown": "提取公共的批次列表视图构建函数，两个路由共用",
      "evidence": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F4",
      "severity": "low",
      "category": "other",
      "title": "路由层直接访问服务层内部仓库属性",
      "descriptionMarkdown": "在 scheduler_batches.py 第292行的 bulk_copy_batches 路由中，使用了 lambda 来检查批次是否存在：`exists_fn=lambda x: batch_svc.batch_repo.get(x) is not None`。这里直接访问了 batch_svc.batch_repo（仓库层的内部属性），破坏了分层封装。更好的做法是通过服务层的公共方法来查询。",
      "recommendationMarkdown": "在 BatchService 上添加一个 exists(batch_id) 公共方法，替代直接访问 batch_repo",
      "evidence": [
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 292,
          "lineEnd": 292,
          "symbol": "bulk_copy_batches"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F5",
      "severity": "low",
      "category": "other",
      "title": "路由层访问服务层私有方法 _normalize_date",
      "descriptionMarkdown": "在 scheduler_excel_calendar.py 第54行，直接访问了 CalendarService._normalize_date（私有方法，前缀带下划线），这属于访问内部实现细节。如果 CalendarService 的内部方法被重构或重命名，多处路由代码会受到影响。",
      "recommendationMarkdown": "将 _normalize_date 提升为公共方法，或在路由层使用独立的日期标准化函数",
      "evidence": [
        {
          "path": "web/routes/scheduler_excel_calendar.py",
          "lineStart": 52,
          "lineEnd": 56
        },
        {
          "path": "web/routes/scheduler_excel_calendar.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F6",
      "severity": "medium",
      "category": "other",
      "title": "V2 首页丢失待排/已排/超期统计数据展示",
      "descriptionMarkdown": "V2 的 dashboard.html 只是一个纯静态的导航卡片页面，没有使用路由传过来的 pending_count、scheduled_count、overdue_count、latest_history 等变量。这意味着用户切换到 V2 界面后，首页不再显示待排/已排/超期的统计数据，而这些数据在后端仍然被查询但被浪费。\n\n这是一个功能降级问题——用户在 V2 首页看不到关键的业务状态概览。",
      "recommendationMarkdown": "为 V2 的 dashboard.html 补充统计数据展示区域，使用路由已传递的变量",
      "evidence": [
        {
          "path": "web_new_test/templates/dashboard.html",
          "lineStart": 1,
          "lineEnd": 83
        },
        {
          "path": "web/routes/dashboard.py",
          "lineStart": 1,
          "lineEnd": 65
        },
        {
          "path": "web_new_test/templates/dashboard.html"
        },
        {
          "path": "web/routes/dashboard.py"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F7",
      "severity": "low",
      "category": "maintainability",
      "title": "app.py 和 app_new_ui.py 启动流程大量重复",
      "descriptionMarkdown": "app.py 和 app_new_ui.py 的 main() 函数、_configure_runtime_contract()、_parse_cli_args() 等几乎完全相同（约 150 行重复），唯一区别是 ui_mode 参数值。如果启动流程需要修改（如端口策略、运行时锁逻辑等），很容易只改一个文件而漏改另一个。",
      "recommendationMarkdown": "将公共启动流程提取到 web/bootstrap/ 中的共享函数，两个入口文件只保留差异化配置",
      "evidence": [
        {
          "path": "app.py"
        },
        {
          "path": "app_new_ui.py"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:1ea481cb97b6742130638803b85078b36048682ccb1a5863642d658657ed3a99",
    "generatedAt": "2026-04-02T17:05:52.324Z",
    "locale": "zh-CN"
  }
}
```
