# 静默回退与隐藏BUG专项审查
- 日期: 2026-04-02
- 概述: 专项审查：web/与web_new_test/中的静默回退、过度兜底、隐藏BUG的异常吞掉模式
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 静默回退与隐藏BUG专项审查

**审查日期**: 2026-04-02  
**审查范围**: `web/` 和 `web_new_test/` 中所有 `except ... pass`、默认值兜底、静默降级逻辑  
**审查策略**: 三轮递进式

## 审查计划

### 第一轮：启动链路与请求生命周期中的静默吞错
- factory.py 的 before_request / after_request / teardown 中的异常处理
- 运行时锁、退出备份等关键流程的异常吞掉

### 第二轮：路由层的过度兜底与静默回退
- Excel导入确认阶段的错误行处理逻辑
- 批量操作中 continue 跳过错误但不充分记录
- 数据标准化中的宽松回退（未知值原样返回）

### 第三轮：跨层引用链中的静默断裂
- logger=None 在服务层→仓库层→数据库层的传播链
- 模板渲染中的 safe_url_for 返回 None 后的下游影响
- ui_mode 降级路径中的日志与可观测性缺口

## 评审摘要

- 当前状态: 已完成
- 已审模块: web/bootstrap/factory.py, data/repositories/base_repo.py, core/infrastructure/transaction.py, core/services/common/safe_logging.py, web/routes/normalizers.py, web/routes/scheduler_utils.py, core/services/common/excel_validators.py, web/routes/process_excel_routes.py, web/routes/scheduler_excel_batches.py, templates/, web_new_test/templates/, web/ui_mode.py, web/viewmodels/scheduler_analysis_vm.py, core/services/scheduler/schedule_service.py, web/routes/, web/routes/scheduler_batch_detail.py, web/bootstrap/launcher.py, web/bootstrap/plugins.py, core/services/scheduler/resource_pool_builder.py, web/bootstrap/security.py, web/bootstrap/static_versioning.py, web/error_handlers.py
- 当前进度: 已记录 5 个里程碑；最新：M5
- 里程碑总数: 5
- 已完成里程碑: 5
- 问题总数: 15
- 问题严重级别分布: 高 0 / 中 3 / 低 12
- 最新结论: 经过 M5 三轮严谨复核修正后的最终结论：\n\n**真正确认的过度防御问题仅2处**：OD2（告警合并三层嵌套+死代码→1行）和 OD3（相邻函数防御策略不一致）。\n\nM4 中标记的其余4处（OD1/4/5/6）经复核发现均有合理防御理由，尤其是 Flask LocalProxy 代理对象在上下文异常时抛 RuntimeError（不是 AttributeError），导致 getattr 的默认值机制无法捕获——这使得 OD1 和 OD6 的"过度"判断不成立。\n\n最高优先级仍是 SF1（48处日志断链，1行修复）。
- 下一步建议: 1. 立即修复 SF1（1行代码解决48处日志断链）\n2. 简化 OD2（告警合并 10行→1行，含死代码清理）\n3. 修复 OD3（删除 _count_internal_ops 的多余 try/except）\n4. 可选：合并 safe_url_for 第3+4层 try 块（纯风格优化）
- 总体结论: 有条件通过

## 评审发现

### 48处 logger=None 穿透导致日志链断开

- ID: SF1
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  在 web/routes/ 目录中有 48处 使用 getattr(g, 'app_logger', None) 传入 logger 参数。由于 g.app_logger 从未被设置，这 48 处全部传入 None。经过逐层代码追踪：路由层 logger=None → 服务层 self.logger=None → 仓库层 self.logger=None → base_repo._log_db_error 第116行 if not self.logger: return 直接跳过 → 数据库错误日志被完全丢弃。不会崩溃，但 SQL 错误详情、参数信息等关键排障信息无法被记录。
- 建议:

  在 _open_db 钩子中添加一行 g.app_logger = current_app.logger
- 证据:
  - `web/bootstrap/factory.py:262-294#_open_db`
  - `data/repositories/base_repo.py:115-117#_log_db_error`
  - `core/services/common/safe_logging.py:6-8#safe_log`
  - `web/bootstrap/factory.py`
  - `data/repositories/base_repo.py`
  - `core/services/common/safe_logging.py`

### _count_internal_ops 整个循环包在 try/except 中静默返回 0

- ID: SF2
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  _count_internal_ops 函数把整个循环包在一个 try/except Exception: return 0 中。如果工序列表中任意一个对象的属性访问出错，整个函数静默返回 0 不记录任何日志，导致下游 _resolve_lazy_select_enabled 误判。
- 建议:

  去掉外层宽泛异常捕获，仅捕获已知可预期异常类型
- 证据:
  - `web/routes/scheduler_batch_detail.py:18-27#_count_internal_ops`
  - `web/routes/scheduler_batch_detail.py`

### 排产服务层告警合并的三层嵌套 try/except 可能丢失资源池告警

- ID: SF3
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  在 schedule_service.py 第 392-400 行，合并资源池告警信息时使用了三层嵌套 try/except。第 393 行的 `if algo_warnings is None` 永远为假（因为第 371-372 行已保证不为 None）。第二层和第三层 except 会在 pool_warnings 为非可迭代类型时静默吃掉异常，可能导致重要的资源池告警信息丢失。
- 建议:

  简化为单层 try/except，并在 except 中记录 warning 日志而不是完全静默
- 证据:
  - `core/services/scheduler/schedule_service.py:390-401`
  - `core/services/scheduler/schedule_service.py`

### Excel 导入确认阶段允许部分失败但事务仍提交

- ID: SF4
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  在 process_excel_routes.py 的 excel_routes_confirm 函数中，第 203-218 行先检查“只要有错误行就全部拒绝”，但第 254-265 行的循环中仍然有 `except AppError` 捕获并 continue 的逻辑。这意味着如果预览通过但实际写入时抛出 AppError（如数据库状态在预览和确认之间变化），部分数据会被导入而部分被跳过，事务仍然提交。虽然 baseline 签名模式大大降低了这种发生的概率，但理论上仍可能出现部分导入的情况。
- 建议:

  考虑在循环结束后检查 error_count，如果大于 0 则回滚事务（或在 AppError 捕获时记录 warning 日志）
- 证据:
  - `web/routes/process_excel_routes.py:233-265`
  - `web/routes/process_excel_routes.py`

### ui_mode.py 的 23 处 except Exception 均为有意设计的降级

- ID: SF5
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 不修复
- 相关里程碑: M3
- 说明:

  ui_mode.py 中有 23 处 except Exception，通过逐一审查确认：

  **合理的静默回退（不需修改）：**
  - _read_ui_mode_from_db → DB 不可用时回退默认模式（避免整页 500）
  - get_ui_mode 的 Cookie 读取 → Cookie 损坏时回退 DB/默认
  - safe_url_for 的 BuildError 捕获 → 有一次性 warning 日志
  - g.ui_mode 赋值失败 → 只影响下游可观测性，不影响渲染
  - init_ui_mode 中 V2 env 创建失败 → 有 warning 日志 + 回退 V1
  - env.globals 写入失败 → 几乎不可能发生

  **结论：所有静默回退都是有意设计，为了保持“页面可用性”。关键降级路径有日志覆盖（_warn_v2_render_fallback_once、safe_url_for 的 warning），不存在隐藏 BUG 的风险。

### safe_url_for 的5层嵌套异常处理

- ID: OD1
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M4
- 说明:

  safe_url_for（第267-295行）在 BuildError 处理分支中嵌套了4层 try/except，核心目的仅是"记录一条 warning 日志"。具体结构：

  - 第1层：`try: url_for()` / `except BuildError` — 合理
  - 第2层：`try: logged = getattr(g, ...)` — 合理
  - 第3层：`try: path = getattr(request, 'path', '')` — **多余**，getattr 带默认值不会抛异常
  - 第4层：`try: current_app.logger.warning(...)` — **过度**，标准 logging 不会抛异常
  - 第5层：`except Exception: return None` — 兜底层

  30行函数中有15行是异常处理代码，占比50%。简化后可从30行缩减到15行。
- 建议:

  合并第3、4层到第2层的 try 体中，删除对 getattr(request, 'path', '') 的独立 try/except。简化为：外层捕获 BuildError，内层一个 try 完成日志记录（包含 path 获取和 logger.warning），最外层一个 except Exception 兜底。
- 证据:
  - `web/ui_mode.py:259-295#safe_url_for`
  - `web/ui_mode.py`

### 告警合并10行代码含死代码和三层嵌套

- ID: OD2
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M4
- 说明:

  schedule_service.py 第391-400行的告警合并逻辑：

  ```python
  try:
      if algo_warnings is None:  # ← 死代码：第371-372行保证非 None
          algo_warnings = []
      algo_warnings.extend(list(pool_warnings))
  except Exception:
      try:
          algo_warnings = list(algo_warnings or []) + list(pool_warnings or [])
      except Exception:
          algo_warnings = list(pool_warnings or [])
  ```

  问题：
  1. `if algo_warnings is None` 永远为假（死代码）
  2. `algo_warnings.extend(list(pool_warnings))` 不需要 try/except — algo_warnings 是 list，pool_warnings 是函数返回的 list
  3. 第二/三层 except 是"如果 extend 失败就用加法，如果加法也失败就丢弃原有告警"——这种级联降级在实践中毫无意义

  10行代码可替换为1行：`algo_warnings.extend(pool_warnings)`
- 建议:

  替换整个 if pool_warnings 块为：`algo_warnings.extend(pool_warnings)`。如果确实需要防御 pool_warnings 的类型，最多加一行类型检查。
- 证据:
  - `core/services/scheduler/schedule_service.py:391-401`
  - `core/services/scheduler/schedule_service.py`

### 相邻函数防御策略不一致（_count_internal_ops vs _collect_selected_resource_ids）

- ID: OD3
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M4
- 说明:

  scheduler_batch_detail.py 中两个紧邻定义的函数（第18行和第30行），迭代相同的 ops: List[Any] 参数，使用完全相同的属性访问模式 `(getattr(op, 'source', '') or '').strip().lower()`，并与相同的 SourceType.INTERNAL.value 比较。

  但 _count_internal_ops 用 `try/except Exception: return 0` 包裹整个函数体，而 _collect_selected_resource_ids 没有任何异常处理。

  后者（做更复杂操作：还访问 machine_id、operator_id、supplier_id）在没有 try/except 的情况下运行正常，**直接证明** _count_internal_ops 的 try/except 是不必要的。同时造成了代码风格的不一致。
- 建议:

  删除 _count_internal_ops 的 try/except 包裹，使其与相邻函数风格一致。
- 证据:
  - `web/routes/scheduler_batch_detail.py:18-27#_count_internal_ops`
  - `web/routes/scheduler_batch_detail.py:30-44#_collect_selected_resource_ids`
  - `web/routes/scheduler_batch_detail.py`

### launcher.py 约15处对不可能失败操作的冗余异常捕获

- ID: OD4
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M4
- 说明:

  launcher.py 全文934行中有50处 except Exception，其中约15处保护的操作在 Python 中永远不会抛异常：

  **对 str() 的防御**（第188-192行）：
  `str(cfg_log_dir).strip()` — Python 的 str() 对任何对象都不会抛异常（最坏情况调用 __repr__），.strip() 对字符串也不会抛异常。

  **对已知 int 类型的 int() 防御**（第59-62行）：
  `int(p)` 其中 p 来自硬编码列表 [preferred, 5000, 5705, ...]，整数字面量 int(5000) 永远不会抛 ValueError。

  **对类型签名为 int 的参数做 int() 防御**（第306-308、339-342行）：
  `int(pid)` 其中 pid 的函数签名已标注为 int。

  **对 logger.warning() 的防御**（约10处如第32、854行）：
  Python 的 logging.Logger.handle() 方法内部已有 try/except，设计为永不将异常传播到调用方。对 logger 调用再包一层 try/except 纯粹是噪音。
- 建议:

  分批清理：优先删除 str().strip() 和整数字面量 int() 的无意义 try/except；logger 调用的防御可纳入下次重构。
- 证据:
  - `web/bootstrap/launcher.py:188-192`
  - `web/bootstrap/launcher.py:59-62`
  - `web/bootstrap/launcher.py:306-308`
  - `web/bootstrap/launcher.py:339-342`
  - `web/bootstrap/launcher.py:851-855`
  - `web/bootstrap/launcher.py`

### plugins.py 60行代码7个 except Exception 形成嵌套迷宫

- ID: OD5
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M4
- 说明:

  bootstrap_plugins 函数60行中有7个 except Exception 块，形成多层嵌套的"洋葱型"错误处理结构。其中3处（第23-26、32-35、50-51行）是对日志调用本身的防御——`try: logger.warning(...) except Exception: pass`。

  Python 标准 logging 库设计为不抛异常（Logger.handle 内部已有保护），因此这些包裹层纯粹增加缩进噪音。

  此外，连接关闭操作（第53-56行）`try: conn0.close() except Exception: pass` 虽合理但可以用 contextmanager 模式简化。
- 建议:

  1. 删除对 logger.warning/error 调用的 try/except 包裹
  2. 考虑使用 contextmanager 管理数据库连接
  3. 整体简化为：一个顶层 try/finally 管理 conn0 生命周期 + 内部逻辑直接调用
- 证据:
  - `web/bootstrap/plugins.py:10-58#bootstrap_plugins`
  - `web/bootstrap/plugins.py`

### ui_mode.py 中对 getattr(带默认值) 和 request.endpoint 的冗余异常捕获

- ID: OD6
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M4
- 说明:

  ui_mode.py 中有多处对不可能失败操作的防御：

  1. **第40-43行** `_resolve_manual_endpoint`：`request.endpoint` 在 has_request_context() 检查后不会抛异常
  2. **第66-75行** `_resolve_manual_src`：`getattr(request, 'full_path', '')` 使用了默认值，不会抛 AttributeError。但用了两个串联的 try/except 块来分别获取 full_path 和 path
  3. **第244-246行** `_warn_v2_render_fallback_once`：`getattr(request, 'path', '')` 同理
  4. **第279-282行** safe_url_for 内部：同上

  这些操作使用了 Python getattr 的安全模式（提供默认值），不存在 AttributeError 的可能。try/except 增加的是纯代码噪音，不提供额外安全性。
- 建议:

  删除上述函数中对 getattr(obj, attr, default) 和 request.endpoint 的 try/except 包裹。如需防御 request context 无效的极端情况，第一行的 has_request_context() 检查已足够。
- 证据:
  - `web/ui_mode.py:35-43#_resolve_manual_endpoint`
  - `web/ui_mode.py:61-75#_resolve_manual_src`
  - `web/ui_mode.py:244-256#_warn_v2_render_fallback_once`
  - `web/ui_mode.py`

### OD1 降级：safe_url_for 嵌套有合理理由，仅结构可优化

- ID: OD1-REV
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M5
- 说明:

  **M4 原结论**：safe_url_for 5层嵌套"过度"，第3/4层对 getattr(request, 'path', '') 和 logger.warning() 的保护"多余"。

  **复核后纠正**：

  Flask 的 `request` 是 `LocalProxy` 代理对象。当请求上下文处于异常状态（如 teardown 回调中、并发边界条件）时，代理的 `__getattribute__` 会抛出 `RuntimeError("Working outside of request context")`。

  Python `getattr(obj, name, default)` 的默认值机制**只捕获 `AttributeError`**，不捕获其他异常类型。因此 `getattr(request, 'path', '')` 在 Flask 代理上**不是安全操作**——当代理状态异常时 `RuntimeError` 会穿透 getattr。

  同理，`current_app` 也是 `LocalProxy`，`current_app.logger.warning()` 在应用上下文异常时同样可能抛 `RuntimeError`。

  **结论**：第3层和第4层的 try/except 都有合理防御理由，不是"纯噪音"。但两个相邻的 try 块可以合并为一个（因为它们防御的是同类风险），结构从5层减为3层作为可读性优化。
- 建议:

  可选优化：将第3层（path获取）和第4层（日志记录）合并为一个 try 块。这是风格改进，不是必须修复。
- 证据:
  - `web/ui_mode.py:259-295#safe_url_for`
  - `web/ui_mode.py`

### OD6 撤回：Flask LocalProxy 的 getattr 确实需要 try/except

- ID: OD6-REV
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 接受风险
- 相关里程碑: M5
- 说明:

  **M4 原结论**：`getattr(request, 'path', '')` 带默认值"不可能抛异常"，try/except 是"纯代码噪音"。

  **复核后撤回**：

  这个判断对普通 Python 对象成立，但对 Flask 的 `LocalProxy` **不成立**。技术原因：

  1. `getattr(obj, name, default)` 内部机制：先调用 `type(obj).__getattribute__(obj, name)`，如果抛出 `AttributeError` 则返回 default。如果抛出**任何其他异常类型**（如 `RuntimeError`），异常会直接传播。

  2. Flask 的 `request` 是 `LocalProxy`。当请求上下文不可用时（teardown、异步边界、测试环境），代理的 `__getattribute__` 抛出的是 `RuntimeError`，不是 `AttributeError`。

  3. 因此 `getattr(request, 'path', '')` **不能**安全地回退到默认值——`RuntimeError` 会穿透。

  **结论**：ui_mode.py 中所有对 Flask 代理对象做 `getattr` 后包裹 try/except 的代码（第40-43、66-75、244-246、279-282行）都是在防御一个**真实的失败场景**，不是冗余防御。此发现应从过度防御清单中撤回。
- 建议:

  无需修改。这些 try/except 保护了一个 getattr 默认值机制无法覆盖的真实边界条件。
- 证据:
  - `web/ui_mode.py:35-75`
  - `web/ui_mode.py:279-282`
  - `web/ui_mode.py`

### OD4 缩窄：launcher.py 仅1处确认多余（str 转 str），其余有合理理由

- ID: OD4-REV
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 接受风险
- 相关里程碑: M5
- 说明:

  **M4 原结论**：launcher.py 约15处 except Exception 保护的操作"永远不会抛异常"。

  **复核后缩窄**：

  逐项重新评估：

  1. **第188-192行 `str(cfg_log_dir).strip()`**：参数类型 `str | None`，代码已在非 None 分支中。`str(一个str对象)` 确实不会失败。**确认多余**。

  2. **第59-62行 `int(p)` 在 pick_port 中**：列表是 `[preferred, 5000, ...]`，`preferred` 参数类型标注为 `int` 但 Python 不做运行时检查。追踪调用方（app.py 第144行），`preferred_port` 虽然已是 int，但 `pick_port` 作为公共函数不应信赖调用方遵守类型约定。**保留合理**。

  3. **第306-308行 `int(pid)` 在 _pid_exists**：唯一调用方（第369行）传入的 `pid` 已是 int，但函数是独立的工具函数。对输入做类型防御在系统编程中是惯例。**保留合理**。

  4. **logger.warning() 包裹**：`logger` 参数类型为 `Logger | None`，代码已检查非 None。标准 Logger 确实不抛异常，但在启动链路中，logger 可能来自外部传入（如测试中的 mock），额外保护可接受。**争论区，但不算明显过度**。

  综上，仅第188-192行的1处可确认为多余。
- 建议:

  可选清理第188-192行的 try/except，但优先级极低。
- 证据:
  - `web/bootstrap/launcher.py:188-192`
  - `web/bootstrap/launcher.py`

### OD5 缩窄：plugins.py 结构冗长但非"迷宫"，每层保护不同故障域

- ID: OD5-REV
- 严重级别: 低
- 分类: 可维护性
- 跟踪状态: 接受风险
- 相关里程碑: M5
- 说明:

  **M4 原结论**：60行7个 except Exception "形成嵌套迷宫"，日志调用包裹"纯粹是缩进噪音"。

  **复核后修正**：

  逐层分析7个 except 的保护目标：
  - 第20行：`get_connection()` 失败 → 数据库连接异常 → **必要**
  - 第25行：`logger.warning()` 包裹 → logger 可能是外部传入的自定义对象 → **过度谨慎但不无道理**
  - 第30行：`PluginManager.load_from_base_dir()` 失败 → 第三方插件加载异常 → **必要**
  - 第34行：`logger.error()` 包裹 → 同上 → **过度谨慎**
  - 第38行：`get_plugin_status()` 回退 → 状态查询异常 → **合理降级**
  - 第50行：`OperationLogger(...).info()` → 日志落库失败 → **合理**（不应阻断启动）
  - 第55行：`conn0.close()` → 连接关闭异常 → **标准实践**

  7个中仅2个（第25、34行对 logger 调用的包裹）属于"可精简但非必须"。整个函数管理3个独立故障域（数据库连接、插件加载、日志落库），每域需独立处理异常，不宜简单合并为"一个顶层 try"。
- 建议:

  可选删除第25行和第34行对 logger 调用的 try/except 包裹。整体结构无需大改——3个故障域需要独立的错误处理边界。
- 证据:
  - `web/bootstrap/plugins.py:10-58#bootstrap_plugins`
  - `web/bootstrap/plugins.py`

## 评审里程碑

### M1 · 第一轮：启动链路与请求生命周期的静默吞错分析

- 状态: 已完成
- 记录时间: 2026-04-02T17:19:44.745Z
- 已审模块: web/bootstrap/factory.py, data/repositories/base_repo.py, core/infrastructure/transaction.py, core/services/common/safe_logging.py
- 摘要:

  完成对启动链路和请求生命周期中静默吞错模式的深度分析。核心发现：48处 logger=None 穿透导致整个服务层→仓库层日志链断开。factory.py 请求生命周期中的异常处理总体合理，大部分 except 都有日志记录或合理降级。
- 结论:

  logger=None 穿透链是最严重的静默回退问题，影响面广但不会崩溃。factory.py 的请求生命周期异常处理总体合理。
- 问题:
  - [中] 其他: 48处 logger=None 穿透导致日志链断开
  - [低] 其他: _count_internal_ops 整个循环包在 try/except 中静默返回 0

### M2 · 第二轮：路由层过度兜底与静默回退分析

- 状态: 已完成
- 记录时间: 2026-04-02T17:21:53.481Z
- 已审模块: web/routes/normalizers.py, web/routes/scheduler_utils.py, core/services/common/excel_validators.py, web/routes/process_excel_routes.py, web/routes/scheduler_excel_batches.py, templates/, web_new_test/templates/
- 摘要:

  完成对路由层过度兜底和静默回退的分析。重点验证了：\n\n1. **数据标准化的宽松回退是安全的**：normalizers.py 中的"未知值原样返回"策略被 excel_validators.py 中的严格校验正确拦截\n2. **safe_url_for 的使用是正确的**：所有模板（V1和V2）都对 None 返回值做了 if 检查\n3. **路由层大部分 except Exception 都有日志**：40 处中约 35 处有 current_app.logger.exception() 记录\n4. **Excel 导入确认阶段的部分导入风险**：理论上可能在事务中部分成功部分失败，但 baseline 签名降低了发生概率\n5. **排产服务层的告警合并逻辑过度防御**：三层嵌套 try/except 可能丢失资源池告警
- 结论:

  路由层的异常处理整体规范——大部分 except Exception 都有日志记录。标准化函数的"未知值原样返回"策略被下游校验器正确拦截，不构成数据完整性风险。
- 问题:
  - [低] 其他: 排产服务层告警合并的三层嵌套 try/except 可能丢失资源池告警
  - [低] 其他: Excel 导入确认阶段允许部分失败但事务仍提交

### M3 · 第三轮：跨层引用链与 UI 降级路径的静默断裂分析

- 状态: 已完成
- 记录时间: 2026-04-02T17:23:02.808Z
- 已审模块: web/ui_mode.py, web/viewmodels/scheduler_analysis_vm.py, core/services/scheduler/schedule_service.py
- 摘要:

  完成对 ui_mode.py 中 23 处 except Exception 的逐一审查，以及跨层引用链中静默断裂的分析。\n\n**ui_mode.py 审查结论：**\n所有 23 处 except Exception 都是有意设计的降级保护，目的是保持页面可用性。关键降级路径（V2 env 创建失败、safe_url_for 的 BuildError）都有日志记录。\n\n**跨层引用链总结：**\n1. logger=None 穿透 → 已在 SF1 中完整记录\n2. safe_url_for 返回 None → 所有模板都做了 if 检查 → 安全\n3. V2 env 不可用时回退 V1 → 有一次性 warning 日志 → 安全\n4. DB 不可用时 ui_mode 回退默认 → 合理降级
- 结论:

  ui_mode.py 中的静默回退设计整体合理——在不影响页面可用性的前提下做降级，且有一次性 warning 日志保障可观测性。跨层引用链的主要问题已在第一轮 SF1 中覆盖。
- 问题:
  - [低] 其他: ui_mode.py 的 23 处 except Exception 均为有意设计的降级

### M4 · 第四轮：过度防御性编程导致代码不必要复杂的模式分析

- 状态: 已完成
- 记录时间: 2026-04-02T17:49:30.582Z
- 已审模块: web/ui_mode.py, core/services/scheduler/schedule_service.py, web/routes/scheduler_batch_detail.py, web/bootstrap/launcher.py, web/bootstrap/plugins.py
- 摘要:

  针对审查报告中已标记的 SF2/SF3 以及其他未覆盖区域，进行过度防御性编程导致代码不优雅、不简洁的专项分析。聚焦三类反模式：\n\n1. **多层嵌套异常捕获**：保护→保护→再保护的"俄罗斯套娃"结构\n2. **对不可能失败操作的防御**：`str()`、`getattr(obj, attr, default)`、整数字面量的 `int()` 等永远不会抛异常的操作被 try/except 包裹\n3. **相邻函数防御策略不一致**：相同数据结构、相同访问模式，但一个有 try/except 另一个没有\n\n### 核心发现\n\n**OD1 — safe_url_for 的5层嵌套异常处理**（中）\n第267-295行。在 BuildError 的处理分支中嵌套了4层 try/except，核心目的仅是"记录一条 warning 日志"。getattr(request, \"path\", \"\") 使用了默认值不可能抛异常，但仍被单独包裹；日志记录本身又被包裹；最外层再兜一个 except Exception。可从5层简化为2层而不丧失任何功能安全。\n\n**OD2 — schedule_service.py 三层嵌套 + 死代码**（中，是 SF3 的升级分析）\n第392-400行。第393行 `if algo_warnings is None` 是永远为假的死代码（第371-372行已保证非 None）。`algo_warnings.extend(list(pool_warnings))` 是一行的事，被包了3层嵌套 try/except。整块10行代码可替换为1行。\n\n**OD3 — _count_internal_ops 与 _collect_selected_resource_ids 的不一致**（低，是 SF2 的升级分析）\n两个函数紧邻定义（第18行和第30行），迭代相同的 ops 列表，使用完全相同的 getattr(op, \"source\", \"\") 模式，但只有 _count_internal_ops 有 try/except Exception: return 0。_collect_selected_resource_ids 没有任何防御却运行正常——这直接证明 _count_internal_ops 的 try/except 是多余的。\n\n**OD4 — launcher.py 50处 except Exception 中约15处对不可能失败操作的防御**（低）\n- 第59-62行：`int(p)` 其中 p 来自硬编码整数字面量列表 [5000, 5705, ...]，永远不会失败\n- 第188-192行：`str(cfg_log_dir).strip()` — str() 对任何对象都不会抛异常\n- 第306-308行、339-342行：`int(pid)` 其中 pid 的类型签名已是 int\n- 约10处对 logger.warning() 调用本身的 try/except — Python 标准 logging 库设计为永不抛异常\n\n**OD5 — plugins.py 整文件7个 except Exception 嵌套迷宫**（低）\n60行代码中7个 except Exception，其中至少3个（第23-26、32-35行）是对日志调用本身的防御。整个文件可以通过一个顶层 try/except + 简化内部逻辑来大幅减少层数。\n\n**OD6 — _resolve_manual_endpoint 和 _resolve_manual_src 的冗余防御**（低）\n- 第40-43行：`request.endpoint` 在有效请求上下文中（第38行已检查 has_request_context()）不会抛异常\n- 第66-75行：`getattr(request, \"full_path\", \"\")` 带默认值不会抛 AttributeError，但套了两个串联的 try/except 块\n- 第244-246行：_warn_v2_render_fallback_once 中 `getattr(request, \"path\", \"\")` 同理
- 结论:

  确认存在系统性的过度防御编程模式，主要集中在3个区域：\n1. safe_url_for 和 schedule_service.py 的多层嵌套（可显著简化）\n2. launcher.py 的部分冗余防御（信噪比低但不紧急）\n3. 若干对不可能失败操作的"保险型" try/except（纯代码噪音）\n\n建议优先简化 OD1 和 OD2（代码可读性提升最大），其余可纳入日常重构。
- 下一步建议:

  优先简化 OD1（safe_url_for 5层→2层）和 OD2（告警合并 10行→1行），这两处改动最简单、可读性提升最大。
- 问题:
  - [中] 可维护性: safe_url_for 的5层嵌套异常处理
  - [中] 可维护性: 告警合并10行代码含死代码和三层嵌套
  - [低] 可维护性: 相邻函数防御策略不一致（_count_internal_ops vs _collect_selected_resource_ids）
  - [低] 可维护性: launcher.py 约15处对不可能失败操作的冗余异常捕获
  - [低] 可维护性: plugins.py 60行代码7个 except Exception 形成嵌套迷宫
  - [低] 可维护性: ui_mode.py 中对 getattr(带默认值) 和 request.endpoint 的冗余异常捕获

### M5 · 第五轮：对 M4 过度防御性编程结论的三轮严谨复核

- 状态: 已完成
- 记录时间: 2026-04-02T17:56:53.140Z
- 已审模块: web/ui_mode.py, core/services/scheduler/schedule_service.py, core/services/scheduler/resource_pool_builder.py, web/routes/scheduler_batch_detail.py, web/bootstrap/launcher.py, web/bootstrap/plugins.py, web/bootstrap/security.py, web/bootstrap/static_versioning.py, web/error_handlers.py
- 摘要:

  针对 M4 中标记的6个"过度防御性编程"发现（OD1-OD6），进行三轮严谨复核，重点验证每处防御是否真的"不可能失败"。\n\n### 第一轮：技术机制验证\n\n发现一个被 M4 忽略的关键技术细节：**Flask 的 `request` 和 `current_app` 是 `LocalProxy` 代理对象**。当上下文异常时，代理抛出的是 `RuntimeError`（不是 `AttributeError`）。Python 的 `getattr(obj, name, default)` **只捕获 `AttributeError`**，`RuntimeError` 会穿透。因此之前"getattr 带默认值不会失败"的判断对 Flask 代理对象**不成立**。这直接影响 OD1 和 OD6 的结论。\n\n### 第二轮：逐项复核\n\n| 发现 | M4判定 | 复核结论 | 修正理由 |\n|------|--------|----------|----------|\n| OD1 | 中-过度 | **低-可优化** | 每层防御 Flask 代理 RuntimeError，有合理理由；但第3+4层可合并 |\n| OD2 | 中-过度 | **中-确认过度** | build_resource_pool 返回 List[str]，list.extend(list) 不可能失败 |\n| OD3 | 低-过度 | **低-确认过度** | 相邻函数证据确凿 |\n| OD4 | 低-~15处 | **低-仅1处确认** | 除 str(str).strip() 外，其余 int() 防御在无运行时类型检查下有理由 |\n| OD5 | 低-迷宫 | **低-可精简** | 7个中仅2个（logger 包裹）可删，3个故障域不宜合并 |\n| OD6 | 低-冗余 | **撤回** | Flask LocalProxy 的 RuntimeError 不被 getattr 默认值捕获 |\n\n### 第三轮：补充模块检查\n\n检查了尚未覆盖的 error_handlers.py、security.py、static_versioning.py：\n- error_handlers.py：代码简洁，无过度防御问题。\n- security.py：第22-25行 `str(log_dir).strip()` 的 try/except 与 OD4 同类（来自 app.config 的值可能是任何类型），在 Flask 配置场景下发生异常的概率极低但理论上存在。4处 `app.logger.warning/info` 包裹与 OD5 同类。\n- static_versioning.py：代码干净，try/except 用法全部合理。
- 结论:

  经过三轮严谨复核，M4 的6个 OD 发现中：\n- **2个确认成立**（OD2 告警合并、OD3 不一致）\n- **1个应降级**（OD1 从中→低，结构可优化但非"过度"）\n- **1个应撤回**（OD6 对 Flask 代理 getattr 的判断有误）\n- **2个需大幅缩窄范围**（OD4 从15处→仅1处确认、OD5 从"迷宫"→"可精简"）\n\n核心纠正：Flask 的 `request` 和 `current_app` 是 `LocalProxy`，在上下文异常时会抛 `RuntimeError`，而 `getattr(proxy, name, default)` **只捕获 `AttributeError`**，不捕获 `RuntimeError`。之前 M4 中"getattr 带默认值不会失败"的判断**对 Flask 代理对象不成立**。
- 下一步建议:

  1. 修复 OD2（告警合并死代码+三层嵌套→1行）和 OD3（删除不一致的 try/except）——这两个是唯一确认的过度防御问题。\n2. OD1 可选择合并 safe_url_for 的第3+4层为一个 try 块（风格改进，非必须）。\n3. 其余 OD4/5/6 建议保留或仅在日常重构中顺带精简。
- 问题:
  - [低] 可维护性: OD1 降级：safe_url_for 嵌套有合理理由，仅结构可优化
  - [低] 可维护性: OD6 撤回：Flask LocalProxy 的 getattr 确实需要 try/except
  - [低] 可维护性: OD4 缩窄：launcher.py 仅1处确认多余（str 转 str），其余有合理理由
  - [低] 可维护性: OD5 缩窄：plugins.py 结构冗长但非"迷宫"，每层保护不同故障域

## 最终结论

经过 M5 三轮严谨复核修正后的最终结论：\n\n**真正确认的过度防御问题仅2处**：OD2（告警合并三层嵌套+死代码→1行）和 OD3（相邻函数防御策略不一致）。\n\nM4 中标记的其余4处（OD1/4/5/6）经复核发现均有合理防御理由，尤其是 Flask LocalProxy 代理对象在上下文异常时抛 RuntimeError（不是 AttributeError），导致 getattr 的默认值机制无法捕获——这使得 OD1 和 OD6 的"过度"判断不成立。\n\n最高优先级仍是 SF1（48处日志断链，1行修复）。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnhqjtfa-cp96m8",
  "createdAt": "2026-04-02T00:00:00.000Z",
  "updatedAt": "2026-04-02T17:57:36.837Z",
  "finalizedAt": "2026-04-02T17:57:36.837Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "静默回退与隐藏BUG专项审查",
    "date": "2026-04-02",
    "overview": "专项审查：web/与web_new_test/中的静默回退、过度兜底、隐藏BUG的异常吞掉模式"
  },
  "scope": {
    "markdown": "# 静默回退与隐藏BUG专项审查\n\n**审查日期**: 2026-04-02  \n**审查范围**: `web/` 和 `web_new_test/` 中所有 `except ... pass`、默认值兜底、静默降级逻辑  \n**审查策略**: 三轮递进式\n\n## 审查计划\n\n### 第一轮：启动链路与请求生命周期中的静默吞错\n- factory.py 的 before_request / after_request / teardown 中的异常处理\n- 运行时锁、退出备份等关键流程的异常吞掉\n\n### 第二轮：路由层的过度兜底与静默回退\n- Excel导入确认阶段的错误行处理逻辑\n- 批量操作中 continue 跳过错误但不充分记录\n- 数据标准化中的宽松回退（未知值原样返回）\n\n### 第三轮：跨层引用链中的静默断裂\n- logger=None 在服务层→仓库层→数据库层的传播链\n- 模板渲染中的 safe_url_for 返回 None 后的下游影响\n- ui_mode 降级路径中的日志与可观测性缺口"
  },
  "summary": {
    "latestConclusion": "经过 M5 三轮严谨复核修正后的最终结论：\\n\\n**真正确认的过度防御问题仅2处**：OD2（告警合并三层嵌套+死代码→1行）和 OD3（相邻函数防御策略不一致）。\\n\\nM4 中标记的其余4处（OD1/4/5/6）经复核发现均有合理防御理由，尤其是 Flask LocalProxy 代理对象在上下文异常时抛 RuntimeError（不是 AttributeError），导致 getattr 的默认值机制无法捕获——这使得 OD1 和 OD6 的\"过度\"判断不成立。\\n\\n最高优先级仍是 SF1（48处日志断链，1行修复）。",
    "recommendedNextAction": "1. 立即修复 SF1（1行代码解决48处日志断链）\\n2. 简化 OD2（告警合并 10行→1行，含死代码清理）\\n3. 修复 OD3（删除 _count_internal_ops 的多余 try/except）\\n4. 可选：合并 safe_url_for 第3+4层 try 块（纯风格优化）",
    "reviewedModules": [
      "web/bootstrap/factory.py",
      "data/repositories/base_repo.py",
      "core/infrastructure/transaction.py",
      "core/services/common/safe_logging.py",
      "web/routes/normalizers.py",
      "web/routes/scheduler_utils.py",
      "core/services/common/excel_validators.py",
      "web/routes/process_excel_routes.py",
      "web/routes/scheduler_excel_batches.py",
      "templates/",
      "web_new_test/templates/",
      "web/ui_mode.py",
      "web/viewmodels/scheduler_analysis_vm.py",
      "core/services/scheduler/schedule_service.py",
      "web/routes/",
      "web/routes/scheduler_batch_detail.py",
      "web/bootstrap/launcher.py",
      "web/bootstrap/plugins.py",
      "core/services/scheduler/resource_pool_builder.py",
      "web/bootstrap/security.py",
      "web/bootstrap/static_versioning.py",
      "web/error_handlers.py"
    ]
  },
  "stats": {
    "totalMilestones": 5,
    "completedMilestones": 5,
    "totalFindings": 15,
    "severity": {
      "high": 0,
      "medium": 3,
      "low": 12
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "第一轮：启动链路与请求生命周期的静默吞错分析",
      "status": "completed",
      "recordedAt": "2026-04-02T17:19:44.745Z",
      "summaryMarkdown": "完成对启动链路和请求生命周期中静默吞错模式的深度分析。核心发现：48处 logger=None 穿透导致整个服务层→仓库层日志链断开。factory.py 请求生命周期中的异常处理总体合理，大部分 except 都有日志记录或合理降级。",
      "conclusionMarkdown": "logger=None 穿透链是最严重的静默回退问题，影响面广但不会崩溃。factory.py 的请求生命周期异常处理总体合理。",
      "evidence": [],
      "reviewedModules": [
        "web/bootstrap/factory.py",
        "data/repositories/base_repo.py",
        "core/infrastructure/transaction.py",
        "core/services/common/safe_logging.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "SF1",
        "SF2"
      ]
    },
    {
      "id": "M2",
      "title": "第二轮：路由层过度兜底与静默回退分析",
      "status": "completed",
      "recordedAt": "2026-04-02T17:21:53.481Z",
      "summaryMarkdown": "完成对路由层过度兜底和静默回退的分析。重点验证了：\\n\\n1. **数据标准化的宽松回退是安全的**：normalizers.py 中的\"未知值原样返回\"策略被 excel_validators.py 中的严格校验正确拦截\\n2. **safe_url_for 的使用是正确的**：所有模板（V1和V2）都对 None 返回值做了 if 检查\\n3. **路由层大部分 except Exception 都有日志**：40 处中约 35 处有 current_app.logger.exception() 记录\\n4. **Excel 导入确认阶段的部分导入风险**：理论上可能在事务中部分成功部分失败，但 baseline 签名降低了发生概率\\n5. **排产服务层的告警合并逻辑过度防御**：三层嵌套 try/except 可能丢失资源池告警",
      "conclusionMarkdown": "路由层的异常处理整体规范——大部分 except Exception 都有日志记录。标准化函数的\"未知值原样返回\"策略被下游校验器正确拦截，不构成数据完整性风险。",
      "evidence": [],
      "reviewedModules": [
        "web/routes/normalizers.py",
        "web/routes/scheduler_utils.py",
        "core/services/common/excel_validators.py",
        "web/routes/process_excel_routes.py",
        "web/routes/scheduler_excel_batches.py",
        "templates/",
        "web_new_test/templates/"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "SF3",
        "SF4"
      ]
    },
    {
      "id": "M3",
      "title": "第三轮：跨层引用链与 UI 降级路径的静默断裂分析",
      "status": "completed",
      "recordedAt": "2026-04-02T17:23:02.808Z",
      "summaryMarkdown": "完成对 ui_mode.py 中 23 处 except Exception 的逐一审查，以及跨层引用链中静默断裂的分析。\\n\\n**ui_mode.py 审查结论：**\\n所有 23 处 except Exception 都是有意设计的降级保护，目的是保持页面可用性。关键降级路径（V2 env 创建失败、safe_url_for 的 BuildError）都有日志记录。\\n\\n**跨层引用链总结：**\\n1. logger=None 穿透 → 已在 SF1 中完整记录\\n2. safe_url_for 返回 None → 所有模板都做了 if 检查 → 安全\\n3. V2 env 不可用时回退 V1 → 有一次性 warning 日志 → 安全\\n4. DB 不可用时 ui_mode 回退默认 → 合理降级",
      "conclusionMarkdown": "ui_mode.py 中的静默回退设计整体合理——在不影响页面可用性的前提下做降级，且有一次性 warning 日志保障可观测性。跨层引用链的主要问题已在第一轮 SF1 中覆盖。",
      "evidence": [],
      "reviewedModules": [
        "web/ui_mode.py",
        "web/viewmodels/scheduler_analysis_vm.py",
        "core/services/scheduler/schedule_service.py"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "SF5"
      ]
    },
    {
      "id": "M4",
      "title": "第四轮：过度防御性编程导致代码不必要复杂的模式分析",
      "status": "completed",
      "recordedAt": "2026-04-02T17:49:30.582Z",
      "summaryMarkdown": "针对审查报告中已标记的 SF2/SF3 以及其他未覆盖区域，进行过度防御性编程导致代码不优雅、不简洁的专项分析。聚焦三类反模式：\\n\\n1. **多层嵌套异常捕获**：保护→保护→再保护的\"俄罗斯套娃\"结构\\n2. **对不可能失败操作的防御**：`str()`、`getattr(obj, attr, default)`、整数字面量的 `int()` 等永远不会抛异常的操作被 try/except 包裹\\n3. **相邻函数防御策略不一致**：相同数据结构、相同访问模式，但一个有 try/except 另一个没有\\n\\n### 核心发现\\n\\n**OD1 — safe_url_for 的5层嵌套异常处理**（中）\\n第267-295行。在 BuildError 的处理分支中嵌套了4层 try/except，核心目的仅是\"记录一条 warning 日志\"。getattr(request, \\\"path\\\", \\\"\\\") 使用了默认值不可能抛异常，但仍被单独包裹；日志记录本身又被包裹；最外层再兜一个 except Exception。可从5层简化为2层而不丧失任何功能安全。\\n\\n**OD2 — schedule_service.py 三层嵌套 + 死代码**（中，是 SF3 的升级分析）\\n第392-400行。第393行 `if algo_warnings is None` 是永远为假的死代码（第371-372行已保证非 None）。`algo_warnings.extend(list(pool_warnings))` 是一行的事，被包了3层嵌套 try/except。整块10行代码可替换为1行。\\n\\n**OD3 — _count_internal_ops 与 _collect_selected_resource_ids 的不一致**（低，是 SF2 的升级分析）\\n两个函数紧邻定义（第18行和第30行），迭代相同的 ops 列表，使用完全相同的 getattr(op, \\\"source\\\", \\\"\\\") 模式，但只有 _count_internal_ops 有 try/except Exception: return 0。_collect_selected_resource_ids 没有任何防御却运行正常——这直接证明 _count_internal_ops 的 try/except 是多余的。\\n\\n**OD4 — launcher.py 50处 except Exception 中约15处对不可能失败操作的防御**（低）\\n- 第59-62行：`int(p)` 其中 p 来自硬编码整数字面量列表 [5000, 5705, ...]，永远不会失败\\n- 第188-192行：`str(cfg_log_dir).strip()` — str() 对任何对象都不会抛异常\\n- 第306-308行、339-342行：`int(pid)` 其中 pid 的类型签名已是 int\\n- 约10处对 logger.warning() 调用本身的 try/except — Python 标准 logging 库设计为永不抛异常\\n\\n**OD5 — plugins.py 整文件7个 except Exception 嵌套迷宫**（低）\\n60行代码中7个 except Exception，其中至少3个（第23-26、32-35行）是对日志调用本身的防御。整个文件可以通过一个顶层 try/except + 简化内部逻辑来大幅减少层数。\\n\\n**OD6 — _resolve_manual_endpoint 和 _resolve_manual_src 的冗余防御**（低）\\n- 第40-43行：`request.endpoint` 在有效请求上下文中（第38行已检查 has_request_context()）不会抛异常\\n- 第66-75行：`getattr(request, \\\"full_path\\\", \\\"\\\")` 带默认值不会抛 AttributeError，但套了两个串联的 try/except 块\\n- 第244-246行：_warn_v2_render_fallback_once 中 `getattr(request, \\\"path\\\", \\\"\\\")` 同理",
      "conclusionMarkdown": "确认存在系统性的过度防御编程模式，主要集中在3个区域：\\n1. safe_url_for 和 schedule_service.py 的多层嵌套（可显著简化）\\n2. launcher.py 的部分冗余防御（信噪比低但不紧急）\\n3. 若干对不可能失败操作的\"保险型\" try/except（纯代码噪音）\\n\\n建议优先简化 OD1 和 OD2（代码可读性提升最大），其余可纳入日常重构。",
      "evidence": [],
      "reviewedModules": [
        "web/ui_mode.py",
        "core/services/scheduler/schedule_service.py",
        "web/routes/scheduler_batch_detail.py",
        "web/bootstrap/launcher.py",
        "web/bootstrap/plugins.py"
      ],
      "recommendedNextAction": "优先简化 OD1（safe_url_for 5层→2层）和 OD2（告警合并 10行→1行），这两处改动最简单、可读性提升最大。",
      "findingIds": [
        "OD1",
        "OD2",
        "OD3",
        "OD4",
        "OD5",
        "OD6"
      ]
    },
    {
      "id": "M5",
      "title": "第五轮：对 M4 过度防御性编程结论的三轮严谨复核",
      "status": "completed",
      "recordedAt": "2026-04-02T17:56:53.140Z",
      "summaryMarkdown": "针对 M4 中标记的6个\"过度防御性编程\"发现（OD1-OD6），进行三轮严谨复核，重点验证每处防御是否真的\"不可能失败\"。\\n\\n### 第一轮：技术机制验证\\n\\n发现一个被 M4 忽略的关键技术细节：**Flask 的 `request` 和 `current_app` 是 `LocalProxy` 代理对象**。当上下文异常时，代理抛出的是 `RuntimeError`（不是 `AttributeError`）。Python 的 `getattr(obj, name, default)` **只捕获 `AttributeError`**，`RuntimeError` 会穿透。因此之前\"getattr 带默认值不会失败\"的判断对 Flask 代理对象**不成立**。这直接影响 OD1 和 OD6 的结论。\\n\\n### 第二轮：逐项复核\\n\\n| 发现 | M4判定 | 复核结论 | 修正理由 |\\n|------|--------|----------|----------|\\n| OD1 | 中-过度 | **低-可优化** | 每层防御 Flask 代理 RuntimeError，有合理理由；但第3+4层可合并 |\\n| OD2 | 中-过度 | **中-确认过度** | build_resource_pool 返回 List[str]，list.extend(list) 不可能失败 |\\n| OD3 | 低-过度 | **低-确认过度** | 相邻函数证据确凿 |\\n| OD4 | 低-~15处 | **低-仅1处确认** | 除 str(str).strip() 外，其余 int() 防御在无运行时类型检查下有理由 |\\n| OD5 | 低-迷宫 | **低-可精简** | 7个中仅2个（logger 包裹）可删，3个故障域不宜合并 |\\n| OD6 | 低-冗余 | **撤回** | Flask LocalProxy 的 RuntimeError 不被 getattr 默认值捕获 |\\n\\n### 第三轮：补充模块检查\\n\\n检查了尚未覆盖的 error_handlers.py、security.py、static_versioning.py：\\n- error_handlers.py：代码简洁，无过度防御问题。\\n- security.py：第22-25行 `str(log_dir).strip()` 的 try/except 与 OD4 同类（来自 app.config 的值可能是任何类型），在 Flask 配置场景下发生异常的概率极低但理论上存在。4处 `app.logger.warning/info` 包裹与 OD5 同类。\\n- static_versioning.py：代码干净，try/except 用法全部合理。",
      "conclusionMarkdown": "经过三轮严谨复核，M4 的6个 OD 发现中：\\n- **2个确认成立**（OD2 告警合并、OD3 不一致）\\n- **1个应降级**（OD1 从中→低，结构可优化但非\"过度\"）\\n- **1个应撤回**（OD6 对 Flask 代理 getattr 的判断有误）\\n- **2个需大幅缩窄范围**（OD4 从15处→仅1处确认、OD5 从\"迷宫\"→\"可精简\"）\\n\\n核心纠正：Flask 的 `request` 和 `current_app` 是 `LocalProxy`，在上下文异常时会抛 `RuntimeError`，而 `getattr(proxy, name, default)` **只捕获 `AttributeError`**，不捕获 `RuntimeError`。之前 M4 中\"getattr 带默认值不会失败\"的判断**对 Flask 代理对象不成立**。",
      "evidence": [],
      "reviewedModules": [
        "web/ui_mode.py",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/resource_pool_builder.py",
        "web/routes/scheduler_batch_detail.py",
        "web/bootstrap/launcher.py",
        "web/bootstrap/plugins.py",
        "web/bootstrap/security.py",
        "web/bootstrap/static_versioning.py",
        "web/error_handlers.py"
      ],
      "recommendedNextAction": "1. 修复 OD2（告警合并死代码+三层嵌套→1行）和 OD3（删除不一致的 try/except）——这两个是唯一确认的过度防御问题。\\n2. OD1 可选择合并 safe_url_for 的第3+4层为一个 try 块（风格改进，非必须）。\\n3. 其余 OD4/5/6 建议保留或仅在日常重构中顺带精简。",
      "findingIds": [
        "OD1-REV",
        "OD6-REV",
        "OD4-REV",
        "OD5-REV"
      ]
    }
  ],
  "findings": [
    {
      "id": "SF1",
      "severity": "medium",
      "category": "other",
      "title": "48处 logger=None 穿透导致日志链断开",
      "descriptionMarkdown": "在 web/routes/ 目录中有 48处 使用 getattr(g, 'app_logger', None) 传入 logger 参数。由于 g.app_logger 从未被设置，这 48 处全部传入 None。经过逐层代码追踪：路由层 logger=None → 服务层 self.logger=None → 仓库层 self.logger=None → base_repo._log_db_error 第116行 if not self.logger: return 直接跳过 → 数据库错误日志被完全丢弃。不会崩溃，但 SQL 错误详情、参数信息等关键排障信息无法被记录。",
      "recommendationMarkdown": "在 _open_db 钩子中添加一行 g.app_logger = current_app.logger",
      "evidence": [
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 262,
          "lineEnd": 294,
          "symbol": "_open_db"
        },
        {
          "path": "data/repositories/base_repo.py",
          "lineStart": 115,
          "lineEnd": 117,
          "symbol": "_log_db_error"
        },
        {
          "path": "core/services/common/safe_logging.py",
          "lineStart": 6,
          "lineEnd": 8,
          "symbol": "safe_log"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "data/repositories/base_repo.py"
        },
        {
          "path": "core/services/common/safe_logging.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "SF2",
      "severity": "low",
      "category": "other",
      "title": "_count_internal_ops 整个循环包在 try/except 中静默返回 0",
      "descriptionMarkdown": "_count_internal_ops 函数把整个循环包在一个 try/except Exception: return 0 中。如果工序列表中任意一个对象的属性访问出错，整个函数静默返回 0 不记录任何日志，导致下游 _resolve_lazy_select_enabled 误判。",
      "recommendationMarkdown": "去掉外层宽泛异常捕获，仅捕获已知可预期异常类型",
      "evidence": [
        {
          "path": "web/routes/scheduler_batch_detail.py",
          "lineStart": 18,
          "lineEnd": 27,
          "symbol": "_count_internal_ops"
        },
        {
          "path": "web/routes/scheduler_batch_detail.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "SF3",
      "severity": "low",
      "category": "other",
      "title": "排产服务层告警合并的三层嵌套 try/except 可能丢失资源池告警",
      "descriptionMarkdown": "在 schedule_service.py 第 392-400 行，合并资源池告警信息时使用了三层嵌套 try/except。第 393 行的 `if algo_warnings is None` 永远为假（因为第 371-372 行已保证不为 None）。第二层和第三层 except 会在 pool_warnings 为非可迭代类型时静默吃掉异常，可能导致重要的资源池告警信息丢失。",
      "recommendationMarkdown": "简化为单层 try/except，并在 except 中记录 warning 日志而不是完全静默",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 390,
          "lineEnd": 401
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "SF4",
      "severity": "low",
      "category": "other",
      "title": "Excel 导入确认阶段允许部分失败但事务仍提交",
      "descriptionMarkdown": "在 process_excel_routes.py 的 excel_routes_confirm 函数中，第 203-218 行先检查“只要有错误行就全部拒绝”，但第 254-265 行的循环中仍然有 `except AppError` 捕获并 continue 的逻辑。这意味着如果预览通过但实际写入时抛出 AppError（如数据库状态在预览和确认之间变化），部分数据会被导入而部分被跳过，事务仍然提交。虽然 baseline 签名模式大大降低了这种发生的概率，但理论上仍可能出现部分导入的情况。",
      "recommendationMarkdown": "考虑在循环结束后检查 error_count，如果大于 0 则回滚事务（或在 AppError 捕获时记录 warning 日志）",
      "evidence": [
        {
          "path": "web/routes/process_excel_routes.py",
          "lineStart": 233,
          "lineEnd": 265
        },
        {
          "path": "web/routes/process_excel_routes.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "SF5",
      "severity": "low",
      "category": "other",
      "title": "ui_mode.py 的 23 处 except Exception 均为有意设计的降级",
      "descriptionMarkdown": "ui_mode.py 中有 23 处 except Exception，通过逐一审查确认：\n\n**合理的静默回退（不需修改）：**\n- _read_ui_mode_from_db → DB 不可用时回退默认模式（避免整页 500）\n- get_ui_mode 的 Cookie 读取 → Cookie 损坏时回退 DB/默认\n- safe_url_for 的 BuildError 捕获 → 有一次性 warning 日志\n- g.ui_mode 赋值失败 → 只影响下游可观测性，不影响渲染\n- init_ui_mode 中 V2 env 创建失败 → 有 warning 日志 + 回退 V1\n- env.globals 写入失败 → 几乎不可能发生\n\n**结论：所有静默回退都是有意设计，为了保持“页面可用性”。关键降级路径有日志覆盖（_warn_v2_render_fallback_once、safe_url_for 的 warning），不存在隐藏 BUG 的风险。",
      "recommendationMarkdown": null,
      "evidence": [],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "wont_fix"
    },
    {
      "id": "OD1",
      "severity": "medium",
      "category": "maintainability",
      "title": "safe_url_for 的5层嵌套异常处理",
      "descriptionMarkdown": "safe_url_for（第267-295行）在 BuildError 处理分支中嵌套了4层 try/except，核心目的仅是\"记录一条 warning 日志\"。具体结构：\n\n- 第1层：`try: url_for()` / `except BuildError` — 合理\n- 第2层：`try: logged = getattr(g, ...)` — 合理\n- 第3层：`try: path = getattr(request, 'path', '')` — **多余**，getattr 带默认值不会抛异常\n- 第4层：`try: current_app.logger.warning(...)` — **过度**，标准 logging 不会抛异常\n- 第5层：`except Exception: return None` — 兜底层\n\n30行函数中有15行是异常处理代码，占比50%。简化后可从30行缩减到15行。",
      "recommendationMarkdown": "合并第3、4层到第2层的 try 体中，删除对 getattr(request, 'path', '') 的独立 try/except。简化为：外层捕获 BuildError，内层一个 try 完成日志记录（包含 path 获取和 logger.warning），最外层一个 except Exception 兜底。",
      "evidence": [
        {
          "path": "web/ui_mode.py",
          "lineStart": 259,
          "lineEnd": 295,
          "symbol": "safe_url_for"
        },
        {
          "path": "web/ui_mode.py"
        }
      ],
      "relatedMilestoneIds": [
        "M4"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "OD2",
      "severity": "medium",
      "category": "maintainability",
      "title": "告警合并10行代码含死代码和三层嵌套",
      "descriptionMarkdown": "schedule_service.py 第391-400行的告警合并逻辑：\n\n```python\ntry:\n    if algo_warnings is None:  # ← 死代码：第371-372行保证非 None\n        algo_warnings = []\n    algo_warnings.extend(list(pool_warnings))\nexcept Exception:\n    try:\n        algo_warnings = list(algo_warnings or []) + list(pool_warnings or [])\n    except Exception:\n        algo_warnings = list(pool_warnings or [])\n```\n\n问题：\n1. `if algo_warnings is None` 永远为假（死代码）\n2. `algo_warnings.extend(list(pool_warnings))` 不需要 try/except — algo_warnings 是 list，pool_warnings 是函数返回的 list\n3. 第二/三层 except 是\"如果 extend 失败就用加法，如果加法也失败就丢弃原有告警\"——这种级联降级在实践中毫无意义\n\n10行代码可替换为1行：`algo_warnings.extend(pool_warnings)`",
      "recommendationMarkdown": "替换整个 if pool_warnings 块为：`algo_warnings.extend(pool_warnings)`。如果确实需要防御 pool_warnings 的类型，最多加一行类型检查。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 391,
          "lineEnd": 401
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        }
      ],
      "relatedMilestoneIds": [
        "M4"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "OD3",
      "severity": "low",
      "category": "maintainability",
      "title": "相邻函数防御策略不一致（_count_internal_ops vs _collect_selected_resource_ids）",
      "descriptionMarkdown": "scheduler_batch_detail.py 中两个紧邻定义的函数（第18行和第30行），迭代相同的 ops: List[Any] 参数，使用完全相同的属性访问模式 `(getattr(op, 'source', '') or '').strip().lower()`，并与相同的 SourceType.INTERNAL.value 比较。\n\n但 _count_internal_ops 用 `try/except Exception: return 0` 包裹整个函数体，而 _collect_selected_resource_ids 没有任何异常处理。\n\n后者（做更复杂操作：还访问 machine_id、operator_id、supplier_id）在没有 try/except 的情况下运行正常，**直接证明** _count_internal_ops 的 try/except 是不必要的。同时造成了代码风格的不一致。",
      "recommendationMarkdown": "删除 _count_internal_ops 的 try/except 包裹，使其与相邻函数风格一致。",
      "evidence": [
        {
          "path": "web/routes/scheduler_batch_detail.py",
          "lineStart": 18,
          "lineEnd": 27,
          "symbol": "_count_internal_ops"
        },
        {
          "path": "web/routes/scheduler_batch_detail.py",
          "lineStart": 30,
          "lineEnd": 44,
          "symbol": "_collect_selected_resource_ids"
        },
        {
          "path": "web/routes/scheduler_batch_detail.py"
        }
      ],
      "relatedMilestoneIds": [
        "M4"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "OD4",
      "severity": "low",
      "category": "maintainability",
      "title": "launcher.py 约15处对不可能失败操作的冗余异常捕获",
      "descriptionMarkdown": "launcher.py 全文934行中有50处 except Exception，其中约15处保护的操作在 Python 中永远不会抛异常：\n\n**对 str() 的防御**（第188-192行）：\n`str(cfg_log_dir).strip()` — Python 的 str() 对任何对象都不会抛异常（最坏情况调用 __repr__），.strip() 对字符串也不会抛异常。\n\n**对已知 int 类型的 int() 防御**（第59-62行）：\n`int(p)` 其中 p 来自硬编码列表 [preferred, 5000, 5705, ...]，整数字面量 int(5000) 永远不会抛 ValueError。\n\n**对类型签名为 int 的参数做 int() 防御**（第306-308、339-342行）：\n`int(pid)` 其中 pid 的函数签名已标注为 int。\n\n**对 logger.warning() 的防御**（约10处如第32、854行）：\nPython 的 logging.Logger.handle() 方法内部已有 try/except，设计为永不将异常传播到调用方。对 logger 调用再包一层 try/except 纯粹是噪音。",
      "recommendationMarkdown": "分批清理：优先删除 str().strip() 和整数字面量 int() 的无意义 try/except；logger 调用的防御可纳入下次重构。",
      "evidence": [
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 188,
          "lineEnd": 192
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 59,
          "lineEnd": 62
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 306,
          "lineEnd": 308
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 339,
          "lineEnd": 342
        },
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 851,
          "lineEnd": 855
        },
        {
          "path": "web/bootstrap/launcher.py"
        }
      ],
      "relatedMilestoneIds": [
        "M4"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "OD5",
      "severity": "low",
      "category": "maintainability",
      "title": "plugins.py 60行代码7个 except Exception 形成嵌套迷宫",
      "descriptionMarkdown": "bootstrap_plugins 函数60行中有7个 except Exception 块，形成多层嵌套的\"洋葱型\"错误处理结构。其中3处（第23-26、32-35、50-51行）是对日志调用本身的防御——`try: logger.warning(...) except Exception: pass`。\n\nPython 标准 logging 库设计为不抛异常（Logger.handle 内部已有保护），因此这些包裹层纯粹增加缩进噪音。\n\n此外，连接关闭操作（第53-56行）`try: conn0.close() except Exception: pass` 虽合理但可以用 contextmanager 模式简化。",
      "recommendationMarkdown": "1. 删除对 logger.warning/error 调用的 try/except 包裹\n2. 考虑使用 contextmanager 管理数据库连接\n3. 整体简化为：一个顶层 try/finally 管理 conn0 生命周期 + 内部逻辑直接调用",
      "evidence": [
        {
          "path": "web/bootstrap/plugins.py",
          "lineStart": 10,
          "lineEnd": 58,
          "symbol": "bootstrap_plugins"
        },
        {
          "path": "web/bootstrap/plugins.py"
        }
      ],
      "relatedMilestoneIds": [
        "M4"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "OD6",
      "severity": "low",
      "category": "maintainability",
      "title": "ui_mode.py 中对 getattr(带默认值) 和 request.endpoint 的冗余异常捕获",
      "descriptionMarkdown": "ui_mode.py 中有多处对不可能失败操作的防御：\n\n1. **第40-43行** `_resolve_manual_endpoint`：`request.endpoint` 在 has_request_context() 检查后不会抛异常\n2. **第66-75行** `_resolve_manual_src`：`getattr(request, 'full_path', '')` 使用了默认值，不会抛 AttributeError。但用了两个串联的 try/except 块来分别获取 full_path 和 path\n3. **第244-246行** `_warn_v2_render_fallback_once`：`getattr(request, 'path', '')` 同理\n4. **第279-282行** safe_url_for 内部：同上\n\n这些操作使用了 Python getattr 的安全模式（提供默认值），不存在 AttributeError 的可能。try/except 增加的是纯代码噪音，不提供额外安全性。",
      "recommendationMarkdown": "删除上述函数中对 getattr(obj, attr, default) 和 request.endpoint 的 try/except 包裹。如需防御 request context 无效的极端情况，第一行的 has_request_context() 检查已足够。",
      "evidence": [
        {
          "path": "web/ui_mode.py",
          "lineStart": 35,
          "lineEnd": 43,
          "symbol": "_resolve_manual_endpoint"
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 61,
          "lineEnd": 75,
          "symbol": "_resolve_manual_src"
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 244,
          "lineEnd": 256,
          "symbol": "_warn_v2_render_fallback_once"
        },
        {
          "path": "web/ui_mode.py"
        }
      ],
      "relatedMilestoneIds": [
        "M4"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "OD1-REV",
      "severity": "low",
      "category": "maintainability",
      "title": "OD1 降级：safe_url_for 嵌套有合理理由，仅结构可优化",
      "descriptionMarkdown": "**M4 原结论**：safe_url_for 5层嵌套\"过度\"，第3/4层对 getattr(request, 'path', '') 和 logger.warning() 的保护\"多余\"。\n\n**复核后纠正**：\n\nFlask 的 `request` 是 `LocalProxy` 代理对象。当请求上下文处于异常状态（如 teardown 回调中、并发边界条件）时，代理的 `__getattribute__` 会抛出 `RuntimeError(\"Working outside of request context\")`。\n\nPython `getattr(obj, name, default)` 的默认值机制**只捕获 `AttributeError`**，不捕获其他异常类型。因此 `getattr(request, 'path', '')` 在 Flask 代理上**不是安全操作**——当代理状态异常时 `RuntimeError` 会穿透 getattr。\n\n同理，`current_app` 也是 `LocalProxy`，`current_app.logger.warning()` 在应用上下文异常时同样可能抛 `RuntimeError`。\n\n**结论**：第3层和第4层的 try/except 都有合理防御理由，不是\"纯噪音\"。但两个相邻的 try 块可以合并为一个（因为它们防御的是同类风险），结构从5层减为3层作为可读性优化。",
      "recommendationMarkdown": "可选优化：将第3层（path获取）和第4层（日志记录）合并为一个 try 块。这是风格改进，不是必须修复。",
      "evidence": [
        {
          "path": "web/ui_mode.py",
          "lineStart": 259,
          "lineEnd": 295,
          "symbol": "safe_url_for"
        },
        {
          "path": "web/ui_mode.py"
        }
      ],
      "relatedMilestoneIds": [
        "M5"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "OD6-REV",
      "severity": "low",
      "category": "maintainability",
      "title": "OD6 撤回：Flask LocalProxy 的 getattr 确实需要 try/except",
      "descriptionMarkdown": "**M4 原结论**：`getattr(request, 'path', '')` 带默认值\"不可能抛异常\"，try/except 是\"纯代码噪音\"。\n\n**复核后撤回**：\n\n这个判断对普通 Python 对象成立，但对 Flask 的 `LocalProxy` **不成立**。技术原因：\n\n1. `getattr(obj, name, default)` 内部机制：先调用 `type(obj).__getattribute__(obj, name)`，如果抛出 `AttributeError` 则返回 default。如果抛出**任何其他异常类型**（如 `RuntimeError`），异常会直接传播。\n\n2. Flask 的 `request` 是 `LocalProxy`。当请求上下文不可用时（teardown、异步边界、测试环境），代理的 `__getattribute__` 抛出的是 `RuntimeError`，不是 `AttributeError`。\n\n3. 因此 `getattr(request, 'path', '')` **不能**安全地回退到默认值——`RuntimeError` 会穿透。\n\n**结论**：ui_mode.py 中所有对 Flask 代理对象做 `getattr` 后包裹 try/except 的代码（第40-43、66-75、244-246、279-282行）都是在防御一个**真实的失败场景**，不是冗余防御。此发现应从过度防御清单中撤回。",
      "recommendationMarkdown": "无需修改。这些 try/except 保护了一个 getattr 默认值机制无法覆盖的真实边界条件。",
      "evidence": [
        {
          "path": "web/ui_mode.py",
          "lineStart": 35,
          "lineEnd": 75
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 279,
          "lineEnd": 282
        },
        {
          "path": "web/ui_mode.py"
        }
      ],
      "relatedMilestoneIds": [
        "M5"
      ],
      "trackingStatus": "accepted_risk"
    },
    {
      "id": "OD4-REV",
      "severity": "low",
      "category": "maintainability",
      "title": "OD4 缩窄：launcher.py 仅1处确认多余（str 转 str），其余有合理理由",
      "descriptionMarkdown": "**M4 原结论**：launcher.py 约15处 except Exception 保护的操作\"永远不会抛异常\"。\n\n**复核后缩窄**：\n\n逐项重新评估：\n\n1. **第188-192行 `str(cfg_log_dir).strip()`**：参数类型 `str | None`，代码已在非 None 分支中。`str(一个str对象)` 确实不会失败。**确认多余**。\n\n2. **第59-62行 `int(p)` 在 pick_port 中**：列表是 `[preferred, 5000, ...]`，`preferred` 参数类型标注为 `int` 但 Python 不做运行时检查。追踪调用方（app.py 第144行），`preferred_port` 虽然已是 int，但 `pick_port` 作为公共函数不应信赖调用方遵守类型约定。**保留合理**。\n\n3. **第306-308行 `int(pid)` 在 _pid_exists**：唯一调用方（第369行）传入的 `pid` 已是 int，但函数是独立的工具函数。对输入做类型防御在系统编程中是惯例。**保留合理**。\n\n4. **logger.warning() 包裹**：`logger` 参数类型为 `Logger | None`，代码已检查非 None。标准 Logger 确实不抛异常，但在启动链路中，logger 可能来自外部传入（如测试中的 mock），额外保护可接受。**争论区，但不算明显过度**。\n\n综上，仅第188-192行的1处可确认为多余。",
      "recommendationMarkdown": "可选清理第188-192行的 try/except，但优先级极低。",
      "evidence": [
        {
          "path": "web/bootstrap/launcher.py",
          "lineStart": 188,
          "lineEnd": 192
        },
        {
          "path": "web/bootstrap/launcher.py"
        }
      ],
      "relatedMilestoneIds": [
        "M5"
      ],
      "trackingStatus": "accepted_risk"
    },
    {
      "id": "OD5-REV",
      "severity": "low",
      "category": "maintainability",
      "title": "OD5 缩窄：plugins.py 结构冗长但非\"迷宫\"，每层保护不同故障域",
      "descriptionMarkdown": "**M4 原结论**：60行7个 except Exception \"形成嵌套迷宫\"，日志调用包裹\"纯粹是缩进噪音\"。\n\n**复核后修正**：\n\n逐层分析7个 except 的保护目标：\n- 第20行：`get_connection()` 失败 → 数据库连接异常 → **必要**\n- 第25行：`logger.warning()` 包裹 → logger 可能是外部传入的自定义对象 → **过度谨慎但不无道理**\n- 第30行：`PluginManager.load_from_base_dir()` 失败 → 第三方插件加载异常 → **必要**\n- 第34行：`logger.error()` 包裹 → 同上 → **过度谨慎**\n- 第38行：`get_plugin_status()` 回退 → 状态查询异常 → **合理降级**\n- 第50行：`OperationLogger(...).info()` → 日志落库失败 → **合理**（不应阻断启动）\n- 第55行：`conn0.close()` → 连接关闭异常 → **标准实践**\n\n7个中仅2个（第25、34行对 logger 调用的包裹）属于\"可精简但非必须\"。整个函数管理3个独立故障域（数据库连接、插件加载、日志落库），每域需独立处理异常，不宜简单合并为\"一个顶层 try\"。",
      "recommendationMarkdown": "可选删除第25行和第34行对 logger 调用的 try/except 包裹。整体结构无需大改——3个故障域需要独立的错误处理边界。",
      "evidence": [
        {
          "path": "web/bootstrap/plugins.py",
          "lineStart": 10,
          "lineEnd": 58,
          "symbol": "bootstrap_plugins"
        },
        {
          "path": "web/bootstrap/plugins.py"
        }
      ],
      "relatedMilestoneIds": [
        "M5"
      ],
      "trackingStatus": "accepted_risk"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:3d8d3a3da2b894db01959a57b465f442bd058cdf7ef4bc830004e05f1e9d06de",
    "generatedAt": "2026-04-02T17:57:36.837Z",
    "locale": "zh-CN"
  }
}
```
