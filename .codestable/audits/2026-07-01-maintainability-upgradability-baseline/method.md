---
doc_type: audit-support
audit: 2026-07-01-maintainability-upgradability-baseline
created: 2026-07-01
status: active
---

# 评价方法

## 外部资料

本次先让子代理使用 Exa MCP 调研行业评价方法，再由主线程补充 Exa 检索。外部资料只用于建立评价口径，本地结论仍以仓库真实证据为准。

| 来源 | 用途 |
|---|---|
| [ISO/IEC 25010:2023](https://www.iso.org/standard/78176.html) | 质量模型总纲，可维护性要看模块化、可分析、可修改、可测试等能力。 |
| [ISO/IEC 25020:2019](https://www.iso.org/standard/72117.html) | 说明如何选择和构造质量度量，避免只凭感觉评价。 |
| [ISO/IEC 25041:2012](https://www.iso.org/standard/35766.html) | 说明质量评价流程，适合做“定义目标、执行评价、形成结论”的闭环。 |
| [SIG/TUV 可维护性评价指南](https://softwareimprovementgroup.com/wp-content/uploads/SIG-TUViT-Evaluation-Criteria-Trusted-Product-Maintainability-Guidance-for-producers.pdf) | 将可维护性拆成规模、重复、复杂度、接口、耦合、组件缠绕等源码指标。 |
| [SonarQube 代码指标说明](https://docs.sonarsource.com/sonarqube-server/user-guide/code-metrics/metrics-definition) | 覆盖复杂度、重复代码、覆盖率、质量门禁等工程化指标。 |
| [微软代码度量说明](https://learn.microsoft.com/en-us/visualstudio/code-quality/code-metrics-values?view=visualstudio) | 说明维护性指数、圈复杂度、继承深度、类耦合等指标如何定位风险。 |
| [OpenSSF Scorecard](https://www.scorecard.dev/) | 依赖和开源供应链健康评估参考。 |
| [DORA 交付能力四指标](https://cloud.google.com/blog/products/devops-sre/using-the-four-keys-to-measure-your-devops-performance) | 发布频率、变更前置时间、失败率、恢复时间可改造成内部交付能力度量。 |

## 本项目适配原则

APS 不是云服务，也不是多用户互联网系统，所以不能把行业方法生搬硬套。

本项目必须额外遵守：

- **Win7 x64**：目标机仍要支持 Windows 7 64 位。
- **Python 3.8**：开发与打包基线仍是 Python 3.8。
- **离线交付**：目标机不要求装 Python，不依赖外网，静态资源和依赖要能本地交付。
- **单机/共享数据场景**：不要把问题硬套成互联网权限或多租户安全问题；但公开字段、内部字段边界仍然要干净。

## 打分口径

每个维度 10 分：

- `10`：有清楚约定，有自动化证据，而且已经进门禁。
- `8`：基本自动化，只有少量人工备查。
- `6`：能量化、能定位，但不一定会拦截。
- `3`：主要靠人工记忆或人工检查。
- `0`：没有证据，或者明显失控。

硬约束：

- 任何新增依赖或升级方案，如果不能证明兼容 Win7、Python 3.8 和离线交付，该维度最高只给 `3`。
- 如果某项变化会导致正式安装包不可交付，综合分建议封顶 `60`，哪怕代码结构看起来更现代。

## 本次用到的本地命令

本次没有运行会写大量门禁产物的全量质量门禁，主要使用只读命令：

```bash
git status --short
git status --short | wc -l
rg --files
python3 -m tools.scan_import_cycles --json
python3 - <<'PY'
# 统计 Python 文件、行数、函数长度和近似复杂度
PY
```

本次重点证据：

- `git status --short | wc -l` 输出 `345`，当前不是干净工作区。
- 当前文件系统下，生产 Python 文件约 `741` 个，生产代码约 `144453` 行；测试约 `685` 个 Python 文件，约 `176424` 行。
- `python3 -m tools.scan_import_cycles --json` 输出 `hard_dir_cycles` 共 `6` 组，`runtime_file_cycle_count=5`。
- `core/services/scheduler/` 结构地图记录该模块约 `43628` 行 / `206` 个 Python 文件，并有 `79` 个根目录业务文件。

## 后续复评办法

后续每次大改后，建议按同一顺序复评：

1. 先看工作区是否干净，避免把临时状态当项目事实。
2. 跑 `python3 -m tools.scan_import_cycles --json`，对比硬环是否减少。
3. 统计 `core/services/scheduler/` 根目录文件数和最大文件/函数规模，确认有没有继续膨胀。
4. 跑项目质量门禁；只有干净工作区加 `--require-clean-worktree` 才能算正式证明。
5. 若涉及依赖或打包，必须补 Win7 真机、离线 wheelhouse、双安装包验收证据。
