---
doc_type: refactor-design
refactor: 2026-07-12-foundation-a2-dependency-decoupling
status: approved
scope: foundation A2 的 errors 与 migration common 两个依赖切点，以及对应双基线/调用图/事实文档
summary: 用零依赖 core.errors 和父层 migration_common 建立单向 DAG，生产函数调用方直连新实现，旧路径只做 identity-compatible re-export
---

# foundation A2 dependency decoupling refactor design

## 1. 本次范围

执行用户已勾选的 **A2-01 + A2-02**，目标是消除：

```text
core/infrastructure ⇄ core/infrastructure/migrations ⇄ core/models ⇄ core/shared
```

目标依赖方向：

```text
migrations → infrastructure → models → shared → core.errors
```

允许跳过中间层直接依赖更低层；禁止低层回借高层实现。

设计阶段盲审对 scan 做了两项范围补全：

1. `web/bootstrap/factory.py` 也是 `migrations.common.fallback_log` 的生产调用方，须改走父层实现。
2. 只切最小反向边虽能消圈，却会让兼容 wrapper 遮掉 57 条现有调用图确信边。因此，7 个直接调用错误响应函数的生产模块和 migrations 包内 21 个生产模块也直连新实现；这些额外文件只改 import，不改业务函数体。

因此生产代码预计涉及 47 个文件，其中绝大多数只有一行 import 变化；真正搬动的实现只有 `errors.py` 170 行与 `migrations/common.py` 95 行。总风险为中：错误合同影响面广，migration common 被全部历史迁移共享，但本设计不改错误值、SQL、数据、事务、备份或迁移流程。

本次实施授权不包含 `git commit`、推送或创建 PR；提交与 clean-HEAD 最终证明需要另行明确授权。

## 2. 前置依赖与冻结合同

### 2.1 起点证据

- clean HEAD：`a53172e77671d722594aeb81c06b72d1cc6b1b22`。
- 当前双 scope：production 761 模块 / 5 hard 目录 SCC；production-and-tests 1455 模块 / 6 SCC。
- A2：四成员、28 条圈内模块边。
- 当前 HEAD 已重建 SCIP；deep callers/callees 位于 `/tmp/aps-symbol-a2-20260712`。
- 起点专项测试：错误、解析、migration_db、事件数据、v16/v18/v19 共 `193 passed in 5.63s`。
- 直连版临时原型：双 scope 只删除 A2，其他 SCC 记录逐项不变；Python 3.8 正逆序导入与旧新对象 identity 均通过。

### 2.2 错误合同

旧路径和新路径必须导出同一对象：

- `ErrorCode`
- `AppError`
- `ValidationError`
- `NotFoundError`
- `BusinessError`
- `app_error_http_status`
- `error_response`

冻结内容：

- 37 个 `ErrorCode` 名称与值；
- 全部公开构造签名；
- `Exception.args`、`__cause__`、`__str__`、`to_dict()`；
- `details` / `field` 装配；
- 400/403/404/409/413 映射；
- JSON 字段和用户可见中文消息。

实现移到 `core/errors.py` 后，对象的自然 `__module__` 会指向新规范位置。全仓搜索没有 pickle、`__module__` 或按旧源码文件路径反射的依赖；不通过运行时改写 `__module__` 伪装旧位置。旧命名 import 路径仍返回同一对象。

### 2.3 migration common 合同

旧路径和新路径必须导出同一对象：

- `MigrationOutcome`
- `merge_outcomes`
- `table_exists`
- `column_exists`
- `add_column_if_missing`
- `fallback_log`

冻结内容：

- outcome 值 `applied / skipped / partial`；
- 函数签名；
- SQLite 标识符校验和异常类型/文本；
- 表/列不存在、连接关闭、补列和 outcome 合并语义；
- logger 不存在、正常、抛错时的回退表现和 stderr 文本；
- v1-v19 SQL、默认值、执行顺序、阻断时机、版本推进、备份/回滚、事务边界和旧库升级结果。

`core.infrastructure.logging` 只顶层依赖同目录 `transaction`，没有反向依赖 migration 模块；因此 `migration_common.py` 可把 `safe_log` 改为顶层显式 import，不再保留函数内 import。

### 2.4 生成证据合同

- 双 v2 import-cycle 基线各删除 A2 目录块；因 migrations 生产模块改为直接依赖父层 common，父包感知 migration 文件 SCC 允许从 21 成员 / 45 边严格收缩为 5 成员 / 11 边。其余 SCC 记录和 unresolved 不得变化。
- 13 个迁移 callable 按路径映射后必须零丢失：
  - `core/infrastructure/errors.py` → `core/errors.py`：7 个；
  - `core/infrastructure/migrations/common.py` → `core/infrastructure/migration_common.py`：6 个。
- 调用图两个独立临时目录的 10 个 JSON 必须逐文件 SHA256 一致。
- 直连原型预期调用图总量完全不变：7329 callable、25786 edges、10166 confident、15620 ambiguous、typed 0、8 个受限简单循环、193 islands；按移动路径映射后边集零丢失、零新增。
- dead-code 基线只迁移 `AppError.__post_init__`、`AppError.__str__`、`AppError.to_dict` 三个路径身份，不全量 refresh 接受既有漂移。

## 3. 执行顺序

### 步骤 1：锁定 A2 边界与行为刻画

- **引用方法**：M-L1-04 Characterization Test。
- **具体操作**：新增 `tests/models_domain/test_foundation_a2_dependency_boundary.py`，冻结 §2.2/§2.3 的旧行为、签名和枚举值；加入旧新对象 identity、正逆序独立 Python 3.8 import、低层禁反借和 A2 SCC 消失断言。测试使用函数内 `importlib.import_module` 分开两个迁移目标，保证红灯能准确定位。
- **退出信号**：旧合同断言通过；涉及新模块/消圈的断言按预期失败，失败原因只能是新路径尚不存在或 A2 尚存在，不得出现无关行为失败。
- **验证责任**：AI 自证。
- **回滚**：删除新增测试文件；生产代码仍未改。

### 步骤 2：把错误合同归到 core.errors

- **引用方法**：M-L1-01 Parallel Change、M-L2-04 Move Function、M-L3-06 Layer Rectification。
- **具体操作**：
  1. 将 `core/infrastructure/errors.py` 实现原样搬到 `core/errors.py`。
  2. 旧文件改为七个公开对象的显式单向 re-export；不用 `import *`、动态 `__getattr__` 或复制类定义。
  3. 四个 models 与三个 shared 反向调用点改走 `core.errors`。
  4. `web/error_boundary.py`、`web/error_handlers.py`、scheduler gantt/adjustment/resource-dispatch 的 5 个相关模块（合计 7 文件）直连 `core.errors`，保留 27 条错误响应函数调用图边；其余 class-only 生产 import 不做 182 文件全量替换。
- **退出信号**：错误 identity/签名/序列化/HTTP/中文消息测试通过；models/shared 不再 import `core.infrastructure`；A2 临时缩为只含 infrastructure/migrations 的剩余闭环且无新 SCC；错误 callable 按路径映射后零丢失。
- **验证责任**：AI 自证。
- **回滚**：恢复旧实现和 14 个 import，删除 `core/errors.py`。

### 步骤 3：把 migration common 归到 infrastructure 父层

- **引用方法**：M-L1-01 Parallel Change、M-L2-04 Move Function、M-L3-06 Layer Rectification。
- **具体操作**：
  1. 将 `core/infrastructure/migrations/common.py` 实现搬到 `core/infrastructure/migration_common.py`。
  2. `safe_log` 改为同目录顶层 import；函数体、SQL 和文本保持不变。
  3. 旧 child 文件改为六个公开对象的显式单向 re-export。
  4. 七个 infrastructure 父层调用方和 `web/bootstrap/factory.py` 改走父层路径。
  5. `migrations/__init__.py`、v1-v19 与 v4_sanitizers 中共 21 个 `from .common` 只改为 `from ..migration_common`；用 diff 守卫证明这些历史文件除此之外零变化。
- **退出信号**：边界测试全绿；migration_db、v16/v18/v19、schema、bootstrap 专项通过；A2 从双 scope 完全消失，无新 SCC；Python 3.8 正逆序 import 通过；migration callable/调用边按路径映射后零丢失。
- **验证责任**：AI 自证。
- **回滚**：恢复旧 child 实现和全部 import，删除父层新模块。

### 步骤 4：收紧证据并同步当前事实

- **引用方法**：M-L3-06 Layer Rectification。
- **具体操作**：
  1. 生产/含测试正式扫描输出临时 JSON，逐项核对 A2 消失、其他 SCC 记录相同、unresolved 仍为 6/44、parse error 为 0。
  2. 生成双候选 v2 基线；确认各只删除 A2 目录块，并把同一 migration 父包感知文件 SCC 从 21 成员 / 45 边收缩为其 5 成员 / 11 边严格子集后，覆盖正式双基线，再跑两条 `--fail-on-new-cycle`。
  3. 调用图输出两个独立临时目录，逐文件 SHA；做 13 callable 路径映射和全边集比较，核对通过后覆盖正式 10 JSON。
  4. 只迁移 dead-code 基线的三个 AppError 路径，跑 quick 模式确认 A2 没有新增候选，不全量 refresh。
  5. 更新 `.codestable/checkup/baseline.json`、README、相关 architecture/audits、dependency roadmap/items 与 apply notes；架构文档只写已落地现状。
- **退出信号**：实施终态为 production 763 模块 / 4 SCC、with-tests 1458 模块 / 5 SCC（相对原型多 1 个新增边界测试模块）；父包感知/纯显式 hard 文件 SCC 仍 9/0，runtime 文件 SCC 仍 13/4；调用图映射后零增删；artifact SHA 全匹配；文档与机器数字一致。
- **验证责任**：AI 自证。
- **回滚**：业务代码不回滚时，证据必须重新按当前源码生成；若差异无法解释，则停止并回退步骤 2/3，不得用刷新基线掩盖。

### 步骤 5：局部、完整与 clean-HEAD 证明

- **引用方法**：M-L1-04 Characterization Test、M-L3-06 Layer Rectification。
- **具体操作**：跑 A2 边界测试、错误/解析/config、migration_db、事件迁移、bootstrap 专项；再跑 Ruff、Pyright gate/tools、Python 3.8 语法扫描、双 scope 正式循环门禁和允许脏工作区的完整无缓存/无续跑门禁。局部证明通过后停下请求提交授权；获授权提交后，在最终干净 HEAD 运行 `--require-clean-worktree --no-long-gate-cache --no-resume`。
- **退出信号**：专项、静态检查和完整门禁全部通过；只有提交后的最终 HEAD 工作区前后均干净，才能记录 clean-worktree proof。未获提交授权时只记录局部/dirty-worktree 证明，roadmap 不提前标 completed。
- **验证责任**：AI 自证；提交由 HUMAN 明确授权。
- **回滚**：提交前按步骤逆序恢复；提交后只用独立 revert，不改写历史。

## 4. 风险与看点

- **公开对象分叉**：禁止复制错误类或 Enum；旧新路径一律 `is` 同一对象。
- **历史迁移误改**：21 个 child 文件只允许 import 行变化；任何 SQL/函数体 diff 都是 blocker。
- **兼容 wrapper 遮边**：生产函数调用方直连 canonical 实现；旧路径主要留给 class-only 兼容消费与测试。
- **父包初始化**：`core/__init__.py`、`core/infrastructure/__init__.py` 为空，`core/shared/__init__.py` 仅 docstring；直连原型已验证旧/新顺序。迁移版本模块只有常量构造，无数据库或日志顶层副作用。
- **生成物顺序**：业务代码冻结后才生成调用图/基线/哈希；生成后任何相关源码变化都使证据失效，必须重跑。
- **范围外诱惑**：不顺手拆 HTTP 映射、不移动事件数据合同、不整理 182 个 class-only 错误 import、不做 A3-A6。
- **平台约束**：新增代码只用 Python 3.8 语法和现有标准库/依赖；不改变 Win7 打包边界。

## 5. 双轨复审

### 5.1 定向合同复审

按错误、数据库和迁移既有合同逐项复核：

- 错误 identity、签名、Enum 值、args/cause、序列化、HTTP 映射均有现成测试与新增边界测试承接。
- migration common 的标识符、连接错误、outcome、logger 回退由现有 migration_db/infra 测试承接。
- v16/v18/v19 的脏数据阻断、事件顺序、重建前检查和 schema 约束已有专项测试；设计不移动事件合同。
- SQL、默认值、事务、备份、版本推进均明确禁止变化。

结论：未发现合同 blocker。

### 5.2 调用链与数据流盲审

不从拟定方案出发，重新沿 import、调用图、父包初始化、测试与证据链检查，发现并处理：

1. **遗漏生产调用方**：`web/bootstrap/factory.py` 使用 `fallback_log`，已加入步骤 3。
2. **wrapper 遮挡 57 条调用边**：最小原型 callable 不变但 confident 10166 → 10109、islands 193 → 196；补齐生产函数直连后，按移动路径映射的旧新全边集零差异，已据此扩充步骤 2/3。
3. **dead-code 路径身份**：基线绑定三个 AppError 方法，已加入受控路径迁移，不全量刷新。
4. **导入时序**：迁移模块无状态性顶层副作用，registry 在 `run_migration` 使用时仍会加载；Python 3.8 正逆序原型通过。
5. **反射/持久化**：无 pickle、`__module__` 或旧源码文件路径依赖；不增加动态伪装。
6. **证据链**：双基线、调用图、总 artifact SHA 与现状文档必须同批更新，已加入步骤 4。
7. **父包感知文件 SCC 收缩**：实际候选基线显示 migrations 文件圈从 21 成员 / 45 边缩为 5 成员 / 11 边；新成员与边都是旧记录的严格子集，属于直接父层 import 带来的额外降复杂度，不是新圈。

结论：上述缺口纳入设计后，当前 blocker 为 0。复审由主代理单线程完成，未调用 subagent。

## 6. 用户 checkpoint

- 2026-07-12：用户批准按本 design 实施 A2-01 + A2-02，并同意双轨复审后的 import-only 范围补全。
- 本次批准包含步骤 1-5 的提交前实现与验证，不包含 `git commit`、推送或创建 PR；提交授权仍单独询问。
