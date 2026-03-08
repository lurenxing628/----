# APS Windsurf Skills 索引

本目录承接 `.cursor/skills` 的技能层：记录每个 skill 的用途、对应 workflow，以及已镜像到本目录的脚本 / 参考资料位置。

## 使用方式

- 想直接让助手执行一套流程：优先进入 `../workflows/`
- 想确认这套流程背后有没有脚本、参考文档、样例：先看本文件
- 想看 skill 原文：优先阅读对应目录下的 `SKILL.md`

## 资源保留原则

- `SKILL.md`、`scripts/`、`reference.md`、`examples.md` 已镜像到 `.windsurf/skills/`
- `.cursor/skills/` 仍保留为上游来源，后续同步时以本地镜像更新为主
- workflow 中的脚本与说明，应优先引用本目录中的本地副本

## Cursor skill -> Windsurf workflow 映射

### `aps-arch-audit`

- **对应 workflow**：`../workflows/aps-arch-audit.md`
- **本地 skill**：`aps-arch-audit/SKILL.md`
- **附带资源**：`aps-arch-audit/scripts/arch_audit.py`
- **定位**：架构合规审计：分层、越层导入、循环依赖、复杂度、死代码与架构适应度函数

### `aps-deep-review`

- **对应 workflow**：`../workflows/aps-deep-review.md`
- **本地 skill**：`aps-deep-review/SKILL.md`
- **附带资源**：`aps-deep-review/scripts/project_size.py`、`aps-deep-review/scripts/reference_tracer.py`
- **定位**：深度代码审查：引用链追踪、影响面评估、数据流分析、边界条件与回归风险检查

### `aps-dev-doc-backfill`

- **对应 workflow**：`../workflows/aps-dev-doc-backfill.md`
- **本地 skill**：`aps-dev-doc-backfill/SKILL.md`
- **附带资源**：`aps-dev-doc-backfill/reference.md`、`aps-dev-doc-backfill/examples.md`
- **定位**：基于 `git diff` 与当前实现，对开发文档逐文件逐章节核对并回写事实

### `aps-drift-detect`

- **对应 workflow**：`../workflows/aps-drift-detect.md`
- **本地 skill**：`aps-drift-detect/SKILL.md`
- **附带资源**：`aps-drift-detect/scripts/drift_detect.py`
- **定位**：漂移检测与一致性体检：综合检测脚本、架构适应度函数、引用链追踪与健康报告

### `aps-fjsp-benchmark`

- **对应 workflow**：`../workflows/aps-fjsp-benchmark.md`
- **本地 skill**：`aps-fjsp-benchmark/SKILL.md`
- **附带资源**：`aps-fjsp-benchmark/scripts/run_fjsp_benchmark.py`
- **定位**：运行 Brandimarte FJSP 基准并汇总 makespan、utilization 与 gap，生成 `evidence/Benchmark/fjsp_benchmark_report.md`

### `aps-full-selftest`

- **对应 workflow**：`../workflows/aps-full-selftest.md`
- **本地 skill**：`aps-full-selftest/SKILL.md`
- **附带资源**：`aps-full-selftest/reference.md`、`aps-full-selftest/scripts/run_full_selftest.py`
- **定位**：全量自测（不打包）：运行 smoke、web smoke、FullE2E、regression 与复杂 Excel 用例，并汇总报告

### `aps-package-win7`

- **对应 workflow**：`../workflows/aps-package-win7.md`
- **本地 skill**：`aps-package-win7/SKILL.md`
- **附带资源**：`aps-package-win7/reference.md`、`aps-package-win7/scripts/package_win7.ps1`
- **定位**：Win7 打包流程：onedir 构建、注入 Chrome109、生成安装包并执行冷启动验收

### `aps-post-change-check`

- **对应 workflow**：`../workflows/aps-post-change-check.md`
- **本地 skill**：`aps-post-change-check/SKILL.md`
- **附带资源**：`aps-post-change-check/scripts/post_change_check.py`
- **定位**：改动后一键质量检查：变更范围、ruff、分层快检、复杂度与联动更新提醒

### `aps-start-and-rerun-route`

- **对应 workflow**：`../workflows/aps-start-and-rerun-route.md`
- **本地 skill**：`aps-start-and-rerun-route/SKILL.md`
- **附带资源**：`aps-start-and-rerun-route/scripts/run_start_and_rerun_route.py`
- **定位**：启动 APS 并重跑真实排产：必要时拉起服务、重建 `ROUTEDEMO_` 样例、校验 `/scheduler/gantt/data` 并返回页面地址

### `git-commit-safe-workflow`

- **对应 workflow**：`../workflows/git-commit-safe-workflow.md`
- **本地 skill**：`git-commit-safe-workflow/SKILL.md`
- **附带资源**：无独立脚本，核心流程在 `SKILL.md` 本文
- **定位**：在 PowerShell 环境安全执行 Git 提交：提交前后门禁、UTF-8 提交信息、乱码诊断、`amend` / 重写历史与 `Co-authored-by` 处理

## Windsurf 原生补充 workflow

### `bug-hunt`

- **位置**：`../workflows/bug-hunt.md`
- **来源**：Windsurf 侧新增，不对应 Cursor skill
- **定位**：复杂 Bug 三轮深审、证伪核实、根因链闭合与修复计划收敛
