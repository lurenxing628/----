# 机器证据文件说明

本目录里的 `_*.json` 不是临时缓存,而是本次水下债修复计划的机器可读证据。

## 为什么要提交

- `phase0/PHASE0-TRUTH.md` 已明确说明: `_truth.json`、`_all_debts_full.json`、`_bucket_packs.json` 是 Phase 0 的机器可读副本。
- `phase1/PHASE1-MATRIX.md` 已明确说明: `_phase1_blast.json` 是 80 条债的逐债爆炸半径明细,后续 Phase 2 agent 必须读取。
- `MASTER-PLAN.md` 已明确说明: 逐债爆炸半径看 `phase1/_phase1_blast.json`,逐债修法看 `phase2/units/*.json`。
- `phase3/_audit_raw.json` 是 Phase 3 对抗核查裁定的结构化副本,字段为 `verdict`、`checks`、`must_fix`;上层说明对应 `MASTER-PLAN.md` 第 1 节"对抗核查裁定"和 `must_fix（已在本文件消解）` 段。
- `phase3/_master_raw.json` 是 Phase 3 总计划编排的结构化副本,字段为 `summary`、`execution_order`、`cross_bucket_conflicts`、`precondition_gates`、`owner_decisions`;上层说明对应 `MASTER-PLAN.md` 的总纲、批次计划、跨桶冲突裁断和 owner 决策表。
- 这两个 Phase 3 JSON 目前没有独立生成脚本,所以本次把它们明确记为"上层说明文档的机器可读副本";后续如果改 JSON,必须同步更新 `MASTER-PLAN.md` 对应段落,或补一份可复现生成脚本。

## 后续维护规则

- 修改这些 JSON 时,必须同时能指出生成脚本、上层说明文档或对应阶段文档。
- 不能把这些 JSON 当作可随手删除的构建产物。
- 如果某个 JSON 只是一次性临时文件,应改放到被忽略的临时目录,不要放进本 `fix-plan/` 证据树。
