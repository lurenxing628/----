---
description: APS 全量自测（不打包）：运行 smoke、web smoke、FullE2E、regression 与复杂 Excel 用例，并汇总报告
---
当用户提到“全量自测 / 冒烟测试 / smoke / E2E / 回归测试 / regression / 复杂 Excel 用例”，或要求“通读项目并跑全量自测”且**不需要打包**时，使用本 workflow。

- 本地 skill 说明：`.windsurf/skills/aps-full-selftest/SKILL.md`

1. 先做轻量扫描，不要一上来把整个仓库逐文件读完。
   - 快速浏览仓库顶层与关键目录：`core/`、`data/`、`web/`、`tests/`、`templates/`、`static/`、`schema.sql`、`requirements.txt`。
   - 如果是 git 仓库，读取 `git status` 与 `git diff`，把改动按模块归类，并先标记高风险点：数据库、排产、Excel 导入、路由、模板。
   - 优先关注“本次改动文件”和“改动影响的入口/服务”。

2. 运行全量自测 runner。
   - 默认：`python .windsurf/skills/aps-full-selftest/scripts/run_full_selftest.py`
   - 可选：`python .windsurf/skills/aps-full-selftest/scripts/run_full_selftest.py --fail-fast --step-timeout 900`
   - 如果环境缺依赖，只提示按仓库约定安装 `requirements.txt`，不要擅自改依赖。

3. 明确覆盖范围与约束。
   - 覆盖范围包含 smoke、web smoke、FullE2E、自动枚举的 `tests/regression_*.py`、复杂 Excel cases。
   - **不要执行打包/出包**：不要运行 PyInstaller、`dist/`、`validate_dist_exe.py` 等。

4. 读取结果证据。
   - 汇总报告：`evidence/FullSelfTest/full_selftest_report.md`
   - 如有失败，再查看 `evidence/FullSelfTest/logs/*.log.txt` 与相关 `evidence/...` 报告。

5. 按固定结构向用户回报。
   - 总结：PASS/FAIL。
   - 耗时：总耗时与关键步骤耗时。
   - 失败项：脚本名、退出码、关键错误摘要、证据路径。
   - 下一步：优先从第一个失败项给出最短修复路径。

6. 如果用户要求留痕或需要评估“哪些值得先修”，再补一份审阅结论。
   - 结论必须基于 `evidence/FullSelfTest/` 中的实际报告与日志。
   - 明确区分必须改、建议改、可暂缓。
