---
doc_type: refactor-design
refactor: 2026-07-10-scheduler-a1-dependency-decoupling
status: approved
scope: scheduler 根/config/run/summary A1 hard 目录 SCC
summary: 用已有低层叶子、execution 内聚子包和 neutral contracts 单向化依赖，旧路径显式 re-export
---

# scheduler A1 dependency decoupling refactor design

## 1. 本次范围

执行 scan 中 A1-01/A1-02/A1-03。用户于 2026-07-12 明确授权启动 A1，并要求遵循 KISS 与全局复杂度下降原则。总风险为中：只移动实现和 import 方向，但触及排产主链 DTO、执行快照和公开投影；必须靠 identity/行为合同与独立进程导入证明等价。提交、推送和创建 PR 不包含在本次实施授权中。

## 2. 前置依赖

- 已在当前 HEAD `964d74d9d665353a043a1cf00e6736cfc0764d82` 重建 SCIP 索引，并用 `symbol_locator whereis/callers --deep/callees --deep` 复核 12 个待迁移边界符号；结果在 `/tmp/aps-symbol-a1-20260711`。
- 已用正式 scanner 重跑起点生产图，A1 仍为同一四目录、49 条圈内模块边；结果在 `/tmp/a1-current-scan-20260712.json`。
- 工具阶段已完成双 v2 基线、父包感知/纯显式双文件图、正式门禁与调用图修准。
- 新增刻画测试先锁旧路径/新路径对象 identity、关键函数签名和 import 顺序，再迁移调用点。

## 3. 执行顺序

### 步骤 1：锁兼容与导入合同

- 引用方法：M-L1-04 Characterization Test
- 操作：新增 A1 module-boundary 测试，要求旧路径可导入、兼容 re-export 与新实现为同一对象；正序/逆序新解释器 import 均成功；最终扫描中 A1 成员集合消失。
- 退出信号：测试在迁移前对尚不存在的新路径按预期失败，迁移后通过。
- 验证责任：AI 自证。
- 回滚：删除新增测试，不改业务。

### 步骤 2：根目录叶子能力归位

- 引用方法：M-L3-06 Layer Rectification、M-L1-01 Parallel Change
- 操作：`core.shared.boolean_normalize` 提供与旧 `to_yes_no` 同签名入口；config/run 改走 shared；run/summary 改直接依赖 model degradation 合同；旧 root module 保持兼容。
- 退出信号：config/freeze/summary degradation 测试通过，config/run/summary→root 对应边消失。
- 验证责任：AI 自证。
- 回滚：恢复 import，删除 shared alias。

### 步骤 3：execution 族下沉

- 引用方法：M-L2-04 Move Function、M-L1-01 Parallel Change
- 操作：把 fact provider、snapshot、scope read、enrichment 实现迁入 `scheduler/execution/`；旧根文件改显式 re-export；run 调用方切新路径，root/web/tests 可继续旧路径。
- 退出信号：execution/gantt/reschedule 测试通过；旧新对象 identity 相同；execution 子包无 root/run/summary/config 顶层依赖。
- 验证责任：AI 自证。
- 回滚：恢复根实现与 run import，删除新子包。

### 步骤 4：summary contracts 下沉

- 引用方法：M-L2-04 Move Function、M-L1-01 Parallel Change
- 操作：把 graph public projection、optimizer public safety/search projection、summary DTO 和 count parser 实现迁入 `scheduler/contracts/`；summary 旧文件显式 re-export；4 个 run import 改走 contracts。
- 退出信号：orchestrator/summary/optimizer/graph 合同测试通过；run→summary hard 边为 0，旧新对象 identity 相同。
- 验证责任：AI 自证。
- 回滚：恢复 summary 实现与 run import，删除 contracts。

### 步骤 5：A1 静态与动态验收

- 引用方法：M-L3-06 Layer Rectification
- 操作：生产/含测试扫描，核对 A1 hard 目录 SCC 消失且无新 SCC/新圈内边/新未解析动态导入；新进程正逆序导入；跑 scheduler config/run/summary/persistence/gantt/operation execution tests、Ruff、Pyright、Python 3.8 语法。
- 退出信号：A1 消失，现存其他圈未扩大，行为测试全绿。
- 验证责任：AI 自证；无页面视觉变化，不需要 HUMAN 目视。
- 回滚：按步骤逆序恢复。

## 4. 风险与看点

- 兼容 wrapper 只能从新叶子导入，不能让新叶子反向 import wrapper。
- `contracts/__init__.py` 与 `execution/__init__.py` 保持空/无重导出，避免父包初始化扩大文件 SCC。
- 不改 dataclass 字段、默认值、Enum 值、hash 拼接、公开白名单和错误文本。
- 扫描验收看目录 SCC 成员/边，不用函数内 import 或 TYPE_CHECKING 掩盖 hard 边。
