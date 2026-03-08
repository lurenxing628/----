---
description: APS 改动后一键质量检查：变更范围、ruff、分层快检、复杂度与联动更新提醒
---
当用户提到“检查一下 / 查一下 / review / 改完了 / 验一下 / 对话后检查 / 质量检查”时，使用本 workflow。

- 本地 skill 说明：`.windsurf/skills/aps-post-change-check/SKILL.md`

1. 先确认检查范围。
   - 运行 `git status --short`。
   - 运行 `git diff --name-only`。
   - 列出本次改动文件，并指出是否出现了超出用户目标范围的文件。

2. 运行项目自带检查脚本。
   - 执行：`python .windsurf/skills/aps-post-change-check/scripts/post_change_check.py`
   - 如果用户只想看某一类问题，也优先跑这个脚本，再从输出里筛重点。

3. 解读结果时重点关注以下项目。
   - 新增 Ruff lint 问题。
   - 分层违反。
   - 裸字符串枚举。
   - 缺少 `from __future__ import annotations`。
   - 改动文件里的圈复杂度是否超过 15。
   - 由改动类型触发的联动更新提醒。

4. 如果脚本提示缺工具，不要直接中止。
   - `ruff` 或 `radon` 缺失时，明确告诉用户哪些检查被跳过。
   - 只把“本次新增问题”作为阻断项，不要求顺手清理历史遗留。

5. 按固定结构向用户回报。
   - 变更范围：改动文件数、文件列表、是否有未预期文件。
   - Lint 检查：PASS/FAIL、新增问题数量和位置。
   - 架构合规：PASS/FAIL、违反项。
   - 代码质量：裸字符串枚举、future annotations。
   - 圈复杂度：超标函数、等级、是否建议拆分。
   - 联动更新提醒：是否需要同步文档、模板、速查表、枚举引用等。

6. 若发现以下任一情况，建议升级到更重的 workflow。
   - 大面积跨模块改动：转 `aps-deep-review`。
   - 架构体检或定期健康检查：转 `aps-arch-audit` 或 `aps-drift-detect`。
   - 文档已明显落后于实现：转 `aps-dev-doc-backfill`。
