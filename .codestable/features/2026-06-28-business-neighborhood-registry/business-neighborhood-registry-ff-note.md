# business-neighborhood-registry fast-forward note

日期：2026-06-28

## 范围

- roadmap item：`business-neighborhood-registry`
- 本阶段只建立业务邻域注册表、`NeighborhoodMove` 合同、trace 和 public 小摘要。
- 本阶段不做 VNS / SA / threshold / Record-to-Record Travel acceptance，也不做 ALNS destroy / repair / operator 权重。

## 实现

- 新增 `core/services/scheduler/run/optimizer_neighborhood_moves.py`、`optimizer_neighborhood_move_support.py`、`optimizer_neighborhood_registry.py`。
- 默认注册六个业务邻域：`critical_chain`、`tardy_window`、`bottleneck_machine`、`changeover_block`、`resource_alternative`、`time_window`。
- 旧 `swap` / `insert` / `block` 不在正式 registry 和 profile 白名单里；默认 improve profile 已改为六个业务邻域。
- local search 只从 registry 取 move，候选正式结果仍走现有 SGS 解码链。
- `OptimizationSearchReport` 新增：
  - `neighborhood_moves`：diagnostics trace。
  - `neighborhood_summary`：public 计数小摘要。
- no-op move 写 `candidate_rejected=noop_neighbor`；fallback move 写 `fallback_reason`；未知邻域 `ValidationError` fail-loud。

## 边界

- public / OperationLogs / size guard 只展示邻域名称和计数。
- raw move、内部 op/resource id、fingerprint hash、完整候选输入不进 public。
- `improved` 仍服从 item 5 三条件；邻域跑过、候选变多、接受过候选都不会单独制造 improvement。

## 验证

- 新增并登记 `tests/algorithm/test_optimizer_business_neighborhood_registry_contract.py`。
- 覆盖白名单、未知邻域 fail-loud、no-op、fallback、decision/output fingerprint 分层、SGS 解码接入、resource-only move、public 投影边界。
