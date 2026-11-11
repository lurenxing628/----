---
name: aps-post-change-check
description: 检查本轮 APS 代码改动的静态质量、分层和文档联动。用于明确的改后快检或收尾验证；普通查询、只读研究和未指定范围的“检查一下”不自动启动此流程。
---

# APS 改动后检查

## 范围与验证入口

遵循根目录 `AGENTS.md` 的授权与范围规则。先用 `git status --short` 和 diff 区分已有改动与本轮改动；不把全部 dirty 文件视为本轮产物，不重复确认已授权工作。普通审查只报告问题；已有修复授权时，在该范围内连续修复和验证。

按任务选择已有入口，不连续叠跑所有模式。命令使用项目 `.venv` Python；以下 `python` 仅为已激活项目环境后的简写。正式定义见 [开发文档/README.md](../../../开发文档/README.md)：

| 需要的证据 | 入口 |
|---|---|
| 本轮 Python 改动的快速静态预检 | `python scripts/run_quality_gate.py --fast-precheck` |
| 日常开发快门禁 | `python scripts/run_daily_quality_gate.py` |
| 普通完整质量门禁 | `python scripts/run_quality_gate.py` |
| 最终收口 / 托管环境证明 | `python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache` |

快检、daily gate 和普通完整门禁不能代替最终 clean proof。只有最终 HEAD、干净工作区和要求的门禁证据符合项目约定时，才能报告 clean-worktree proof；已有脏改时如实限定验证范围。

## 专项静态扫描

需要分层、复杂度或联动提示时，可运行保留的专项脚本；纯宿主工具的解释器按 `.codestable/attention.md` 选择，不将产品语法约束扩大到工具本身：

```bash
python .limcode/skills/aps-post-change-check/scripts/post_change_check.py
```

脚本检查它识别到的改动文件，包括 Ruff、分层、裸字符串枚举、future annotations、Radon 和文档联动。先核对脚本实际覆盖清单与本轮范围；若包含已有改动，分别归属结论。已有有效输出可复用，不再手工重复跑同一检查。

- `ruff` 不可用时可能显示 SKIP；读取失败或 `radon` 不可用时显示 FAIL。跳过项和失败项必须披露，不能包装成完整通过。
- 静态命中只是线索：裸字符串集合可能是输入校验，动态调用可能被漏掉；回到相关源码核实，区分新增问题与历史问题。
- Route、Schema、公开 Service 签名、枚举、ScheduleConfig、Excel 和可见文案变更按 `.limcode/rules/change-scope-protocol.mdc` 的相关联动项核对。已授权的必要文档同步直接完成，不为小改动自动启动全量文档回填。
- 涉及公开合同或跨层影响时，按实际风险读取 `aps-deep-review`；文件数量本身不触发完整深审。

## 汇报与完成

说明实际范围、命令与结果、跳过项、确认的问题及证据，区分脚本事实与判断。检查通过不等于可提交、完整门禁通过或业务全链路已验证。

默认在对话中给结论；只有用户要求保存报告或当前已授权流程明确要求落档时，写到 `.codestable/audits/` 或当前流程指定的证据位置。警告或 FAIL 不自动创建审计文档、不自动扩大修复范围。原始脚本证据保持其既有位置。
