# 20260405_技术债务最终合并修复plan_深度review_第四轮
- 日期: 2026-04-05
- 概述: 针对 .limcode/plans/20260405_技术债务最终合并修复plan.md 的可执行性、边界一致性与潜在BUG进行三轮式深度审查。
- 状态: 已完成
- 总体结论: 需要后续跟进

## 评审范围

# review

- 日期：2026-04-05
- 目标：审查 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 是否能在当前仓库事实上达成其治理目标，重点关注可执行性、优雅性、是否存在过度兜底/静默回退、逻辑严谨性与潜在BUG。
- 方法：以计划文本为主，交叉核对当前代码与目录事实，按模块逐步记录里程碑。
- 当前状态：进行中。

## 评审摘要

- 当前状态: 已完成
- 已审模块: .limcode/plans/20260405_技术债务最终合并修复plan.md, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_input_builder.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_persistence.py, core/services/scheduler/schedule_orchestrator.py, web/bootstrap/static_versioning.py, web/ui_mode.py, tests/test_architecture_fitness.py, pyproject.toml, requirements-dev.txt, .pre-commit-config.yaml, web/bootstrap/factory.py, web/routes/scheduler_config.py
- 当前进度: 已记录 3 个里程碑；最新：m3
- 里程碑总数: 3
- 已完成里程碑: 3
- 问题总数: 3
- 问题严重级别分布: 高 1 / 中 2 / 低 0
- 最新结论: 结论：这份 plan 的主体框架、批次顺序和多数事实基线是可信的，具备“修订后执行”的价值，不建议推倒重写；但它暂时还不能原样作为唯一权威执行文件。最关键的问题有三类：一是任务 3 之后仍反复引用迁移前旧路径，破坏顺序执行的一致性；二是对 `web/ui_mode.py` 等现有静默回退路径的治理与门禁约束仍不够硬；三是新增 `tests/regression/**` 的时序早于嵌套测试门禁配置落地，和“每批次都跑统一质量门禁”的规则存在冲突。建议先做一次只改 plan 文本的勘误：统一任务 3 之后的路径口径、前移最小测试目录门禁配置、补强静默回退治理要求；完成这三点后，该 plan 才适合作为后续唯一执行依据。
- 下一步建议: 先修订 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 本身，再启动实际整改批次；修订优先级依次为：1）全文路径勘误；2）静默回退治理与门禁补强；3）嵌套测试目录门禁时序前移。
- 总体结论: 需要后续跟进

## 评审发现

### 任务 3 后路径漂移

- ID: post-task3-path-drift
- 严重级别: 高
- 分类: 文档
- 跟踪状态: 开放
- 相关里程碑: m1
- 说明:

  任务 3 已明确把大量 scheduler 服务文件迁入 `core/services/scheduler/run|gantt|summary|calendar/**`，并把页面 route 迁入 `web/routes/domains/**`；但任务 4、5、7、8 的文件职责、步骤说明和改造目标仍多次引用迁移前的旧根路径，例如 `core/services/scheduler/schedule_optimizer.py`、`core/services/scheduler/schedule_input_builder.py`、`core/services/scheduler/gantt_critical_chain.py`、`web/routes/scheduler_excel_calendar.py`、`web/routes/system_logs.py`。其中 route 侧问题是确定性冲突，因为任务 3 的根层保留清单并不包含这些文件。该漂移会使 plan 失去“唯一权威执行文件”的价值，执行者必须自行猜测应该修改旧文件、薄门面，还是新子包文件。
- 建议:

  先统一一次“任务 3 之后只能使用迁移后路径”的全文勘误：route 统一改写为 `web/routes/domains/**`，scheduler 内部文件统一改写为 `core/services/scheduler/<子包>/**`；仅对显式保留的根层薄门面继续使用旧路径，并把这些例外写入一张兼容入口清单。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:470-560`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:649-699`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:734-752`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:944-985`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1057-1097`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/ui_mode.py`
  - `web/bootstrap/static_versioning.py`
  - `tests/test_architecture_fitness.py`

### 静默回退门禁缺口

- ID: silent-fallback-governance-gap
- 严重级别: 中
- 分类: 可维护性
- 跟踪状态: 开放
- 相关里程碑: m1
- 说明:

  plan 全局规则反复强调禁止新增静默回退，并在任务 8 中强制清理 `static_versioning.py` 的吞异常路径；但对 `web/ui_mode.py` 仅要求“显式收口”，没有把当前多处 `except Exception: pass`、返回空字符串、返回 `None` 的路径纳入硬性删除/门禁范围。同时，当前 `tests/test_architecture_fitness.py` 的静默吞异常门禁只识别 `except Exception: pass / ...`，并不覆盖 `except Exception: return None`、`return ""`、`continue` 这类同样会隐藏故障的分支。结果是：即使按 plan 完成任务 1 和任务 8，仓库仍缺少一条能持续约束“静默回退”语义的统一门禁。
- 建议:

  在任务 1 或任务 8 中增加一条明确规则：`web/ui_mode.py` 的 `except Exception: pass` 与“异常后直接返回空值”的分支要么改成可观测降级，要么列入带退出条件的白名单；同时扩展门禁覆盖范围，不再只扫描 `pass / ...` 两种静默模式。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:122-127`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1117-1139`
  - `web/ui_mode.py:167-205#init_ui_mode`
  - `web/ui_mode.py:305-418#safe_url_for`
  - `tests/test_architecture_fitness.py:453-481#test_no_silent_exception_swallow`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/ui_mode.py`
  - `web/bootstrap/static_versioning.py`
  - `tests/test_architecture_fitness.py`

### 嵌套测试门禁时序断裂

- ID: nested-test-gate-ordering
- 严重级别: 中
- 分类: 测试
- 跟踪状态: 开放
- 相关里程碑: m2
- 说明:

  任务 1 要求所有批次共用统一质量门禁；任务 8 又明确要求把新增专项回归直接落到 `tests/regression/**`；但任务 9 才计划修改 `pyproject.toml` 补充分层目录的采集与规则。当前仓库的 `ruff` 例外仅写成 `tests/*`，不会匹配 `tests/regression/**` 这类嵌套路径。这意味着执行到任务 8 时，新增的嵌套测试文件会立即进入统一门禁，却没有获得计划预期中的测试目录宽松规则，导致批次间的校验语义不稳定。
- 建议:

  把最小化的嵌套测试目录门禁配置前移到任务 1 或任务 8 起点，例如先把 `ruff` 放宽规则改成递归匹配，并为 `pytest` 提前建立子目录可收集的保守配置；这样任务 8 新增 `tests/regression/**` 文件时就不会破坏“每批次都能跑统一门禁”的要求。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:250-253`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1110-1153`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1218-1221`
  - `pyproject.toml:37-43`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `pyproject.toml`

## 评审里程碑

### m1 · 主链与目录迁移一致性首轮审查

- 状态: 已完成
- 记录时间: 2026-04-05T18:26:31.845Z
- 已审模块: .limcode/plans/20260405_技术债务最终合并修复plan.md, core/services/scheduler/schedule_service.py, core/services/scheduler/schedule_input_collector.py, core/services/scheduler/schedule_input_builder.py, core/services/scheduler/schedule_optimizer.py, core/services/scheduler/schedule_optimizer_steps.py, core/services/scheduler/schedule_persistence.py, core/services/scheduler/schedule_orchestrator.py, web/bootstrap/static_versioning.py, web/ui_mode.py, tests/test_architecture_fitness.py
- 摘要:

  已完成对任务 3～8 的路径落位、主链兼容桥收口点、静态资源版本化与双模板运行时治理条目的交叉核对。结论是：plan 的治理方向总体正确，但仍存在一个会直接影响顺序执行的高风险问题——任务 3 已规定把大量 scheduler 服务文件与 route 文件迁入子包/子目录，但任务 4、5、7、8 的多处后续步骤仍继续引用迁移前旧路径，执行者在批次推进时会遇到“按 plan 已迁走、按后续步骤又要改旧文件”的冲突。此外，plan 对 `web/ui_mode.py` 的静默回退治理表述偏软，尚不足以覆盖当前代码中的多处 `except Exception: pass` / 返回空值路径。
- 结论:

  plan 已接近可执行，但在“任务 3 之后的路径事实一致性”和“静默回退治理闭环”上仍未完全达标，暂不适合原样作为唯一权威执行文件。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:450-560`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:640-760`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:930-990`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1057-1139`
  - `web/ui_mode.py:144-205#init_ui_mode`
  - `web/ui_mode.py:305-418#safe_url_for`
  - `web/bootstrap/static_versioning.py:59-103#build_versioned_url_for`
  - `tests/test_architecture_fitness.py:404-497#test_no_silent_exception_swallow`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `web/ui_mode.py`
  - `web/bootstrap/static_versioning.py`
  - `tests/test_architecture_fitness.py`
- 下一步建议:

  继续检查测试重组、请求级装配与文档入口链是否存在范围低估或验证命令与现状不一致的问题。
- 问题:
  - [高] 文档: 任务 3 后路径漂移
  - [中] 可维护性: 静默回退门禁缺口

### m2 · 质量门禁与测试重组时序审查

- 状态: 已完成
- 记录时间: 2026-04-05T18:27:12.104Z
- 已审模块: .limcode/plans/20260405_技术债务最终合并修复plan.md, pyproject.toml
- 摘要:

  已核对任务 1、任务 8、任务 9 与当前 `pyproject.toml` 的门禁配置关系。发现 plan 在“先创建嵌套测试目录、再统一配置门禁”的时序上存在一个中风险断点：任务 8 已要求新增 `tests/regression/**` 专项回归，但任务 9 才补 `pyproject.toml` 的分层采集与目录规则；而当前 `ruff` 对测试文件的放宽规则仅覆盖 `tests/*`，不会命中嵌套子目录。由于任务 1 已把统一质量门禁前置到全批次执行，这会让任务 8 新增的嵌套测试文件在批次 4 就受到与计划预期不一致的更严格校验。
- 结论:

  plan 在测试分层的最终方向上是正确的，但为保证逐批可落地，至少需要把“嵌套测试目录的最小门禁配置”前移到首次新增 `tests/regression/**` 文件之前。
- 证据:
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:250-253`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1110-1153`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md:1218-1221`
  - `pyproject.toml:37-43`
  - `.limcode/plans/20260405_技术债务最终合并修复plan.md`
  - `pyproject.toml`
- 下一步建议:

  最后再检查测试重组范围估计、固定父级路径改造量与文档入口链约束是否还有遗漏。
- 问题:
  - [中] 测试: 嵌套测试门禁时序断裂

### m3 · 工程基线事实核对与正向确认

- 状态: 已完成
- 记录时间: 2026-04-05T18:28:15.310Z
- 已审模块: requirements-dev.txt, .pre-commit-config.yaml, pyproject.toml, core/services/scheduler/schedule_service.py, web/bootstrap/factory.py, web/routes/scheduler_config.py
- 摘要:

  已对 plan 中若干关键“现状事实”做抽样核对，结果表明这份 plan 并非脱离仓库现实的空中设计：`requirements-dev.txt` 当前确实只有最小依赖；`.pre-commit-config.yaml` 已实际启用 `ruff`；`ScheduleService.__init__` 当前签名仍是 `(conn, logger=None, op_logger=None)` 且内部平铺创建 10 个仓储实例；`web/bootstrap/factory.py:_open_db` 目前确实承担静态路径短路、维护窗口检查、`g.db/g.op_logger/g.app_logger` 初始化；`web/routes/` 中直接 `Service(g.db, ...)` 命中数为 182，`scheduler_config.py` 里也确有 6 处直接装配。说明 plan 的大方向与很多关键数字、文件边界是建立在真实代码事实之上的。
- 结论:

  除前两轮发现的执行性缺口外，这份 plan 的基线盘点质量总体较高，很多关键事实描述是准确的，因此它更适合被修订而不是推倒重写。
- 证据:
  - `requirements-dev.txt:1-4`
  - `.pre-commit-config.yaml:1-12`
  - `pyproject.toml:1-43`
  - `core/services/scheduler/schedule_service.py:78-96#ScheduleService.__init__`
  - `web/bootstrap/factory.py:262-305#_open_db`
  - `web/routes/scheduler_config.py:281-426`
  - `requirements-dev.txt`
  - `.pre-commit-config.yaml`
  - `pyproject.toml`
  - `core/services/scheduler/schedule_service.py`
  - `web/bootstrap/factory.py`
  - `web/routes/scheduler_config.py`
- 下一步建议:

  综合前面三轮结论，给出最终结论与修订优先级建议。

## 最终结论

结论：这份 plan 的主体框架、批次顺序和多数事实基线是可信的，具备“修订后执行”的价值，不建议推倒重写；但它暂时还不能原样作为唯一权威执行文件。最关键的问题有三类：一是任务 3 之后仍反复引用迁移前旧路径，破坏顺序执行的一致性；二是对 `web/ui_mode.py` 等现有静默回退路径的治理与门禁约束仍不够硬；三是新增 `tests/regression/**` 的时序早于嵌套测试门禁配置落地，和“每批次都跑统一质量门禁”的规则存在冲突。建议先做一次只改 plan 文本的勘误：统一任务 3 之后的路径口径、前移最小测试目录门禁配置、补强静默回退治理要求；完成这三点后，该 plan 才适合作为后续唯一执行依据。

## 评审快照

```json
{
  "formatVersion": 4,
  "kind": "limcode.review",
  "reviewRunId": "review-mnm37k4n-bnsc4x",
  "createdAt": "2026-04-05T00:00:00.000Z",
  "updatedAt": "2026-04-05T18:28:29.477Z",
  "finalizedAt": "2026-04-05T18:28:29.477Z",
  "status": "completed",
  "overallDecision": "needs_follow_up",
  "header": {
    "title": "20260405_技术债务最终合并修复plan_深度review_第四轮",
    "date": "2026-04-05",
    "overview": "针对 .limcode/plans/20260405_技术债务最终合并修复plan.md 的可执行性、边界一致性与潜在BUG进行三轮式深度审查。"
  },
  "scope": {
    "markdown": "# review\n\n- 日期：2026-04-05\n- 目标：审查 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 是否能在当前仓库事实上达成其治理目标，重点关注可执行性、优雅性、是否存在过度兜底/静默回退、逻辑严谨性与潜在BUG。\n- 方法：以计划文本为主，交叉核对当前代码与目录事实，按模块逐步记录里程碑。\n- 当前状态：进行中。"
  },
  "summary": {
    "latestConclusion": "结论：这份 plan 的主体框架、批次顺序和多数事实基线是可信的，具备“修订后执行”的价值，不建议推倒重写；但它暂时还不能原样作为唯一权威执行文件。最关键的问题有三类：一是任务 3 之后仍反复引用迁移前旧路径，破坏顺序执行的一致性；二是对 `web/ui_mode.py` 等现有静默回退路径的治理与门禁约束仍不够硬；三是新增 `tests/regression/**` 的时序早于嵌套测试门禁配置落地，和“每批次都跑统一质量门禁”的规则存在冲突。建议先做一次只改 plan 文本的勘误：统一任务 3 之后的路径口径、前移最小测试目录门禁配置、补强静默回退治理要求；完成这三点后，该 plan 才适合作为后续唯一执行依据。",
    "recommendedNextAction": "先修订 `.limcode/plans/20260405_技术债务最终合并修复plan.md` 本身，再启动实际整改批次；修订优先级依次为：1）全文路径勘误；2）静默回退治理与门禁补强；3）嵌套测试目录门禁时序前移。",
    "reviewedModules": [
      ".limcode/plans/20260405_技术债务最终合并修复plan.md",
      "core/services/scheduler/schedule_service.py",
      "core/services/scheduler/schedule_input_collector.py",
      "core/services/scheduler/schedule_input_builder.py",
      "core/services/scheduler/schedule_optimizer.py",
      "core/services/scheduler/schedule_optimizer_steps.py",
      "core/services/scheduler/schedule_persistence.py",
      "core/services/scheduler/schedule_orchestrator.py",
      "web/bootstrap/static_versioning.py",
      "web/ui_mode.py",
      "tests/test_architecture_fitness.py",
      "pyproject.toml",
      "requirements-dev.txt",
      ".pre-commit-config.yaml",
      "web/bootstrap/factory.py",
      "web/routes/scheduler_config.py"
    ]
  },
  "stats": {
    "totalMilestones": 3,
    "completedMilestones": 3,
    "totalFindings": 3,
    "severity": {
      "high": 1,
      "medium": 2,
      "low": 0
    }
  },
  "milestones": [
    {
      "id": "m1",
      "title": "主链与目录迁移一致性首轮审查",
      "status": "completed",
      "recordedAt": "2026-04-05T18:26:31.845Z",
      "summaryMarkdown": "已完成对任务 3～8 的路径落位、主链兼容桥收口点、静态资源版本化与双模板运行时治理条目的交叉核对。结论是：plan 的治理方向总体正确，但仍存在一个会直接影响顺序执行的高风险问题——任务 3 已规定把大量 scheduler 服务文件与 route 文件迁入子包/子目录，但任务 4、5、7、8 的多处后续步骤仍继续引用迁移前旧路径，执行者在批次推进时会遇到“按 plan 已迁走、按后续步骤又要改旧文件”的冲突。此外，plan 对 `web/ui_mode.py` 的静默回退治理表述偏软，尚不足以覆盖当前代码中的多处 `except Exception: pass` / 返回空值路径。",
      "conclusionMarkdown": "plan 已接近可执行，但在“任务 3 之后的路径事实一致性”和“静默回退治理闭环”上仍未完全达标，暂不适合原样作为唯一权威执行文件。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 450,
          "lineEnd": 560
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 640,
          "lineEnd": 760
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 930,
          "lineEnd": 990
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1057,
          "lineEnd": 1139
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 144,
          "lineEnd": 205,
          "symbol": "init_ui_mode"
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 305,
          "lineEnd": 418,
          "symbol": "safe_url_for"
        },
        {
          "path": "web/bootstrap/static_versioning.py",
          "lineStart": 59,
          "lineEnd": 103,
          "symbol": "build_versioned_url_for"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 404,
          "lineEnd": 497,
          "symbol": "test_no_silent_exception_swallow"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/20260405_技术债务最终合并修复plan.md",
        "core/services/scheduler/schedule_service.py",
        "core/services/scheduler/schedule_input_collector.py",
        "core/services/scheduler/schedule_input_builder.py",
        "core/services/scheduler/schedule_optimizer.py",
        "core/services/scheduler/schedule_optimizer_steps.py",
        "core/services/scheduler/schedule_persistence.py",
        "core/services/scheduler/schedule_orchestrator.py",
        "web/bootstrap/static_versioning.py",
        "web/ui_mode.py",
        "tests/test_architecture_fitness.py"
      ],
      "recommendedNextAction": "继续检查测试重组、请求级装配与文档入口链是否存在范围低估或验证命令与现状不一致的问题。",
      "findingIds": [
        "post-task3-path-drift",
        "silent-fallback-governance-gap"
      ]
    },
    {
      "id": "m2",
      "title": "质量门禁与测试重组时序审查",
      "status": "completed",
      "recordedAt": "2026-04-05T18:27:12.104Z",
      "summaryMarkdown": "已核对任务 1、任务 8、任务 9 与当前 `pyproject.toml` 的门禁配置关系。发现 plan 在“先创建嵌套测试目录、再统一配置门禁”的时序上存在一个中风险断点：任务 8 已要求新增 `tests/regression/**` 专项回归，但任务 9 才补 `pyproject.toml` 的分层采集与目录规则；而当前 `ruff` 对测试文件的放宽规则仅覆盖 `tests/*`，不会命中嵌套子目录。由于任务 1 已把统一质量门禁前置到全批次执行，这会让任务 8 新增的嵌套测试文件在批次 4 就受到与计划预期不一致的更严格校验。",
      "conclusionMarkdown": "plan 在测试分层的最终方向上是正确的，但为保证逐批可落地，至少需要把“嵌套测试目录的最小门禁配置”前移到首次新增 `tests/regression/**` 文件之前。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 250,
          "lineEnd": 253
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1110,
          "lineEnd": 1153
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1218,
          "lineEnd": 1221
        },
        {
          "path": "pyproject.toml",
          "lineStart": 37,
          "lineEnd": 43
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "pyproject.toml"
        }
      ],
      "reviewedModules": [
        ".limcode/plans/20260405_技术债务最终合并修复plan.md",
        "pyproject.toml"
      ],
      "recommendedNextAction": "最后再检查测试重组范围估计、固定父级路径改造量与文档入口链约束是否还有遗漏。",
      "findingIds": [
        "nested-test-gate-ordering"
      ]
    },
    {
      "id": "m3",
      "title": "工程基线事实核对与正向确认",
      "status": "completed",
      "recordedAt": "2026-04-05T18:28:15.310Z",
      "summaryMarkdown": "已对 plan 中若干关键“现状事实”做抽样核对，结果表明这份 plan 并非脱离仓库现实的空中设计：`requirements-dev.txt` 当前确实只有最小依赖；`.pre-commit-config.yaml` 已实际启用 `ruff`；`ScheduleService.__init__` 当前签名仍是 `(conn, logger=None, op_logger=None)` 且内部平铺创建 10 个仓储实例；`web/bootstrap/factory.py:_open_db` 目前确实承担静态路径短路、维护窗口检查、`g.db/g.op_logger/g.app_logger` 初始化；`web/routes/` 中直接 `Service(g.db, ...)` 命中数为 182，`scheduler_config.py` 里也确有 6 处直接装配。说明 plan 的大方向与很多关键数字、文件边界是建立在真实代码事实之上的。",
      "conclusionMarkdown": "除前两轮发现的执行性缺口外，这份 plan 的基线盘点质量总体较高，很多关键事实描述是准确的，因此它更适合被修订而不是推倒重写。",
      "evidence": [
        {
          "path": "requirements-dev.txt",
          "lineStart": 1,
          "lineEnd": 4
        },
        {
          "path": ".pre-commit-config.yaml",
          "lineStart": 1,
          "lineEnd": 12
        },
        {
          "path": "pyproject.toml",
          "lineStart": 1,
          "lineEnd": 43
        },
        {
          "path": "core/services/scheduler/schedule_service.py",
          "lineStart": 78,
          "lineEnd": 96,
          "symbol": "ScheduleService.__init__"
        },
        {
          "path": "web/bootstrap/factory.py",
          "lineStart": 262,
          "lineEnd": 305,
          "symbol": "_open_db"
        },
        {
          "path": "web/routes/scheduler_config.py",
          "lineStart": 281,
          "lineEnd": 426
        },
        {
          "path": "requirements-dev.txt"
        },
        {
          "path": ".pre-commit-config.yaml"
        },
        {
          "path": "pyproject.toml"
        },
        {
          "path": "core/services/scheduler/schedule_service.py"
        },
        {
          "path": "web/bootstrap/factory.py"
        },
        {
          "path": "web/routes/scheduler_config.py"
        }
      ],
      "reviewedModules": [
        "requirements-dev.txt",
        ".pre-commit-config.yaml",
        "pyproject.toml",
        "core/services/scheduler/schedule_service.py",
        "web/bootstrap/factory.py",
        "web/routes/scheduler_config.py"
      ],
      "recommendedNextAction": "综合前面三轮结论，给出最终结论与修订优先级建议。",
      "findingIds": []
    }
  ],
  "findings": [
    {
      "id": "post-task3-path-drift",
      "severity": "high",
      "category": "docs",
      "title": "任务 3 后路径漂移",
      "descriptionMarkdown": "任务 3 已明确把大量 scheduler 服务文件迁入 `core/services/scheduler/run|gantt|summary|calendar/**`，并把页面 route 迁入 `web/routes/domains/**`；但任务 4、5、7、8 的文件职责、步骤说明和改造目标仍多次引用迁移前的旧根路径，例如 `core/services/scheduler/schedule_optimizer.py`、`core/services/scheduler/schedule_input_builder.py`、`core/services/scheduler/gantt_critical_chain.py`、`web/routes/scheduler_excel_calendar.py`、`web/routes/system_logs.py`。其中 route 侧问题是确定性冲突，因为任务 3 的根层保留清单并不包含这些文件。该漂移会使 plan 失去“唯一权威执行文件”的价值，执行者必须自行猜测应该修改旧文件、薄门面，还是新子包文件。",
      "recommendationMarkdown": "先统一一次“任务 3 之后只能使用迁移后路径”的全文勘误：route 统一改写为 `web/routes/domains/**`，scheduler 内部文件统一改写为 `core/services/scheduler/<子包>/**`；仅对显式保留的根层薄门面继续使用旧路径，并把这些例外写入一张兼容入口清单。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 470,
          "lineEnd": 560
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 649,
          "lineEnd": 699
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 734,
          "lineEnd": 752
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 944,
          "lineEnd": 985
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1057,
          "lineEnd": 1097
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        }
      ],
      "relatedMilestoneIds": [
        "m1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "silent-fallback-governance-gap",
      "severity": "medium",
      "category": "maintainability",
      "title": "静默回退门禁缺口",
      "descriptionMarkdown": "plan 全局规则反复强调禁止新增静默回退，并在任务 8 中强制清理 `static_versioning.py` 的吞异常路径；但对 `web/ui_mode.py` 仅要求“显式收口”，没有把当前多处 `except Exception: pass`、返回空字符串、返回 `None` 的路径纳入硬性删除/门禁范围。同时，当前 `tests/test_architecture_fitness.py` 的静默吞异常门禁只识别 `except Exception: pass / ...`，并不覆盖 `except Exception: return None`、`return \"\"`、`continue` 这类同样会隐藏故障的分支。结果是：即使按 plan 完成任务 1 和任务 8，仓库仍缺少一条能持续约束“静默回退”语义的统一门禁。",
      "recommendationMarkdown": "在任务 1 或任务 8 中增加一条明确规则：`web/ui_mode.py` 的 `except Exception: pass` 与“异常后直接返回空值”的分支要么改成可观测降级，要么列入带退出条件的白名单；同时扩展门禁覆盖范围，不再只扫描 `pass / ...` 两种静默模式。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 122,
          "lineEnd": 127
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1117,
          "lineEnd": 1139
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 167,
          "lineEnd": 205,
          "symbol": "init_ui_mode"
        },
        {
          "path": "web/ui_mode.py",
          "lineStart": 305,
          "lineEnd": 418,
          "symbol": "safe_url_for"
        },
        {
          "path": "tests/test_architecture_fitness.py",
          "lineStart": 453,
          "lineEnd": 481,
          "symbol": "test_no_silent_exception_swallow"
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "web/ui_mode.py"
        },
        {
          "path": "web/bootstrap/static_versioning.py"
        },
        {
          "path": "tests/test_architecture_fitness.py"
        }
      ],
      "relatedMilestoneIds": [
        "m1"
      ],
      "trackingStatus": "open"
    },
    {
      "id": "nested-test-gate-ordering",
      "severity": "medium",
      "category": "test",
      "title": "嵌套测试门禁时序断裂",
      "descriptionMarkdown": "任务 1 要求所有批次共用统一质量门禁；任务 8 又明确要求把新增专项回归直接落到 `tests/regression/**`；但任务 9 才计划修改 `pyproject.toml` 补充分层目录的采集与规则。当前仓库的 `ruff` 例外仅写成 `tests/*`，不会匹配 `tests/regression/**` 这类嵌套路径。这意味着执行到任务 8 时，新增的嵌套测试文件会立即进入统一门禁，却没有获得计划预期中的测试目录宽松规则，导致批次间的校验语义不稳定。",
      "recommendationMarkdown": "把最小化的嵌套测试目录门禁配置前移到任务 1 或任务 8 起点，例如先把 `ruff` 放宽规则改成递归匹配，并为 `pytest` 提前建立子目录可收集的保守配置；这样任务 8 新增 `tests/regression/**` 文件时就不会破坏“每批次都能跑统一门禁”的要求。",
      "evidence": [
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 250,
          "lineEnd": 253
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1110,
          "lineEnd": 1153
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md",
          "lineStart": 1218,
          "lineEnd": 1221
        },
        {
          "path": "pyproject.toml",
          "lineStart": 37,
          "lineEnd": 43
        },
        {
          "path": ".limcode/plans/20260405_技术债务最终合并修复plan.md"
        },
        {
          "path": "pyproject.toml"
        }
      ],
      "relatedMilestoneIds": [
        "m2"
      ],
      "trackingStatus": "open"
    }
  ],
  "render": {
    "rendererVersion": 4,
    "bodyHash": "sha256:ceb66ad8f78f96b9de3374bfcde28da7720b1c9d22084e8b968c8c9f6eae1dcd",
    "generatedAt": "2026-04-05T18:28:29.477Z",
    "locale": "zh-CN"
  }
}
```
