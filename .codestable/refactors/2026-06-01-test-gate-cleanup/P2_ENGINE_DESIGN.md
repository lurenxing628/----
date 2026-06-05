# P2 引擎手术设计（M4 瘦身核销器 + M2 增量塌缩 + M3 指纹简化）

> 2026-06-06 落库。B-12 塌缩（0506b27d）已交付；本文档是 P2 剩余主体的实施蓝图。
> 实施纪律：每阶段独立提交 + 全量门禁验证 + 双跑验证（见 §6）；随时可停，已交付阶段自洽。

## 1. 现状架构图（实测核对过的承重事实）

```
full gate (run_quality_gate.py, 16 步)
 ├─ full_test_debt 步：跑全量 3960（容忍 debt ledger 登记的失败）
 │   └─ long_gate_full_test_debt.py(2034)：增量引擎
 │       ├─ 变更分类(测试/助手/生产/台账) + AST import 影响分析(~50 函数)
 │       ├─ long_gate_test_body_diff.py(317)：测试体差分→精确 nodeid 选择
 │       └─ INCREMENTAL_MERGE_POLICIES：增量结果合并回全量 payload
 ├─ required_regressions 步：python tools/verify_required_regressions_from_full_test_debt.py
 │   ├─ 真实语义：从 full_test_debt payload 核销「required 全过且不得是债」 ← 必须保留
 │   └─ 证明捆绑：写父证明(required_regressions.json) + 8 组子证明(305K)
 │       ├─ 写入侧：run_quality_gate.py:1802-1865(uses_full_test_debt_verifier 分支)
 │       └─ 消费侧：long_gate_cache.py:442-457(评估复用时校验子证明) ← 唯一消费者
 └─ 缓存系统：manifest(1203) + fingerprint(1319) + cache(1150) + collect(63)

daily gate (run_daily_quality_gate.py)
 └─ 只用 test_registry 的分组 target_paths/scopes 做影响面规划(P0 已收窄)
     ★ 不消费任何证明（grep 证实 0 命中）→ registry 分组一仆二主，分组本身不可删

full_test_debt_shards.py(80)：serial/parallel nodeid 分类器 = P4 并行前置，M2 不删
（P2.1 合并测试文件时同步其硬编码文件名模式）
```

## 2. 目标架构

- **required 核销语义保留**（required ⊄ debt），但证明捆绑系统整体退役：
  核销器瘦身为「读 payload→核销→写简单回执」，缓存复用退化为纯指纹判定（组 scope 并集指纹已存在）。
- **full_test_debt 缓存退化为整体复用**：指纹全中→复用上次 payload；任何 miss→全量重跑。
  删测试体差分/精确选择/增量合并全套。
- **新增 `pytest -m required` 人用入口**：conftest 按 registry 分组自动打 marker（不改 210 个文件）。

## 3. 阶段划分（风险升序）

### M4a 核销器瘦身（不删模块——比 PLAN 原文更保守的安全变体）
PLAN 原文是「删模块+改接」；本设计选择**保留模块路径与 CLI display 串瘦身之**，理由：
manifest 按 display 串分类(:772)、fingerprint/registry/shared 多处路径引用、16 步结构全部免改，
B-14 的 :25/:1858 改接需求自动消解（import 仍有效）。
- `tools/verify_required_regressions_from_full_test_debt.py` 620→约 200 行：
  保留 `verify_required_regressions_from_payload` + CLI;删 `_build_proof_payload`/
  `write_required_regressions_proof_bundle`/`_build_group_proof_payload`/`_group_rows_for_required_paths`
  等证明机器；输出退化为单一简单 JSON（required_regressions.json，无子证明）。
- `scripts/run_quality_gate.py`：删 :1802-1865 的 `uses_full_test_debt_verifier` 分支与
  `_load_required_regressions_verifier_proof`。
- `tools/long_gate_cache.py`：删 :442-457 子证明特例 → required_regressions 变普通可复用条目
  （指纹=组 scope 并集，机制已有且有契约测试）。
- `tests/conftest.py`：按 `tools.test_registry` 分组自动打 `required` marker + pytest.ini 注册 marker。
- `§1.4 SOP` 第 3 行：换 `pytest -m required`。
- 同步测试：`test_long_gate_required_regression_cache.py`(742) 证明篡改类用例退役、指纹类保留；
  `test_run_quality_gate.py` verifier 相关段瘦身；`long_gate_cache_helpers.py` 适配。
- 清理产物：`evidence/QualityGate/required_regressions/` 子证明目录退役（拦截条目保留防旧产物入库）。

### M2 增量引擎塌缩
- `tools/long_gate_test_body_diff.py`(317) 整删。
- `tools/long_gate_full_test_debt.py` 2034→目标 <600：删变更分类/AST import 影响分析/精确选择/
  增量合并；保留「指纹比对→整体复用 or 全量重跑」+ payload 校验 + 台账联动。
- `tests/test_long_gate_full_test_debt_cache.py` 4054→目标 <800：增量边角用例退役，
  整体复用/失效/payload 校验契约保留。
- 风险：改后首次门禁必然全量重跑（指纹变化），属预期。

### M3 指纹简化（搭车）
- `tools/long_gate_fingerprint.py`(1319) 删 Chrome 指纹部分；浏览器几何组的 env_keys 仍由
  registry 声明，组级失效语义不变。须核对 `test_long_gate_chrome_preflight_diagnostics.py`
  与 manifest 中 chrome 相关断言的连带。

### P2.1 缓存测试模板族合并（引擎稳定后）
- `test_long_gate_*_cache` 簇参数化合并；同步 `full_test_debt_shards.py` 硬编码文件名。

### P2.3 DWT 清扫（随工具死亡）
- `regression_quality_gate_registry_split_scope_contract.py`：⚠ 它 PIN 着 §3⊆required 等
  B 关心的锁——退役前过 _B_COMPAT §B-8（R20 自证替代），拿不准则问用户。
- 其余 DWT 逐一核对其工具是否真死，工具不死则测试不删。

### P2.4 总验证
按 PLAN 原文五条 + `du -sh evidence/QualityGate/`（基线 16M，B-12 后 13M）。

## 4. 不可破坏清单（来自 _B_COMPAT + 本次核对）
- registry 分组的 target_paths/input_file_scopes/env_keys（daily gate 承重）
- `test_architecture_fitness.py` 锁 KEEP，A 只可禁删不可加内容指纹锁（B-11/B-12 旁注）
- run_quality_gate 对外 CLI（flags/入口）；步骤构成可改（PLAN M4「改门禁编排」授权）
- 「required ⊄ debt」核销语义
- `full_test_debt_shards.py`（P4 前置）
- HOLD_FOR_R51 / HOLD_FOR_R43 两文件仍然碰不得

## 5. 数字账（预期）
- M4a：约 -400(verifier) -300(run_quality_gate 分支+cache 特例) -400(契约测试净减) = ~-1100 行
- M2：约 -1700(full_test_debt) -317(body_diff) -3300(测试净减) = ~-5300 行
- 产物：required_regressions/ 305K + 子证明逻辑退役；current_full_test_debt.json 5.7M 保留（payload 本体）
- M3 + P2.1 另计

## 6. 双跑验证协议（M4a 与 M2 各做一次）
1. 改前基线：干净树上 `run_quality_gate.py --require-clean-worktree` 全绿 + 记录 16 步耗时
2. 改后双跑：第一跑（冷缓存，预期全量重跑）全绿；第二跑（热缓存）全绿且复用条目命中
3. 语义等价抽查:故意让一个 required 测试失败（本地临时改动，不提交），
   验证门禁必须红且报错指向该测试；恢复后再跑绿 → 证明核销语义未丢

## 7. 执行进度(2026-06-06 续作锚点)
- ✅ B-12(0506b27d) / M4a(eaf83cbf) / M2(3ed51929+2c47c2fb+0fb44c74) / M3(7a4a9c1a) 全部交付并推送,各自门禁 16/16 绿
- 对抗审查:M4a CLEAN;M2 两 issue(消费侧死代码/死 import)已收口
- 累计净 -7300 行、运行产物 -10.2MB;`pytest -m required` 入口已加(1821 nodeids)
- ▶ P2.1 进行中:按 csv KEEP_TRIM 剪快照尾(manifest:228 巨型清单/startup:60+90/debt_ledger:53/
  summary markdown 整行/quickref+collect 指纹参数化并簇入 test_long_gate_cache)
  ⚠ 裁决修正:`test_required_scope_tracks_real_inputs_without_unrelated_markdown` 不删——
  P0 实战中它拦住过真实覆盖损失(group7 doc scopes 误删),是承重 fail-closed 守卫,只允许瘦身
- 待办:P2.3 DWT 逐一核对工具死亡再删(registry_split_scope_contract 退役前过 B-8);P2.4 总验证
