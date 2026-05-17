---
doc_type: issue-fix
issue: 2026-05-18-scheduler-graph-report-hardening
path: fast-track
fix_date: 2026-05-18
severity: P1
tags: [scheduler, graph, report-mode, diagnostics, performance, codestable]
---

# 阶段 10 图报告加固修复记录

## 1. 问题描述

阶段 10 已经把 `graph_analysis_mode=report` 接到排产结果摘要里，但复审后发现文档和代码证据还不能直接支撑后续 PR-5：

- public 小摘要里的 basic metrics 需要更明确，不能只证明有图报告字段。
- 冻结窗口和 seed scope 必须证明只读、不重复排，不能让后续 on 模式误把 frozen / seed 工序放回候选。
- `warning.data` 需要做深层 JSON 采样，不能只看第一层字段。
- 已知图错误必须在顶层 public warning 里能看见，不能只藏在 diagnostics 里。
- exporter、config 和 fail-fast 这些 P3 边界也要记录清楚，避免后续 PR 把“能跑”误解成“全链路证据齐了”。

## 2. 根因

根因不是阶段 10 要改变排产算法，而是“报告能力”的证据还不够细：

- report 模式是旁路能力，容易只测到字段存在，却没测到字段内容是否足够稳定。
- diagnostics 是给开发排障看的，里面如果出现过深对象、不可 JSON 序列化对象或超大明细，会拖累历史摘要和日志阅读。
- frozen / seed scope 是后续 ready 队列最容易踩错的边界。阶段 10 虽然不改候选集合，但必须把这个边界提前写清楚。
- PR-4 原本写成“调试导出和性能证据”，范围太像单纯文件导出；实际下一步更应该先补性能护栏、diagnostics 加固和真实集成证明。

## 3. 本轮已修问题

### P1：会阻塞后续 PR-5 的问题

- basic metrics 已补强：public 摘要要稳定记录节点数、边数、DAG 状态、关键路径、warning 数、cycle 数和耗时，后续不能只判断 `graph_analysis` 字段存在。
- frozen / seed scope 已补强：图报告读取完整 `algo_ops` 建图，并把 `frozen_op_ids` 命中的工序标成固定节点；`algo_ops_to_schedule` 只用于“本次可重排工序数”的口径说明，`seed_results` 只记录固定前置数量，不参与重新排产。
- known graph error 顶层 warning 已补强：已知图输入或图构建错误要在 public 小摘要里给出 `status`、`reason`、`message`，不能只在 diagnostics 深处留下开发者才看得懂的对象。

### P2：影响诊断可信度的问题

- `warning.data` 深层 JSON 安全投影已补强：采样诊断里的 warning 数据会递归处理列表和字典；列表只保留样本、总数和截断标记；遇到不能 JSON 保存的对象时只保留类型标记，不把对象本身塞进历史摘要。
- diagnostics 截断口径已补强：topological order、critical path、cycle edges、warnings 和 node metrics 都只能放采样、总数和截断标记，不能写完整图对象。
- OperationLogs 边界已补强：日志只能跟随 `algo.graph_analysis` public 小摘要，不写 diagnostics、nodes、edges、raw、完整 node_metrics 或完整 topological_order。

### P3：边界清理和后续维护问题

- exporter 口径已补强：exporter 只负责把图分析结果转成普通 dict，不猜默认值、不吞未知对象、不做万能清洗器。
- config 口径已补强：`off/report/on` 的默认关闭和保存链路继续作为 PR-3/PR-4 的前置事实，PR-4 不能绕过配置合同另开入口。
- fail-fast 口径已补强：未知异常不允许被吞成空报告；合同错误必须明确暴露为可识别状态，方便测试和用户排障。

## 4. 文档回填

- `.codestable/features/2026-05-17-scheduler-graph-report-mode/scheduler-graph-report-mode-acceptance.md`：补充本轮 P1/P2/P3 加固结果和 PR-4/PR-5 阻塞口径。
- `.codestable/features/2026-05-17-scheduler-graph-report-mode/scheduler-graph-report-mode-checklist.yaml`：补充加固步骤和验收项。
- `.codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-items.yaml`：把 PR-4 调整为“性能护栏 + diagnostics 加固 + 真实集成证明”，并写明 PR-5 仍被这些证据阻塞。
- `.codestable/roadmap/networkx-scheduler-graph-introduction/networkx-scheduler-graph-introduction-roadmap.md`：补充阶段 10 加固后的 PR-4/PR-5 承接说明。

## 5. 验证口径

- 本轮修复同时修改 `core/`、`tests/`、`web/`、`templates/` 和 `.codestable/`；本记录用于说明这些改动的收口口径。
- 运行代码和测试结果以当前未提交 diff 为准；在本地提交前，不能把这些验证冒充 clean-worktree proof。
- PR-5 进入 on 模式 ready 队列之前，必须先看到 PR-4 的性能护栏、diagnostics 加固和真实集成证明全部通过。

## 6. 遗留事项

- PR-4 仍需补齐 2000 节点性能护栏和受控 debug/export 证据；真实排产链路集成、diagnostics 采样合同、warning 顶层可见性已经由本轮回归测试先补上第一层证明。
- PR-5 仍处于阻塞状态；不能因为阶段 10 report 模式已加固，就直接开始改 SGS ready 队列。
