# issue-report 参考模板

本文件提供 `cs-issue-report` 使用的 `{slug}-report.md` 模板。流程、提问顺序、快速通道判定仍以 `SKILL.md` 为准。

## 问题报告模板

```markdown
---
doc_type: issue-report
issue: {issue 目录名}
status: draft
severity: P2  # P0 | P1 | P2 | P3
summary: {问题现象一句话}
tags: [bug]
---

# {问题简述} Issue Report

## 1. 问题现象

{用户描述的具体异常表现，纯现象描述，不含根因推测}

## 2. 复现步骤

1. {步骤 1}
2. {步骤 2}
3. 观察到：{问题现象}

复现频率：{稳定 / 概率（约 X%） / 暂无法稳定}

## 3. 期望 vs 实际

**期望行为**：{做了 A 应该发生 B}

**实际行为**：{但实际发生了 C}

## 4. 环境信息

- 涉及模块 / 功能：{模块名或功能描述}
- 相关文件 / 函数：{已知 file:line 或"待定"}
- 运行环境：{dev / staging / prod / 不确定}
- 其他上下文：{OS、浏览器、最近改动等，没有写"无"}

## 5. 严重程度

**{P0 / P1 / P2 / P3}** - {一句话理由}

## 备注

{可选：截图描述、日志片段等}
```
