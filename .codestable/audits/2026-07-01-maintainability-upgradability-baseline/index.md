---
doc_type: audit-index
audit: 2026-07-01-maintainability-upgradability-baseline
scope: APS 全项目可维护性与可升级性只读基线审计
created: 2026-07-01
status: active
total_findings: 5
---

# APS 可维护性与可升级性基线审计

## 范围

本次审计的目标不是修代码，而是把“这个项目以后好不好维护、好不好升级”先落成一份可复用基线。后续每次大改、重构、依赖升级或 Win7 打包链调整，都可以拿这份基线对照。

本次覆盖：

- 外部评价方法：通过子代理调用 Exa MCP，并由主线程补充 Exa 检索，参考 ISO/IEC 25010、ISO/IEC 25020、ISO/IEC 25041、SIG/TUV 可维护性评分、代码度量、依赖健康和交付能力方法。
- 本地代码证据：`core/`、`web/`、`data/`、`scripts/`、`tools/`、`tests/`、`.github/workflows/`、`installer/`、`requirements*.txt`、`.codestable/architecture/`。
- 本次只读，不修复、不重排、不清理工作区。

## 当前现场边界

- 当前分支：`feat/default-light-improve-sgs`。
- 当前 `HEAD`：`52171c3b`。
- `git status --short | wc -l` 输出 `345`，说明工作区已有大量改动。本次文档只作为“脏工作区上的只读审计”，不能当作干净基线证明。
- 未运行 `scripts/run_quality_gate.py --require-clean-worktree`，因为该命令会在脏工作区失败，且会写质量门禁产物；本次只做审计落档。

## 评分总览

这不是绝对科学分数，而是为了让后续对比有一个稳定参照。

| 项目 | 分数 | 大白话解释 |
|---|---:|---|
| 可维护性 | 70/100 | 项目不是散装代码，有文档、测试、门禁、分层和页面合同；但排产核心太重，循环依赖还在，改核心功能仍然需要很小心。 |
| 可升级性 | 58/100 | 系统有打包说明和离线意识，但 Win7、Python 3.8、PyInstaller 4.10、NetworkX 3.1 和离线依赖链把升级空间压得很窄。 |
| 综合基线 | 64/100 | 已经有治理体系的大项目，不是不可救；但关键结构债会持续拖慢后续大改。 |

## 10 维度评分

| 维度 | 分数 | 关键证据 | 判断 |
|---|---:|---|---|
| 架构模块边界 | 7/10 | `core` 不反向依赖 `web`，算法层未依赖服务层；但仍有硬加载期目录环 | 大方向清楚，局部环要治理 |
| 复杂度和大文件 | 5/10 | `core/services/scheduler/` 约 43628 行 / 206 个 Python 文件，根目录仍有 79 个业务文件 | 最大维护压力在排产核心 |
| 耦合和影响面 | 6/10 | 排产主链已函数注入，但 `run` / `summary` / `config` 互借仍重 | 能改，但影响面要先查清 |
| 重复代码 | 6/10 | 本轮未做全量重复率扫描；已看到多处旧垫片和兼容入口 | 证据不足，暂按中等风险 |
| 技术债和静态问题 | 6/10 | 项目已有循环依赖扫描、死代码扫描、债务台账；现存硬环仍未清零 | 治理工具在，债还没还完 |
| 测试覆盖和回归保护 | 8/10 | 测试文件规模大，质量门禁计划覆盖格式、类型、架构、启动回归和必跑回归 | 这是项目最强的维护资产之一 |
| 依赖健康和离线兼容 | 5/10 | 运行依赖少且锁版本；开发依赖未全锁，Win7/Python 3.8 限制明显 | 可控但升级空间窄 |
| 构建发布自动化 | 5/10 | CI 跑 Windows 最新环境，不是真 Win7；正式双包链依赖 Win7 打包机和离线 wheelhouse | 交付链有说明，但证明不完整 |
| 数据和配置可升级 | 7/10 | 仓储封装、迁移版本、备份回滚、严格解析都存在；迁移链较长 | 比一般项目稳，但改表仍重 |
| 可分析性和文档同步 | 9/10 | `.codestable/architecture/`、审计记录、质量门禁说明都很丰富 | 文档体系是明显优势 |

## 发现清单

| # | 性质 | 严重度 | 置信度 | 标题 | 文件 |
|---|---|---|---|---|---|
| 1 | arch-drift | P1 | high | 硬加载期目录环仍在，核心层升级容易被导入顺序卡住 | [finding-01.md](finding-01.md) |
| 2 | maintainability | P1 | high | 排产核心是巨型模块，根目录平铺和旧垫片增加改动成本 | [finding-02.md](finding-02.md) |
| 3 | maintainability | P1 | high | Win7/Python 3.8/离线交付链限制升级，真机闭环证明不足 | [finding-03.md](finding-03.md) |
| 4 | maintainability | P2 | medium | 质量门禁保护强，但门禁系统自身复杂且依赖干净工作区证明 | [finding-04.md](finding-04.md) |
| 5 | maintainability | P2 | medium | 前端重页面依赖脚本顺序和黑名单过滤，替换或拆包会偏慢 | [finding-05.md](finding-05.md) |

## 按维度分布

| 性质 | P0 | P1 | P2 | 合计 |
|---|---:|---:|---:|---:|
| bug | 0 | 0 | 0 | 0 |
| security | 0 | 0 | 0 | 0 |
| performance | 0 | 0 | 0 | 0 |
| maintainability | 0 | 2 | 2 | 4 |
| arch-drift | 0 | 1 | 0 | 1 |
| **合计** | **0** | **3** | **2** | **5** |

## 重要优势

- 分层方向是对的：本次扫描未发现 `core` 反向依赖 `web`，也未发现算法层依赖服务层。
- 测试和门禁是强资产：统一门禁已经覆盖格式、类型、Python 3.8 语法、架构、启动、债务和必跑回归。
- 页面层不是散装：统一壳、统一链接、公开字段治理、本地静态资源交付都已经成体系。
- 数据层有护栏：仓储、严格解析、安全固定文件读写、迁移备份回滚都已经存在。
- 文档体系强：`.codestable/architecture/`、历史审计、质量门禁和交付说明能让后续接手的人少走弯路。

## 下一步建议

- **P1 本迭代优先排**：
  - 先用 `cs-refactor` 设计硬加载期目录环治理方案，优先从 `run` / `summary` 互借纯函数和 `config_snapshot` 公共契约开始。
  - 为 `core/services/scheduler/` 做分包路线图，不直接大搬家，先定入口规范和旧垫片退役规则。
  - 补齐 Win7 真机、双安装包、离线 wheelhouse 的可复跑证明，避免“代码绿了但交付不了”。
- **P2 有空治理**：
  - 给质量门禁系统本身拆出更清楚的子包和轻量验证入口。
  - 给甘特图前端脚本链做下一阶段拆包方案，优先把黑名单字段过滤换成白名单公开投影。

## 相关文件

- [method.md](method.md) —— 本次采用的外部评价方法和本地评分口径。
- [.codestable/architecture/service-scheduler.md](../../architecture/service-scheduler.md) —— 排产核心结构地图。
- [.codestable/audits/2026-06-28-circular-imports/index.md](../2026-06-28-circular-imports/index.md) —— 循环依赖专项审计。
- [.github/workflows/quality.yml](../../../.github/workflows/quality.yml) —— 统一质量门禁的持续集成入口。
