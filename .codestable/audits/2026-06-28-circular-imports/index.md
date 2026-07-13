---
doc_type: audit
slug: circular-imports
scope: 历史普查 + 2026-07-13 当前生产非测试/含测试双 scope 终态复核
summary: A1/A2/A3 已解除，当前 3/4 个 hard 目录 SCC；纯显式 hard 文件 SCC 为 0，父包初始化感知 hard 文件 SCC 仍为 9 且 algorithms A3 圈已严格缩小
status: open
created: 2026-06-28
last_reviewed: 2026-07-13
verified_by: 2026-06-28 Codex 历史审核 + 2026-07-10 首次工具复扫 + 2026-07-11 确定性重建 + 2026-07-12 A1/A2 差异核对 + 2026-07-13 A3 双 scope/调用图全映射
tags: [architecture, circular-dependency, import-cycle, audit]
---

# 循环依赖普查（历史报告 + 2026-07-13 当前口径校正）

## 2026-07-13 当前事实（覆盖下方冲突的历史数字）

> 下方 2026-07-12、2026-07-11 与 2026-06-28 内容保留当时证据，不再代表当前结构。当前事实以本节、双 v2 基线和 A1/A2/A3 refactor 为准。

- **scope**：生产扫描 779 模块，含测试 1475 模块，解析失败均为 0。
- **目录商图**：生产为 3 个 hard 目录 SCC，含测试为 4 个。A1、A2 与 A3 `algorithms/greedy/dispatch` 均已解除；A4/A5/A6 和 tests 既有 SCC 的成员、圈内规范化模块边逐项未变。
- **文件图双口径**：父包初始化感知 hard 文件 SCC 数仍为 9，纯显式 hard 文件 SCC 仍为 0；migration 圈保持 5 成员 / 11 边，A3 相关 algorithms 父包加载圈从 21 成员 / 94 边严格缩为 8 成员 / 24 边。父包感知/纯显式 runtime 文件 SCC 仍为 13/4。
- **动态加载盲区**：import-cycle production / with-tests unresolved 仍为 6 / 44，逐记录与 A3 起点相同。
- **基线**：A3 双基线只删除 3 成员 / 42 边目录块，并用 8/24 严格子集替换旧 algorithms 文件 SCC；其余目录/文件圈与 unresolved 不变。刷新后双正式命令通过，A1/A2/A3 回潮都会被阻断。
- **调用图**：7337 callable、25798 输出边、10171 确信边、15627 模糊边、typed 0、8 条受限简单循环、island 193、dynamic unresolved 685。A/B 十份 JSON 逐文件 SHA 相同；7329 个旧 callable 全映射，新增仅 8 个 dispatch context adapter callable；6 条旧边差异和 14 个 adapter 新端点均已解释，无旧 callable/调用端点无故丢失。
- **证明边界**：A1/A2 的既有 clean proof 继续只绑定 `c2243cd0` / `d6d41e1a`。A3 实现提交 `f422b88c` 已在前后工作区均干净的固定 HEAD 上完成无缓存、无续跑 19/19 门禁（4731 collected、unexpected failure 0、manifest=`passed`），`clean_worktree_proof=true`；该证明只绑定此实现提交，历史决定考古仍为 pending。

## 2026-07-11 前一终态事实（历史）

> 本节是 A1 启动前的可信起点；其中 6/7 个 SCC 与 A1 仍存在的描述已被上节更新。

- **scope**：生产非测试扫描为 `core/web/data/desktop/plugins/tools/scripts/*.py`，包含顶层 `app.py`、`app_new_ui.py`、`config.py` 等入口；含测试命令再加 `tests`。生产 750 模块，含测试 1443 模块，解析失败均为 0。
- **目录商图**：生产仍是 6 个 hard 目录 SCC，含测试为 7 个。A1/A2/A3/A5/A6 成员不变；A4 因补入真实入口与 config/bootstrap，现为 `. ⇄ web/bootstrap ⇄ web/routes ⇄ web/routes/domains/scheduler`。目录 SCC 是结构耦合，不等同具体文件已互相咬死。
- **文件图双口径**：纯显式 import 的 hard 文件 SCC 仍为 0；补入 Python 会先执行父包 `__init__.py` 的真实加载链后，父包感知 hard 文件加载 SCC 为 9。后者表示部分初始化风险面，不等于 9 组都已复现 ImportError；两种口径必须同时写明。
- **运行时图双口径**：父包感知 runtime 文件 SCC 为 14；纯显式 `hard+cond+lazy` 文件 SCC 为 5，且现已输出成员和圈内边，不再只有计数。
- **动态加载盲区**：生产已有 6 个无法静态定目标的站点（scheduler/config/repository 重导出、路由 f-string、orchestrator 常量和插件文件加载器）；含测试共 44 个，其中额外 38 个全部位于测试脚本，均为显式动态测试装载或变量目标。它们完整进入 JSON/文本清单；v2 基线允许既有项删除，但阻断新增未解析动态导入。
- **基线/门禁**：`.codestable/checkup/import_cycles_production_baseline.json` 与 `import_cycles_with_tests_baseline.json` 同时锁定 schema、scope、scan roots、文件加载语义、SCC 成员、圈内规范化模块边和未解析动态导入。缺失/损坏/版本或 scope 不符/源码解析失败/扫描异常均返回工具错误码 2；两条命令已进入正式 19 步质量门禁、计划哈希、逐步收据、重放和 long-gate 稳定 entry。2026-07-11 候选双基线与正式文件逐字节一致，证明 alias 重绑定修复没有改变现有生产/测试 SCC、圈内边或 unresolved 身份。
- **调用图区分**：当前快照为 7329 个 callable（含 316 个嵌套 def/lambda）、25772 条输出边、10152 条确信边、15620 条模糊边、0 条 typed 边和 8 条真实受限简单循环记录。`cycle_count` 是“确信边上长度 2-8、最多 200 条的 simple cycles”，**不是函数 SCC 数**；两个独立临时输出目录的 10 个 JSON 逐文件 SHA256 完全一致。

当时生产边计数 `hard=8809 / cond=4 / lazy=257 / typeonly=135` 包含 6654 条父包初始化隐式文件边。相对首次 749 模块口径新增的 `tools/import_cycle_graph.py` 使 scanner 的 `from tools import import_cycle_graph` 解析为 `tools` 与 `tools.import_cycle_graph` 两个目标，因此模块数 +1、hard 边 +2、父包初始化边 +1；这不是新增 SCC。当时 A1-A6 均未拆除；当前 A1 状态以上一节为准。

## 2026-06-28 历史正文（仅作当时证据）

> 性质:**发现清单**,不代表已修复。治理(改代码)按节奏待办。
> 口径已经过 Codex 独立对抗审核 + 扫描脚本修正,可信度:**中偏高**(6 个硬加载期目录环可信;根因/严重度按保守口径写)。

## 0. 一句话结论

全仓存在 **6 个"硬加载期"包级循环依赖(目录级)**,但 **0 个硬加载期文件级循环**——即"包与包之间互相 import"成环属实,但**没有"某两个具体文件互相咬死"**。这 6 个环目前都能正常加载(靠 import 顺序/叶子位置维持),属**结构债**;本次**未发现必须阻塞执行的证据**(不等于保证都无害)。

## 1. 方法与口径

- 自写 AST 脚本(`/tmp/find_cycles.py`,v2)扫 **723 个生产模块**(core/web/data/desktop/tools/scripts,**排除 tests**),解析失败 0;Tarjan 求强连通分量(SCC>1=环)。
- **import 三分类**（与 checkup 函数调用图口径不同：后者是 capped simple-cycle 记录，不是 import SCC，也看不到包级环）：
  - **hard**:无条件顶层 import(会在模块加载期执行)→ 真正可能 `ImportError` 的环
  - **cond**:顶层 `try` / 非 `TYPE_CHECKING` 的 `if` 块内(条件加载)
  - **lazy**:函数体内(延迟加载)
  - **typeonly**:`TYPE_CHECKING` 块体(运行时不执行,不计入耦合)
- 边计数:hard 2474 / cond 12 / lazy 45 / typeonly 43。
- 粒度:目录(包)级 + 文件(模块)级;目录级过滤同目录边。

## 2. 三类结果总览

| 类别 | 数量 | 含义 |
|---|---|---|
| **① 硬加载期目录环** | **6** | 包与包之间无条件顶层 import 成环 —— **治理重点** |
| **② 硬加载期文件环** | **0** | 无"具体文件互相咬死"的加载期环 |
| **③ 延迟/条件耦合环** | 2 目录环 + 5 文件环 | 由函数内/条件 import 形成,**by-design 缓解**,非硬债 |

## 3. 第一类:6 个硬加载期目录环(治理重点)

> 编号沿用 Codex 核验报告的 A1–A6。根因经 Codex 修正,**不再是 v1 的"四个同一病根"**,而分三类:**误放位置 / 复合耦合 / 底层互借**。

| 环 | 涉及包 | 关键证据(file:line) | 根因(Codex 修正后) | 严重度 |
|---|---|---|---|---|
| **A1** | scheduler 根 ⇄ run ⇄ summary ⇄ config | `schedule_service.py:29`→summary;`run/schedule_persistence.py:6`→根 execution_fact_provider(+9);`config/config_field_coercion.py:10`→根 number_utils;`run/schedule_orchestrator.py:7`→summary | **复合耦合**:run⇄summary 反借 + 根目录垫片 + `config_snapshot` 隐性公共依赖 + 公共工具误放,非单一病根 | 🔴 最重(有据) |
| **A2** | infrastructure ⇄ migrations ⇄ models ⇄ shared | `models/schedule_resource_filter.py:6`→infrastructure.errors;`infrastructure/operation_execution_event_data_contract.py:6`→models._helpers | **底层架构耦合**:基础层互借对象(errors/_helpers 互为叶子) | 🔴 基础层影响最广 |
| **A3** | algorithms ⇄ greedy ⇄ greedy/dispatch | `greedy/run_state.py:7`→algorithms.ordering(+16);`greedy/dispatch/sgs_scoring.py:6`→algorithms.dispatch_rules(+7);`ortools_bottleneck.py:19`→greedy.date_parsers | **误放位置**:父包公共工具被子包大量反依赖,父包又依赖子包 | 🟡 中(无量化依据,不强排) |
| **A4** | web/routes ⇄ web/routes/domains/scheduler | `domains/scheduler/scheduler_excel_calendar.py:16`→routes.excel_utils(+23);`routes/reports_export_support.py:11`→domains.scheduler.scheduler_plan_context_token | **误放位置**:路由公共辅助/排产域 token 互借,边界没分干净 | 🟡 中(同上) |
| **A5** | core/plugins ⇄ core/services/common | `common/excel_backend_factory.py:6`→plugins;`plugins/manager.py:11`→common.enum_normalizers | **架构耦合**:插件框架与公共服务互供能力 | 🟢 偏轻(局部) |
| **A6** | core/services/report ⇄ report/exporters | `report/execution_review.py:15`→exporters;`exporters/xlsx.py:14`→report.report_number_parsing | **误放位置**:exporters 回取父包数字解析工具 | 🟢 偏轻(局部) |

**严重度说明(保守口径)**:A1 最重、A2 基础层影响最广有依据;A5/A6 局部较轻;**A3/A4 中间档缺统一量化依据,不强行排序**。**不下"全部非现故障"的结论**,只能说本次未发现必须阻塞执行的证据。

## 4. 第二类:硬加载期文件环 = 0

修正脚本口径(不再把 `from . import 兄弟模块` 误算成"依赖包根")后,**文件级硬加载期环为 0**。即不存在"某两个具体文件在加载期互相 import 咬死"。v1 曾报告的 report(4)/personnel(3)/config(9)"文件环"**全部是该口径 bug 造成的伪报**,已消除。

## 5. 第三类:延迟/条件耦合环(by-design 缓解)

仅在算上"运行时可能执行"的 cond+lazy 边时才出现,**加载期不成环**:

- **web ⇄ bootstrap ⇄ routes ⇄ domains/scheduler**:`web/routes/system_health.py` 等以**函数内延迟 import** 取 `web.bootstrap.factory`(路由→应用工厂的反向依赖,被延迟 import 隔离)。
- **scripts ⇄ tools**:`tools/git_hook_checks.py:212`→scripts 为函数内延迟边,非生产运行时。
- 另有 5 个运行时文件环(如 `execution_snapshot ⇄ execution_fact_provider` 用 `TYPE_CHECKING`、`schedule_graph` 两 context / `config_field` 对用函数内延迟),均为**主动用延迟/类型导入拆掉加载期环**的 by-design 实践,不计入硬债。

## 6. 修正声明(本报告相对最初口径的更正)

经 Codex 对抗核验,以下最初结论已更正:
1. ❌ 收回"6 个环里 4 个同一病根=公共工具放父目录"的**过度概括** → 改为三类根因(见 §3)。
2. ❌ 收回"全部非现故障"的**武断结论** → 改为"未发现必须阻塞执行的证据"。
3. ⚠️ A1 不是干净的"四段单环",是同一强连通块内多组跨目录顶层边互相闭合。
4. ⚠️ config 文件环剔除原因更正:不是"包根 re-export",而是 `TYPE_CHECKING`+`__getattr__` 懒加载+函数内延迟(`config/__init__.py:6-24`)。
5. ⚠️ report/personnel/config "文件环"系脚本 `from . import` 假边伪报,已由 v2 修正消除(§4)。

## 7. Codex 对抗核验背书

- Codex(session `019f0e4c-cb3c-79b1-98db-39d415563483`)**fan-out 5 子代理**独立复核:真环核实 / 伪报剔除 / 脚本 bug / 漏报盲区 / 根因与严重度。
- **独立重扫**(不依赖本脚本):717+ 生产文件、加 tests 共 1367 文件,**文件级硬环均为 0**,与本报告一致。
- **漏报盲区**:tests 排除 / 目录粒度 / try-except / if 块 / 星号 / 动态 import 六项逐个排除,**未发现清单外的生产真环**。
- 可信度评级:**中偏高**。

## 8. 治理建议(待办,按节奏)

- **优先级**:A1 scheduler + A2 infrastructure/models 优先;A5/A6 局部,不应与核心同级处理。
- A1 与 [[service-scheduler]] §8 的 run⇄summary、共享工具下沉是**同一件事**,建议合并治理(走 cs-refactor)。
- 通用解法:把被子包/同级反依赖的公共工具下沉成**无反向依赖的叶子包**;基础层(A2)互借的 errors/_helpers 可评估微调或接受。
- 改代码动作等当前并行任务(optimizer 改动)完成后再启动。

## 9. 附：当前扫描与正式门禁入口

- 分析/图记录/比较：`tools/import_cycle_analysis.py`、`tools/import_cycle_graph.py`、`tools/scan_import_cycles.py`、`tools/import_cycle_baseline.py`。
- 生产基线：`.codestable/checkup/import_cycles_production_baseline.json`。
- 含测试基线：`.codestable/checkup/import_cycles_with_tests_baseline.json`。
- 审计输出：`python -m tools.scan_import_cycles --json`；文本模式会列出 parse error、父包初始化边摘要、未解析动态导入和 runtime 文件 SCC 证据。
- 正式门禁：

```text
python -m tools.scan_import_cycles --fail-on-new-cycle --quiet-when-clean
python -m tools.scan_import_cycles --include-tests --fail-on-new-cycle --quiet-when-clean
```

- 2026-07-11 回归覆盖：语句体上下文、相对字面量动态 import、`__name__` 包重导出、父包初始化真实复现、顶层 glob/plugins、动态加载器词法遮蔽/重绑定、缺失/损坏/版本/scope/roots 基线、同成员新增边、删边/消圈、parse error 与扫描异常 fail-closed、正式计划删除命令失败、收据/哈希/重放和 long-gate scope。
