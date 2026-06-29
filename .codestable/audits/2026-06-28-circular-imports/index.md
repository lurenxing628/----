---
doc_type: audit
slug: circular-imports
scope: 全仓(core/web/data/desktop/tools/scripts,排除 tests)循环依赖普查
summary: 全仓循环依赖普查——6 个硬加载期包级目录环,0 个硬加载期文件环;经 Codex 对抗核验 + 脚本口径修正后的最终结论
status: open
created: 2026-06-28
last_reviewed: 2026-06-28
verified_by: Codex 对抗审核(session 019f0e4c-cb3c-79b1-98db-39d415563483,5 子代理 fan-out)
tags: [architecture, circular-dependency, import-cycle, audit]
---

# 循环依赖普查(经 Codex 对抗核验)

> 性质:**发现清单**,不代表已修复。治理(改代码)按节奏待办。
> 口径已经过 Codex 独立对抗审核 + 扫描脚本修正,可信度:**中偏高**(6 个硬加载期目录环可信;根因/严重度按保守口径写)。

## 0. 一句话结论

全仓存在 **6 个"硬加载期"包级循环依赖(目录级)**,但 **0 个硬加载期文件级循环**——即"包与包之间互相 import"成环属实,但**没有"某两个具体文件互相咬死"**。这 6 个环目前都能正常加载(靠 import 顺序/叶子位置维持),属**结构债**;本次**未发现必须阻塞执行的证据**(不等于保证都无害)。

## 1. 方法与口径

- 自写 AST 脚本(`/tmp/find_cycles.py`,v2)扫 **723 个生产模块**(core/web/data/desktop/tools/scripts,**排除 tests**),解析失败 0;Tarjan 求强连通分量(SCC>1=环)。
- **import 三分类**(这是和 checkup `cycle_count` 的关键区别——它是函数级 SCC,看不到包级环):
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

## 9. 附:扫描脚本与修正清单

- 脚本:**已固化为 `tools/scan_import_cycles.py`**(v2 口径)。入口 `python3 -m tools.scan_import_cycles`;`--json` 机器可读、`--fail-on-hard-cycle` 检出硬加载期环退出码 1(供门禁)、`--include-tests` 纳入 tests。实际挂进 `run_quality_gate.py` / git hook 待按节奏决定。
- v1→v2 修正(对应 Codex 指出的 6 个 bug):
  1. `from . import 兄弟模块` 不再误连"包根"假边(消除 §4 伪报)。
  2. import 三分类 hard/cond/lazy/typeonly。
  3. `TYPE_CHECKING` 的 `else` 归运行时(此前整块跳过会漏 else 边)。
  4. 纳入动态 `importlib.import_module("字面量")`。
  5. 运行时图排除 typeonly(运行时不执行)。
  6. 硬加载期环与延迟/条件环分开报。
- 复跑:`python3 -m tools.scan_import_cycles`(2026-06-28 固化后实测:**724** 模块=723 生产模块+本扫描脚本自身、6 硬目录环、0 硬文件环、2 延迟条件环,与本报告 §2/§3 一致)。
