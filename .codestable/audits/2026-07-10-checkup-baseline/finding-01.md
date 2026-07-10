---
doc_type: audit-finding
audit: 2026-07-10-checkup-baseline
finding_id: "arch-drift-01"
nature: arch-drift
severity: P1
confidence: high
suggested_action: cs-issue
status: open
---

# Finding 01：决定考古水位线落后代码基线 332 个提交

## 速答

旧决定日志只证明考古到 `65870e47`，而当前代码基线是 `606bcda1`；中间 332 个提交没有逐提交完成分量分级和必要 diff 核验，不能直接把 watermark 跳到 HEAD。

## 关键证据

- `.codestable/checkup/baseline.json` — `code_baseline.commit` 与 `history_baseline.decision_watermark_commit` 分别记录两条水位线，待审提交数为 332。
- `.codestable/checkup/legacy/2026-06-01-foundation-maturity/decision-log.md:9` — 旧 frontmatter 的水位线是 `65870e47`。
- `.codestable/checkup/legacy/2026-06-01-foundation-maturity/PROVENANCE.md` — 旧决定日志来自 stash untracked 快照，不是正式主线文件。

## 影响

如果直接推进 watermark，6 月 1 日后的未成文决定会被永久跳过；后续 Checkup 会错误地认为这些提交已经考古，失去“防止和过去的自己打架”的核心价值。

## 修复方向

按提交分量分批考古 `65870e47..606bcda1`，记录每批覆盖区间；全部完成后再生成当前决定档案并推进 watermark。

## 建议动作

走 `cs-issue`，因为这是 Checkup 历史覆盖合同缺失，不是一次普通代码重构。
