# APS排产系统技术债务全面梳理
- 日期: 2026-04-05
- 概述: 对回转壳体单元智能排产系统进行全面技术债务梳理，涵盖架构、代码质量、测试、文档、性能等维度
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# APS 排产系统技术债务全面梳理

**审查日期**: 2026-04-05  
**审查范围**: 整个项目工作区  
**审查目标**: 系统性梳理项目中存在的技术债务，按严重程度分类并提出治理建议  

## 审查维度

1. **架构层面** — 分层合理性、模块耦合、职责边界
2. **代码质量** — 圈复杂度、重复代码、命名规范
3. **依赖与兼容性** — 版本锁定、运行时兼容
4. **测试体系** — 覆盖率、测试组织、回归测试膨胀
5. **前端与模板** — 模板组织、静态资源管理
6. **文档与留存** — 文档一致性、过时内容
7. **运维与部署** — 打包流程、运行时维护

## 评审摘要

- 当前状态: 已完成
- 已审模块: core/services/scheduler（目录结构）, web/routes（目录结构）, 项目整体分层架构, tests/（测试体系）, 核心算法代码质量, 类型标注与安全性, 前端模板与静态资源, 开发文档与审计记录, 依赖与兼容性, 运维与部署体系
- 当前进度: 已记录 3 个里程碑；最新：M3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 15
- 问题严重级别分布: 高 4 / 中 8 / 低 3
- 最新结论: ## 技术债务全面梳理总结 对回转壳体单元智能排产系统进行了全面的技术债务梳理，覆盖架构、代码质量、测试、前端、文档、依赖兼容性、运维部署共 7 个维度，共发现 **15 项技术债务**（高 4 / 中 8 / 低 3）。 ### 值得肯定的方面 - 四层分层架构（模型→仓储→服务→路由）设计清晰，职责边界明确 - 已完成多轮拆分治理（schedule_summary、batch_service 等大文件已拆为子模块） - 枚举值归一化机制完善（normalization_matrix.py 作为统一事实来源） - 数据库迁移机制成熟（6 个版本迁移脚本、前置检查、失败回滚） - 错误处理体系完整（错误码、统一响应格式、中文提示） - Excel 导入导出链路健壮（预览→确认→事务保护→留痕→严格拒绝） - 备份/恢复机制设计周全（维护窗口互斥、完整性检查、自动回滚） ### 最紧迫的技术债务（按治理优先级排序） 1. **Python 3.8 已停止官方支持**（受 Win7 环境约束，需推动环境升级才能解决） 2. **回归测试体系膨胀**（252 个非标准脚本式测试，维护成本极高） 3. **排产服务目录膨胀**（45 文件扁平堆放，需进一步拆为子包） 4. **GreedyScheduler.schedule() 方法过大**（330 行单方法，需继续拆分） ### 建议的治理路径 - **短期**（可立即开始）：文档归档清理、开发依赖补充（pytest-cov）、建立基础 CI - **中期**（规划排期）：测试体系重组（合并回归测试、分层目录）、scheduler 服务子包化、算法方法拆分 - **长期**（需业务配合）：推动 Win7→Win10 升级以解除 Python 3.8 束缚、完成 v2 模板迁移或放弃 overlay 方案
- 下一步建议: 建议优先处理：1）将文档归档清理和 CI 建设作为近期可执行的低成本改善；2）规划测试体系重组的迭代计划；3）评估目标环境升级可能性以解除 Python 3.8 约束
- 总体结论: 需要后续跟进

## 评审发现

### 排产调度服务目录过度膨胀

- ID: F-排产调度服务目录过度膨胀
- 严重级别: 高
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  core/services/scheduler/ 目录包含 45 个文件，是项目中最庞大的单一模块目录。虽然已经过拆分治理（如 schedule_summary 拆为 4 个子文件、batch_service 拆出 3 个协作文件），但该目录仍承载了排产执行、批次管理、甘特图、资源排班、配置管理等多个独立子域的全部逻辑。文件之间的命名有较多前缀共享（schedule_*、gantt_*、resource_dispatch_*、batch_*），导致浏览和定位困难。
- 建议:

  考虑将 scheduler 服务进一步拆分为子包（如 scheduler/gantt/、scheduler/dispatch/、scheduler/config/），每个子包保持独立的 __init__.py 和对外入口，降低目录内浏览成本。
- 证据:
  - `core/services/scheduler`

### 路由层文件数量过多

- ID: F-路由层文件数量过多
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  web/routes/ 目录包含 59 个文件。虽然每个文件职责相对单一，但大量以蓝图前缀开头的文件（scheduler_*.py 有 16 个、equipment_*.py 有 6 个、personnel_*.py 有 7 个、process_*.py 有 7 个、system_*.py 有 8 个）使得目录过于扁平。路由的 'side-effect 导入注册' 模式（如 scheduler.py 中 import scheduler_pages 仅为注册路由）增加了理解成本。
- 建议:

  考虑将路由按业务域进一步组织为子包（如 routes/scheduler/、routes/equipment/ 等），用 __init__.py 统一注册蓝图。
- 证据:
  - `web/routes`

### ScheduleService 构造器承载 12 个仓储依赖

- ID: F-scheduleservice-构造器承载-12-个仓储依赖
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  ScheduleService.__init__ 直接创建了 12 个仓储实例（batch_repo、op_repo、part_op_repo、group_repo、machine_repo、operator_repo、operator_machine_repo、supplier_repo、schedule_repo、history_repo 等），缺乏依赖注入容器或工厂方法的抽象。这意味着每次构造该服务都会创建大量数据库访问对象，且测试时难以隔离单个依赖。
- 建议:

  引入轻量级的服务定位器或工厂模式，将仓储创建集中到一个 ServiceContainer 中，便于测试替换和生命周期管理。
- 证据:
  - `core/services/scheduler/schedule_service.py:78-96`
  - `core/services/scheduler/schedule_service.py`

### 缺乏统一的依赖注入机制

- ID: F-缺乏统一的依赖注入机制
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M1
- 说明:

  当前所有服务（ScheduleService、BatchService、GanttService 等）都在路由层或工厂函数中手动实例化，每个路由需要手动从请求上下文获取数据库连接并传入服务构造器。没有统一的 IoC 容器或服务注册机制，导致服务创建逻辑重复分散在各路由文件中。
- 建议:

  可考虑在 Flask before_request 中统一创建 ServiceContainer 并绑定到请求上下文（g），各路由通过 g.services.xxx 获取服务实例。

### 回归测试数量过度膨胀且约定非标准

- ID: F-回归测试数量过度膨胀且约定非标准
- 严重级别: 高
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  测试目录中共有 **252 个** regression_*.py 文件，32 个 test_*.py，15 个 smoke_*.py，8 个 run_*.py，总计超过 **310 个测试文件**。大量 regression_ 文件采用“带 main() 函数的脚本式”模式而非标准 pytest 测试类/函数模式，通过 conftest.py 中的自定义收集器运行。这导致：
  1. 测试发现和维护困难，新来开发者难以理解这套非标准约定
  2. 每个 regression 文件通常只验证一个特定微观行为，粒度过细导致总文件数过多
  3. 创建临时目录、数据库等复杂设置逻辑在各 regression 文件间大量重复
  4. 没有明确的测试分组或标记机制，难以按模块、层级筛选执行
- 建议:

  将相近的回归测试合并为标准 pytest 测试类，按模块分组到 tests/unit/、tests/integration/ 等子目录；引入 pytest.mark 分组机制。
- 证据:
  - `tests/conftest.py`
  - `tests/`

### 测试缺乏分层目录结构

- ID: F-测试缺乏分层目录结构
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  当前 regression 测试文件全部扁平地放在 tests/ 目录下，没有按业务域分子目录。252 个 regression 文件 + 32 个 test 文件 + 15 个 smoke 文件使得开发者极难快速定位某个模块的相关测试。命名约定不统一：有 regression_、test_、smoke_、run_、verify_、check_ 多种前缀，各自语义模糊。
- 建议:

  建立 tests/unit/、tests/integration/、tests/e2e/ 等分层目录结构，并在各层内按业务域（scheduler/、equipment/ 等）进一步细分。

### GreedyScheduler.schedule() 方法过于庞大

- ID: F-greedyscheduler-schedule-方法过于庞大
- 严重级别: 高
- 分类: JavaScript
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  GreedyScheduler.schedule() 方法体从第 56 行到第 388 行，共约 **330 行**，是整个项目中最庞大的单个方法。虽然内部已将部分逻辑抽取到 _schedule_external 和 _schedule_internal，但主方法仍然包含：参数解析、ID 规范化、批次排序、种子结果处理、资源时间线初始化、就绪日期处理、主循环、结果汇总等多个职责。圆复杂度高，难以单独测试和理解。
- 建议:

  考虑将 schedule() 方法进一步拆分，将“参数解析”“ID 规范化”“资源时间线初始化”“结果汇总”等抽取为独立私有方法。
- 证据:
  - `core/algorithms/greedy/scheduler.py:56-388`
  - `core/algorithms/greedy/scheduler.py`

### 算法层关键参数缺乏类型约束

- ID: F-算法层关键参数缺乏类型约束
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  GreedyScheduler.schedule() 的 operations 参数类型为 List[Any]，batches 为 Dict[str, Any]，start_dt 为 Any，这些关键参数缺乏精确的类型标注。在 600 行的算法文件中，大量使用 Any 使得静态分析工具无法提供有效提示，也增加了开发者理解数据流的难度。尤其是 operations 中的元素在算法中被访问了 .batch_id、.seq、.source、.machine_id 等诸多属性，却没有定义对应的 Protocol 或抽象类型。
- 建议:

  为算法层定义 ScheduleOperation / ScheduleBatch 等 Protocol 或轻量级接口类型，替代当前的 Any。
- 证据:
  - `core/algorithms/greedy/scheduler.py:56-72`
  - `core/algorithms/greedy/scheduler.py`

### 开发依赖不完整，缺乏覆盖率工具

- ID: F-开发依赖不完整-缺乏覆盖率工具
- 严重级别: 低
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: M2
- 说明:

  requirements-dev.txt 仅包含 pytest 一个依赖，缺乏 pytest-cov、mypy、其他测试工具。项目中配置了 ruff 用于代码风格检查，但没有 pyright/mypy 的持续集成（pyrightconfig.json 存在但未在 CI 中强制执行）。缺乏覆盖率报告生成机制，无法量化了解当前测试覆盖情况。
- 建议:

  向 requirements-dev.txt 添加 pytest-cov 并在 CI 中生成覆盖率报告；考虑引入 pyright 或 mypy 的 CI 检查。
- 证据:
  - `requirements-dev.txt`

### 双套模板体系迁移不完整

- ID: F-双套模板体系迁移不完整
- 严重级别: 中
- 分类: HTML
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  当前项目存在两套并行的模板体系（v1: templates/ 和 v2: web_new_test/templates/）。v2 只覆盖了 7 个模板（base.html、dashboard.html、batches.html、batches_manage.html、config.html、config_manual.html、gantt.html），其余数十个页面仍用 v1 模板但嵌入 v2 的 base.html。这意味着：
  1. 迭代过渡期无限期延长——近 40+ 个页面未完成 v2 迁移
  2. 同一页面在 v1/v2 两种模式下的视觉体验可能不一致
  3. 模板 overlay 机制增加了调试难度，开发者需要了解“当前模式下实际加载了哪个模板”
- 建议:

  制定明确的 v2 迁移计划和截止日期；或者评估是否放弃 v2 overlay 方案，直接在 v1 模板上演进。
- 证据:
  - `web_new_test/templates`
  - `templates/`

### 开发文档体量庞大且与实现存在偏差

- ID: F-开发文档体量庞大且与实现存在偏差
- 严重级别: 中
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  开发文档目录中存在大量历史性文档：
  - 开发文档.md 超过 4300 行，内容涵盖从方案设计到实现代码示例，很多示例代码与实际实现已不一致
  - 系统速查表.md 超过 720 行，试图收敛所有知识但也需要持续同步
  - audit/ 目录下有 30+ 个审计文件，大部分为历史快照而非活跃文档
  - 策划方案/ 目录下仍保留早期策划文档，与当前实现已有差异
  这些文档体量庞大但缺乏明确的“当前有效/仅历史留档”标记，新开发者难以判断哪些信息仍然有效。
- 建议:

  对开发文档进行一次“归档清理”：将纯历史留档的文件移入 archived/ 子目录，策划方案标记为“已归档”；在开发文档.md 顶部明确标注“本文档为开工时点快照，实际实现以代码为准”。
- 证据:
  - `开发文档/`
  - `audit/`
  - `策划方案/`

### Python 3.8 已停止官方支持

- ID: F-python-3-8-已停止官方支持
- 严重级别: 高
- 分类: 性能
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  项目锁定 Python 3.8 以满足 Win7 兼容需求，但 Python 3.8 已于 2024 年 10 月官方停止支持（EOL）。这意味着：
  1. 无法利用 Python 3.9+ 的语言特性（如内置类型注解、字典合并操作符等）
  2. 新的安全漏洞不会被官方修复
  3. 部分三方库新版本已不再支持 3.8，未来升级会受限
  4. pyproject.toml 配置了 ruff target-version="py38"，强制语法限制在旧版本
  这是项目最大的技术债务之一，但由于 Win7 环境约束，短期内难以解决。
- 建议:

  评估目标环境升级到 Win10 的可能性，一旦环境允许即升级到 Python 3.10+；在此之前继续保持 3.8 但要关注关键安全修复。
- 证据:
  - `pyproject.toml`
  - `requirements.txt`

### 缺乏自动化持续集成流水线

- ID: F-缺乏自动化持续集成流水线
- 严重级别: 中
- 分类: 其他
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  项目当前缺乏 CI/CD 配置文件（未发现 .github/workflows/、.gitlab-ci.yml、Jenkinsfile 等）。所有测试似乎都依赖手动运行。雨然项目定位为 Win7 单机版且使用 PyInstaller 打包，但在开发机上仍然可以建立自动化测试流水线，确保每次提交不会引入回归问题。
- 建议:

  建立基础的 CI 流水线（可使用本地 Git hook 或简单的运行脚本），至少包含 ruff 检查 + pytest 快速套件。

### 前端静态资源缺乏构建流水线

- ID: F-前端静态资源缺乏构建流水线
- 严重级别: 低
- 分类: CSS
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  当前静态资源缺乏构建流水线：
  1. static/js/ 下有 23 个独立的 JS 文件（包含 common.js、common_confirm.js、common_draft.js 等 11 个 common_* 文件），每个页面可能需要加载多个文件
  2. 没有 JS/CSS 压缩、合并或版本哈希机制（虽然 web/bootstrap/static_versioning.py 存在，但是轻量级方案）
  3. 无模块化管理（无 webpack/vite/rollup），纯手动管理 script 标签
  对于单机离线应用来说这不是严重问题，但随着前端逻辑增多，这套方案会越来越难维护。
- 建议:

  将同属一个页面/功能的 JS 文件按模块合并；考虑引入轻量级构建工具或简单的合并脚本。

### 文档示例代码与实际实现偏差大

- ID: F-文档示例代码与实际实现偏差大
- 严重级别: 低
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: M3
- 说明:

  开发文档.md 中内嵌了大量“方案原始代码，保留”的示例（如 RouteParser、DeletionValidator、排产算法、事务管理、日志记录器、资源锁等），这些“方案代码”与实际实现已有明显差异（例如实际实现已经有 SGS 派工、自动资源分配、多起点优化等功能，但文档中的示例代码仍是早期的简单版本）。新开发者如果参考文档而非代码，会被误导。
- 建议:

  将文档中的“方案原始代码”块标记为“已归档/仅供参考，实际代码已大幅超越此版本”，避免误导。

## 评审里程碑

### M1 · 架构与项目结构层面技术债务

- 状态: 已完成
- 记录时间: 2026-04-05T14:43:08.081Z
- 已审模块: core/services/scheduler（目录结构）, web/routes（目录结构）, 项目整体分层架构
- 摘要:

  审查了整体项目结构、分层架构、模块职责边界。该项目采用四层架构（模型 → 仓储 → 服务 → 路由），已经过多轮拆分治理（schedule_summary、batch_service 等大文件已拆为子模块），整体分层合理。但仍存在若干架构层面的技术债务。
- 结论:

  审查了整体项目结构、分层架构、模块职责边界。该项目采用四层架构（模型 → 仓储 → 服务 → 路由），已经过多轮拆分治理（schedule_summary、batch_service 等大文件已拆为子模块），整体分层合理。但仍存在若干架构层面的技术债务。
- 问题:
  - [高] 可维护性: 排产调度服务目录过度膨胀
  - [中] 可维护性: 路由层文件数量过多
  - [中] 可维护性: ScheduleService 构造器承载 12 个仓储依赖
  - [中] 可维护性: 缺乏统一的依赖注入机制

### M2 · 测试体系与代码质量层面技术债务

- 状态: 已完成
- 记录时间: 2026-04-05T14:45:01.225Z
- 已审模块: tests/（测试体系）, 核心算法代码质量, 类型标注与安全性
- 摘要:

  审查了测试体系和核心代码质量。测试目录共计超过 310 个文件，其中 252 个为非标准的 regression 脚本式测试。核心算法中 GreedyScheduler.schedule() 方法过于庞大（330 行），关键参数缺乏类型约束（大量 Any）。测试基础设施和覆盖率工具有待补充。
- 结论:

  审查了测试体系和核心代码质量。测试目录共计超过 310 个文件，其中 252 个为非标准的 regression 脚本式测试。核心算法中 GreedyScheduler.schedule() 方法过于庞大（330 行），关键参数缺乏类型约束（大量 Any）。测试基础设施和覆盖率工具有待补充。
- 问题:
  - [高] 测试: 回归测试数量过度膨胀且约定非标准
  - [中] 测试: 测试缺乏分层目录结构
  - [高] JavaScript: GreedyScheduler.schedule() 方法过于庞大
  - [中] 可维护性: 算法层关键参数缺乏类型约束
  - [低] 测试: 开发依赖不完整，缺乏覆盖率工具

### M3 · 前端/文档/依赖兼容性/运维部署层面技术债务

- 状态: 已完成
- 记录时间: 2026-04-05T14:46:55.728Z
- 已审模块: 前端模板与静态资源, 开发文档与审计记录, 依赖与兼容性, 运维与部署体系
- 摘要:

  审查了前端模板体系、文档一致性、依赖兼容性与运维部署。发现最突出的技术债务是 Python 3.8 已停止官方支持但因 Win7 环境约束无法升级；双套模板体系迁移不完整（v2 仅覆盖 7 个模板）；开发文档体量庞大但与实际实现存在偏差；缺乏持续集成流水线。
- 结论:

  审查了前端模板体系、文档一致性、依赖兼容性与运维部署。发现最突出的技术债务是 Python 3.8 已停止官方支持但因 Win7 环境约束无法升级；双套模板体系迁移不完整（v2 仅覆盖 7 个模板）；开发文档体量庞大但与实际实现存在偏差；缺乏持续集成流水线。
- 问题:
  - [中] HTML: 双套模板体系迁移不完整
  - [中] 文档: 开发文档体量庞大且与实现存在偏差
  - [高] 性能: Python 3.8 已停止官方支持
  - [中] 其他: 缺乏自动化持续集成流水线
  - [低] CSS: 前端静态资源缺乏构建流水线
  - [低] 文档: 文档示例代码与实际实现偏差大

## 最终结论

## 技术债务全面梳理总结

对回转壳体单元智能排产系统进行了全面的技术债务梳理，覆盖架构、代码质量、测试、前端、文档、依赖兼容性、运维部署共 7 个维度，共发现 **15 项技术债务**（高 4 / 中 8 / 低 3）。

### 值得肯定的方面

- 四层分层架构（模型→仓储→服务→路由）设计清晰，职责边界明确
- 已完成多轮拆分治理（schedule_summary、batch_service 等大文件已拆为子模块）
- 枚举值归一化机制完善（normalization_matrix.py 作为统一事实来源）
- 数据库迁移机制成熟（6 个版本迁移脚本、前置检查、失败回滚）
- 错误处理体系完整（错误码、统一响应格式、中文提示）
- Excel 导入导出链路健壮（预览→确认→事务保护→留痕→严格拒绝）
- 备份/恢复机制设计周全（维护窗口互斥、完整性检查、自动回滚）

### 最紧迫的技术债务（按治理优先级排序）

1. **Python 3.8 已停止官方支持**（受 Win7 环境约束，需推动环境升级才能解决）
2. **回归测试体系膨胀**（252 个非标准脚本式测试，维护成本极高）
3. **排产服务目录膨胀**（45 文件扁平堆放，需进一步拆为子包）
4. **GreedyScheduler.schedule() 方法过大**（330 行单方法，需继续拆分）

### 建议的治理路径

- **短期**（可立即开始）：文档归档清理、开发依赖补充（pytest-cov）、建立基础 CI
- **中期**（规划排期）：测试体系重组（合并回归测试、分层目录）、scheduler 服务子包化、算法方法拆分
- **长期**（需业务配合）：推动 Win7→Win10 升级以解除 Python 3.8 束缚、完成 v2 模板迁移或放弃 overlay 方案

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnlve9te-mj6md5",
  "createdAt": "2026-04-05T00:00:00.000Z",
  "updatedAt": "2026-04-05T14:47:19.418Z",
  "finalizedAt": "2026-04-05T14:47:19.418Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "APS排产系统技术债务全面梳理",
    "date": "2026-04-05",
    "overview": "对回转壳体单元智能排产系统进行全面技术债务梳理，涵盖架构、代码质量、测试、文档、性能等维度"
  },
  "scope": {
    "markdown": "# APS 排产系统技术债务全面梳理\n\n**审查日期**: 2026-04-05  \n**审查范围**: 整个项目工作区  \n**审查目标**: 系统性梳理项目中存在的技术债务，按严重程度分类并提出治理建议  \n\n## 审查维度\n\n1. **架构层面** — 分层合理性、模块耦合、职责边界\n2. **代码质量** — 圈复杂度、重复代码、命名规范\n3. **依赖与兼容性** — 版本锁定、运行时兼容\n4. **测试体系** — 覆盖率、测试组织、回归测试膨胀\n5. **前端与模板** — 模板组织、静态资源管理\n6. **文档与留存** — 文档一致性、过时内容\n7. **运维与部署** — 打包流程、运行时维护"
  },
  "summary": {
    "latestConclusion": "## 技术债务全面梳理总结\n\n对回转壳体单元智能排产系统进行了全面的技术债务梳理，覆盖架构、代码质量、测试、前端、文档、依赖兼容性、运维部署共 7 个维度，共发现 **15 项技术债务**（高 4 / 中 8 / 低 3）。\n\n### 值得肯定的方面\n\n- 四层分层架构（模型→仓储→服务→路由）设计清晰，职责边界明确\n- 已完成多轮拆分治理（schedule_summary、batch_service 等大文件已拆为子模块）\n- 枚举值归一化机制完善（normalization_matrix.py 作为统一事实来源）\n- 数据库迁移机制成熟（6 个版本迁移脚本、前置检查、失败回滚）\n- 错误处理体系完整（错误码、统一响应格式、中文提示）\n- Excel 导入导出链路健壮（预览→确认→事务保护→留痕→严格拒绝）\n- 备份/恢复机制设计周全（维护窗口互斥、完整性检查、自动回滚）\n\n### 最紧迫的技术债务（按治理优先级排序）\n\n1. **Python 3.8 已停止官方支持**（受 Win7 环境约束，需推动环境升级才能解决）\n2. **回归测试体系膨胀**（252 个非标准脚本式测试，维护成本极高）\n3. **排产服务目录膨胀**（45 文件扁平堆放，需进一步拆为子包）\n4. **GreedyScheduler.schedule() 方法过大**（330 行单方法，需继续拆分）\n\n### 建议的治理路径\n\n- **短期**（可立即开始）：文档归档清理、开发依赖补充（pytest-cov）、建立基础 CI\n- **中期**（规划排期）：测试体系重组（合并回归测试、分层目录）、scheduler 服务子包化、算法方法拆分\n- **长期**（需业务配合）：推动 Win7→Win10 升级以解除 Python 3.8 束缚、完成 v2 模板迁移或放弃 overlay 方案",
    "recommendedNextAction": "建议优先处理：1）将文档归档清理和 CI 建设作为近期可执行的低成本改善；2）规划测试体系重组的迭代计划；3）评估目标环境升级可能性以解除 Python 3.8 约束",
    "reviewedModules": [
      "core/services/scheduler（目录结构）",
      "web/routes（目录结构）",
      "项目整体分层架构",
      "tests/（测试体系）",
      "核心算法代码质量",
      "类型标注与安全性",
      "前端模板与静态资源",
      "开发文档与审计记录",
      "依赖与兼容性",
      "运维与部署体系"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 15,
    "severity": {
      "high": 4,
      "medium": 8,
      "low": 3
    }
  },
  "milestones": [
    {
      "id": "M1",
      "title": "架构与项目结构层面技术债务",
      "status": "completed",
      "recordedAt": "2026-04-05T14:43:08.081Z",
      "summaryMarkdown": "审查了整体项目结构、分层架构、模块职责边界。该项目采用四层架构（模型 → 仓储 → 服务 → 路由），已经过多轮拆分治理（schedule_summary、batch_service 等大文件已拆为子模块），整体分层合理。但仍存在若干架构层面的技术债务。",
      "conclusionMarkdown": "审查了整体项目结构、分层架构、模块职责边界。该项目采用四层架构（模型 → 仓储 → 服务 → 路由），已经过多轮拆分治理（schedule_summary、batch_service 等大文件已拆为子模块），整体分层合理。但仍存在若干架构层面的技术债务。",
      "evidence": [],
      "reviewedModules": [
        "core/services/scheduler（目录结构）",
        "web/routes（目录结构）",
        "项目整体分层架构"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-排产调度服务目录过度膨胀",
        "F-路由层文件数量过多",
        "F-scheduleservice-构造器承载-12-个仓储依赖",
        "F-缺乏统一的依赖注入机制"
      ]
    },
    {
      "id": "M2",
      "title": "测试体系与代码质量层面技术债务",
      "status": "completed",
      "recordedAt": "2026-04-05T14:45:01.225Z",
      "summaryMarkdown": "审查了测试体系和核心代码质量。测试目录共计超过 310 个文件，其中 252 个为非标准的 regression 脚本式测试。核心算法中 GreedyScheduler.schedule() 方法过于庞大（330 行），关键参数缺乏类型约束（大量 Any）。测试基础设施和覆盖率工具有待补充。",
      "conclusionMarkdown": "审查了测试体系和核心代码质量。测试目录共计超过 310 个文件，其中 252 个为非标准的 regression 脚本式测试。核心算法中 GreedyScheduler.schedule() 方法过于庞大（330 行），关键参数缺乏类型约束（大量 Any）。测试基础设施和覆盖率工具有待补充。",
      "evidence": [],
      "reviewedModules": [
        "tests/（测试体系）",
        "核心算法代码质量",
        "类型标注与安全性"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-回归测试数量过度膨胀且约定非标准",
        "F-测试缺乏分层目录结构",
        "F-greedyscheduler-schedule-方法过于庞大",
        "F-算法层关键参数缺乏类型约束",
        "F-开发依赖不完整-缺乏覆盖率工具"
      ]
    },
    {
      "id": "M3",
      "title": "前端/文档/依赖兼容性/运维部署层面技术债务",
      "status": "completed",
      "recordedAt": "2026-04-05T14:46:55.728Z",
      "summaryMarkdown": "审查了前端模板体系、文档一致性、依赖兼容性与运维部署。发现最突出的技术债务是 Python 3.8 已停止官方支持但因 Win7 环境约束无法升级；双套模板体系迁移不完整（v2 仅覆盖 7 个模板）；开发文档体量庞大但与实际实现存在偏差；缺乏持续集成流水线。",
      "conclusionMarkdown": "审查了前端模板体系、文档一致性、依赖兼容性与运维部署。发现最突出的技术债务是 Python 3.8 已停止官方支持但因 Win7 环境约束无法升级；双套模板体系迁移不完整（v2 仅覆盖 7 个模板）；开发文档体量庞大但与实际实现存在偏差；缺乏持续集成流水线。",
      "evidence": [],
      "reviewedModules": [
        "前端模板与静态资源",
        "开发文档与审计记录",
        "依赖与兼容性",
        "运维与部署体系"
      ],
      "recommendedNextAction": null,
      "findingIds": [
        "F-双套模板体系迁移不完整",
        "F-开发文档体量庞大且与实现存在偏差",
        "F-python-3-8-已停止官方支持",
        "F-缺乏自动化持续集成流水线",
        "F-前端静态资源缺乏构建流水线",
        "F-文档示例代码与实际实现偏差大"
      ]
    }
  ],
  "findings": [
    {
      "id": "F-排产调度服务目录过度膨胀",
      "severity": "high",
      "category": "maintainability",
      "title": "排产调度服务目录过度膨胀",
      "descriptionMarkdown": "core/services/scheduler/ 目录包含 45 个文件，是项目中最庞大的单一模块目录。虽然已经过拆分治理（如 schedule_summary 拆为 4 个子文件、batch_service 拆出 3 个协作文件），但该目录仍承载了排产执行、批次管理、甘特图、资源排班、配置管理等多个独立子域的全部逻辑。文件之间的命名有较多前缀共享（schedule_*、gantt_*、resource_dispatch_*、batch_*），导致浏览和定位困难。",
      "recommendationMarkdown": "考虑将 scheduler 服务进一步拆分为子包（如 scheduler/gantt/、scheduler/dispatch/、scheduler/config/），每个子包保持独立的 __init__.py 和对外入口，降低目录内浏览成本。",
      "evidence": [
        {
          "path": "core/services/scheduler"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-路由层文件数量过多",
      "severity": "medium",
      "category": "maintainability",
      "title": "路由层文件数量过多",
      "descriptionMarkdown": "web/routes/ 目录包含 59 个文件。虽然每个文件职责相对单一，但大量以蓝图前缀开头的文件（scheduler_*.py 有 16 个、equipment_*.py 有 6 个、personnel_*.py 有 7 个、process_*.py 有 7 个、system_*.py 有 8 个）使得目录过于扁平。路由的 'side-effect 导入注册' 模式（如 scheduler.py 中 import scheduler_pages 仅为注册路由）增加了理解成本。",
      "recommendationMarkdown": "考虑将路由按业务域进一步组织为子包（如 routes/scheduler/、routes/equipment/ 等），用 __init__.py 统一注册蓝图。",
      "evidence": [
        {
          "path": "web/routes"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-scheduleservice-构造器承载-12-个仓储依赖",
      "severity": "medium",
      "category": "maintainability",
      "title": "ScheduleService 构造器承载 12 个仓储依赖",
      "descriptionMarkdown": "ScheduleService.__init__ 直接创建了 12 个仓储实例（batch_repo、op_repo、part_op_repo、group_repo、machine_repo、operator_repo、operator_machine_repo、supplier_repo、schedule_repo、history_repo 等），缺乏依赖注入容器或工厂方法的抽象。这意味着每次构造该服务都会创建大量数据库访问对象，且测试时难以隔离单个依赖。",
      "recommendationMarkdown": "引入轻量级的服务定位器或工厂模式，将仓储创建集中到一个 ServiceContainer 中，便于测试替换和生命周期管理。",
      "evidence": [
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 78,
          "lineEnd": 96
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        }
      ],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-缺乏统一的依赖注入机制",
      "severity": "medium",
      "category": "maintainability",
      "title": "缺乏统一的依赖注入机制",
      "descriptionMarkdown": "当前所有服务（ScheduleService、BatchService、GanttService 等）都在路由层或工厂函数中手动实例化，每个路由需要手动从请求上下文获取数据库连接并传入服务构造器。没有统一的 IoC 容器或服务注册机制，导致服务创建逻辑重复分散在各路由文件中。",
      "recommendationMarkdown": "可考虑在 Flask before_request 中统一创建 ServiceContainer 并绑定到请求上下文（g），各路由通过 g.services.xxx 获取服务实例。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-回归测试数量过度膨胀且约定非标准",
      "severity": "high",
      "category": "test",
      "title": "回归测试数量过度膨胀且约定非标准",
      "descriptionMarkdown": "测试目录中共有 **252 个** regression_*.py 文件，32 个 test_*.py，15 个 smoke_*.py，8 个 run_*.py，总计超过 **310 个测试文件**。大量 regression_ 文件采用“带 main() 函数的脚本式”模式而非标准 pytest 测试类/函数模式，通过 conftest.py 中的自定义收集器运行。这导致：\n1. 测试发现和维护困难，新来开发者难以理解这套非标准约定\n2. 每个 regression 文件通常只验证一个特定微观行为，粒度过细导致总文件数过多\n3. 创建临时目录、数据库等复杂设置逻辑在各 regression 文件间大量重复\n4. 没有明确的测试分组或标记机制，难以按模块、层级筛选执行",
      "recommendationMarkdown": "将相近的回归测试合并为标准 pytest 测试类，按模块分组到 tests/unit/、tests/integration/ 等子目录；引入 pytest.mark 分组机制。",
      "evidence": [
        {
          "path": "tests/conftest.py"
        },
        {
          "path": "tests/"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-测试缺乏分层目录结构",
      "severity": "medium",
      "category": "test",
      "title": "测试缺乏分层目录结构",
      "descriptionMarkdown": "当前 regression 测试文件全部扁平地放在 tests/ 目录下，没有按业务域分子目录。252 个 regression 文件 + 32 个 test 文件 + 15 个 smoke 文件使得开发者极难快速定位某个模块的相关测试。命名约定不统一：有 regression_、test_、smoke_、run_、verify_、check_ 多种前缀，各自语义模糊。",
      "recommendationMarkdown": "建立 tests/unit/、tests/integration/、tests/e2e/ 等分层目录结构，并在各层内按业务域（scheduler/、equipment/ 等）进一步细分。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-greedyscheduler-schedule-方法过于庞大",
      "severity": "high",
      "category": "javascript",
      "title": "GreedyScheduler.schedule() 方法过于庞大",
      "descriptionMarkdown": "GreedyScheduler.schedule() 方法体从第 56 行到第 388 行，共约 **330 行**，是整个项目中最庞大的单个方法。虽然内部已将部分逻辑抽取到 _schedule_external 和 _schedule_internal，但主方法仍然包含：参数解析、ID 规范化、批次排序、种子结果处理、资源时间线初始化、就绪日期处理、主循环、结果汇总等多个职责。圆复杂度高，难以单独测试和理解。",
      "recommendationMarkdown": "考虑将 schedule() 方法进一步拆分，将“参数解析”“ID 规范化”“资源时间线初始化”“结果汇总”等抽取为独立私有方法。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 56,
          "lineEnd": 388
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-算法层关键参数缺乏类型约束",
      "severity": "medium",
      "category": "maintainability",
      "title": "算法层关键参数缺乏类型约束",
      "descriptionMarkdown": "GreedyScheduler.schedule() 的 operations 参数类型为 List[Any]，batches 为 Dict[str, Any]，start_dt 为 Any，这些关键参数缺乏精确的类型标注。在 600 行的算法文件中，大量使用 Any 使得静态分析工具无法提供有效提示，也增加了开发者理解数据流的难度。尤其是 operations 中的元素在算法中被访问了 .batch_id、.seq、.source、.machine_id 等诸多属性，却没有定义对应的 Protocol 或抽象类型。",
      "recommendationMarkdown": "为算法层定义 ScheduleOperation / ScheduleBatch 等 Protocol 或轻量级接口类型，替代当前的 Any。",
      "evidence": [
        {
          "path": "core/algorithms/greedy/scheduler.py",
          "lineStart": 56,
          "lineEnd": 72
        },
        {
          "path": "core/algorithms/greedy/scheduler.py"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-开发依赖不完整-缺乏覆盖率工具",
      "severity": "low",
      "category": "test",
      "title": "开发依赖不完整，缺乏覆盖率工具",
      "descriptionMarkdown": "requirements-dev.txt 仅包含 pytest 一个依赖，缺乏 pytest-cov、mypy、其他测试工具。项目中配置了 ruff 用于代码风格检查，但没有 pyright/mypy 的持续集成（pyrightconfig.json 存在但未在 CI 中强制执行）。缺乏覆盖率报告生成机制，无法量化了解当前测试覆盖情况。",
      "recommendationMarkdown": "向 requirements-dev.txt 添加 pytest-cov 并在 CI 中生成覆盖率报告；考虑引入 pyright 或 mypy 的 CI 检查。",
      "evidence": [
        {
          "path": "requirements-dev.txt"
        }
      ],
      "relatedMilestoneIds": [
        "M2"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-双套模板体系迁移不完整",
      "severity": "medium",
      "category": "html",
      "title": "双套模板体系迁移不完整",
      "descriptionMarkdown": "当前项目存在两套并行的模板体系（v1: templates/ 和 v2: web_new_test/templates/）。v2 只覆盖了 7 个模板（base.html、dashboard.html、batches.html、batches_manage.html、config.html、config_manual.html、gantt.html），其余数十个页面仍用 v1 模板但嵌入 v2 的 base.html。这意味着：\n1. 迭代过渡期无限期延长——近 40+ 个页面未完成 v2 迁移\n2. 同一页面在 v1/v2 两种模式下的视觉体验可能不一致\n3. 模板 overlay 机制增加了调试难度，开发者需要了解“当前模式下实际加载了哪个模板”",
      "recommendationMarkdown": "制定明确的 v2 迁移计划和截止日期；或者评估是否放弃 v2 overlay 方案，直接在 v1 模板上演进。",
      "evidence": [
        {
          "path": "web_new_test/templates"
        },
        {
          "path": "templates/"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-开发文档体量庞大且与实现存在偏差",
      "severity": "medium",
      "category": "docs",
      "title": "开发文档体量庞大且与实现存在偏差",
      "descriptionMarkdown": "开发文档目录中存在大量历史性文档：\n- 开发文档.md 超过 4300 行，内容涵盖从方案设计到实现代码示例，很多示例代码与实际实现已不一致\n- 系统速查表.md 超过 720 行，试图收敛所有知识但也需要持续同步\n- audit/ 目录下有 30+ 个审计文件，大部分为历史快照而非活跃文档\n- 策划方案/ 目录下仍保留早期策划文档，与当前实现已有差异\n这些文档体量庞大但缺乏明确的“当前有效/仅历史留档”标记，新开发者难以判断哪些信息仍然有效。",
      "recommendationMarkdown": "对开发文档进行一次“归档清理”：将纯历史留档的文件移入 archived/ 子目录，策划方案标记为“已归档”；在开发文档.md 顶部明确标注“本文档为开工时点快照，实际实现以代码为准”。",
      "evidence": [
        {
          "path": "开发文档/"
        },
        {
          "path": "audit/"
        },
        {
          "path": "策划方案/"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-python-3-8-已停止官方支持",
      "severity": "high",
      "category": "performance",
      "title": "Python 3.8 已停止官方支持",
      "descriptionMarkdown": "项目锁定 Python 3.8 以满足 Win7 兼容需求，但 Python 3.8 已于 2024 年 10 月官方停止支持（EOL）。这意味着：\n1. 无法利用 Python 3.9+ 的语言特性（如内置类型注解、字典合并操作符等）\n2. 新的安全漏洞不会被官方修复\n3. 部分三方库新版本已不再支持 3.8，未来升级会受限\n4. pyproject.toml 配置了 ruff target-version=\"py38\"，强制语法限制在旧版本\n这是项目最大的技术债务之一，但由于 Win7 环境约束，短期内难以解决。",
      "recommendationMarkdown": "评估目标环境升级到 Win10 的可能性，一旦环境允许即升级到 Python 3.10+；在此之前继续保持 3.8 但要关注关键安全修复。",
      "evidence": [
        {
          "path": "pyproject.toml"
        },
        {
          "path": "requirements.txt"
        }
      ],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-缺乏自动化持续集成流水线",
      "severity": "medium",
      "category": "other",
      "title": "缺乏自动化持续集成流水线",
      "descriptionMarkdown": "项目当前缺乏 CI/CD 配置文件（未发现 .github/workflows/、.gitlab-ci.yml、Jenkinsfile 等）。所有测试似乎都依赖手动运行。雨然项目定位为 Win7 单机版且使用 PyInstaller 打包，但在开发机上仍然可以建立自动化测试流水线，确保每次提交不会引入回归问题。",
      "recommendationMarkdown": "建立基础的 CI 流水线（可使用本地 Git hook 或简单的运行脚本），至少包含 ruff 检查 + pytest 快速套件。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-前端静态资源缺乏构建流水线",
      "severity": "low",
      "category": "css",
      "title": "前端静态资源缺乏构建流水线",
      "descriptionMarkdown": "当前静态资源缺乏构建流水线：\n1. static/js/ 下有 23 个独立的 JS 文件（包含 common.js、common_confirm.js、common_draft.js 等 11 个 common_* 文件），每个页面可能需要加载多个文件\n2. 没有 JS/CSS 压缩、合并或版本哈希机制（虽然 web/bootstrap/static_versioning.py 存在，但是轻量级方案）\n3. 无模块化管理（无 webpack/vite/rollup），纯手动管理 script 标签\n对于单机离线应用来说这不是严重问题，但随着前端逻辑增多，这套方案会越来越难维护。",
      "recommendationMarkdown": "将同属一个页面/功能的 JS 文件按模块合并；考虑引入轻量级构建工具或简单的合并脚本。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "F-文档示例代码与实际实现偏差大",
      "severity": "low",
      "category": "docs",
      "title": "文档示例代码与实际实现偏差大",
      "descriptionMarkdown": "开发文档.md 中内嵌了大量“方案原始代码，保留”的示例（如 RouteParser、DeletionValidator、排产算法、事务管理、日志记录器、资源锁等），这些“方案代码”与实际实现已有明显差异（例如实际实现已经有 SGS 派工、自动资源分配、多起点优化等功能，但文档中的示例代码仍是早期的简单版本）。新开发者如果参考文档而非代码，会被误导。",
      "recommendationMarkdown": "将文档中的“方案原始代码”块标记为“已归档/仅供参考，实际代码已大幅超越此版本”，避免误导。",
      "evidence": [],
      "relatedMilestoneIds": [
        "M3"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:ddc90dcd20f09eb8b43fa839ce3a2b149a281e0dd06e947dec1240e24c50f712",
    "generatedAt": "2026-04-05T14:47:19.418Z",
    "locale": "zh-CN"
  }
}
```
