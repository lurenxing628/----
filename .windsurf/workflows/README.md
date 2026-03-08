# APS Windsurf Workflow 总览

这份目录是给这批 workflow 当“工具箱说明书”的：你不用记名字，只要先看这里，就知道**现在该用哪个**。

## 先理解目录分层

- **项目长期约束**
  - 看 `../rules/README.md`
- **来源 skill 与脚本/参考资料入口**
  - 看 `../skills/README.md`
- **现在该跑哪个 workflow**
  - 看本目录下的 `*.md`

当前 11 个 workflow 中：

- **承接自 Cursor skill**
  - 共 10 个，对应关系见 `../skills/README.md`
- **Windsurf 原生补充**
  - `bug-hunt.md`
- **资源保留策略**
  - `.windsurf/skills` 已镜像 `SKILL.md`、`scripts/`、`reference.md`、`examples.md`，workflow 默认引用本地副本

## 先选哪个

- **刚改完代码，想快速验一遍**
  - `aps-post-change-check.md`
- **怀疑是复杂 Bug，想先确认是不是真 bug、根因在哪，再决定怎么修**
  - `bug-hunt.md`
- **这次改动有点大，担心影响别处**
  - `aps-deep-review.md`
- **想做全仓架构体检**
  - `aps-arch-audit.md`
- **想做更全面的健康检查/漂移检测**
  - `aps-drift-detect.md`
- **想跑全量测试，但不打包**
  - `aps-full-selftest.md`
- **想启动系统并重跑真实排产**
  - `aps-start-and-rerun-route.md`
- **想把开发文档和当前实现对齐**
  - `aps-dev-doc-backfill.md`
- **想用公开数据集跑 FJSP 基准**
  - `aps-fjsp-benchmark.md`
- **想打 Win7 包并做冷启动验收**
  - `aps-package-win7.md`
- **想安全提交 Git，避免 PowerShell/乱码/重写历史翻车**
  - `git-commit-safe-workflow.md`

## 最容易混淆的几个

### `aps-post-change-check` vs `aps-deep-review`

- **`aps-post-change-check`**
  - 适合：改完后快速扫一遍
  - 重点：变更范围、ruff、分层快检、复杂度、联动提醒
  - 特点：快、轻、适合日常
- **`aps-deep-review`**
  - 适合：重要改动、合并前、怀疑影响面很大
  - 重点：引用链、数据流、边界条件、回归风险
  - 特点：慢一些，但看得更深

### `aps-deep-review` vs `bug-hunt`

- **`aps-deep-review`**
  - 适合：代码已经改了，或你已经有明确改动，想评估影响面与回归风险
  - 重点：引用链、参数/返回值一致性、事务边界、边界条件、测试覆盖
  - 特点：偏“已有改动后的深审”
- **`bug-hunt`**
  - 适合：先别改代码，先确认它是不是真 bug、是不是有意实现、根因到底在哪里
  - 重点：候选问题发现、证伪上一轮、根因链闭合、同根因扩搜、最终修复 plan
  - 特点：偏“改动前/计划前的 Bug 深挖与收敛”

### `aps-arch-audit` vs `aps-drift-detect`

- **`aps-arch-audit`**
  - 适合：专门查架构问题
  - 重点：分层、越层导入、循环依赖、复杂度、死代码
  - 特点：偏“架构纪律检查”
- **`aps-drift-detect`**
  - 适合：阶段性体检、里程碑前检查
  - 重点：架构 + lint + conformance + 文档新鲜度 + 引用链
  - 特点：偏“综合健康体检”

### `aps-full-selftest` vs `aps-start-and-rerun-route`

- **`aps-full-selftest`**
  - 适合：想知道整仓测试是否整体通过
  - 重点：smoke、web smoke、FullE2E、regression、复杂 Excel
  - 特点：覆盖广
- **`aps-start-and-rerun-route`**
  - 适合：你刚改了排产链路，想直接启动并重跑真实案例
  - 重点：服务拉起、真实库样例重建、`/scheduler/gantt/data` 校验
  - 特点：更像“快速业务验证”

## 按场景选

## 1. 日常改完代码

推荐顺序：

1. `aps-post-change-check.md`
2. 如果改动跨模块或有签名变化，再用 `aps-deep-review.md`
3. 需要更高把握时，再跑 `aps-full-selftest.md`
4. 准备提交时，用 `git-commit-safe-workflow.md`

## 2. 做了比较大的重构或架构调整

推荐顺序：

1. `aps-deep-review.md`
2. `aps-arch-audit.md`
3. `aps-full-selftest.md`
4. 如果文档也受影响，再用 `aps-dev-doc-backfill.md`

## 3. 想做阶段性全面体检

推荐顺序：

1. `aps-drift-detect.md`
2. 如果报告里出现明确架构问题，再补 `aps-arch-audit.md`
3. 如果是某一处改动影响面不清，再补 `aps-deep-review.md`

## 4. 改了排产或页面，想直接看效果

推荐顺序：

1. `aps-start-and-rerun-route.md`
2. 如果还要确认整仓稳定性，再跑 `aps-full-selftest.md`

## 5. 怀疑遇到复杂 Bug，想先把问题挖透再决定怎么修

推荐顺序：

1. `bug-hunt.md`
2. 如果已经有改动且想评估影响面，再补 `aps-deep-review.md`
3. 如果需要运行层确认，再补 `aps-full-selftest.md` 或 `aps-start-and-rerun-route.md`

## 6. 要交付、出包、发版本

推荐顺序：

1. `aps-full-selftest.md`
2. `aps-package-win7.md`
3. `git-commit-safe-workflow.md`

## 7. 改动涉及文档、接口、Schema、模板、用户文案

直接考虑：

- `aps-dev-doc-backfill.md`

尤其是以下情况：

- 改了 Route 或 Blueprint
- 改了 `schema.sql` 或 migration
- 改了 ScheduleConfig 键或默认值
- 改了 Excel 模板/导入导出逻辑
- 改了 flash 文案、页面提示、错误信息

## 一句话速记

- **快查一遍**：`aps-post-change-check`
- **先把 Bug 挖透**：`bug-hunt`
- **深挖影响**：`aps-deep-review`
- **查架构纪律**：`aps-arch-audit`
- **做综合体检**：`aps-drift-detect`
- **跑全量测试**：`aps-full-selftest`
- **启动并重跑真实排产**：`aps-start-and-rerun-route`
- **回填文档**：`aps-dev-doc-backfill`
- **跑公开基准**：`aps-fjsp-benchmark`
- **打 Win7 包**：`aps-package-win7`
- **安全提交 Git**：`git-commit-safe-workflow`
