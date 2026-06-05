# 测试与门禁专项治理总纲（2026-06-05 重做）

> 仓库：APS 排产系统（Python 3.8 / Flask，目标 Win7 离线）。
> 性质：行为不变的测试/门禁体系治理。整合三条线 —— **提速（主）+ 删合并 + 可读性** —— 成一个有先后、有依赖、有防回潮的工程。
> **本版基于当前仓库实测**（645 文件，2026-06-05），替换 6-01 旧版（607 文件，已因 +38 文件 / 14 次提交过时）。
> 读者：执行人（AI 或人类）。本文是**唯一权威执行入口**。文件级明细见 `L3_verdicts.csv`，支撑文档：`L3_VERDICTS.md`（裁决）/`BASELINE.md`（度量）/`SPEED_AND_READABILITY.md`（提速可读性）/`PLAN.md`（执行明细）。

---

## 第 0 章　治理目标与衡量口径

### 0.1 三个真痛点（用户原话）
1. **慢**：每次 commit/push 跑测试太久，挡着干活。
2. **看不懂**：不看内容根本不知道测什么，难维护。
3. **繁杂**：同一主题散落几十文件、风格不一、样板重复。

### 0.2 KPI 仪表盘（多指标，取代误导性的"文件数"）

| KPI | 清理前（实测 06-05） | 治理后目标 | 痛点 |
|---|---|---|---|
| **push 典型耗时** | ~40s（最坏 180s） | **<10s** | 慢 ★ |
| commit | ~2-3s（已可接受） | 维持 | 慢 |
| 全量并行(xdist) | N/A（未装） | **<90s** | 慢 |
| 全量串行 | 330s | — | 慢 |
| **模块 docstring 覆盖率** | **4.5%** | **100%** | 看不懂 ★ |
| 裸 assert 占比 | 85.3% | <40% | 看不懂 |
| **main-style 文件** | 197（35.8%） | **0** | 看不懂+慢 |
| find_repo_root 样板 | 443（70.9%） | 0 | 繁杂 |
| 测试文件数 | 645 | ~589（-9%）| 繁杂 |
| 测试代码行数 | 161986 | ~140000（-14%）| 繁杂 |
| 门禁脚手架行数 | 23026 | ~7000（-70%）| 繁杂 |
| 门禁缓存 | 17 MB | <1 MB | 繁杂 |

★ = 用户最痛，优先级最高。

### 0.3 一个必须先纠正的认知：文件数不是主 KPI

L3 逐文件精读 645 个文件的准确结论：
- **直接可删（DROP 38 + DROP_WITH_TOOL 7 + MERGE 净减 11）= 56 个文件 = 仅 -9%**。
- 按行数：直接可删 8.2%，但 **KEEP_TRIM 占 28.2% 行**。

**真能整删的只有 9% —— 这是真相，不是失败。** 价值在三处，都不是"删文件"：
1. **提速**：纯配置改（scope 通配），push ~40s→<10s，**一个测试都不删**。
2. **剪 KEEP_TRIM 的 28% 脆性尾巴**：123 个"真测试+脆性快照尾"，剪尾消除"改文案/CSS 就红"。
3. **main-style 转 pytest（35.8%）**：失败可读 + 并行前置 + 删一套元机制。

删/合并是配菜（行 -8%），但其中**删门禁自指测试同时也提速**（最慢榜 ~12 个是 test_long_gate_*_cache）。

### 0.4 铁律
- 不损失任何真实业务回归覆盖（KEEP 429 个〔B-COMPAT 调整后，原 427〕 + §0.5 不回退验证）。
- 不改 run_quality_gate.py 对外 CLI（AGENTS.md 硬约束）。
- 每阶段独立分支、独立提交、可回滚。
- **产物立即 git add**（本治理目录曾被并行 git clean 清空，未跟踪文件无保护）。
- 每阶段后跑 `BASELINE.md` 复测脚本回填 KPI。
- **🔴 B-兼容铁律（与 80 条水下债交接）**：执行 P5/P6（及 P1/P2/P3）前**必读 `_B_COMPAT_SAFEGUARDS.md`**。`regression_sort_strategy_case_insensitive.py` 已标 `HOLD_FOR_R51`（A 不合并·不剪·不删，绑 R51 灵魂线）；`test_architecture_fitness.py` 已锁 `KEEP`。**严禁裸筛 csv `verdict` 后机械 `git rm`**（`DROP_WITH_TOOL`/`HOLD_FOR_R51` 都不可删）。

> **⚠️ 与 B（80 条水下债）交接**：本计划与 `.codestable/audits/2026-06-02-underwater-debt-census/` 的 80 债治理**共用 tests/ 战场**。经 20-agent 交叉核对（`_CROSS_IMPACT_REPORT.md`）：先 A 后 B 顺序**无需调整**，A 不物理删除任何 B 现存安全网、不违反 B 承重纪律；但 **P5 合并 / P6 迁移必须按 `_B_COMPAT_SAFEGUARDS.md` 做保护**（1 个 BLOCKER + 2 个 HIGH + 8 个 MEDIUM）。两处 csv 埋雷已就地消除。

### 0.5 不回退验证（每阶段必满足）
- 全量 passed 数不低于该阶段应有值，**无新增 failed**（当前干净基线 4073 passed / 0 failed）。
- 门禁 `run_quality_gate.py --require-clean-worktree` 绿。
- 每合并簇：参数化后断言条数 ≥ 合并前各文件之和（去重）。

---

## 第 1 章　治理全景（依赖与顺序）

```
P0 配置提速 ──────────────┐ (独立,最快见效,零删除)
P1 死代码+docstring ──────┤ (独立,零风险)
P2 门禁元系统瘦身 ────────┤ (独立,删自指=提速+减体积)
P3 main-style→pytest ─────┼──→ P4 并行xdist (P4依赖P3隔离)
   (可读性+并行前置)       │
P5 业务合并+剪脆性尾 ─────┤ (独立,减维护面)
P6 目录重组+命名 ─────────┘ (放最后,动import路径)
P7 固化+防回潮门禁 ───────→ (收尾,防复发)
```

**最小可行子集**：P0 + P1 + P2（约 1 周）解决 80% 痛点（push 快、能看懂、删最大一坨自指）。其余为深度优化。

| 阶段 | 主题 | 工作量 | 风险 | 主收割 KPI |
|---|---|---|---|---|
| **P0** | 配置层提速 | 1.5 天 | 中 | **push 40→15s** |
| **P1** | 死代码清除 + docstring | 2-3 天 | 零-低 | docstring 100%、删 38 文件 |
| **P2** | 门禁元系统瘦身 | 3-4 天 | 中 | 脚手架 -16000 行、删慢自指 |
| **P3** | main-style→pytest | 5-8 天（分批） | 中 | main-style 197→0、失败可读 |
| **P4** | 启用并行 xdist | 2-3 天 | 中 | 全量 330→90s、push 最坏 -130s |
| **P5** | 业务合并 + 剪脆性尾 | 4-6 天（分簇） | 中 | 剪 28% 脆性尾、合并 11 簇 |
| **P6** | 目录重组 + 命名规范 | 3-4 天 | 中 | 定位 grep→进目录 |
| **P7** | 固化 + 防回潮门禁 | 1-2 天 | 低 | 防复发 |

> 各阶段执行明细见 `PLAN.md` 同名章节；提速/可读性手段细节见 `SPEED_AND_READABILITY.md`。

---

## 第 2 章　各阶段要点（明细在 PLAN.md）

### P0 配置层提速（最快见效，零删除）
真因：push 慢不是测试多（固定底噪才 2s），是 scope 通配过宽（66 个 `**`，改 1 文件命中 5-7 组 180-227 文件）+ 工作树污染升全量。
- P0.0 清工作树暂存的 outside-scope 文件（含本治理产出的 csv，它们正强制全量）
- P0.1 精简 FOCUSED（8 个里 5 个门禁自指）
- P0.2 登记 outside-scope + 未知路径设小默认
- P0.3 收窄 scope 通配（保守档子目录级）→ 典型 40→15s
- ⚠️ 风险：收窄可能漏跑，靠 CI 全量兜底；保守档起步

### P1 死代码清除 + docstring（零风险）
- 删 DROP 38 个（模板快照 24 + 反向结构守卫 5 + 文档死代码）
- 强制 docstring：先 KEEP 427 个，AI 批量生成 + 人工核 → 4.5%→100%

### P2 门禁元系统瘦身（删自指=提速+减体积）
- 缓存模板族参数化合并 + 脚手架瘦身（增量塌缩/指纹简化/必跑改标记，-16000 行）
- DROP_WITH_TOOL 7 个随工具删（**`test_architecture_fitness.py` 例外保留**——验证业务架构合规）
- 缓存 17MB→<1MB

### P3 main-style→pytest（可读性+并行前置）
- 197 文件转 `def test_xxx()`，子进程机制在 `tests/conftest.py:51-106`
- C 类污染源先转（monkeypatch fixture）→ 抽共享 fixture（消 443 样板=R3）→ 批量转（裸 assert 保留=R2 + 加 docstring=R1）→ 删 collector
- 一举多得：可读性 + 删元机制 + P4 前置

### P4 启用并行 xdist
- vendor `pytest-xdist`+`execnet`（纯 wheel，Win7 离线可行）；serial 隔离；`-n auto --dist worksteal`
- 全量 330→~90s，push 最坏 178→~50s

### P5 业务合并 + 剪脆性尾
- MERGE 11 多文件簇 + 6 单挂靠（净减 11，`real_db_replay` 保 e2e 删 check/smoke）
- KEEP_TRIM 123 个剪脆性尾（28.2% 行的收益大头）
- REWRITE 3 + ISOLATE_PERF 8（性能/重 E2E 标 perf/slow 从 push 剔除）

### P6 目录重组 + 命名规范
- 626 文件迁 `tests/<模块>/<子模块>/`（参照 scheduler_graph/），文件名去前缀
- 后缀词表收敛 `_contract`/`_guard`/`_smoke`

### P7 固化 + 防回潮门禁
- 新文件门禁：拦 main-style、强制 docstring、新源文件须 scope 覆盖
- 基线固化 + acceptance.md 填 KPI

---

## 第 3 章　执行建议

1. **立即可做、最快见效**：P0（1.5 天）→ push 40→15s。**强烈建议先做让你解脱。**
2. **最小可行治理**：P0+P1+P2（约 1 周）解决 80% 痛点。
3. **完整治理**：P0→P7 分阶段独立交付，随时可暂停。
4. **隔离**：开工前提交手头改动 + 本治理产物（否则 clean worktree 不满足、且 outside-scope 暂存文件强制全量），或用 worktree。
5. 每阶段后跑 `BASELINE.md` 复测回填 KPI，用真实数字证明每步价值。

---

## 第 4 章　文档集导航

| 文件 | 角色 |
|---|---|
| **GOVERNANCE.md**（本文） | 总纲，唯一执行入口 |
| `PLAN.md` | 各阶段执行明细（命令/步骤/验证）|
| `L3_VERDICTS.md` | 645 文件逐个裁决报告 |
| `L3_verdicts.csv` | 机器可读全量裁决（按 verdict/cluster 筛）|
| `SPEED_AND_READABILITY.md` | 提速瓶颈 + 可读性病灶细节 |
| `BASELINE.md` | 基线 + KPI 仪表盘 + 复测脚本 |
| `test_inventory.csv` | L2 结构清单（行数/函数/断言/模块）|
| `speed_report.md` / `readability_report.md` | 原始专项报告 |
| `raw_verdicts/` | 12 批原始裁决（防丢备份；为 B-COMPAT 调整**前**快照，重跑汇总须重应用 `_B_COMPAT_SAFEGUARDS.md` §6/§7）|
| `summary.json` / `baseline.json` | 统计与基线数据 |

> 数据时效：本文档集基于 2026-06-05 仓库状态（645 文件）。若后续再有大改动，重跑 `scripts/build_test_inventory.py` 刷新 L2，必要时重跑 L3 工作流。
