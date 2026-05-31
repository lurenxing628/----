---
doc_type: issue-fix
slug: aps-workbench-roadmap-review-alignment
status: done
path: fast-track
created: 2026-06-01
last_reviewed: 2026-06-01
tags:
  - aps
  - frontend
  - roadmap
  - documentation
---

# APS 工作台路线图审查对齐修复记录

## 1. 问题

只读审查基于 GitHub commit `23fb7ca4ec37b4630c4f6d800ec7880db1cdf83a`，指出路线图、开工总方案、items 和页面设计稿之间还有几处口径不一致。

本地未提交版本里，`WorkbenchLink.target_page` 的完整目标页字典已经和开工总方案/items 对齐；但页面设计稿和审计 finding 里仍残留几类容易误导开工的说法：

- 甘特资源负荷摘要有些地方还像第一版验收内容。
- 资源派工仍有“现场人员填实际”的多人现场口径。
- 首页和报表仍有“现场反馈缺口”这类容易导向必填的说法。
- 审计推进顺序少了 `workbench-nav-entry`。
- 部分 finding 还在让用户重新拍板已经明确后移的暂停、异常、审批、扫码、MES 闭环。

## 2. 修复

- 把 roadmap 里的甘特资源负荷摘要明确标成第二阶段增强，第一版甘特只要求任务详情区、超期说明入口和资源负荷报表跳转入口。
- 把页面设计稿里的“现场反馈缺口”统一改成“现场情况待确认”，把“现场人员填实际”改成“计划员代录现场事实”。
- 把设计稿里的 Excel 口径改成短期不新建预览/确认；如果历史页面残留预览/确认入口，非正式方案下也不得开放。
- 把审计 index 的推进顺序改成 A/B/C：`workbench-context-link-contract`、`workbench-nav-entry`、`dashboard-workbench-risk-todos`。
- 给 finding 05/07/08 补阶段归属：甘特详情区和报表回跳属于第一版；甘特资源负荷摘要、停机任务级明细、牵连批次/订单影响面、延期解释接现场事实属于第二阶段。
- 把 finding 06 从“必须拍板”改成“按已拍板口径进入 resource-dispatch feature design”。
- 把 finding 10 更新为“关键边界已补，不再挡第一轮开工；后续 feature design 继续补硬验收”。
- 按第二份只读审查继续补齐 roadmap 的 `WorkbenchLink.required_params`，并在开工总方案的 `WorkbenchPlanContext` 字段表补 `is_preview`、`guardrail_reason_type`、`capacity_source_label`、`capacity_gap_text`。
- 在 items.yaml 文件头补阶段口径注释，说明前 3 条是第一轮 A/B/C、第 4-9 条是第一版、第 10-11 条是第二阶段；同时把门禁入口说明改成优先登记 `tools/test_registry.py`。
- 把页面设计稿和相关 finding 里的入口文案统一成“资源派工”，并把“现场反馈”类残留改成“现场事实 / 现场情况”。
- 启动只读 SubAgent `019e7efc-14f1-7351-b1d6-b80febfe6d46` 做执行性复核；SubAgent 结论是“可以直接开工，无阻塞”。随后按它的非阻塞建议清掉审计 index 的“反馈缺口统计”残留，并把页面设计稿里“甘特看资源负荷”的宽泛说法改成“第一版只跳资源负荷报表 / 资源派工，Top 摘要第二阶段做”。

## 3. 验证

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-roadmap.md`：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-frontend-workbench/2026-05-31-aps-frontend-workbench-start-plan.md`：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-frontend-workbench/aps-frontend-workbench-items.yaml`：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/roadmap/aps-frontend-workbench/drafts/2026-05-31-aps-frontend-page-design-spec.md`：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/audits/2026-05-31-aps-frontend-workbench-design-gap/index.md`：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/audits/2026-05-31-aps-frontend-workbench-design-gap/finding-01.md`：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/audits/2026-05-31-aps-frontend-workbench-design-gap/finding-03.md`：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/audits/2026-05-31-aps-frontend-workbench-design-gap/finding-05.md`：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/audits/2026-05-31-aps-frontend-workbench-design-gap/finding-06.md`：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/audits/2026-05-31-aps-frontend-workbench-design-gap/finding-07.md`：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/audits/2026-05-31-aps-frontend-workbench-design-gap/finding-08.md`：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/audits/2026-05-31-aps-frontend-workbench-design-gap/finding-10.md`：passed。
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python .codestable/tools/validate-yaml.py --file .codestable/audits/2026-05-31-aps-frontend-workbench-design-gap/finding-04.md`：passed。
- `rg -n "填现场实际|现场反馈|资源排班" .codestable/roadmap/aps-frontend-workbench .codestable/audits/2026-05-31-aps-frontend-workbench-design-gap`：无结果。
- 只读 SubAgent `019e7efc-14f1-7351-b1d6-b80febfe6d46` 执行性复核：结论为“可以直接开工”，阻塞问题为“无”。

## 4. 遗留

本轮只改文档，不改前端实现代码。

当前工作区在本轮开始前已有未提交路线图文档修改，所以本记录不声明 clean-worktree proof。GitHub 只读 Agent 如果继续审查 GitHub commit `23fb7ca...`，仍看不到本地这些最新修改，除非后续提交并推送。
