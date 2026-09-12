---
doc_type: refactor-apply-notes
refactor: 2026-09-12-sgs-incremental-scoring
status: completed
summary: Native certificates, scalar parsing and slot handoff passed focused regression and structural gates.
---

# 实施与证据

## 已完成

- 新增 `core/algorithm_runtime/native_snapshot.py`、`owned_timeline.py`、`sgs_estimate_reuse.py` 以及 `core/algorithms/greedy/dispatch/sgs_reuse.py`，只在原生认证路径复用。
- SGS 评分、正式估时、CalendarService 原生政策证书和 scheduler scope 已接入；同一调度器的 `_decode_invocations` 单调计数和 `_last_sgs_reuse_stats` 私有诊断不进入用户 payload。
- exact str 交期解析按 `(strict_mode, value)` 缓存成功结果，最多 4096 条；无效输入、字符串子类与被替换的 parser 保持原路径。
- 与资源质量分支协作：保留其 MachineTypeState，读取真实插入邻居证书；scheduler 初始化资源需求；修正空 MachineTypeState 被 `or {}` 丢弃的问题。run_state 仅由本项接两处时间轴 factory，保留其他 agent 的业务生命周期改动。

## 已执行的局部验证

- 第一批四组合同：359 passed。最终扩大到 B 资源质量/稀缺需求、H 复核缺口、G 原生计数与真实 cache hit、既有 SGS/piece/legacy callback/资源复用合同：**545 passed，6.84 秒**。
- 实际 cProfile 计数：10 个独立工序由 55 次评分降至 10 次；30 个由 465 次降至 30 次。相同最终排程、工时、错误和摘要（排除 duration_seconds）。
- H 独立复核曾复现 OwnedSegments.certificate 实例覆盖藏住同长变更，以及继承 dict.get 覆盖改变首错误；均已修复并加入测试。H 当前定点复查确认与 fresh scoring 一致，timeline/type-state get 覆盖保持 due_date 首错。
- 最终 14 个产品/测试路径 Ruff 通过；Pyright `--pythonversion 3.8` 为 **0 errors, 0 warnings**。首次私有序列适配和测试动态字典注解错误已修复，没有用全局忽略或升级运行时处理。
- 官方 `scan_complexity_entries` 和 `scan_oversize_entries` 对本项全部产品路径均返回 `[]`。按职责拆出 dispatch/route.py，同时保留 scheduler 传入当前 dispatch callback 的测试/覆盖可见性。

## 性能试验记录

`native-comparison.json` 为同一已加载源、100 批次各 10 工序、原生日历、1000 工序的 12 个探索性对照。只通过 factory 禁用 cache 作同代码对照，没有 patch GreedyScheduler.schedule；每行带完整产品结果/摘要 SHA-256。所有三组资源布局启用/禁用的 payload 哈希相等。

- 100 组专用机人：关闭 0.866/0.908 秒，启用 0.690/0.711 秒。
- 全部共用一组机人：关闭 4.608/4.560 秒，结构门槛启用后 4.711/4.633 秒，cache hits/misses 均为 0。
- 三组共享机人：首次启用 5.271/5.205 秒，对照 1.401/1.414 秒。该版本被拒绝。已把尚未选中工序的正式估时证书改为共享本轮证据，并对高频共享失效采用上面的资源独占门槛；这份慢化记录保留，不覆写。

最终门槛版本另存 `native-comparison-final.json`，不能与初版 receipt 混称同一份源码。`native-comparison-selected.json` 保留门槛收敛后的中间确认（后续又禁止只剩一个候选时新建缓存）。所有比较都是单机合成数据上的探索性测量；正式工作台 1000/5000 和完整门禁由主线程在冻结源码后统一执行。

小规模极轻工序仍有固定认证开销（30 道一小时独立工序约额外 1 毫秒）；未承诺所有规模均加速。优化不会改变业务方案、扩大搜索预算或降低既有验收要求。

本项没有连接原始业务数据库，没有提交 Git 或运行全仓质量门禁。所有样例数据库为 SQLite 内存数据库且开启 query_only；运行期间记录并核对 total_changes。

## 隔离门禁发现的加载环修复

主线程首次完整隔离门禁在 import-cycle 步骤发现 `dispatch/sgs_reuse.py -> greedy/run_context.py` 反向依赖，导致新增目录环和父包初始化文件环。已把 RunContext guard 的固定创建移回 scheduler 模块初始化阶段，再作为明确参数传入子层；没有在首次运行时按传入实例类型创建“原方法”基线。新增测试覆盖首个 reuse 构造前替换 RunContext 方法仍完整评分。

与 A 去重模块协作新增纯 runtime 注册入口 `native_multi_start_calendar_snapshot` 和独立服务层 `calendar_multi_start_certificate.py`。CalendarService 初始化时冻结 Engine/Shift/仓库（包含 BaseRepository MRO）守卫，随后 helper 加载/重载前的覆盖不会被认成原方法；每个 DayPolicy 都核查实例覆盖，完整字段及字典顺序进入证书，所有仓库连接保持同一身份。这不声称防住依赖在首次 CalendarService 导入前已被替换的情况；主线程确认维持本次最小范围，不扩大到七个依赖 owner 模块。

- C 受影响短合同：130 passed；随后 A31+C30 联合合同：61 passed。
- Ruff、Python 3.8 Pyright 通过；官方复杂度与体量扫描均为空。
- `python -m tools.scan_import_cycles --fail-on-new-cycle --quiet-when-clean` 最终 exit 0；日志 `/private/tmp/aps-algorithm-implementation-20260912/native-certificate-import-cycle-fix.log` 为空。没有更新 import-cycle baseline。

## 全自动资源下的零命中开销收口

父线程真实 workload 的 48 工序 `shift_pool` 派生小例确认：全自动资源无法复用固定资源评分，却仍承担占用时间轴包装和每轮资格检查。新增 `can_skip_native_sgs_reuse`，只对 exact `SimpleNamespace` 或经原类结构认证的 `BatchOperation`，以原生字典和字符串键、字段类型确认本趟没有完整固定机人组合，整趟放弃可选缓存。未知对象、字段、字典或 descriptor 保持原路径。先静态确认原生类访问结构，再读取候选字典，避免探测抢先调用用户代码；首次加载边界的收口见下一节。

同一个标志在准备阶段选择机器 `SlotReuseTimeline` 和人员原生 `dict`，并跳过评分 factory。机器仍保留原完整内容时隙索引；`ScheduleRunState` 默认构造、legacy 借用、`MachineTypeState` 和 `OwnedTypeEntries` 不变。callback 后续把工序改为固定资源时继续实时完整评分；没有缓存或冻结字段，没有把 OwnedSegments 改成可被 C 层 mutator 绕过的 list 子类。

- 新增 `tests/algorithm/test_sgs_plain_auto_timelines.py` 的 14 个合同，覆盖两种 DTO、种入/齐套、固定资源保守路径、callback 后变化、原生 list 同长修改、字段/键/字典/元类与 descriptor 首错。
- 连同原 SGS 缓存、Owned mutation、资源质量和 busy-block/union 短合同：**218 passed，8.75 秒**。这些是当前 dirty 工作区的局部验证，不是 clean-worktree proof。
- 独立只读子代理定点复查了上述实现与合同，未发现阻断问题；复查未另跑测试或 benchmark。
- 隔离 source 从父冻结的 validation 复制，只有本次 scheduler.py 和 dispatch/sgs_reuse.py 两文件不同，未混入并行 B 改动。同一 48 工序 fixture，三份 baseline/validation/C-isolated payload 逐字节一致，SHA-256 `3431ffb60db465d8a1c7c7bcc1d1ba6c987e9b30fdae401818ea73048b75583f`。
- 对 validation 的 C 独立变化：总调用 `686695 → 636874`，Owned 段包装读 `25727 → 9230`（剩余属于保留的工种历史），每轮 `begin_round` 与正式 `selected_estimate` 均 `48 → 0`。评分 `315`、估时 `2145`、配对 `1782`、内部尝试 `3854` 全部不变。
- 单次 cProfile 的 CPU 汇总 `0.540958 → 0.479016` 秒，仅用于定位开销；含 profiler/timer 成本，不是正式无 profiler walltime 提速。未新增大矩阵、1000/5000 或全仓门禁运行。

详细 receipt、完整已加载源码哈希、只有两文件差异的清单和 profile 位于 `/private/tmp/aps-algorithm-implementation-20260912/c-shift-pool-cpu-1yoPEE/`，见其中 `c-isolated-comparison.json` 和 `README.md`。最终局部 Ruff、Python 3.8 Pyright、官方 complexity/size 与文件哈希收据在 `c-final-checks.json`。

## 首次加载与可选证书回调边界

父线程最终定点阅读发现：先导入模型并覆盖 `BatchOperation.__init__`，再首次加载 helper 时，中间版本的模块级 DTO 样本会额外触发构造回调。已删除样本，未改成另一种隐式构造。提前探测独立静态确认 exact metaclass、原生 object 基类/getter/字典 descriptor 及默认资源字段；只有确认后才读取实例字典和执行既有漂移 guard。`make_class_guard` 记录加载时状态，单凭它不能证明提前覆盖的方法仍是原生方法。

同一提前覆盖边界也影响固定资源缓存：原始 afc 三工序完整评分为 6 次、Batch.due_date getter 为 9 次，中间版本可以出现 3 次命中并把 getter 降至 6 次。因此 `_record` 对 `Batch` 与 `BatchOperation` 的缓存准入复用静态访问结构及相关字段认证，提前 getter/property 覆盖不再进入缓存。最终两模型均恢复 6 次评分、9 次 getter、0 命中，完整结果/摘要/策略/参数 payload 与 afc 相同，SHA-256 为 `0a50fc61a94307c753ced1482b31e2a487466e3ca3e0ed584199738c715e6bce`。证据为 `c-preimport-fixed-comparison.json`；没有把中间 H 版本当作用户原始基线。

父线程另直接复现自定义 metaclass 在标量证书的 tuple membership 或 set/hash 中抛错。`scalar_snapshot`、`scalar_tuple_snapshot`、`native_record_snapshot` 以及嵌套 `content_snapshot` 现先用 `type(kind) is type` 做无副作用准入，再走原生类型快速判断。两个日历证书 registry 查询同样先拒绝自定义 metaclass，避免可选缓存抢先调用 `__hash__`/`__eq__`。

- `test_sgs_plain_auto_timelines.py` 现有 27 条合同，包含真正冷进程的构造/访问 hook 顺序，以及两模型 × getter/property 的固定资源缓存对照。
- 新增 `test_native_snapshot_callback_boundaries.py` 的 11 条合同：未知元类的 scalar/tuple/record/content 与 calendar 查询均返回不支持且回调数为零；正常标量 token 和原生日历证书继续可用。
- 联合既有原生 SGS 缓存合同：**68 passed，2.88 秒**。局部 Ruff、Python 3.8 Pyright、官方 complexity/size 最终通过。当前工作区仍是 dirty 状态，未提交，未新跑大矩阵或完整门禁。
- 最终边界修复与文件哈希收据为 `c-boundary-final-checks.json`。48 工序 CPU profile 绑定的是上一节所列冻结版本，未把它改称此次边界修复后重新测得的 walltime。
