---
doc_type: refactor-design
refactor: 2026-09-12-sgs-incremental-scoring
status: approved
scope: Native SGS scoring, scalar due-date parsing, and formal slot handoff
summary: Reuse only unchanged native candidate dependencies and retain legacy callback semantics.
---

# SGS incremental scoring

用户在算法研究后明确授权“全部都做，多并发 agent 全力全速推进”。本项按项目 `cs-refactor` 的扫描、设计、实施和验证记录执行；该授权已覆盖研究报告里的优化，不增加重复审批。

## 现状与选择

原 SGS 每轮完整评分所有 ready 工序。30 个互不共享资源的独立工序评分 465 次，正式派工又额外估时 30 次。2026-09-11 的 timing 工作明确拒绝过没有充分失效证据的整份评分缓存，本次不复用该被撤回方案。

采用 M-L4 性能缓存、M-L1-04 行为刻画、M-L2-01 按职责提取：新缓存只属于一次原生 `GreedyScheduler.schedule()`，正常退出、异常和嵌套调用由 ContextVar token 成对恢复；借用的 legacy dispatch 不自动取得该资格。

## 输入及失效合同

- 原生 scheduler、run context、run state、Batch/BatchOperation（或 exact SimpleNamespace）及其相关 MRO 方法必须保持原样，实例覆盖继承方法也不予认证。
- 只复用固定设备和人员的自制工序。自动派工和外协继续完整评分。实测共享资源频繁失效的额外成本高于重算，所以仅当机、人都在当前 ready 集合中独占且不只剩一个候选时，才新建缓存；已有且仍有效的条目可以继续命中。
- 每次查缓存仍读取该候选实际影响评分的原生字段内容、批次进度、图优先级/前置完成、已采样工时、排序参数、相关设备/人员/停机、机器工种邻居以及已消费日历政策。
- 原生标量一经证明不可变，可在每次重读字段后按逐值身份确认未变；任一值被替换则重新生成包含类型的精确内容证书。没有按整个可变对象的 id 或列表长度猜测未变。
- 普通 list 保持内容快照。新建运行状态使用 OwnedTimeline 和私有 OwnedSegments；同一写入协议也用于 OwnedTypeEntries 工种历史。所有标准序列写入更新 revision，非原生段/工种记录不能得到版本证书。OwnedSegments 不继承 list，防止 list.__setitem__ 绕过写入协议，迭代直接使用底层原生列表迭代器。借用 legacy 字典和列表保持原样，MachineTypeState.certificate 仍返回原 tuple。
- 日历层提供原生政策读取证据，算法层不反向导入 CalendarService。每轮认证原生方法，逐候选核对上次确实消费的 operator/date 政策键；清空、替换、原地字段修改和方法覆盖均失效。政策内容缓存只复用已证明原生不可变的标量，并有 4096 条上限。
- 仅成功评分可以入缓存；读取未知对象或无法证明的状态直接执行原评分，保留原来的首错误和回调顺序。

## 正式放置

评分得到的估时仅作为待核验候选。正式派工仍完成固定资源解析、独立工时校验、截止窗口处理、占用写入和业务失败记录；只有当前内容证书与评分证书相等且独立计算的基础工时相等，才复用冻结 InternalSlotEstimate。不会把 probe_only 自动派工冒充正式提交。

## 验证与边界

需要证明 10/30 独立工序结构性评分减少、最终排程相等、共享资源正确失效、动态对象/类方法/实例覆盖保留原路径、同长度输入和占用变更可见、所有标准 OwnedSegments mutator 失效、日期子类与 parser override 保留回调。

必须同时计量真实耗时。首次实现曾显著慢化，不能以调用次数下降作为提速证明；被拒绝的计时保留在 `native-comparison.json`，后续测量独立留档。局部验证不等于全仓 clean proof，也不代表 Win7 实机速度。
