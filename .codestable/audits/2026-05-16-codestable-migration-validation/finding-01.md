---
doc_type: audit-finding
audit: 2026-05-16-codestable-migration-validation
finding_id: arch-drift-01
nature: arch-drift
severity: P1
confidence: high
suggested_action: cs-issue
status: fixed
---

# Finding 01：项目 CodeStable 骨架没有完整反映新版技能入口

## 速答

旧目录迁移到 `.codestable/` 后，主路径已经迁好，但新版技能里的主动审计和开放脑暴入口没有在项目骨架里完整登记，后续 AI 可能找不到正确落盘位置。

## 关键证据

- `/Users/lurenxing/.agents/skills/cs-audit/SKILL.md` — `cs-audit` 明确把审计报告写到 `.codestable/audits/{YYYY-MM-DD}-{slug}/`。
- `/Users/lurenxing/.agents/skills/cs-brainstorm/SKILL.md` — case 4 明确使用 `.codestable/brainstorms/{slug}/brainstorm.md`。
- `.codestable/reference/shared-conventions.md` — 修复前登记的是单数 brainstorm 目录，和技能实际使用的复数目录不一致。

## 影响

这不影响已有业务代码运行，但会影响以后继续使用 CodeStable：主动审计报告和大需求开放脑暴记录可能落错地方，或者被后续 roadmap 搜索漏掉。

## 修复方向

项目骨架、共享口径和总览文档统一到新版技能实际路径，并补齐目录占位文件。

## 建议动作

`cs-issue`，因为这是迁移后项目入口和技能实际行为不一致的问题；本次已经定点修复并重新验证。
