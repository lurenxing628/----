---
doc_type: feature-acceptance
feature: 2026-09-12-gap-resource-quality
status: accepted
summary: 全剥夺提示恢复shift_pool完整历史baseline，原生工序类型读取减去3000次反射，独占资源与插空收益保留，134项定向测试通过。
tags: [scheduler, resource-quality]
---

# 插空换型与稀缺资源选择验收

## 1. 接口契约

- `GreedyScheduler.schedule`、dispatch callback、自动分配公开接口及持久化结果字段不变。
- `MachineTypeState` 保持 dict 尾工种映射，另存真实时间排序的工种记录；`certificate(machine_id)` 返回不可变内容证据。
- `update_machine_last_state` 增加可选 `start_time`、`op_id`，原调用仍可只维护末态；普通借入 dict 保留原行为。
- `ResourceDemand.penalties(op, pairs)` 对一次并列比较只做一次证据复核；调用方只在实际完工与换型增量并列、且稀缺提示可能改变选择时使用。`penalty` 为单组合包装，revision 不作为外部输入不变证明。
- scheduler 初始化及 `internal_operation` 空映射保持由并行 SGS 分工接入；run_state 的机器/人员占用结构也由该分工换成 `OwnedTimeline`。本项定向测试已覆盖这些集成后的代码。

## 2. 行为与决策

挂载点实际检索并核对：scheduler 在种子加载后调用 `initialize_resource_quality`；run_state 在成功、失败、跳过、异常和图传播时退休需求；internal_slot 找到最终合法槽后计算邻接换型；auto_assign 只对两个基础目标相同的合法组合调用 `prefer_resource_pair`。后续性能收紧增加 `comparison_is_neutral`：旧提示同分时直接沿用原排序，有分差时才调用完整认证。

拔除推演由真实反例对照落实：强制原错误机台仍得到 4 次换型/2 小时工期，自动选择得到 2 次换型/1 小时工期；不会以修改工时、删除种子或放宽资格得到改进。无需求证据的一般路径沿用原字典和排序，不提前触发自定义属性或转换。

边界修正记录：

- 定向复核确认字符串 ID 可能与结果中的整数 ID 不一致，导致完成需求未退休；现仅原生正整数 ID 纳入需求，字符串及其他形式继续走原排产转换和验证路径。
- 同时间点或重叠种子可能使“最大结束时间的工种”与“按开始时间排序的最后工种”不同。快速追加仅在两者相同才沿用尾罚分；其他情况按实际邻接计算。既有末态守卫保持。
- 官方局部扫描发现新资格函数复杂度 21 超过阈值 15；已按候选机器、工种过滤与组合构造拆分，未改白名单或阈值。

## 3. 验收场景与命令

真实 `GreedyScheduler` 的 `batch_order`、`sgs` 两条路径均验证：

| 场景 | 对照与结果 |
| --- | --- |
| M1=A/A/B，M2=B/B/A，新增B可09–10插入 | 强制M1换型4次；自动M2换型2次；种子内容和时间不动 |
| A可M1/O1或M2/O2，B仅M1/O1，各1小时 | 强制A到M1总工期2小时；自动A到M2总工期1小时 |
| 稀缺替代组合更晚完成 | 仍选择更早完工组合 |
| 已冻结种子占用M1 | 保留该机人及时隙，不为了稀缺度搬动 |
| 同批两个独立piece，批量10 | 各按1件工量排产，可并行1小时完成 |
| 同piece有前置链 | 后继仍不早于前道完成 |
| 成功、失败、异常、缺批次、跳过、图阻塞 | 已退出需求不再保留资源 |
| pool或活跃工序同长度原地修改 | 停用旧提示并记录明确fallback_reason |
| 末态守卫、动态descriptor、固定资源、窗口归因 | 既有合同保持 |

最终定向命令：

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/algorithm/test_gap_resource_quality.py \
  tests/algorithm/test_resource_demand_contract.py \
  tests/algorithm/test_machine_last_state_gap_backfill_contract.py \
  tests/algorithm/test_greedy_run_state_contract.py \
  tests/algorithm/test_auto_assign_window_blocked_attribution.py \
  tests/algorithm/test_sgs_internal_scoring_matches_execution.py \
  tests/algorithm/test_greedy_refactor_contract.py \
  tests/algorithm/test_resource_demand_neutral_comparison.py \
  tests/algorithm/test_resource_demand_total_blocking.py
```

初始功能验证为 **110 passed in 0.58s**；中性比较阶段为 **118 passed in 0.54s**；包含全剥夺收紧和历史 baseline 完整回归的最终定向验证为 **124 passed in 0.75s**。

对 `resource_quality.py`、`resource_demand.py`、`runtime_state.py`、`run_state.py`、`internal_slot.py`、`auto_assign.py` 及两个新增测试执行 Ruff、Python 3.8 配置下的 Pyright：均通过，Pyright 为 `0 errors, 0 warnings, 0 informations`。同批文件 `ast.parse(..., feature_version=(3, 8))` 通过。官方 `scan_complexity_entries` 和 `scan_oversize_entries` 对六个产品文件均返回空；本项 tracked diff 的 `git diff --check` 通过。

中性比较后续增量的两产品文件和 `test_resource_demand_neutral_comparison.py` 再次通过 Ruff、Pyright、Python 3.8 语法及官方局部复杂度/大小检查。新序列测试覆盖：同分阶段池、当前字段、descriptor、class default 已变化时不声称认证；下一次有分差必须认证并拒绝旧证据。公共 `penalties` 在同分时仍完整认证、仍及时设置原 `fallback_reason/revision`，保持原直接调用合同。

早期整合阶段曾因空 `MachineTypeState` 被 `or {}` 替换导致三条稀缺用例红灯，已显式保留非 None 映射后重验；曾出现短暂 `penalties` 接口接线未完成，现接口已稳定并通知总矩阵执行方重跑。未把这些中间失败写成最终通过证据。

## 4. 术语一致性

换型增量对应最终换型次数，不声称实现顺序相关 setup 时长。稀缺提示不替代资源资格或可行性判断；未知资格不造默认组合。新增类型均为内部运行态，不进入页面或导出字段。

## 5. 架构归并

本项依赖维持 `algorithms/greedy -> algorithm_runtime`，新增 helper 不反向 import algorithms/services。运行态统一承载类型证据、完成与失败生命周期，避免在评分/执行复制需求账。共享架构总入口由本轮主代理统一归并，本子分工没有并行改写该共享文件。

## 6. Requirement

既有合法机人调度与换型、工期评价目标不变；本项改进内部选择，没有新增用户配置、输入字段或持久化合同。本子项不引入独立 UI 需求。

## 7. Roadmap

本项来自本轮研究后的直接实施授权，统一关联 `scheduler-global-optimizer` 的 `optimizer-quality-efficiency-20260912` 条目及本轮清单 B；不回写无关事项。

## 8. Attention 候选

没有修改 attention.md，也没有修改跨会话记忆。可复用的回调证据和同时间工种边界已记录在本设计与测试中。

## 9. 遗留与证据边界

本记录验收的是本项功能与定向合同。当前为多分工并行修改的工作区；未提交、未运行全仓门禁、未打开业务数据库、未做正式大容量计时或 Win7 真机验收，不声称 clean-worktree proof。整轮质量矩阵和性能基准由主代理统一提供；本项微例收益不能外推为全部业务数据的固定提速或固定质量增益。

### 后续性能收紧：同分提示不做无效认证

整轮 `medium_shift_pool` 的 48 工序诊断暴露新成本：290 次 `penalties/_certify`、2751 次 `_fields_match`。该固定用例中两工种共享相同六个合格机人组合，每个组合对其他头的冲突比例都为 3/6，因此这些认证不会改变选择。新方法只证明“当前比较不会受稀缺提示影响”，不声称输入内容没变，不把身份或长度当内容证据。

同一当前源码、同一进程内用原并列比较函数强制完整认证作为控制，只改变这一个比较钩子；各三次 48 工序单解码交替计时：控制为 0.135318、0.136300、0.139849 秒；中性比较为 0.111068、0.113418、0.113252 秒。中位数 0.136300→0.113252 秒，约下降 16.9%。另各一次 profile 只用于调用计数，不混入原生计时：`_certify` 290→0、`_fields_match` 2751→0、`_plain_class` 291→1；`slot_changeover_penalty` 仍为 1612 次。

全部八次均为 48 行、零失败，完整结果 SHA-256 均为 `5700847e0c59d9d9272a854518f8c3c4eee8388ace2d5408c35d795a8fcac21c`。证据为 `/private/tmp/aps-algorithm-implementation-20260912/b-neutral-decode.json` 及同目录 `b-neutral-force_certificate.pstats`、`b-neutral-neutral.pstats`；JSON 保存本项两产品文件散列，计时前后相同。这是单解码微例，不是旧版本整体性能结论、10 秒优化质量矩阵或正式 5000 工序容量验收。

### 后续质量根因收紧：部分组合损失不能冒充阻塞

完整入口旧/新 b、c 结果中，`shift_pool` baseline 四目标均出现总拖期 1489.5→1507、加权拖期 3136.5→3171.5；c 版两侧 competing_samples 均为 0。只读逐条比较确认选择顺序不变、前四条结果相同，第五条 `op40/B09-3` 在相同 M2、相同时隙上由 O0 改为 O2。原占用比例提示在此给 O0/O2 分别 5.5/3.5，但四道 TYPE1 头在 O0 被占用后仍各有 M0/O1 可选。后续人员分配变化令 `op31/B07-2` 占据 O1 的 01-09 09:30～11:00，最终只使 `op8/B01-3` 完工从 01-09 15:00 变成 01-10 08:30；17.5 小时与 urgent 权重 2 精确解释全部新增拖期。

先在临时进程中仅替换 `_score` 为全合格组合剥夺计数：原分数版精确匹配退化新 c 的完整 payload，全剥夺版精确恢复旧 c 的完整 payload；原两工序独占例仍并行 1 小时完成、零失败。证据 `/private/tmp/aps-algorithm-implementation-20260912/b-full-deprivation-counterfactual.json`。探针最末打印曾使用 Python 3.8 不支持的 dict union，报错发生于全部断言通过且证据写完之后；随后只读打印已落盘证据核对，没有重复运行排产掩盖该记录。

因果成立后实施通用收紧：只有其他头全部合格组合被当前机器/人员的联合占用覆盖才计 1；有剩余组合则计 0；当前头排除。新增正反合同验证部分人员损失不计阻塞、唯一机台多操作员保护、唯一操作员跨机台保护、机人联合覆盖只计一次、跨当前工序查询与完成退休不串分。没有夹具分支，没有新 baseline 策略开关，没有增加第二次全量解码，也没有改夹具或比较器。

正式代码回归校验完整 `shift_pool` 历史 payload SHA-256 为 `7c8ba505b8cc36e9b35fabc91aa939e5560037e872f0458c45b67cf4b8b1c3ec`，包含全部 48 行与四套完整质量向量。最终 124 项测试通过，`resource_demand.py` 与变更新旧测试的 Ruff、Pyright、Python 3.8 语法和官方局部结构检查通过。该收紧仅是局部保守启发式，不能据此声称任意数据全局不退化；整轮完整入口及容量仍由主代理统一验证。

### 后续性能收紧：原生工序类型逐次直接读取

相同 48 工序诊断中 `_plain_operation_type` 调用 1000 次，每次三次静态反射。仅当 `type(op) is SimpleNamespace` 时改为读取当前原生实例字典的 `id/op_type_name`；不保存字段快照，不使用身份或长度作为内容证据。正整数、字符串及去空白规则保持，子类和一般对象仍走原静态路径，实际邻接换型规则不变。

新增 10 项合同覆盖同长度字段替换、字段删除、特殊同名实例键、非原生/无效字段、descriptor/转换不执行、空白工种、子类动态安装类 property 和自定义访问器无额外首错。原 124 项加新用例共 **134 passed in 0.64s**；补充空白断言后该测试文件 **29 passed in 0.45s**。Ruff、模块方式启动的 Pyright、Python 3.8 语法和官方局部复杂度/大小检查均通过。直接 `.venv/bin/pyright` 曾因 shebang 指向已不存在的旧 `Documents/GitHub` 路径退出 127，改用 `.venv/bin/python -m pyright` 后为零错误，不改环境。

临时脚本只在对照进程把这一个 helper 恢复为旧静态读取，各进行一次 48 工序 CPU profile；两次加载源码散列完全相同，全部结果/摘要/策略/参数逐字节相同，输入未改、排产期间数据库零写入，均 48 行且零失败。两侧 payload SHA-256 为 `3431ffb60db465d8a1c7c7bcc1d1ba6c987e9b30fdae401818ea73048b75583f`。`getattr_static` 5587→2587 次，全部调用 686695→655695；helper 1000 次累计 CPU 24.653→2.218 ms，`slot_changeover_penalty` 保持 1585 次、SGS score 保持 315 次。CPU 数字包含 profiler 开销，仅证明目标调用成本被移除，不能当作原生整体提速或正式容量结论。

证据为 `/private/tmp/aps-algorithm-implementation-20260912/b-native-operation-type/comparison.json`、两侧 `functions.json/payload.json/loaded-source.json/cpu.prof`，以及只改 helper 的 `run_profile.py`。独立只读复核在 Python 3.8.10 上验证 exact `SimpleNamespace` 的类不可修改、原生字典不可替换和实例特殊同名键边界，未发现阻断问题。本项已停止额外 CPU 工作，整轮串行验收仍由主代理执行。

碰撞键定向补核：原生 `__dict__` 仍可放入非字符串键，查找确实可能触发该键的 `__eq__`。核对 Python 3.8 的旧 `inspect._check_instance`，其同样通过 `dict.get(instance_dict, attr, sentinel)` 按 `id`、`op_type_name` 顺序读取；exact `SimpleNamespace` 下两次读取使用同一不可替换的字典，其间旧路径只有不可变内置类的静态读取。因此新路径不增加或调整这些潜在回调点。新增 12 个真实哈希碰撞差分合同，覆盖对象键/字符串子类键、正常匹配、回调中修改下一字段、ID 不匹配、ID 抛错、类型抛错及相等结果 `__bool__` 抛错，两侧返回值、完整回调日志和首错一致。初版测试将失败查找错误限定为一次比较，实际字典探测可能再次比较同一槽；两侧差分断言一直相等，修正的是测试的无依据次数限制。测试文件 **41 passed in 0.47s**；添加准确类型标注后碰撞子集 **12 passed in 0.45s**，Ruff/Pyright 通过。没有修改产品实现或增加每次遍历全部键的成本，没有重跑性能或广泛审计。
