---
doc_type: audit-finding
audit: 2026-07-10-checkup-baseline
finding_id: "maintainability-02"
nature: maintainability
severity: P2
confidence: high
suggested_action: cs-issue
status: open
---

# Finding 02：四张全景 HTML 缺少 clean clone 可重放链路

## 速答

四张全景页面和 `docs/_panorama_data/` 都被 Git 忽略；本机只找到专业版与债务版构建脚本，没有大白话、时间线和边界三张页面的完整确定性生成器。

## 关键证据

- `.gitignore:243-250` — `docs/_panorama_data/`、全景图和演进时间线均明确忽略。
- 本机未入库观察：`docs/_panorama_data/_build_pro.py:1-9` 显示专业版依赖本地日期化 JSON 输入；该路径本身被忽略，不能作为 clean clone 可复验事实。
- `.codestable/checkup/README.md` — 将四张页面状态标成 `local_generated_not_versioned`，不作为 clean clone 证明。

## 影响

换机器或重新克隆仓库后无法按技能描述完整重生四张图；如果继续把“四图已重生”当退出条件，会迫使执行者手工拼页面或把旧页面改日期冒充新结果。

## 修复方向

二选一：把完整生成器、版本化输入与视觉检查纳入仓库；或正式把全景页面降级为本机一次性辅助材料，并从 Checkup 强制退出条件中移除。

## 建议动作

走 `cs-issue`，因为当前技能承诺与实际可重放资产不一致。
