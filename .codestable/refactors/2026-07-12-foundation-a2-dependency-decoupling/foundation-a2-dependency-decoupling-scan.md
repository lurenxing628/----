---
doc_type: refactor-scan
refactor: 2026-07-12-foundation-a2-dependency-decoupling
status: user-reviewed
scope: core/infrastructure、core/infrastructure/migrations、core/models、core/shared 的 A2 hard 目录 SCC及直接错误/迁移/事件合同测试
summary: 两条结构归位项；均为中风险、行为等价的 Parallel Change，不改数据库与迁移语义
---

# foundation A2 dependency decoupling scan

## 1. 总览

- 扫描范围：A2 四目录 SCC、28 条圈内模块边，以及错误合同、migration common、v16/v18/v19 事件迁移合同和直接测试。
- 发现 2 条值得实施的结构项：错误合同中立化 1 条、迁移公共合同归位 1 条；不为满足普通 scan 的条目数下限虚构第三项。
- 按风险：中 2；没有行为改动项、性能项或页面目视项。
- 建议顺序：先做 **A2-01**（纯错误合同，无数据库写入），再做 **A2-02**（历史迁移公共合同，专项验证面更大）。
- 建议慎做 / 后做：**A2-02** 必须在不改 `migrations/v1.py`—`v19.py` SQL、默认值、执行顺序和异常文本的前提下实施。
- 验证责任：两项均由 AI 用 identity、签名、正逆序新解释器导入、双 scope 循环扫描和专项测试自证；没有页面视觉变化，不需要 HUMAN 目视。

### 前置检查说明

普通 `cs-refactor` 的第 3 条“跨模块”和第 6 条“范围超过 15 文件”天然命中。本批不是绕过：它已经由 `dependency-cycle-governance` roadmap 的 R2/§4.6 建立跨模块结构合同，并明确要求独立 A2、先设计和复审；本 scan 再把整体范围拆成两个各约 10 文件的原子 Parallel Change。第 7 条通常要求至少 3 个候选，但当前只有两个可证明的根因，继续凑项会增加复杂度，因此保留两项。其余检查结果：

- 行为改动：无；数据库格式、迁移版本、公开错误表现均冻结。
- 测试覆盖：有；本轮起点专项集 **193 passed**。
- 风格口味：无。
- 生成物 / 第三方代码：无。

## 2. 当前事实与切边证明

当前 clean HEAD 为 `a53172e77671d722594aeb81c06b72d1cc6b1b22`。正式生产扫描为 761 模块、5 个 hard 目录 SCC；含测试为 1455 模块、6 个 hard 目录 SCC。A2 圈内 28 条边如下：

| 方向 | 条数 | 根因 |
|---|---:|---|
| infrastructure → migrations | 7 | 七个父层模块反借 `migrations.common` |
| migrations → infrastructure | 3 | v16/v18/v19 使用事件数据合同 |
| migrations → models | 1 | v16 使用事件模型时间解析 |
| infrastructure → models | 2 | 事件数据合同使用模型解析/校验 |
| models → infrastructure | 4 | 四个模型模块反借 `infrastructure.errors` |
| models → shared | 8 | 配置模型使用共享解析与降级工具 |
| shared → infrastructure | 3 | 三个共享解析模块反借 `infrastructure.errors` |

在 `/tmp/a2-prototype-20260712` 做了不改工作区的最小原型：

1. 将错误实现放到零依赖 `core.errors`，旧 `core.infrastructure.errors` 单向显式 re-export；切换 models/shared 的 7 个反向调用点，并让 7 个直接调用错误响应函数的生产模块直连新实现，避免兼容 wrapper 遮掉真实调用图边。
2. 将 migration common 实现放到父层 `core.infrastructure.migration_common`，旧 `migrations.common` 单向显式 re-export；七个 infrastructure 父层调用方、`web/bootstrap/factory.py` 和 migrations 包内 21 个生产模块只改 import 到父层，历史迁移 SQL/函数体不动。
3. `fallback_log` 对 `safe_log` 改为同目录顶层显式 import，不保留函数内 import 掩盖依赖。

原型结果：

- production：模块 761 → 763，hard 目录 SCC 5 → 4；A2 整块消失。
- production-and-tests：模块 1455 → 1457，hard 目录 SCC 6 → 5；A2 整块消失。
- 两个 scope 均无新目录 SCC，其他目录 SCC 记录逐项完全相同；parse error 为 0，unresolved 仍为 6 / 44。父包感知 migration 文件 SCC 还会从 21 成员 / 45 边严格缩为 5 成员 / 11 边，纯显式 hard 文件 SCC 仍为 0。
- Python 3.8.10 下旧路径优先、新路径优先两种独立进程导入均成功；错误类/Enum/函数与 migration Enum/helper 的旧新路径对象 identity 全相同。
- 设计盲审原型证明：若只有最小 7+7 切边，兼容 wrapper 会让调用图丢失 57 条真实确信边；补齐上述生产直连后，13 个迁移 callable 按路径映射为新位置，7329 callable / 25786 edges / 10166 confident / 15620 ambiguous / 8 cycles / 193 islands 全部不变，映射后旧新边集零丢失、零新增。

这证明无需移动事件数据合同，也无需改历史迁移 SQL；目标单向结构可收敛为：

```text
migrations → infrastructure → models → shared → core.errors
```

其中可跳层依赖仍允许指向更低层，禁止反向回借。

## 3. 条目

### A2-01 把应用错误合同移到零依赖 core.errors ✓

- **位置**：`core/infrastructure/errors.py:1-170`；`core/models/schedule_config_runtime_{coercion,read,weights}.py`、`core/models/schedule_resource_filter.py`、`core/shared/{compat_parse,field_parse,strict_parse}.py` 的 7 个反向 import。
- **分类**：结构。
- **现状**：`ErrorCode`、`AppError`、`ValidationError`、`NotFoundError`、`BusinessError`、HTTP 状态映射和错误响应函数本身零项目依赖，却位于 infrastructure；models/shared 因使用 `ValidationError` 形成 7 条指回 infrastructure 的 hard 边。旧路径当前被 182 个生产文件和 151 个测试文件导入。
- **问题**：4 条 models→infrastructure 与 3 条 shared→infrastructure 边把最低层解析/模型代码拉回 infrastructure；复制一套错误类又会破坏 `except`、`isinstance` 和 Enum identity。
- **建议**：只搬实现到 `core/errors.py`；旧 `core/infrastructure/errors.py` 改为显式单向 re-export；把上述 7 个低层调用点和 7 个直接调用 `error_response` / `app_error_http_status` 的生产模块切到 `core.errors`，其余 class-only 上层 import 保留旧兼容路径。新增边界测试冻结全部公开对象 identity、构造签名、Enum 值、`Exception.args`、`__cause__`、`__str__`、`to_dict()`、HTTP 映射和响应结构。
- **建议映射的方法**：M-L1-01 Parallel Change + M-L2-04 Move Function + M-L3-06 Layer Rectification。
- **风险**：中；实现纯且零 I/O，但错误类型是全仓公共合同，必须防止旧新路径对象分叉或序列化/错误文案漂移。
- **验证**：AI 自证（新增 identity/签名/双向导入合同；`test_infra_silent_fallback_contract.py`、`test_error_boundary_contract.py`、配置解析/资源过滤测试；grep models/shared 不再 import infrastructure；双 scope scanner）。
- **范围**：约 200 行搬移/兼容代码，16 个生产文件 + 1 个边界测试文件；不做 182 文件全量机械替换。

### A2-02 把 migration common 归到 infrastructure 父层 ✓

- **位置**：`core/infrastructure/migrations/common.py:1-95`；7 个 infrastructure 父层反向 import、`web/bootstrap/factory.py`，以及 `migrations/__init__.py`、v1-v19 / v4_sanitizers 的 21 个包内 import。
- **分类**：结构。
- **现状**：`MigrationOutcome`、SQLite 表/列检查、补列、outcome 合并和日志 helper 放在 migrations 子包；七个父层模块反借该子包，形成 infrastructure→migrations 7 条 hard 边。历史 v1-v19 和测试又广泛使用旧 `migrations.common` 路径。
- **问题**：父包依赖子包 common，而 v16/v18/v19 合理地依赖父层事件合同，构成 infrastructure⇄migrations；把事件合同再搬走会扩大数据库语义风险，却不是消圈所需。
- **建议**：只搬 common 实现到 `core/infrastructure/migration_common.py`；旧 `migrations/common.py` 改为显式单向 re-export；所有生产调用方直连父层实现，历史 migrations 文件只把 `from .common` 改为 `from ..migration_common`。实现归位后把 `safe_log` 改为同目录顶层显式 import，删除现有函数内 import；SQL、标识符校验、日志文本、outcome 值和异常表现逐字保持。
- **建议映射的方法**：M-L1-01 Parallel Change + M-L2-04 Move Function + M-L3-06 Layer Rectification。
- **风险**：中；代码只有 95 行，但被整个历史迁移链共享，任何对象 identity、logger 回退或 SQLite helper 语义变化都可能影响旧库升级。
- **验证**：AI 自证（旧新 `MigrationOutcome`/helper identity 与签名；非法标识符和关闭连接 fail-loud；broken logger stderr 回退；`tests/migration_db` 全目录；v16/v18/v19 事件迁移与 schema 合同测试；Python 3.8 正逆序独立进程导入；双 scope scanner）。
- **范围**：约 125 行搬移/兼容代码，31 个生产文件 + 与 A2-01 共用的 1 个边界测试文件；历史 `migrations/v1.py`—`v19.py` 只改 import，函数体/SQL 零改动。

## 4. 明确不做

- 不移动或改写 `operation_execution_event_data_contract.py`。原型证明保留 `migrations → infrastructure → models` 即可成 DAG；搬它只会扩大 SQL、问题文本和 v16/v18/v19 阻断时机风险。
- 不移动 `core.models._helpers`、事件模型或 shared 解析模块；这些依赖在目标 DAG 中方向正确。
- 不全仓替换 182 个生产文件的旧错误 import；只切 7 个低层反向边和 7 个错误响应函数调用模块，既消圈又保持调用图可见性。旧路径保留 identity-compatible re-export。
- 不改 `ErrorCode` 值、异常签名、中文消息、details、HTTP 状态、JSON 结构或错误链。
- 不改数据库表、索引、约束、迁移版本、SQL、默认值、事务/备份边界、版本推进、migration outcome 或旧库升级结果。
- 不用函数内 import、`TYPE_CHECKING`、动态 `__getattr__` 或吞错隐藏循环。
- 不提前刷新双基线、调用图或架构现状文档；只有实施后逐项核对真实差异才更新。
- 不处理 A3-A6 或 tests SCC。

## 5. 用户选择

- 2026-07-12：用户选择 **A2-01 + A2-02** 进入 design。
- design 双轨复审补充：`web/bootstrap/factory.py` 也应直连父层 common；历史 migrations 仅改 import、7 个错误函数调用模块直连新实现，以避免兼容 wrapper 遮掉 57 条调用图边。该扩展仍属原两项，须在 design checkpoint 由用户确认。

## 6. 起点验证记录

- SCIP：在当前 HEAD 重建，索引时间 `2026-07-12 19:06`；函数级 deep callers/callees 证据位于 `/tmp/aps-symbol-a2-20260712`。
- 正式扫描：`/tmp/a2-current-production-20260712.json`；生产 A2 为 4 成员、28 条圈内边。
- 临时原型：`/tmp/a2-prototype-20260712`、`/tmp/a2-prototype-production-direct-20260712.json`、`/tmp/a2-prototype-with-tests-direct-20260712.json`、`/tmp/a2-callgraph-prototype-direct-20260712`。
- 起点专项测试：错误、字段解析、资源过滤、migration_db、事件数据与 v16/v18/v19 合同共 **193 passed in 5.63s**。
- 写 scan 前工作区仍干净，HEAD 未变化；本阶段没有修改业务代码、基线或 roadmap 状态。
