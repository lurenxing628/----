---
doc_type: feature-ff-note
feature: vendor-cs-skills
date: 2026-07-10
requirement:
tags: [codestable, limcode, skills, checkup]
---

## 做了什么

把本机共享源中的 27 个 CodeStable 技能复制为项目 `.limcode/skills/` 下的实体快照，并让 LimCode 优先读取项目副本。同步把 APS 专属 `cs-checkup` 改成代码基线与决定水位线分离的可重验流程。

## 改了哪些

- `.limcode/skills/cs*/`、`CS-SNAPSHOT.json`、`README.md` — 完整技能副本、来源哈希、本地入口和宿主 Python 3.14 工具边界说明。
- `.codestable/checkup/` — clean source 机器基线、codemap 脚本/快照和旧体检历史样本。
- `.codestable/audits/2026-07-10-checkup-baseline/` — 本次基线重验与两个未关闭缺口。
- `tools/scan_dead_code_islands.py`、对应合同测试 — 基线刷新说明记录实际 quick/precise mode。
- `.codestable/attention.md` — 记录 CodeStable/LimCode 宿主 Python 3.14 与 APS Python 3.8 / Win7 运行时的边界。
- `AGENTS.md` — 只追加项目内 `.limcode/skills` 优先加载顺序，保留文件中其他既有改动。

## 怎么验证的

27 个技能全部通过 Codex `quick_validate.py`；`cs-onboard` 的维护 CLI 使用本机 Python 3.14 实跑 `--help` 通过。Checkup JSON 与 SHA256 自检通过；定稿 codemap 使用宿主 Python 3.14，在 `git archive HEAD` 的 clean source 快照注入哈希绑定扫描器后重跑，13 个 JSON 与正式快照零差异；循环依赖无新增硬环；dead-code quick 刷新后 0 新增；`test_dead_code_usage_graph_contract.py` 共 14 项通过。

## 顺手发现

- 决定考古水位线仍停在 `65870e47`，到代码基线有 332 个提交待考古，不能冒进到 HEAD。
- 四张全景 HTML 与输入被 Git 忽略，且生成器不完整，只能标为本机 `local-only`。
