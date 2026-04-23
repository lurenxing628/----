# 技术债务最终合并修复plan三轮深度review
- 日期: 2026-04-05
- 概述: 对 20260405_技术债务最终合并修复plan.md 进行三轮深度审查，验证路径、事实、依赖链与逻辑严谨性
- 状态: 已完成
- 总体结论: 有条件通过

## 评审范围

# 技术债务最终合并修复 plan 三轮深度 review

**审查日期**：2026-04-06
**审查目标**：`.limcode/plans/20260405_技术债务最终合并修复plan.md`
**审查方法**：逐任务验证路径真实性、事实描述准确性、依赖链完整性、逻辑严谨性

## 审查范围
- 第一轮：宏观结构与批次依赖链审查
- 第二轮：逐任务事实核验与路径验证
- 第三轮：交叉引用、边界条件与遗漏检测

## 评审摘要

- 当前状态: 已完成
- 已审模块: plan 宏观结构, 路径与事实核验, 兼容桥依赖链, web/routes/ 跨域导入链, 任务 3 目录迁移策略, 任务 2 装配覆盖范围, 任务 4 配置事实源, 任务 5 持久化签名, 任务 6 算法拆分, 任务 7 数据基础设施, 任务 8 双模板与前端, 任务 9 测试迁移, 任务 10 文档收口, 验证命令完整性, 任务 1-10 逐任务审查, 批次依赖与入口退出条件
- 当前进度: 已记录 3 个里程碑；最新：m3-final-cross-reference
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 8
- 问题严重级别分布: 高 2 / 中 4 / 低 2
- 最新结论: ## 三轮深度审查最终结论 ### 总体评价 这份技术债务最终合并修复 plan 是一份**高质量、高精度**的治理方案。在 17 项可量化关键事实（文件数、行号、参数计数、字段计数、装配点数等）的逐一核验中，**准确率达到 100%**。10 个任务的文件路径覆盖完整，问题归属矩阵与代码现状吻合。这在大型遗产代码治理 plan 中极为难得。 ### 必须在执行前修复的 2 个阻断性 BUG | 编号 | 问题 | 影响 | |---|---|---| | **F01** | 任务 5 删除 `_schedule_with_optional_strict_mode` 后，`schedule_optimizer.py` 第 21/181/551 行的 3 处引用全部断裂。任务 6 只覆盖第 551 行，遗漏第 181 行。 | **执行任务 5 后排产主链立即崩溃** | | **F03** | 任务 3 把 44 个路由文件迁入 `web/routes/domains/*/`，但未处理 50+ 处对根层共享工具（`excel_utils` 22 处、`pagination` 10 处、`normalizers` 7 处等）的相对导入断裂。 | **执行任务 3 后全部页面路由立即崩溃** | ### 应在执行中补充的 4 个中等风险遗漏 | 编号 | 问题 | |---|---| | **F04** | `scheduler_config.py` / `scheduler_batches.py` 跨域导入 `system_utils._safe_next_url`，迁移后无法通过根层共享工具解决 | | **F06** | `persist_schedule` 的 22 参数签名未纳入任务 5 的精简范围，可能消解输入收集器精简成果 | | **F07** | `schedule_optimizer.py` 的 `_cfg_value()` / `_norm_text()` 清理仅一句话提及，缺少具体替换方案和 10 处调用点清单 | | **F08** | 静态资源构建脚本缺乏构建时机、质量门禁集成、清单缺失降级策略等生命周期定义 | ### 低风险注意事项（2 项） - **F02**：`Service(g.db` 装配基线实际为 185 处（plan 称约 182 处），建议以精确值写入治理台账 - **F05**：`scheduler_config.py` 的 6 处装配未显式纳入任务 2 批次 ### 修复建议优先级 1. **立即修复 F01**：在任务 5 步骤 4 中补入 `schedule_optimizer.py` 全部 3 处引用的同步更新 2. **立即修复 F03**：在任务 3 中新增"跨包导入策略"步骤，定义迁移后所有 `from .xxx import` 的替换方案 3. **补充 F04**：把 `_safe_next_url` 提取到根层共享工具 4. **补充 F06**：在步骤 3.5 中明确 `persist_schedule` 签名也随上下文对象一并重构 5. **补充 F07/F08**：细化配置读取替换方案和静态资源构建生命周期 ### 结论 plan 的方向正确、结构完整、事实基础扎实。修复上述 2 个阻断性 BUG 和 4 个中等遗漏后，即可进入执行阶段。建议以"有条件接受"结论处理——修复 F01 和 F03 后方可开工。
- 下一步建议: 立即修复 F01（任务 5 步骤 4 补入 schedule_optimizer.py 的 3 处兼容桥引用同步清理）和 F03（任务 3 补入跨包导入策略步骤），然后补充 F04/F06/F07/F08 的细化方案，修复后即可进入执行阶段。
- 总体结论: 有条件通过

## 评审发现

### 任务 5 与任务 6 之间存在兼容桥删除断裂

- ID: F01
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m1-macro-fact-verify
- 说明:

  任务 5 步骤 4 要求从 schedule_optimizer_steps.py 中删除 _schedule_with_optional_strict_mode，但 schedule_optimizer.py 在 3 处导入/调用该函数：(1) 第 21 行 import；(2) 第 181 行 _run_local_search 内调用；(3) 第 551 行 if best is None 兜底调用。任务 5 只针对 schedule_optimizer_steps.py 定义侧的删除，没有同步清理 schedule_optimizer.py 第 181 行的常规调用点。任务 6 步骤 5.5 只处理第 551 行的 if best is None，遗漏了第 181 行。执行任务 5 后 schedule_optimizer.py 将因 ImportError 立即崩溃。
- 建议:

  应在任务 5 步骤 4 中明确要求同步更新 schedule_optimizer.py 的全部 3 处引用：删除 import、把 _run_local_search 第 181 行改为直接调用 scheduler.schedule(strict_mode=..., ...)、把第 551 行的 if best is None 同步改为直接调用或标记为任务 6 必须同批完成的前置。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:21`
  - `core/services/scheduler/schedule_optimizer.py:181`
  - `core/services/scheduler/schedule_optimizer.py:549-563`
  - `core/services/scheduler/schedule_optimizer.py`

### Service(g.db 装配基线计数近似偏差

- ID: F02
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m1-macro-fact-verify
- 说明:

  plan 称初始基线约 182 处，实际搜索结果为 185 处。偏差不大（约 1.6%），但如果用于门禁阈值判定，可能导致残余数不准。
- 建议:

  建议在任务 2 实施前重新精确计数，并以实际值为基线写入治理台账。
- 证据:
  - `web/routes/`

### 任务 3 路由迁移未处理 50+ 处跨包相对导入

- ID: F03
- 严重级别: 高
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m2-cross-package-import
- 说明:

  plan 任务 3 把 44 个路由文件迁入 web/routes/domains/*/，但未处理这些文件对根层共享工具的相对导入。当前跨域导入分布如下：

  - excel_utils.py：22 个文件导入（遍布全部 5 个域）
  - pagination.py：10 个文件导入（遍布 6 个模块）
  - normalizers.py：7 个文件导入（跨 scheduler/personnel 两域）
  - enum_display.py：3 个 bp 文件导入
  - system_utils.py：6 个文件导入，其中 2 个是 scheduler 域文件（scheduler_config.py 和 scheduler_batches.py）跨域引用 system_utils._safe_next_url
  - team_view_helpers.py：2 个文件导入（跨 personnel / equipment 两域）

  迁移后，所有 `from .excel_utils import` 等相对导入都会解析到 domains/*/ 子包内，导致 ModuleNotFoundError。plan 只说“保留原始文件名，不额外重命名模块短名，降低导入修复成本”，但完全未提及跨包导入路径如何修复。
- 建议:

  必须在任务 3 中新增一个明确的“跨包导入策略”步骤。建议采用以下方案之一：(1) 在 web/routes/domains/ 每个域子包的 __init__.py 中统一重新导出根层共享工具；(2) 将这些导入全部改为绝对导入，如 from web.routes.excel_utils import ...；(3) 保留根层一个薄转发层。无论哪种，都必须明确写进 plan 中并列出受影响的 50+ 处导入。
- 证据:
  - `web/routes/scheduler_config.py:27`
  - `web/routes/scheduler_batches.py:26`
  - `web/routes/scheduler_gantt.py:12`
  - `web/routes/scheduler_config.py`
  - `web/routes/scheduler_batches.py`
  - `web/routes/scheduler_gantt.py`

### scheduler 域跨域导入 system_utils 违反域隔离

- ID: F04
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m2-cross-package-import
- 说明:

  scheduler_config.py 和 scheduler_batches.py 当前用 from .system_utils import _safe_next_url 跨域导入。迁移后，scheduler 域和 system 域分属不同包，该导入无法通过任何“根层共享工具”策略解决——必须要么抽取 _safe_next_url 到根层共享工具，要么用绝对导入。
- 建议:

  建议把 _safe_next_url 从 system_utils.py 抽到根层共享工具（如 excel_utils.py 或新建 navigation_utils.py），避免跨域导入。
- 证据:
  - `web/routes/scheduler_config.py:27`
  - `web/routes/scheduler_batches.py:26`
  - `web/routes/scheduler_config.py`
  - `web/routes/scheduler_batches.py`

### scheduler_config.py 未纳入任务 2 装配收口批次

- ID: F05
- 严重级别: 低
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m2-cross-package-import
- 说明:

  scheduler_config.py 有 6 处 Service(g.db 装配，但不在任务 2 的第一批或第二批迁移清单中。plan 只说“步骤 7 清点残余直接装配点”，但未明确将其纳入或登记到台账。考虑到配置服务是排产系统的高频路径之一，应显式列入某一批次。
- 建议:

  将 scheduler_config.py 添加到任务 2 的第二批或显式登记为台账残余项。
- 证据:
  - `web/routes/scheduler_config.py`

### persist_schedule 22 参数签名未纳入精简范围

- ID: F06
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m3-final-cross-reference
- 说明:

  plan 任务 5 步骤 3.5 声明了 27 字段拆分归属要求，步骤 3 要求精简 collect_schedule_run_input 的 16 参数签名并消除 8 个依赖注入参数。但 persist_schedule() 有 22 个命名参数（svc + 21 个关键字参数），这些参数来自 ScheduleRunInput 和 ScheduleOrchestrationOutcome 的直接拆包。plan 虽然提到了 persist_schedule 消费 22 个参数这一事实，但未明确要求 persist_schedule 签名本身也一并简化，导致拆分 ScheduleRunInput 后 persist_schedule 的 22 参数调用可能被原样保留。
- 建议:

  应在步骤 3.5 或步骤 6 中明确指出 persist_schedule 的调用方式也应随 RunContext 和 OrchestrationOutcome 对象边界一并重构，改为接收完整上下文对象而非 22 个平铺参数。
- 证据:
  - `core/services/scheduler/schedule_persistence.py:244-268`
  - `core/services/scheduler/schedule_service.py:291-314`
  - `core/services/scheduler/schedule_persistence.py`
  - `core/services/scheduler/schedule_service.py`

### schedule_optimizer.py 本地配置读取函数清理方案不具体

- ID: F07
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m3-final-cross-reference
- 说明:

  plan 任务 4 步骤 7 要求清理 schedule_optimizer.py 中本地 _cfg_value() 和 _norm_text()，但只用一句话提及，没有给出具体清理方案。这两个函数定义在第 290 和 294 行，在 optimize_schedule() 内部共被调用约 10 处。plan 未说明替换为何种统一读取门面、受影响的调用点清单、以及规范化逻辑是否由注册表内建提供。
- 建议:

  应在任务 4 步骤 6 或步骤 7 中明确列出替换方案和受影响的约 10 个调用点。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:290-296`
  - `core/services/scheduler/schedule_optimizer.py`

### 静态资源构建入口缺乏生命周期定义

- ID: F08
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: m3-final-cross-reference
- 说明:

  plan 任务 8 步骤 8 新增 scripts/build_static_assets.py 和 static/asset_manifest.json，但未定义构建时机（提交前/部署时/质量门禁中）、未将其纳入 run_quality_gate.py、未确认 Win7 + Python 3.8 兼容性、未定义清单不存在时的降级行为。
- 建议:

  应补充构建时机、质量门禁集成、清单缺失时的可观测降级策略以及 Win7 兼容性确认。
- 证据:
  - `web/bootstrap/static_versioning.py`

## 评审里程碑

### m1-macro-fact-verify · 第一轮：宏观事实核验与路径验证

- 状态: 已完成
- 记录时间: 2026-04-05T17:43:43.017Z
- 已审模块: plan 宏观结构, 路径与事实核验, 兼容桥依赖链
- 摘要:

  逐项核验 plan 中所有可量化事实描述和路径引用，发现一个严重的任务间依赖断裂 BUG 和若干偏差。

  ## 已验证正确的关键事实

  1. **ScheduleService 构造器**：3 参数 + 内部创建 10 个仓储实例 ✅
  2. **GreedyScheduler.schedule()**：56-388 行共 332 行 ✅
  3. **调度服务目录**：45 个文件 ✅
  4. **路由目录**：59 个文件 ✅
  5. **兼容桥函数行号**：全部 6 个兼容桥的行号准确无误 ✅
  6. **collect_schedule_run_input**：16 参数 (1 svc + 7 业务 + 2 类注入 + 6 函数注入) ✅
  7. **ScheduleRunInput**：27 字段 ✅
  8. **gantt_critical_chain._load_rows()**：`except Exception: return []` 存在于 49-53 行 ✅
  9. **static_versioning.py**：3 处静默吞异常全部确认 ✅
  10. **schedule_optimizer.py**：`if best is None` 兜底在 549 行 ✅ / `_parse_date` `_parse_datetime` 在 335-357 行 ✅
  11. **database.py**：612 行混合职责 ✅
  12. **backup.py**：包含 `maintenance_window` + `BackupManager` 等 427 行 ✅
  13. **requirements-dev.txt**：当前仅 `pytest`，缺 `pytest-cov`、`radon`、`ruff` ✅
  14. **test_architecture_fitness.py**：白名单无退出条件 ✅
  15. **Service(g.db 装配计数**：实际 185 处，plan 称"约 182 处"，近似正确 ✅
  16. **路由迁移文件总数**：44 迁移 + 15 保留 = 59 全部吻合 ✅
  17. **调度服务迁移文件总数**：39 迁移 + 6 保留 = 45 全部吻合 ✅
- 结论:

  逐项核验 plan 中所有可量化事实描述和路径引用，发现一个严重的任务间依赖断裂 BUG 和若干偏差。 ## 已验证正确的关键事实 1. **ScheduleService 构造器**：3 参数 + 内部创建 10 个仓储实例 ✅ 2. **GreedyScheduler.schedule()**：56-388 行共 332 行 ✅ 3. **调度服务目录**：45 个文件 ✅ 4. **路由目录**：59 个文件 ✅ 5. **兼容桥函数行号**：全部 6 个兼容桥的行号准确无误 ✅ 6. **collect_schedule_run_input**：16 参数 (1 svc + 7 业务 + 2 类注入 + 6 函数注入) ✅ 7. **ScheduleRunInput**：27 字段 ✅ 8. **gantt_critical_chain._load_rows()**：`except Exception: return []` 存在于 49-53 行 ✅ 9. **static_versioning.py**：3 处静默吞异常全部确认 ✅ 10. **schedule_optimizer.py**：`if best is None` 兜底在 549 行 ✅ / `_parse_date` `_parse_datetime` 在 335-357 行 ✅ 11. **database.py**：612 行混合职责 ✅ 12. **backup.py**：包含 `maintenance_window` + `BackupManager` 等 427 行 ✅ 13. **requirements-dev.txt**：当前仅 `pytest`，缺 `pytest-cov`、`radon`、`ruff` ✅ 14. **test_architecture_fitness.py**：白名单无退出条件 ✅ 15. **Service(g.db 装配计数**：实际 185 处，plan 称"约 182 处"，近似正确 ✅ 16. **路由迁移文件总数**：44 迁移 + 15 保留 = 59 全部吻合 ✅ 17. **调度服务迁移文件总数**：39 迁移 + 6 保留 = 45 全部吻合 ✅
- 证据:
  - `core/services/scheduler/schedule_service.py:49-96`
  - `core/services/scheduler/schedule_input_collector.py:17-45`
  - `core/services/scheduler/schedule_optimizer_steps.py:85-115`
  - `core/services/scheduler/schedule_optimizer.py:21`
  - `core/services/scheduler/schedule_optimizer.py:181`
  - `core/services/scheduler/schedule_optimizer.py:549-563`
  - `web/bootstrap/static_versioning.py`
  - `core/services/scheduler/gantt_critical_chain.py:49-53`
- 问题:
  - [高] 其他: 任务 5 与任务 6 之间存在兼容桥删除断裂
  - [低] 其他: Service(g.db 装配基线计数近似偏差

### m2-cross-package-import · 第二轮：路由目录迁移的跨域导入断裂风险

- 状态: 已完成
- 记录时间: 2026-04-05T17:46:58.549Z
- 已审模块: web/routes/ 跨域导入链, 任务 3 目录迁移策略, 任务 2 装配覆盖范围
- 摘要:

  ## \u7b2c\u4e8c\u8f6e\u5ba1\u67e5\u91cd\u70b9\u53d1\u73b0\uff1a\u8def\u7531\u76ee\u5f55\u8fc1\u79fb\u8de8\u5305\u5bfc\u5165\u65ad\u88c2\u98ce\u9669

  \u6df1\u5165\u5206\u6790\u4e86 web/routes/ \u4e0b 59 \u4e2a\u6587\u4ef6\u7684\u5bfc\u5165\u4f9d\u8d56\u56fe\uff0c\u53d1\u73b0\u4efb\u52a1 3 \u7684\u8def\u7531\u8fc1\u79fb\u7b56\u7565\u5b58\u5728\u4e25\u91cd\u7684\u8de8\u5305\u76f8\u5bf9\u5bfc\u5165\u65ad\u88c2\u98ce\u9669\u3002

  ### \u5bfc\u5165\u4f9d\u8d56\u56fe\u5b9e\u6d4b\u7ed3\u679c

  \u6839\u5c42\u5171\u4eab\u5de5\u5177\u88ab\u57df\u6587\u4ef6\u8de8\u5305\u5bfc\u5165\u7684\u5b8c\u6574\u6e05\u5355\uff1a

  | \u6839\u5c42\u6587\u4ef6 | \u88ab\u5bfc\u5165\u6b21\u6570 | \u8de8\u57df\u6587\u4ef6\u5206\u5e03 |
  |---|---|---|
  | excel_utils.py | 22 | \u5168\u90e8 5 \u4e2a\u57df |
  | pagination.py | 10 | 6 \u4e2a\u6a21\u5757 |
  | normalizers.py | 7 | scheduler + personnel |
  | system_utils.py | 6 | system + scheduler\uff08\u8de8\u57df\uff01\uff09 |
  | enum_display.py | 3 | scheduler + personnel + equipment |
  | team_view_helpers.py | 2 | personnel + equipment |

  ### \u6838\u5fc3\u95ee\u9898

  plan \u7684\u201c\u975e\u540c\u540d\u5b50\u5305\u201d\u7b56\u7565\u53ea\u89e3\u51b3\u4e86\u6587\u4ef6/\u76ee\u5f55\u540c\u540d\u51b2\u7a81\uff0c\u4f46\u5b8c\u5168\u672a\u5904\u7406\u8fc1\u79fb\u540e 50+ \u5904\u76f8\u5bf9\u5bfc\u5165\u7684\u8def\u5f84\u5931\u6548\u95ee\u9898\u3002\u8fd9\u4e0d\u662f\u201c\u964d\u4f4e\u5bfc\u5165\u4fee\u590d\u6210\u672c\u201d\u5c31\u80fd\u89e3\u51b3\u7684\uff0c\u800c\u662f\u5fc5\u987b\u6709\u660e\u786e\u7684\u8de8\u5305\u5bfc\u5165\u7b56\u7565\u3002

  ### \u5176\u4ed6\u53d1\u73b0

  - \u6839\u5c42\u95e8\u9762\u6587\u4ef6\uff08scheduler.py \u7b49\uff09\u5f53\u524d\u786e\u5b9e\u662f\u8584\u58f3\uff0cplan \u63cf\u8ff0\u51c6\u786e
  - \u5bfc\u5165\u94fe\u4e3a\uff1afactory.py \u2192 scheduler.py \u2192 scheduler_pages.py \u2192 \u5176\u4f59\u5b50\u6a21\u5757\uff0c\u786e\u8ba4\u662f\u901a\u8fc7 side-effect import \u6ce8\u518c\u8def\u7531
  - templates/system/logs.html \u548c backup.html \u786e\u5b9e\u5404\u6709\u4e00\u4e2a `<script defer>` \u884c\u5185\u811a\u672c\uff0cplan \u63cf\u8ff0\u51c6\u786e
- 结论:

  ## \u7b2c\u4e8c\u8f6e\u5ba1\u67e5\u91cd\u70b9\u53d1\u73b0\uff1a\u8def\u7531\u76ee\u5f55\u8fc1\u79fb\u8de8\u5305\u5bfc\u5165\u65ad\u88c2\u98ce\u9669 \u6df1\u5165\u5206\u6790\u4e86 web/routes/ \u4e0b 59 \u4e2a\u6587\u4ef6\u7684\u5bfc\u5165\u4f9d\u8d56\u56fe\uff0c\u53d1\u73b0\u4efb\u52a1 3 \u7684\u8def\u7531\u8fc1\u79fb\u7b56\u7565\u5b58\u5728\u4e25\u91cd\u7684\u8de8\u5305\u76f8\u5bf9\u5bfc\u5165\u65ad\u88c2\u98ce\u9669\u3002 ### \u5bfc\u5165\u4f9d\u8d56\u56fe\u5b9e\u6d4b\u7ed3\u679c \u6839\u5c42\u5171\u4eab\u5de5\u5177\u88ab\u57df\u6587\u4ef6\u8de8\u5305\u5bfc\u5165\u7684\u5b8c\u6574\u6e05\u5355\uff1a | \u6839\u5c42\u6587\u4ef6 | \u88ab\u5bfc\u5165\u6b21\u6570 | \u8de8\u57df\u6587\u4ef6\u5206\u5e03 | |---|---|---| | excel_utils.py | 22 | \u5168\u90e8 5 \u4e2a\u57df | | pagination.py | 10 | 6 \u4e2a\u6a21\u5757 | | normalizers.py | 7 | scheduler + personnel | | system_utils.py | 6 | system + scheduler\uff08\u8de8\u57df\uff01\uff09 | | enum_display.py | 3 | scheduler + personnel + equipment | | team_view_helpers.py | 2 | personnel + equipment | ### \u6838\u5fc3\u95ee\u9898 plan \u7684\u201c\u975e\u540c\u540d\u5b50\u5305\u201d\u7b56\u7565\u53ea\u89e3\u51b3\u4e86\u6587\u4ef6/\u76ee\u5f55\u540c\u540d\u51b2\u7a81\uff0c\u4f46\u5b8c\u5168\u672a\u5904\u7406\u8fc1\u79fb\u540e 50+ \u5904\u76f8\u5bf9\u5bfc\u5165\u7684\u8def\u5f84\u5931\u6548\u95ee\u9898\u3002\u8fd9\u4e0d\u662f\u201c\u964d\u4f4e\u5bfc\u5165\u4fee\u590d\u6210\u672c\u201d\u5c31\u80fd\u89e3\u51b3\u7684\uff0c\u800c\u662f\u5fc5\u987b\u6709\u660e\u786e\u7684\u8de8\u5305\u5bfc\u5165\u7b56\u7565\u3002 ### \u5176\u4ed6\u53d1\u73b0 - \u6839\u5c42\u95e8\u9762\u6587\u4ef6\uff08scheduler.py \u7b49\uff09\u5f53\u524d\u786e\u5b9e\u662f\u8584\u58f3\uff0cplan \u63cf\u8ff0\u51c6\u786e - \u5bfc\u5165\u94fe\u4e3a\uff1afactory.py \u2192 scheduler.py \u2192 scheduler_pages.py \u2192 \u5176\u4f59\u5b50\u6a21\u5757\uff0c\u786e\u8ba4\u662f\u901a\u8fc7 side-effect import \u6ce8\u518c\u8def\u7531 - templates/system/logs.html \u548c backup.html \u786e\u5b9e\u5404\u6709\u4e00\u4e2a `<script defer>` \u884c\u5185\u811a\u672c\uff0cplan \u63cf\u8ff0\u51c6\u786e
- 证据:
  - `web/routes/scheduler_config.py:27`
  - `web/routes/scheduler_batches.py:26`
  - `web/routes/scheduler_gantt.py:12`
  - `web/routes/scheduler_analysis.py:11`
  - `web/routes/scheduler_week_plan.py:16-17`
  - `web/routes/personnel_pages.py:17`
  - `web/routes/equipment_pages.py:20`
  - `web/routes/personnel_bp.py:9-11`
- 问题:
  - [高] 其他: 任务 3 路由迁移未处理 50+ 处跨包相对导入
  - [中] 其他: scheduler 域跨域导入 system_utils 违反域隔离
  - [低] 其他: scheduler_config.py 未纳入任务 2 装配收口批次

### m3-final-cross-reference · 第三轮：交叉引用、边界条件与遗漏检测

- 状态: 已完成
- 记录时间: 2026-04-05T17:50:06.090Z
- 已审模块: 任务 4 配置事实源, 任务 5 持久化签名, 任务 6 算法拆分, 任务 7 数据基础设施, 任务 8 双模板与前端, 任务 9 测试迁移, 任务 10 文档收口, 验证命令完整性
- 摘要:

  ## 第三轮审查：交叉引用、边界条件与遗漏检测

  ### 额外验证通过的项目

  1. **persist_schedule 参数计数**：22 个命名参数（plan 准确）
  2. **双模板树**：web_new_test/templates/base.html + scheduler/gantt.html 均存在
  3. **所有验证命令引用的测试文件**：逐一确认均存在
  4. **核心支撑文件**：degradation.py / schedule_template_lookup.py / greedy/dispatch/ 均确认
  5. **test_architecture_fitness.py 已部分扫描 web/bootstrap**：第 335 行为 error_codes 扫描，但未纳入 CORE_DIRS 主扫描
  6. **迁移文件**：v1-v6 + common.py 共 8 个文件
  7. **schedule_params.py 配置规则重复**：确认存在与 config_service.py 重复的硬编码默认值

  ### 新发现的三处遗漏

  1. persist_schedule 的 22 参数签名未纳入精简范围
  2. schedule_optimizer.py 本地配置读取函数清理方案不具体
  3. 静态资源构建脚本缺乏生命周期定义

  ### 整体质量评估

  plan 的事实描述准确率极高（17 项关键事实全部核实正确），文件路径覆盖完整，问题归属清晰。但在三个方面存在可执行性缺口：(1) 任务间依赖断裂；(2) 跨包导入策略缺失；(3) 签名精简不彻底。
- 结论:

  ## 第三轮审查：交叉引用、边界条件与遗漏检测 ### 额外验证通过的项目 1. **persist_schedule 参数计数**：22 个命名参数（plan 准确） 2. **双模板树**：web_new_test/templates/base.html + scheduler/gantt.html 均存在 3. **所有验证命令引用的测试文件**：逐一确认均存在 4. **核心支撑文件**：degradation.py / schedule_template_lookup.py / greedy/dispatch/ 均确认 5. **test_architecture_fitness.py 已部分扫描 web/bootstrap**：第 335 行为 error_codes 扫描，但未纳入 CORE_DIRS 主扫描 6. **迁移文件**：v1-v6 + common.py 共 8 个文件 7. **schedule_params.py 配置规则重复**：确认存在与 config_service.py 重复的硬编码默认值 ### 新发现的三处遗漏 1. persist_schedule 的 22 参数签名未纳入精简范围 2. schedule_optimizer.py 本地配置读取函数清理方案不具体 3. 静态资源构建脚本缺乏生命周期定义 ### 整体质量评估 plan 的事实描述准确率极高（17 项关键事实全部核实正确），文件路径覆盖完整，问题归属清晰。但在三个方面存在可执行性缺口：(1) 任务间依赖断裂；(2) 跨包导入策略缺失；(3) 签名精简不彻底。
- 证据:
  - `core/services/scheduler/schedule_optimizer.py:290-296`
  - `core/services/scheduler/schedule_persistence.py:244-268`
  - `web_new_test/templates/base.html`
  - `web_new_test/templates/scheduler/gantt.html`
  - `core/services/common/degradation.py`
  - `core/algorithms/greedy/schedule_params.py`
  - `tests/test_architecture_fitness.py:335-336`
- 问题:
  - [中] 其他: persist_schedule 22 参数签名未纳入精简范围
  - [中] 其他: schedule_optimizer.py 本地配置读取函数清理方案不具体
  - [中] 其他: 静态资源构建入口缺乏生命周期定义

## 最终结论

## 三轮深度审查最终结论

### 总体评价

这份技术债务最终合并修复 plan 是一份**高质量、高精度**的治理方案。在 17 项可量化关键事实（文件数、行号、参数计数、字段计数、装配点数等）的逐一核验中，**准确率达到 100%**。10 个任务的文件路径覆盖完整，问题归属矩阵与代码现状吻合。这在大型遗产代码治理 plan 中极为难得。

### 必须在执行前修复的 2 个阻断性 BUG

| 编号 | 问题 | 影响 |
|---|---|---|
| **F01** | 任务 5 删除 `_schedule_with_optional_strict_mode` 后，`schedule_optimizer.py` 第 21/181/551 行的 3 处引用全部断裂。任务 6 只覆盖第 551 行，遗漏第 181 行。 | **执行任务 5 后排产主链立即崩溃** |
| **F03** | 任务 3 把 44 个路由文件迁入 `web/routes/domains/*/`，但未处理 50+ 处对根层共享工具（`excel_utils` 22 处、`pagination` 10 处、`normalizers` 7 处等）的相对导入断裂。 | **执行任务 3 后全部页面路由立即崩溃** |

### 应在执行中补充的 4 个中等风险遗漏

| 编号 | 问题 |
|---|---|
| **F04** | `scheduler_config.py` / `scheduler_batches.py` 跨域导入 `system_utils._safe_next_url`，迁移后无法通过根层共享工具解决 |
| **F06** | `persist_schedule` 的 22 参数签名未纳入任务 5 的精简范围，可能消解输入收集器精简成果 |
| **F07** | `schedule_optimizer.py` 的 `_cfg_value()` / `_norm_text()` 清理仅一句话提及，缺少具体替换方案和 10 处调用点清单 |
| **F08** | 静态资源构建脚本缺乏构建时机、质量门禁集成、清单缺失降级策略等生命周期定义 |

### 低风险注意事项（2 项）

- **F02**：`Service(g.db` 装配基线实际为 185 处（plan 称约 182 处），建议以精确值写入治理台账
- **F05**：`scheduler_config.py` 的 6 处装配未显式纳入任务 2 批次

### 修复建议优先级

1. **立即修复 F01**：在任务 5 步骤 4 中补入 `schedule_optimizer.py` 全部 3 处引用的同步更新
2. **立即修复 F03**：在任务 3 中新增"跨包导入策略"步骤，定义迁移后所有 `from .xxx import` 的替换方案
3. **补充 F04**：把 `_safe_next_url` 提取到根层共享工具
4. **补充 F06**：在步骤 3.5 中明确 `persist_schedule` 签名也随上下文对象一并重构
5. **补充 F07/F08**：细化配置读取替换方案和静态资源构建生命周期

### 结论

plan 的方向正确、结构完整、事实基础扎实。修复上述 2 个阻断性 BUG 和 4 个中等遗漏后，即可进入执行阶段。建议以"有条件接受"结论处理——修复 F01 和 F03 后方可开工。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnm1qgt6-bu8fnd",
  "createdAt": "2026-04-05T00:00:00.000Z",
  "updatedAt": "2026-04-05T17:50:40.023Z",
  "finalizedAt": "2026-04-05T17:50:40.023Z",
  "status": "completed",
  "overallDecision": "conditionally_accepted",
  "header": {
    "title": "技术债务最终合并修复plan三轮深度review",
    "date": "2026-04-05",
    "overview": "对 20260405_技术债务最终合并修复plan.md 进行三轮深度审查，验证路径、事实、依赖链与逻辑严谨性"
  },
  "scope": {
    "markdown": "# 技术债务最终合并修复 plan 三轮深度 review\n\n**审查日期**：2026-04-06\n**审查目标**：`.limcode/plans/20260405_技术债务最终合并修复plan.md`\n**审查方法**：逐任务验证路径真实性、事实描述准确性、依赖链完整性、逻辑严谨性\n\n## 审查范围\n- 第一轮：宏观结构与批次依赖链审查\n- 第二轮：逐任务事实核验与路径验证\n- 第三轮：交叉引用、边界条件与遗漏检测"
  },
  "summary": {
    "latestConclusion": "## 三轮深度审查最终结论\n\n### 总体评价\n\n这份技术债务最终合并修复 plan 是一份**高质量、高精度**的治理方案。在 17 项可量化关键事实（文件数、行号、参数计数、字段计数、装配点数等）的逐一核验中，**准确率达到 100%**。10 个任务的文件路径覆盖完整，问题归属矩阵与代码现状吻合。这在大型遗产代码治理 plan 中极为难得。\n\n### 必须在执行前修复的 2 个阻断性 BUG\n\n| 编号 | 问题 | 影响 |\n|---|---|---|\n| **F01** | 任务 5 删除 `_schedule_with_optional_strict_mode` 后，`schedule_optimizer.py` 第 21/181/551 行的 3 处引用全部断裂。任务 6 只覆盖第 551 行，遗漏第 181 行。 | **执行任务 5 后排产主链立即崩溃** |\n| **F03** | 任务 3 把 44 个路由文件迁入 `web/routes/domains/*/`，但未处理 50+ 处对根层共享工具（`excel_utils` 22 处、`pagination` 10 处、`normalizers` 7 处等）的相对导入断裂。 | **执行任务 3 后全部页面路由立即崩溃** |\n\n### 应在执行中补充的 4 个中等风险遗漏\n\n| 编号 | 问题 |\n|---|---|\n| **F04** | `scheduler_config.py` / `scheduler_batches.py` 跨域导入 `system_utils._safe_next_url`，迁移后无法通过根层共享工具解决 |\n| **F06** | `persist_schedule` 的 22 参数签名未纳入任务 5 的精简范围，可能消解输入收集器精简成果 |\n| **F07** | `schedule_optimizer.py` 的 `_cfg_value()` / `_norm_text()` 清理仅一句话提及，缺少具体替换方案和 10 处调用点清单 |\n| **F08** | 静态资源构建脚本缺乏构建时机、质量门禁集成、清单缺失降级策略等生命周期定义 |\n\n### 低风险注意事项（2 项）\n\n- **F02**：`Service(g.db` 装配基线实际为 185 处（plan 称约 182 处），建议以精确值写入治理台账\n- **F05**：`scheduler_config.py` 的 6 处装配未显式纳入任务 2 批次\n\n### 修复建议优先级\n\n1. **立即修复 F01**：在任务 5 步骤 4 中补入 `schedule_optimizer.py` 全部 3 处引用的同步更新\n2. **立即修复 F03**：在任务 3 中新增\"跨包导入策略\"步骤，定义迁移后所有 `from .xxx import` 的替换方案\n3. **补充 F04**：把 `_safe_next_url` 提取到根层共享工具\n4. **补充 F06**：在步骤 3.5 中明确 `persist_schedule` 签名也随上下文对象一并重构\n5. **补充 F07/F08**：细化配置读取替换方案和静态资源构建生命周期\n\n### 结论\n\nplan 的方向正确、结构完整、事实基础扎实。修复上述 2 个阻断性 BUG 和 4 个中等遗漏后，即可进入执行阶段。建议以\"有条件接受\"结论处理——修复 F01 和 F03 后方可开工。",
    "recommendedNextAction": "立即修复 F01（任务 5 步骤 4 补入 schedule_optimizer.py 的 3 处兼容桥引用同步清理）和 F03（任务 3 补入跨包导入策略步骤），然后补充 F04/F06/F07/F08 的细化方案，修复后即可进入执行阶段。",
    "reviewedModules": [
      "plan 宏观结构",
      "路径与事实核验",
      "兼容桥依赖链",
      "web/routes/ 跨域导入链",
      "任务 3 目录迁移策略",
      "任务 2 装配覆盖范围",
      "任务 4 配置事实源",
      "任务 5 持久化签名",
      "任务 6 算法拆分",
      "任务 7 数据基础设施",
      "任务 8 双模板与前端",
      "任务 9 测试迁移",
      "任务 10 文档收口",
      "验证命令完整性",
      "任务 1-10 逐任务审查",
      "批次依赖与入口退出条件"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 8,
    "severity": {
      "high": 2,
      "medium": 4,
      "low": 2
    }
  },
  "milestones": [
    {
      "id": "m1-macro-fact-verify",
      "title": "第一轮：宏观事实核验与路径验证",
      "status": "completed",
      "recordedAt": "2026-04-05T17:43:43.017Z",
      "summaryMarkdown": "逐项核验 plan 中所有可量化事实描述和路径引用，发现一个严重的任务间依赖断裂 BUG 和若干偏差。\n\n## 已验证正确的关键事实\n\n1. **ScheduleService 构造器**：3 参数 + 内部创建 10 个仓储实例 ✅\n2. **GreedyScheduler.schedule()**：56-388 行共 332 行 ✅\n3. **调度服务目录**：45 个文件 ✅\n4. **路由目录**：59 个文件 ✅\n5. **兼容桥函数行号**：全部 6 个兼容桥的行号准确无误 ✅\n6. **collect_schedule_run_input**：16 参数 (1 svc + 7 业务 + 2 类注入 + 6 函数注入) ✅\n7. **ScheduleRunInput**：27 字段 ✅\n8. **gantt_critical_chain._load_rows()**：`except Exception: return []` 存在于 49-53 行 ✅\n9. **static_versioning.py**：3 处静默吞异常全部确认 ✅\n10. **schedule_optimizer.py**：`if best is None` 兜底在 549 行 ✅ / `_parse_date` `_parse_datetime` 在 335-357 行 ✅\n11. **database.py**：612 行混合职责 ✅\n12. **backup.py**：包含 `maintenance_window` + `BackupManager` 等 427 行 ✅\n13. **requirements-dev.txt**：当前仅 `pytest`，缺 `pytest-cov`、`radon`、`ruff` ✅\n14. **test_architecture_fitness.py**：白名单无退出条件 ✅\n15. **Service(g.db 装配计数**：实际 185 处，plan 称\"约 182 处\"，近似正确 ✅\n16. **路由迁移文件总数**：44 迁移 + 15 保留 = 59 全部吻合 ✅\n17. **调度服务迁移文件总数**：39 迁移 + 6 保留 = 45 全部吻合 ✅",
      "conclusionMarkdown": "逐项核验 plan 中所有可量化事实描述和路径引用，发现一个严重的任务间依赖断裂 BUG 和若干偏差。 ## 已验证正确的关键事实 1. **ScheduleService 构造器**：3 参数 + 内部创建 10 个仓储实例 ✅ 2. **GreedyScheduler.schedule()**：56-388 行共 332 行 ✅ 3. **调度服务目录**：45 个文件 ✅ 4. **路由目录**：59 个文件 ✅ 5. **兼容桥函数行号**：全部 6 个兼容桥的行号准确无误 ✅ 6. **collect_schedule_run_input**：16 参数 (1 svc + 7 业务 + 2 类注入 + 6 函数注入) ✅ 7. **ScheduleRunInput**：27 字段 ✅ 8. **gantt_critical_chain._load_rows()**：`except Exception: return []` 存在于 49-53 行 ✅ 9. **static_versioning.py**：3 处静默吞异常全部确认 ✅ 10. **schedule_optimizer.py**：`if best is None` 兜底在 549 行 ✅ / `_parse_date` `_parse_datetime` 在 335-357 行 ✅ 11. **database.py**：612 行混合职责 ✅ 12. **backup.py**：包含 `maintenance_window` + `BackupManager` 等 427 行 ✅ 13. **requirements-dev.txt**：当前仅 `pytest`，缺 `pytest-cov`、`radon`、`ruff` ✅ 14. **test_architecture_fitness.py**：白名单无退出条件 ✅ 15. **Service(g.db 装配计数**：实际 185 处，plan 称\"约 182 处\"，近似正确 ✅ 16. **路由迁移文件总数**：44 迁移 + 15 保留 = 59 全部吻合 ✅ 17. **调度服务迁移文件总数**：39 迁移 + 6 保留 = 45 全部吻合 ✅",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 49,
          "lineEnd": 96
        },
        {
          "path": "core/services/scheduler/schedule_input_collector.py",
          "lineStart": 17,
          "lineEnd": 45
        },
        {
          "path": "core/services/scheduler/schedule_optimizer_steps.py",
          "lineStart": 85,
          "lineEnd": 115
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 21,
          "lineEnd": 21
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 181,
          "lineEnd": 181
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 549,
          "lineEnd": 563
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "core/services/scheduler/gantt_critical_chain.py",
          "lineStart": 49,
          "lineEnd": 53
        }
      ],
      "reviewedModules": [
        "plan 宏观结构",
        "路径与事实核验",
        "兼容桥依赖链"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F01",
        "F02"
      ]
    },
    {
      "id": "m2-cross-package-import",
      "title": "第二轮：路由目录迁移的跨域导入断裂风险",
      "status": "completed",
      "recordedAt": "2026-04-05T17:46:58.549Z",
      "summaryMarkdown": "## \\u7b2c\\u4e8c\\u8f6e\\u5ba1\\u67e5\\u91cd\\u70b9\\u53d1\\u73b0\\uff1a\\u8def\\u7531\\u76ee\\u5f55\\u8fc1\\u79fb\\u8de8\\u5305\\u5bfc\\u5165\\u65ad\\u88c2\\u98ce\\u9669\n\n\\u6df1\\u5165\\u5206\\u6790\\u4e86 web/routes/ \\u4e0b 59 \\u4e2a\\u6587\\u4ef6\\u7684\\u5bfc\\u5165\\u4f9d\\u8d56\\u56fe\\uff0c\\u53d1\\u73b0\\u4efb\\u52a1 3 \\u7684\\u8def\\u7531\\u8fc1\\u79fb\\u7b56\\u7565\\u5b58\\u5728\\u4e25\\u91cd\\u7684\\u8de8\\u5305\\u76f8\\u5bf9\\u5bfc\\u5165\\u65ad\\u88c2\\u98ce\\u9669\\u3002\n\n### \\u5bfc\\u5165\\u4f9d\\u8d56\\u56fe\\u5b9e\\u6d4b\\u7ed3\\u679c\n\n\\u6839\\u5c42\\u5171\\u4eab\\u5de5\\u5177\\u88ab\\u57df\\u6587\\u4ef6\\u8de8\\u5305\\u5bfc\\u5165\\u7684\\u5b8c\\u6574\\u6e05\\u5355\\uff1a\n\n| \\u6839\\u5c42\\u6587\\u4ef6 | \\u88ab\\u5bfc\\u5165\\u6b21\\u6570 | \\u8de8\\u57df\\u6587\\u4ef6\\u5206\\u5e03 |\n|---|---|---|\n| excel_utils.py | 22 | \\u5168\\u90e8 5 \\u4e2a\\u57df |\n| pagination.py | 10 | 6 \\u4e2a\\u6a21\\u5757 |\n| normalizers.py | 7 | scheduler + personnel |\n| system_utils.py | 6 | system + scheduler\\uff08\\u8de8\\u57df\\uff01\\uff09 |\n| enum_display.py | 3 | scheduler + personnel + equipment |\n| team_view_helpers.py | 2 | personnel + equipment |\n\n### \\u6838\\u5fc3\\u95ee\\u9898\n\nplan \\u7684\\u201c\\u975e\\u540c\\u540d\\u5b50\\u5305\\u201d\\u7b56\\u7565\\u53ea\\u89e3\\u51b3\\u4e86\\u6587\\u4ef6/\\u76ee\\u5f55\\u540c\\u540d\\u51b2\\u7a81\\uff0c\\u4f46\\u5b8c\\u5168\\u672a\\u5904\\u7406\\u8fc1\\u79fb\\u540e 50+ \\u5904\\u76f8\\u5bf9\\u5bfc\\u5165\\u7684\\u8def\\u5f84\\u5931\\u6548\\u95ee\\u9898\\u3002\\u8fd9\\u4e0d\\u662f\\u201c\\u964d\\u4f4e\\u5bfc\\u5165\\u4fee\\u590d\\u6210\\u672c\\u201d\\u5c31\\u80fd\\u89e3\\u51b3\\u7684\\uff0c\\u800c\\u662f\\u5fc5\\u987b\\u6709\\u660e\\u786e\\u7684\\u8de8\\u5305\\u5bfc\\u5165\\u7b56\\u7565\\u3002\n\n### \\u5176\\u4ed6\\u53d1\\u73b0\n\n- \\u6839\\u5c42\\u95e8\\u9762\\u6587\\u4ef6\\uff08scheduler.py \\u7b49\\uff09\\u5f53\\u524d\\u786e\\u5b9e\\u662f\\u8584\\u58f3\\uff0cplan \\u63cf\\u8ff0\\u51c6\\u786e\n- \\u5bfc\\u5165\\u94fe\\u4e3a\\uff1afactory.py \\u2192 scheduler.py \\u2192 scheduler_pages.py \\u2192 \\u5176\\u4f59\\u5b50\\u6a21\\u5757\\uff0c\\u786e\\u8ba4\\u662f\\u901a\\u8fc7 side-effect import \\u6ce8\\u518c\\u8def\\u7531\n- templates/system/logs.html \\u548c backup.html \\u786e\\u5b9e\\u5404\\u6709\\u4e00\\u4e2a `<script defer>` \\u884c\\u5185\\u811a\\u672c\\uff0cplan \\u63cf\\u8ff0\\u51c6\\u786e",
      "conclusionMarkdown": "## \\u7b2c\\u4e8c\\u8f6e\\u5ba1\\u67e5\\u91cd\\u70b9\\u53d1\\u73b0\\uff1a\\u8def\\u7531\\u76ee\\u5f55\\u8fc1\\u79fb\\u8de8\\u5305\\u5bfc\\u5165\\u65ad\\u88c2\\u98ce\\u9669 \\u6df1\\u5165\\u5206\\u6790\\u4e86 web/routes/ \\u4e0b 59 \\u4e2a\\u6587\\u4ef6\\u7684\\u5bfc\\u5165\\u4f9d\\u8d56\\u56fe\\uff0c\\u53d1\\u73b0\\u4efb\\u52a1 3 \\u7684\\u8def\\u7531\\u8fc1\\u79fb\\u7b56\\u7565\\u5b58\\u5728\\u4e25\\u91cd\\u7684\\u8de8\\u5305\\u76f8\\u5bf9\\u5bfc\\u5165\\u65ad\\u88c2\\u98ce\\u9669\\u3002 ### \\u5bfc\\u5165\\u4f9d\\u8d56\\u56fe\\u5b9e\\u6d4b\\u7ed3\\u679c \\u6839\\u5c42\\u5171\\u4eab\\u5de5\\u5177\\u88ab\\u57df\\u6587\\u4ef6\\u8de8\\u5305\\u5bfc\\u5165\\u7684\\u5b8c\\u6574\\u6e05\\u5355\\uff1a | \\u6839\\u5c42\\u6587\\u4ef6 | \\u88ab\\u5bfc\\u5165\\u6b21\\u6570 | \\u8de8\\u57df\\u6587\\u4ef6\\u5206\\u5e03 | |---|---|---| | excel_utils.py | 22 | \\u5168\\u90e8 5 \\u4e2a\\u57df | | pagination.py | 10 | 6 \\u4e2a\\u6a21\\u5757 | | normalizers.py | 7 | scheduler + personnel | | system_utils.py | 6 | system + scheduler\\uff08\\u8de8\\u57df\\uff01\\uff09 | | enum_display.py | 3 | scheduler + personnel + equipment | | team_view_helpers.py | 2 | personnel + equipment | ### \\u6838\\u5fc3\\u95ee\\u9898 plan \\u7684\\u201c\\u975e\\u540c\\u540d\\u5b50\\u5305\\u201d\\u7b56\\u7565\\u53ea\\u89e3\\u51b3\\u4e86\\u6587\\u4ef6/\\u76ee\\u5f55\\u540c\\u540d\\u51b2\\u7a81\\uff0c\\u4f46\\u5b8c\\u5168\\u672a\\u5904\\u7406\\u8fc1\\u79fb\\u540e 50+ \\u5904\\u76f8\\u5bf9\\u5bfc\\u5165\\u7684\\u8def\\u5f84\\u5931\\u6548\\u95ee\\u9898\\u3002\\u8fd9\\u4e0d\\u662f\\u201c\\u964d\\u4f4e\\u5bfc\\u5165\\u4fee\\u590d\\u6210\\u672c\\u201d\\u5c31\\u80fd\\u89e3\\u51b3\\u7684\\uff0c\\u800c\\u662f\\u5fc5\\u987b\\u6709\\u660e\\u786e\\u7684\\u8de8\\u5305\\u5bfc\\u5165\\u7b56\\u7565\\u3002 ### \\u5176\\u4ed6\\u53d1\\u73b0 - \\u6839\\u5c42\\u95e8\\u9762\\u6587\\u4ef6\\uff08scheduler.py \\u7b49\\uff09\\u5f53\\u524d\\u786e\\u5b9e\\u662f\\u8584\\u58f3\\uff0cplan \\u63cf\\u8ff0\\u51c6\\u786e - \\u5bfc\\u5165\\u94fe\\u4e3a\\uff1afactory.py \\u2192 scheduler.py \\u2192 scheduler_pages.py \\u2192 \\u5176\\u4f59\\u5b50\\u6a21\\u5757\\uff0c\\u786e\\u8ba4\\u662f\\u901a\\u8fc7 side-effect import \\u6ce8\\u518c\\u8def\\u7531 - templates/system/logs.html \\u548c backup.html \\u786e\\u5b9e\\u5404\\u6709\\u4e00\\u4e2a `<script defer>` \\u884c\\u5185\\u811a\\u672c\\uff0cplan \\u63cf\\u8ff0\\u51c6\\u786e",
      "evidence": [
        {
          "path": "web/routes/scheduler_config.py",
          "lineStart": 27,
          "lineEnd": 27
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 26,
          "lineEnd": 26
        },
        {
          "path": "web/routes/scheduler_gantt.py",
          "lineStart": 12,
          "lineEnd": 12
        },
        {
          "path": "web/routes/scheduler_analysis.py",
          "lineStart": 11,
          "lineEnd": 11
        },
        {
          "path": "web/routes/scheduler_week_plan.py",
          "lineStart": 16,
          "lineEnd": 17
        },
        {
          "path": "web/routes/personnel_pages.py",
          "lineStart": 17,
          "lineEnd": 17
        },
        {
          "path": "web/routes/equipment_pages.py",
          "lineStart": 20,
          "lineEnd": 20
        },
        {
          "path": "web/routes/personnel_bp.py",
          "lineStart": 9,
          "lineEnd": 11
        }
      ],
      "reviewedModules": [
        "web/routes/ 跨域导入链",
        "任务 3 目录迁移策略",
        "任务 2 装配覆盖范围"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F03",
        "F04",
        "F05"
      ]
    },
    {
      "id": "m3-final-cross-reference",
      "title": "第三轮：交叉引用、边界条件与遗漏检测",
      "status": "completed",
      "recordedAt": "2026-04-05T17:50:06.090Z",
      "summaryMarkdown": "## 第三轮审查：交叉引用、边界条件与遗漏检测\n\n### 额外验证通过的项目\n\n1. **persist_schedule 参数计数**：22 个命名参数（plan 准确）\n2. **双模板树**：web_new_test/templates/base.html + scheduler/gantt.html 均存在\n3. **所有验证命令引用的测试文件**：逐一确认均存在\n4. **核心支撑文件**：degradation.py / schedule_template_lookup.py / greedy/dispatch/ 均确认\n5. **test_architecture_fitness.py 已部分扫描 web/bootstrap**：第 335 行为 error_codes 扫描，但未纳入 CORE_DIRS 主扫描\n6. **迁移文件**：v1-v6 + common.py 共 8 个文件\n7. **schedule_params.py 配置规则重复**：确认存在与 config_service.py 重复的硬编码默认值\n\n### 新发现的三处遗漏\n\n1. persist_schedule 的 22 参数签名未纳入精简范围\n2. schedule_optimizer.py 本地配置读取函数清理方案不具体\n3. 静态资源构建脚本缺乏生命周期定义\n\n### 整体质量评估\n\nplan 的事实描述准确率极高（17 项关键事实全部核实正确），文件路径覆盖完整，问题归属清晰。但在三个方面存在可执行性缺口：(1) 任务间依赖断裂；(2) 跨包导入策略缺失；(3) 签名精简不彻底。",
      "conclusionMarkdown": "## 第三轮审查：交叉引用、边界条件与遗漏检测 ### 额外验证通过的项目 1. **persist_schedule 参数计数**：22 个命名参数（plan 准确） 2. **双模板树**：web_new_test/templates/base.html + scheduler/gantt.html 均存在 3. **所有验证命令引用的测试文件**：逐一确认均存在 4. **核心支撑文件**：degradation.py / schedule_template_lookup.py / greedy/dispatch/ 均确认 5. **test_architecture_fitness.py 已部分扫描 web/bootstrap**：第 335 行为 error_codes 扫描，但未纳入 CORE_DIRS 主扫描 6. **迁移文件**：v1-v6 + common.py 共 8 个文件 7. **schedule_params.py 配置规则重复**：确认存在与 config_service.py 重复的硬编码默认值 ### 新发现的三处遗漏 1. persist_schedule 的 22 参数签名未纳入精简范围 2. schedule_optimizer.py 本地配置读取函数清理方案不具体 3. 静态资源构建脚本缺乏生命周期定义 ### 整体质量评估 plan 的事实描述准确率极高（17 项关键事实全部核实正确），文件路径覆盖完整，问题归属清晰。但在三个方面存在可执行性缺口：(1) 任务间依赖断裂；(2) 跨包导入策略缺失；(3) 签名精简不彻底。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 290,
          "lineEnd": 296
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py",
          "lineStart": 244,
          "lineEnd": 268
        },
        {
          "path": "web_new_test/templates/base.html"
        },
        {
          "path": "web_new_test/templates/scheduler/gantt.html"
        },
        {
          "path": "core/services/common/degradation.py"
        },
        {
          "path": "core/algorithms/greedy/schedule_params.py"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 335,
          "lineEnd": 336
        }
      ],
      "reviewedModules": [
        "任务 4 配置事实源",
        "任务 5 持久化签名",
        "任务 6 算法拆分",
        "任务 7 数据基础设施",
        "任务 8 双模板与前端",
        "任务 9 测试迁移",
        "任务 10 文档收口",
        "验证命令完整性"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F06",
        "F07",
        "F08"
      ]
    }
  ],
  "findings": [
    {
      "id": "F01",
      "severity": "high",
      "category": "other",
      "title": "任务 5 与任务 6 之间存在兼容桥删除断裂",
      "descriptionMarkdown": "任务 5 步骤 4 要求从 schedule_optimizer_steps.py 中删除 _schedule_with_optional_strict_mode，但 schedule_optimizer.py 在 3 处导入/调用该函数：(1) 第 21 行 import；(2) 第 181 行 _run_local_search 内调用；(3) 第 551 行 if best is None 兜底调用。任务 5 只针对 schedule_optimizer_steps.py 定义侧的删除，没有同步清理 schedule_optimizer.py 第 181 行的常规调用点。任务 6 步骤 5.5 只处理第 551 行的 if best is None，遗漏了第 181 行。执行任务 5 后 schedule_optimizer.py 将因 ImportError 立即崩溃。",
      "recommendationMarkdown": "应在任务 5 步骤 4 中明确要求同步更新 schedule_optimizer.py 的全部 3 处引用：删除 import、把 _run_local_search 第 181 行改为直接调用 scheduler.schedule(strict_mode=..., ...)、把第 551 行的 if best is None 同步改为直接调用或标记为任务 6 必须同批完成的前置。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 21,
          "lineEnd": 21
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 181,
          "lineEnd": 181
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 549,
          "lineEnd": 563
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        }
      ],
      "relatedMilestoneIds": [
        "m1-macro-fact-verify"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F02",
      "severity": "low",
      "category": "other",
      "title": "Service(g.db 装配基线计数近似偏差",
      "descriptionMarkdown": "plan 称初始基线约 182 处，实际搜索结果为 185 处。偏差不大（约 1.6%），但如果用于门禁阈值判定，可能导致残余数不准。",
      "recommendationMarkdown": "建议在任务 2 实施前重新精确计数，并以实际值为基线写入治理台账。",
      "evidence": [
        {
          "path": "web/routes/"
        }
      ],
      "relatedMilestoneIds": [
        "m1-macro-fact-verify"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F03",
      "severity": "high",
      "category": "other",
      "title": "任务 3 路由迁移未处理 50+ 处跨包相对导入",
      "descriptionMarkdown": "plan 任务 3 把 44 个路由文件迁入 web/routes/domains/*/，但未处理这些文件对根层共享工具的相对导入。当前跨域导入分布如下：\n\n- excel_utils.py：22 个文件导入（遍布全部 5 个域）\n- pagination.py：10 个文件导入（遍布 6 个模块）\n- normalizers.py：7 个文件导入（跨 scheduler/personnel 两域）\n- enum_display.py：3 个 bp 文件导入\n- system_utils.py：6 个文件导入，其中 2 个是 scheduler 域文件（scheduler_config.py 和 scheduler_batches.py）跨域引用 system_utils._safe_next_url\n- team_view_helpers.py：2 个文件导入（跨 personnel / equipment 两域）\n\n迁移后，所有 `from .excel_utils import` 等相对导入都会解析到 domains/*/ 子包内，导致 ModuleNotFoundError。plan 只说“保留原始文件名，不额外重命名模块短名，降低导入修复成本”，但完全未提及跨包导入路径如何修复。",
      "recommendationMarkdown": "必须在任务 3 中新增一个明确的“跨包导入策略”步骤。建议采用以下方案之一：(1) 在 web/routes/domains/ 每个域子包的 __init__.py 中统一重新导出根层共享工具；(2) 将这些导入全部改为绝对导入，如 from web.routes.excel_utils import ...；(3) 保留根层一个薄转发层。无论哪种，都必须明确写进 plan 中并列出受影响的 50+ 处导入。",
      "evidence": [
        {
          "path": "web/routes/scheduler_config.py",
          "lineStart": 27,
          "lineEnd": 27
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 26,
          "lineEnd": 26
        },
        {
          "path": "web/routes/scheduler_gantt.py",
          "lineStart": 12,
          "lineEnd": 12
        },
        {
          "path": "web/routes/scheduler_config.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        },
        {
          "path": "web/routes/scheduler_gantt.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2-cross-package-import"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F04",
      "severity": "medium",
      "category": "other",
      "title": "scheduler 域跨域导入 system_utils 违反域隔离",
      "descriptionMarkdown": "scheduler_config.py 和 scheduler_batches.py 当前用 from .system_utils import _safe_next_url 跨域导入。迁移后，scheduler 域和 system 域分属不同包，该导入无法通过任何“根层共享工具”策略解决——必须要么抽取 _safe_next_url 到根层共享工具，要么用绝对导入。",
      "recommendationMarkdown": "建议把 _safe_next_url 从 system_utils.py 抽到根层共享工具（如 excel_utils.py 或新建 navigation_utils.py），避免跨域导入。",
      "evidence": [
        {
          "path": "web/routes/scheduler_config.py",
          "lineStart": 27,
          "lineEnd": 27
        },
        {
          "path": "web/routes/scheduler_batches.py",
          "lineStart": 26,
          "lineEnd": 26
        },
        {
          "path": "web/routes/scheduler_config.py"
        },
        {
          "path": "web/routes/scheduler_batches.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2-cross-package-import"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F05",
      "severity": "low",
      "category": "other",
      "title": "scheduler_config.py 未纳入任务 2 装配收口批次",
      "descriptionMarkdown": "scheduler_config.py 有 6 处 Service(g.db 装配，但不在任务 2 的第一批或第二批迁移清单中。plan 只说“步骤 7 清点残余直接装配点”，但未明确将其纳入或登记到台账。考虑到配置服务是排产系统的高频路径之一，应显式列入某一批次。",
      "recommendationMarkdown": "将 scheduler_config.py 添加到任务 2 的第二批或显式登记为台账残余项。",
      "evidence": [
        {
          "path": "web/routes/scheduler_config.py"
        }
      ],
      "relatedMilestoneIds": [
        "m2-cross-package-import"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F06",
      "severity": "medium",
      "category": "other",
      "title": "persist_schedule 22 参数签名未纳入精简范围",
      "descriptionMarkdown": "plan 任务 5 步骤 3.5 声明了 27 字段拆分归属要求，步骤 3 要求精简 collect_schedule_run_input 的 16 参数签名并消除 8 个依赖注入参数。但 persist_schedule() 有 22 个命名参数（svc + 21 个关键字参数），这些参数来自 ScheduleRunInput 和 ScheduleOrchestrationOutcome 的直接拆包。plan 虽然提到了 persist_schedule 消费 22 个参数这一事实，但未明确要求 persist_schedule 签名本身也一并简化，导致拆分 ScheduleRunInput 后 persist_schedule 的 22 参数调用可能被原样保留。",
      "recommendationMarkdown": "应在步骤 3.5 或步骤 6 中明确指出 persist_schedule 的调用方式也应随 RunContext 和 OrchestrationOutcome 对象边界一并重构，改为接收完整上下文对象而非 22 个平铺参数。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_persistence.py",
          "lineStart": 244,
          "lineEnd": 268
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 291,
          "lineEnd": 314
        },
        {
          "path": "core/services/scheduler/schedule_persistence.py"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        }
      ],
      "relatedMilestoneIds": [
        "m3-final-cross-reference"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F07",
      "severity": "medium",
      "category": "other",
      "title": "schedule_optimizer.py 本地配置读取函数清理方案不具体",
      "descriptionMarkdown": "plan 任务 4 步骤 7 要求清理 schedule_optimizer.py 中本地 _cfg_value() 和 _norm_text()，但只用一句话提及，没有给出具体清理方案。这两个函数定义在第 290 和 294 行，在 optimize_schedule() 内部共被调用约 10 处。plan 未说明替换为何种统一读取门面、受影响的调用点清单、以及规范化逻辑是否由注册表内建提供。",
      "recommendationMarkdown": "应在任务 4 步骤 6 或步骤 7 中明确列出替换方案和受影响的约 10 个调用点。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_optimizer.py",
          "lineStart": 290,
          "lineEnd": 296
        },
        {
          "path": "core/services/scheduler/schedule_optimizer.py"
        }
      ],
      "relatedMilestoneIds": [
        "m3-final-cross-reference"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F08",
      "severity": "medium",
      "category": "other",
      "title": "静态资源构建入口缺乏生命周期定义",
      "descriptionMarkdown": "plan 任务 8 步骤 8 新增 scripts/build_static_assets.py 和 static/asset_manifest.json，但未定义构建时机（提交前/部署时/质量门禁中）、未将其纳入 run_quality_gate.py、未确认 Win7 + Python 3.8 兼容性、未定义清单不存在时的降级行为。",
      "recommendationMarkdown": "应补充构建时机、质量门禁集成、清单缺失时的可观测降级策略以及 Win7 兼容性确认。",
      "evidence": [
        {
          "path": "web/bootstrap/static_versioning.py"
        }
      ],
      "relatedMilestoneIds": [
        "m3-final-cross-reference"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:c921087179044d981a4df77abf43db06a6f3830a4cb2ef6cffeb5e03512a49dc",
    "generatedAt": "2026-04-05T17:50:40.023Z",
    "locale": "zh-CN"
  }
}
```
