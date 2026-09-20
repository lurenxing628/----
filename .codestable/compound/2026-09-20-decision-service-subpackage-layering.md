---
doc_type: decision
category: architecture
date: 2026-09-20
slug: service-subpackage-layering
status: active
area: core/services
tags: [services, workbench, scheduler, subpackages, layering, imports]
---

## 背景

`core/services/workbench/` 平铺 233 个模块（分包前夕 239 个）、`core/services/scheduler/` 根目录 85 个加 `run/` 124 个。500 行门禁把文件切碎了，却没有给出命名接缝：簇之间有 5 对双向依赖，跨模块导入私有符号近百处，新人只能靠文件名前缀猜归属。基础边界治理路线图 P 模块负责分包，2026-09-20 用户裁决执行。簇层次的完整分析见 `.codestable/roadmap/foundation-boundary-governance/workbench-cluster-layering.md`。

## 决定

1. **按业务簇分子包，簇内去前缀。** `run_candidate_adoption.py` → `run/candidate_adoption.py`；与簇同名的主服务模块叫 `service.py`；前缀不是簇名的模块保留原名（`piece_adoption` 留在 `run/`）。
2. **簇之间只允许单向依赖，方向表写进适应度测试。** 工作台的允许方向见 `tests/gate_meta/test_workbench_cluster_layering.py` 的 `ALLOWED` 表：结果侧 `facts ← plan ← execution ← run ← trial ← report ← dashboard`，主数据侧 `facts ← process ← resource`，`batch`、`calibration` 在其上；`material`、`outsourcing`、`system`、`master` 只依赖 `facts`。方向表要改时先改文档再改测试。
3. **共享的只读事实下沉 `facts/`。** 双向依赖只用两种办法解：共享部分下沉到 `facts/`（只读证据读取器、纯叶子助手、编解码），或把误归类的模块搬回它真正的簇。不用"显式接口注入"来绕依赖，那只会把依赖藏进构造参数。
4. **根只留跨簇协调件。** 工作台根目录只有 `commands.py`（命令事务框架）与 `messages.py`（共享文案），谁都可以依赖它们，它们不依赖任何簇。
5. **不留垫片。** 搬迁用 `tools/move_modules.py` 一次改完所有调用方（导入、字符串模块名、路径字面量、注册表 glob）；子包 `__init__.py` 只有 docstring，禁止 `__getattr__` 懒导出与转发导入；旧路径直接消失。
6. **导入写法固定。** 同包用 `.x`，子包用 `.sub.x`，跨包一律绝对导入；不用 `..` 上溯。
7. **排产服务包同样处理。** `run/optimizer_graph_*` 归 `run/optimizer/graph/`，根目录的 `gantt_*`、`resource_dispatch_*`、`calendar_*` 各成子包，`batch_*` 族迁出为 `core/services/batch/`，七个根垫片（freeze_window、schedule_input_builder、schedule_input_collector、schedule_optimizer、schedule_optimizer_steps、schedule_orchestrator、schedule_persistence）与空的 `analysis/` 删除，`_frozen_import_anchor` 的静态清单同步。

## 理由

- 目录即接缝：谁依赖谁一眼可见，目录级环门禁（`tools/scan_import_cycles.py`）在分包后自动覆盖簇间环。
- 下沉而不是注入：本项目是单机离线软件，依赖关系越显式越好；注入会让"谁读了候选存档"从 import 图里消失。
- 不留垫片：垫片让旧路径继续可用，等于分包没有发生；codemod 一次改完的成本一次付清。

## 考虑过的替代方案

- **只加命名规范不分目录**：前缀已经存在，问题恰恰是前缀挡不住双向依赖。
- **一个 `shared/` 大杂烩**：`facts/` 只收"只读事实 + 对这些事实的薄裁决（`*_policy`、存档校验）+ 纯助手"，写操作一律不进；裁决薄壳放 facts 是因为 run/trial 两簇共用同一套读取策略，上提到任一簇都会回到双向依赖。否则又成平铺。
- **插件化 / DI 容器**：2026-09-20 架构评估已否决，分层本身干净，债在包内平铺与 SQL 泄露。

## 后果

- 新模块必须落在某个簇里；找不到簇说明业务归属没想清楚。
- 跨簇引用只能顺着方向表；反向需求先下沉到 `facts/`，再不行才讨论改方向表。
- 测试、注册表 glob、`ui_copy_glossary.json` 的路径随分包一起改；历史证据 JSON（`.codestable/issues/**`）保留旧路径不改。

## 相关文档

- `.codestable/roadmap/foundation-boundary-governance/workbench-cluster-layering.md`
- `.codestable/roadmap/foundation-boundary-governance/moves/*.json`（可复现的搬迁计划）
- `tools/move_modules.py`、`tests/gate_meta/test_move_modules.py`、`tests/gate_meta/test_workbench_cluster_layering.py`
