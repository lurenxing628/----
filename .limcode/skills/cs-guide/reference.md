# 指南模板

创建或更新指南时按需读取；章节是可裁剪的参考，不为凑场景数或截图占位降低交付质量。

## YAML frontmatter

```yaml
---
doc_type: dev-guide  # dev-guide | user-guide
slug: {英文连字符}
component: {关联模块名或 feature slug}
status: draft  # draft | current | outdated
summary: {一句话描述涵盖什么}
tags: []
last_reviewed: YYYY-MM-DD
---
```

`status` 三态：`draft` 待 review；`current` 当前有效；`outdated` 对应代码已变文档没跟上（保留原文，标记后推送更新）。

---

## 文档格式

### dev-guide 正文结构

```markdown
## 概述
一段话描述功能定位和适用场景。

## 前置依赖
集成此模块所需的环境、依赖或配置（如有）。

## 快速上手
最小可运行示例。代码优先文字辅助。

## 核心概念
（可选）理解接口 / API / 模块行为所需的关键术语和设计决定。

## 接口参考
主要 API / 配置选项 / 事件 / 钩子。表格或逐项列举。

## 常见场景
按任务需要给实际使用场景代码示例，覆盖 happy path 和常见边界。

## 已知限制与注意事项
（可选）边界、性能考虑、已知 bug 绕过方式。

## 相关文档
关联的 user-guide、方案 doc、架构 doc 或外部参考。
```

### user-guide 正文结构

```markdown
## 功能简介
一段话描述功能是什么、解决什么问题。

## 前置条件
（可选）使用前的前提（账号权限、需先完成的操作）。

## 如何使用
步骤化操作。每步一行，关键操作配截图占位（`![描述](./assets/xxx.png)` 或注明"此处需截图"）。

## 常见问题
Q: ...
A: ...

## 相关功能
（可选）关联功能跳转链接或说明。
```

