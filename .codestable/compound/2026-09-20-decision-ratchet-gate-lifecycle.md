---
doc_type: decision
category: convention
date: 2026-09-20
slug: ratchet-gate-lifecycle
status: active
area: quality-gate
tags: [quality-gate, ratchet, baseline, sql-boundary, private-import, data-policy]
---

## 背景

架构边界一旦靠人记忆维护就会回潮：服务层重新写 SQL、仓储层重新抛业务拒绝、跨模块拿 `_私有名`。2026-09 基础边界治理路线图 G 模块立了三条"棘轮"规则（`sql_boundary`、`data_policy`、`private_import`），基线文件在 `.codestable/checkup/{rule}_baseline.json`。本决定固定这类门禁的进退规则，避免以后每条新规则各自发明一套。

## 决定

1. **基线只减不增。** 比较口径按 `(path, kind)`：当前出现基线没有的键 → 失败；基线有而当前没有 → 失败并要求刷新（防止"修好了却没收紧"）；同键计数增加 → 失败，减少 → 通过并提示刷新。
2. **刷新只走扫描器命令。** `python -m tools.scan_<rule> --refresh`（`private_import` 为 `tools.scan_private_imports --refresh`）；测试与门禁不得自动改写基线。刷新被拒（总数增长）时，只有人工核对后加 `--allow-growth`，并在提交说明里写明理由。
3. **新规则的最低配置。** 一份扫描器（`--json` / `--fail-on-new` / `--refresh`）、一份基线、一条注册进门禁的适应度测试（`tests/gate_meta/test_boundary_ratchets.py` 参数化即可）、路线图或决定文档里一段判定口径。少任何一项不算上线。
4. **退役条目随业务提交走。** 消除一处债务的提交同时刷新基线，不单独开"刷基线"提交；基线为空后规则仍保留，此时任何新命中直接失败。
5. **搬文件必须重刷基线。** 分包、改名会让基线里的路径失效，`--fail-on-new` 会把它算作"失效条目"而报错，这是设计行为；搬迁提交里跑一次 `--refresh`，并确认总数不增。
6. **规则边界写死在扫描器里，不靠注释豁免。** 需要例外时收窄规则本身（例如 `data_policy` 只认 `WorkbenchCommandRejected` 家族），不加 `# noqa` 式的逐行豁免。

## 理由

- "只减不增"把治理压力放在提交时刻而不是审计时刻，且不要求一次清零，适合分批还债。
- 刷新走命令而非测试自动写，是为了让每一次基线变化都出现在 diff 里可审。
- 把最低配置写死，避免出现"有扫描器没测试"或"有基线没门禁"的半成品规则。

## 考虑过的替代方案

- **一次性清零再上硬门禁**：332 处 SQL 泄露不可能一次修完，中间态无法保护。
- **用 lint 插件逐行豁免**：豁免会积累成第二套债务清单，而且看不见总量。
- **基线放在测试代码里**：测试改动与债务变化混在一起，diff 不可读。

## 后果

- 三条规则当前状态：`sql_boundary` 0 条、`data_policy` 0 条、`private_import` 141 条目 / 385 处；前两条已进入"任何新命中即失败"阶段。
- 后续新边界（例如 web helper 直接组装仓储、模型层反向注解服务层）优先复用同一套扫描器 + 基线 + 参数化测试的形式。

## 相关文档

- `.codestable/roadmap/foundation-boundary-governance/foundation-boundary-governance-roadmap.md` §G、§4.1、§4.2
- `tools/scan_sql_boundary.py`、`tools/scan_private_imports.py`、`tests/gate_meta/test_boundary_ratchets.py`
