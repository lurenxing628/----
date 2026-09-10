---
doc_type: feature-acceptance
feature: workbench-candidate-adoption
status: integration-pending
summary: BX 最小后端纵向路径 53 项专属测试及 193 项关联回归通过；生产/UI/注册/整仓门禁仍由主线验收。
tags: [workbench, adoption, verification]
---

# BX 验收结果

## 结论

已完成可独立验证的最小后端纵向路径；未开放生产能力。无需新增 schema 或改变旧共享 helper 语义。默认 `WORKBENCH_CANDIDATE_ADOPTION_ENABLED=False`，新路由未代主线注册，BL GET 的 `adopt=False` 未修改。

本轮工作区原有大量 staged/unstaged/untracked 内容，BX 仅新增独占文件。未 stage、未 commit、未启动用户端口；测试使用临时数据库。

## 命令与真实结果

```text
.venv/bin/python -m pytest tests/workbench/test_run_candidate_adoption*.py -q -s --tb=short
53 passed in 46.98s
BX 5000 timings compute=35.634s preview=1.245s adopt=1.609s
```

5000 用例通过真实受理、真实 worker、真实引擎计算得到候选，不 mock 核心验证；完整追加 5000 条 Schedule 和 5000 个新正式 task_ref。预览逐表验证零数据变化，采用后逐表核对旧行的 Python/SQLite 存储类型与值。明确允许数据库序列和身份 clock 变化，以及声明的追加表新增行；旧业务记录不能重写或丢失。

```text
.venv/bin/python -m pytest \
  tests/workbench/test_run_candidate_queries.py \
  tests/workbench/test_run_candidate_api.py \
  tests/workbench/test_run_compute_integration.py \
  tests/workbench/test_run_compute_execution.py \
  tests/workbench/test_run_jobs_atomic.py \
  tests/workbench/test_run_jobs_concurrency.py \
  tests/workbench/test_plan_persistent_identity.py \
  tests/workbench/test_commands.py -q --tb=short
193 passed in 9.99s
```

对本轮 14 个 Python 新文件运行 `ast.parse(feature_version=(3,8))` 全通过；对 7 个产品 Python 文件调用仓库 `scan_complexity_entries`、`scan_oversize_entries`、`scan_silent_fallback_entries`，结果分别为 `[]`、`[]`、`[]`。本轮文件无行尾空白。以上属于定点扫描，未将扫描器脱离其目标文件集合产生的装配清单当作整仓门禁结论。

## 覆盖矩阵

| 场景 | 实测证据 |
| --- | --- |
| 无正式历史且无 Schedule 的明确空基线 | `test_run_candidate_adoption.py`，生成 version=1 和新 official 身份 |
| 空历史仍残存 Schedule | `test_run_candidate_adoption_boundaries.py`，empty_baseline_inconsistent，blocked |
| 最大版本实际是模拟记录或当前摘要为损坏 BLOB | 现有执行领域不能确认可执行正式身份，baseline_not_current_official，blocked；旧行不修改 |
| 旧 BLOB、NULL、INTEGER、REAL、TEXT 及全部旧行保留 | `test_run_candidate_adoption.py`，旧历史 BLOB、日志 BLOB、额外旧表逐值/类型比较 |
| 数据库分配版本、跨跳号与真实 refs | 已有历史 7/序列 40，采用得到 41，旧官方/任务引用不旋转 |
| 新报工及旧事件留存 | 两种真实执行来源都保留旧计划/任务依据；新正式安排保持已完工实际时间/资源 |
| 资源、人员、日历、配置、输入、锁、执行及 baseline 漂移 | 边界测试均 409，数据库未发生采用变化 |
| 仅 completed 不算合法 | 破坏原始结果/验证 payload/明细；另同步改变多层数据制造日历、工时、资源和前后序非法，均不签发 token |
| 完整 scope | 漏掉未选中的最后正式安排时 blocked，不悄悄丢批次或补入旧 pending |
| 分件、微秒精度、部分排完、损坏/缺行/缺验证记录 | 明确 blocked，不裁剪、不取整、不改查最新候选 |
| WriteContext 绑定 | 无 token/跨候选 token 均拒绝；只读 preview 才获得授权 |
| 幂等与并发 | 双 SQLite 连接同时采用，只有一次版本/审计/receipt；同键异内容拒绝；新键也不能重复采用同一旧基线候选 |
| 运行与 SQLite 锁 | 已有 worker 锁立即拒绝；guard 阶段另一连接实际 UPDATE 被 SQLite 锁拒绝 |
| 事务 rollback | Schedule 第二行、History、OperationLogs、CommandReceipts 四处 SQLite trigger 注入失败，全表回到原状态 |
| COMMIT/ACK | 真实 sqlite Connection 分别在 COMMIT 前失败、COMMIT 后丢 ACK；只有后者存在原 receipt，不重做 |
| HTTP ACK 查询 | 返回 committed=unknown 和原 request_key/result_target，GET 原 receipt 得到真实成功 |
| 自动派工、跨日历时长、外协周期、固定种子 | 真实引擎及当前资源/日历 helper 验证并采用；主数据原 NULL 资源仍保留 |
| 上游未完工执行保护 | 真实预检返回 execution_review_required，本轮不绕过 |

## 待主线完成

1. 调用独立 `register_run_candidate_adoption_routes(bp)`，联调新的 POST 预览/确认 DTO 和已有通用 receipt GET。具体挂点与 JSON 见 implementation 文档。
2. 将 BX 的 5 个快速测试文件、1 个容量测试文件纳入合适的 registry 路由；`test_run_candidate_adoption_support.py` 仅为专属支持文件，不充当核心 mock。
3. 联合验证候选 UI、runtime、维护入口、离线 build 后，才决定启用新配置及 GET adopt capability；本轮没有代开。
4. 子范围候选补全、分件及微秒无损正式存储仍不支持；未完成的实际生产按上游执行复核规则保持 blocked。ready_date 与候选时间矛盾也不会因关闭齐套检查而被默许。
5. 整仓 `scripts/run_quality_gate.py` 未跑：多人并行修改的 dirty worktree，最终 registry/build/main 接入属于主线独占。本轮不声称 clean-worktree proof，也未实机运行 Win7/Python 3.8；Python 3.8 结论仅是语法解析检查。

## 文件所有权

- 产品：`core/models/workbench_run_adoption.py`，`core/services/workbench/run_candidate_adoption*.py`，`web/routes/workbench/run_candidate_adoption.py`。
- 测试：`tests/workbench/test_run_candidate_adoption*.py`。
- 文档：本目录三个文件。
- 以上当前都是 BX 新增未跟踪文件；既有 staged/unstaged/untracked 内容保持原样，本轮未做任何 Git 暂存或提交动作。
