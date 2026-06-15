---
doc_type: issue-review-fix
issue: 2026-06-15-reference-trace-systemic-hardening
status: fixed
path: standard
review_date: 2026-06-15
parent: reference-trace-systemic-hardening-fix-note.md
tags:
  - reference-trace
  - code-review
  - adversarial-verify
  - fixed-file-security
  - report-degradation
  - public-token
---

# 审计追踪修复的 Review 加固续篇

> 本文是 [reference-trace-systemic-hardening-fix-note.md](reference-trace-systemic-hardening-fix-note.md) 的续篇：
> 对那一轮落地、尚未提交的修改做了一次深度 code review，修复 review 确认的问题，
> 经 Subagent + Codex 对抗审核，并把整批工作切成 6 个 commit 提交推送。

## 1. 背景与范围

对前一轮 fix-note 落地的未提交改动（核心代码 83 文件 / +1737-517，外加 7 个新增 py）做深度 review。
关注点（用户原话）：是否产生**吞错 / 静默回退 / 过度防御**？是否**慎重考虑了整体与全局**？
所有操作是否**对项目有利、而非只做最小修改**？只看核心代码，忽略测试与文档。

讽刺的是：本轮被审的修复，其核心目标之一正是消除 finding-07 的"坏时间静默跳过"。
所以 review 的第一视角就是——**在消除旧静默的过程中，有没有引入新的静默 / 吞错 / 过度防御**。

## 2. Review 方法

4 个 Sub Agent 按四大主题包并行下钻引用链到根因（固定文件安全 / 查询下推 / 报表降级 / 公开 token 回跳），
每个按统一协议审：吞错、静默回退、过度防御、全局一致性、最小修改 vs 系统性。
对最高影响的发现（`safe_files` 祖先软链接守卫、`overdue_calculations` 混合批次）由主 agent 亲自复核引用链与代码。

## 3. 落地的修复（净改动）

### 固定名文件安全（`core/infrastructure/safe_files.py`、`backup.py`）
- `_raise_if_parent_contains_symlink` → 改名 `_guard_fixed_file_parent`，把"逐级遍历整条祖先链拒绝软链接
  （含 `/var,/tmp,/etc` 平台别名白名单）"**收窄为只校验直接父目录**。
  理由：把数据/备份/日志根目录软链接到真实存储是常见合法部署，整条链一律拒绝会误伤（备份、启动契约、SECRET_KEY 全失败）。
  文件本身被软链接/硬链接借壳的防护（O_NOFOLLOW + 打开后 fstat + 前后 stat 复核）全部保留。
- `create_fixed_file_exclusive`：O_EXCL 创建后若安全校验失败，清理残留空文件。
- `write_fixed_text`：删除无效的 `encoding` 死形参（内部固定 UTF-8）；`write_fixed_json` 增加 `replace_symlink` 透传。
- `backup.list_backups`：读取失败从静默 `continue` 改为记 warning 后 continue。

### 查询下推（`data/repositories/schedule_time_sql.py`、`machine_downtime_repo.py`、`material_repo.py`、`operator_repo.py`）
- `schedule_time_sql`：抽出 `overlap_or_bad_time_sql(alias)` 公共片段，`DETAIL_OVERLAP_OR_BAD_TIME_SQL` 复用它；
  `time_dt` 在 `/`→`-`、`T`→空格 基础上新增**全角冒号 `：`→`:` 归一化**，与 core 层 `parse_dt` 对齐口径（消除 F2 漂移）。
- `machine_downtime_repo.list_active_overlaps_with_machine_names`：原本手写一套坏时间/重叠判定（原始字符串比较），
  改为复用 `overlap_or_bad_time_sql("md")`，消除两套判定漂移（参数顺序 `(end_time, start_time)` 不变）。
- `material_repo` / `operator_repo`：抽 `_list_filters`，让 `list` 与 `count` 共用过滤片段，杜绝分页 total 与行数漂移。

### 报表降级 / 诚实展示（`overdue_calculations.py`、`report_engine.py`、`report_context_filters.py`）
- **F1（核心，命中"消除静默却留静默"）**：`overdue_calculations` 新增 `collect_bad_time_rows(rows)`，
  覆盖**所有批次**的坏时间行；`report_engine` 的超期降级计数从"只统计'排程时间异常'桶"改为用它，
  使**混合批次**（有有效完成时间但夹带坏行的批次，原本进 scheduled/准时分支、其坏行被静默吞掉）的坏行也被诚实计入并修正提示文案。
- `report_context_filters._has_bad_time`：从"至少一端时间非空才算坏"改为"解析不出有效区间即算坏"
  （涵盖 start/end 全空的脏停机行），与 `downtime_impact._index_downtime_rows` 口径一致。
- `schedule_delay_diagnosis_utils.plan_link`：`scenario_id` 死形参加注释 + `_ = scenario_id`，说明 by-design（不写 URL，由 token 承载）。

### 公开 token 与回跳（`web/public_token_registry.py`、`scheduler_gantt.py`、`scheduler_gantt_public_payload.py`）
- `public_token_registry`：新增模块级 `threading.RLock` 包住 `issue`/`resolve` 的读改写序列，消除 cleanup 竞态；
  顶部 docstring 钉死"**单进程部署**"约束（多 worker 会 token miss，需改共享存储或签名 token）。
- `scheduler_gantt`：删除 render 甘特模板时传入的死参 `scenario_id=`（模板只用 `plan_context_token`）。
- `scheduler_gantt_public_payload`：黑名单加维护注释（新增内部字段须同步登记）。

## 4. 关键判断：三次守住 by-design（本轮最重要的收获）

对抗（测试 + 深挖原意）**三次推翻了 review/agent 的最初判断**——它们倾向把保守的
fail-loud / fail-closed / 不误报 安全设计误判成 bug：

| 最初判定 | 对抗裁定 | 最终处置 |
|---|---|---|
| 删光固定文件父目录软链接检查 | `test_fixed_file_security` 证明删过头（应保留"直接父目录"） | **收窄**而非删光 |
| 契约写入该加 `replace_symlink=True` | 测试钉死：契约文件本身是软链接应 fail-loud 拒绝并保留现场 | **回退** |
| 维护锁读不出该"自愈清理" | 测试钉死：读不出的锁须 fail-closed 阻止备份（防误删可能有效的锁；软链接父目录下的合法锁也会读不出） | **回退** |
| 甘特漏标"时间坏的逾期批次"=新静默，应标红 | 深挖 finding-09：丢弃 `invalid_time` 桶正是"不把时间坏的批次误报成逾期"的有意成果 | **不标红**，改为降级提示 |

**教训**：机械执行"全部修"会亲手破坏深思熟虑的安全设计。审查结论必须用测试与原始设计意图二次校验，
不能盲从 agent 的"过度防御/新静默"判断。已沉淀到记忆 [[implementation-depth-requirements]]。

## 5. 对抗审核

- **报表 + token 包 Subagent**：成功，逐条确认主修复正确，并贡献了 `plan_overdue_markers` 的疑似新静默发现（见下）。
- **固定文件包 Subagent + 两个 Codex 对抗**：**全部被平台 cyber 安全策略拦截**——审查内容含"软链接 / 路径穿越 / 攻击面"
  被判为攻击性网络安全内容，返回 Usage Policy 错误、0 输出。这是平台限制，无法绕过；固定文件包改用已通过的
  `test_fixed_file_security`（98 passed，本就是验证软链接借壳防护的）作背书。已沉淀 [[cyber-safeguard-blocks-symlink-review]]。

### 甘特/派工坏批次降级提示（对抗发现 → 核实 → 修复）
`plan_overdue_markers.build_overdue_meta_for_plan` 的 candidate/scenario 路径，对"有排程但计划完成时间写法坏"的
"排程时间异常"批次：**不标红是对的**（守 finding-09 不误报逾期），但此前**既不标红也无任何提示**，在甘特/派工视图上闷不吭声。
修复：不改标红（不冤枉为逾期），改为通过现成的 `partial`/`message` 通道（`gantt_boot.js`/`resource_dispatch_core.js` 已消费）
**浮现具体批次号提示**，并记降级日志。新增 2 个回归测试（坏批次浮现 + 无坏批次不无中生有）。

## 6. 验证

分阶段 + 综合自检，全绿：
- `test_fixed_file_security` 等固定文件套：98 passed
- 四包综合回归（app_runtime / migration_db / calendar_maintenance / scheduler_analysis / resource_dispatch / route_view）：966 passed
- gantt / web_pages：309 passed；候选 + 甘特 + 派工：506 passed
- 门禁元契约 `tests/gate_meta/` 全套：939 passed
- `ruff check` 全部改动文件：通过
- `pre-push` daily-fast-gate：通过

## 7. 提交（6 个 commit，已 push 到 origin/ci/install-networkx-win）

```
fd7cca64 docs: 刷新架构/速查文档与 reference-trace 审计修复产物（含 test_registry scope 登记）
bb1b6c35 test: 补充固定文件/下推/降级/token 回跳回归测试
ff994ad6 fix(security): 公开响应白名单 + plan_context_token 回跳收敛内部字段
37b26368 fix(report): 报表坏时间不再静默跳过，降级端到端诚实提示
28e47db7 perf(query): 列表筛选/分页/坏时间过滤下推到 repo 与 SQL
2e6948a7 fix(security): 固定名运行文件统一安全读写原语
```

推送时 pre-push 反回归门禁拦下一次：新增的 `web/public_token_registry.py` 未被任何回归组 scope 认领
（uncovered_source）。已将其登记进 `tools/test_registry_groups_misc.py` 中覆盖 web 顶层请求基础设施的回归组
（与 `navigation_context.py` / `manual_src_security.py` 同组），并入文档 commit；二次推送通过。

## 8. 有意跳过的项及理由（非缺陷）

- **F3** `DegradationCollector` 多样本：非 bug（计数正确，"样例"不承诺固定条数），改公共组件波及所有降级路径，风险 > 收益。
- **F5** 批次详情 `_placement_span` 的 op_count/span 口径差异：by-design 的诚实披露（页面已明示），不改。
- **网址 `scenario_id`**：by-design 计划身份，已由 token 接管 URL 显示（见 [[forbidden-internal-identity-means-visible-text]]），只清死形参、不动行为。
- **`schedule_plan_query_service` 方法间空行**：纯审美紧凑化，不违反 ruff 门禁，手动还原 18 处反有风险。
