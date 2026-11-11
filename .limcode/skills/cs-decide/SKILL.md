---
name: cs-decide
description: 记录已决定的长期约束、技术选型或架构决定；复用已有理由与证据，保留取代关系，不把讨论中的方案写成已定事实。
---

# 决定归档

启动、授权与续作遵守根目录 `AGENTS.md`；读取或复用 `.codestable/attention.md`。路径、状态、查重与取代关系按需查 `.codestable/reference/shared-conventions.md`。

只在用户要求归档或当前任务明确授权记录时执行。尚在讨论的选择可以保留为明确标注的草稿，但不能作为 active 决定供后续实现遵循。

## 记录内容

类别 `category` 沿用 `tech-stack`、`architecture`、`constraint`、`convention`。记录决定、背景、理由、适用范围及后果；被拒方案有实际内容才写，不编造历史取舍。格式按需读 `reference.md`。

## 操作

1. 从当前对话、既有决定和代码证据提炼已知信息，不重复询问已说明的类别或理由。
2. 按类别与关键词查重；更新目标明确时直接读取目标。结论没变只补背景时更新原文；结论变了则保留旧记录并建立 supersede 链。
3. 事实和授权明确时直接起草、核验并保存；尚有实质决策歧义或用户要求先审稿时才等待决定。无法追溯的历史理由写“未记录”或“未做系统评估”，不猜成事实。
4. 保存 `.codestable/compound/YYYY-MM-DD-decision-{slug}.md`，保留 `doc_type: decision`、`category`、`date`、`slug`、`status`、`area`、`tags`；更新补 `updated`。
5. `status` 沿用 `active`、`superseded`、`deprecated`。旧结论被取代时保留原文、加 `superseded-by` 与正文指向，不删除或悄悄覆盖。

## 收尾

按需要核对 architecture 与 attention 的相关摘要及引用。当前授权包含联动更新时直接完成；否则合并说明必要建议，不自动扩写。详细决定和摘要应链接且一致，不让历史记录压过当前用户要求。
