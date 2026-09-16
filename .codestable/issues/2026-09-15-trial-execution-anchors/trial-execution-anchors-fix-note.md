---
doc_type: issue
slug: trial-execution-anchors
status: fixed
created: 2026-09-15
last_reviewed: 2026-09-15
related_roadmap: workbench-manual-remediation
validation_status: targeted-passed-manual-recheck-pending
---

# 新试调按实际执行固定已开工工序

## 现场与根因

5005 手动验收在补齐四批齐套并重新建立快照后，保存的 74 道场景 `0b859d2d98cadb19835f3d9e17edd49ebc43b9af0755cd57` 仍不能采用，底层为 `protected_seed_changed`，首个工序 id=65。

该工序属于 `CALIB-0915-01`：原正式 v15 计划为 10:57–11:06，已确认实际报工为 14:00–14:15。旧试调创建只复制原计划时间，并因有报工而禁止手工修改；采用输入却正确按真实开完工时间构造保护种子。于是用户无法把这道锁定工序改到可采用状态，草稿检查与采用校验不一致。其余四道 CALIB 首工序同样存在实际与计划时间差。

## 修改

- 新增 `core/services/workbench/trial_execution_anchors.py`，直接复用 `build_execution_guardrails_from_projections` 的执行保护种子。完成工序使用实际开完工时间和实际资源；已支持的已开工工序固定实际开工及资源，预计完工仍按原计划时长计算。没有另写一套时间估算或报工汇总。
- `trial_base.py` 在新草稿创建时将当前任务安排设为已验证执行固定时段。私有 `original.execution_anchor` 保存固定依据；原 `original.arrangement`、原来源行、原任务身份及原正式基准全部保留，用于原计划对比。
- `trial_validation.py` 每次检查都复用同一执行种子构造器，与当前事实核对固定安排。旧保存场景若仍是过时计划时间，显示 `scenario_execution_anchor_outdated` 并要求从当前正式计划重建，既不改旧快照，也不在采用时悄悄替换任务。
- `trial_projection.py` 返回可选的公开 `execution_anchor`。`TrialDetails.jsx` 显示固定原因；甘特与当前起止字段展示真实固定时间，原起止字段继续显示原正式安排。`TrialContract.js` 验证固定依据、当前安排一致性及不可编辑状态。
- 既有 `protected_seed_changed`、最终执行持久化保护、实际资源边界、完整范围及齐套规则保持不变。未知执行证据明确形成阻断原因，不按原计划猜成实际报工。

## 定向验证

四组测试文件互不重叠，共 **132 项专项通过**：

| 范围 | 结果 |
| --- | --- |
| `test_trial_adoption.py`、`test_trial_adoption_validation.py`、`test_trial_adoption_raw.py`、`test_trial_adoption_api.py` | 45 passed in 10.20s |
| `test_trial_validation.py`、`test_trial_lifecycle.py`、`test_trial_edges.py`、`test_trial_atomic.py`、`test_trial_api_schema.py`、`test_trial_predecessor_labels.py` | 48 passed in 9.58s |
| `test_trial_adoption_boundaries.py`、`test_trial_adoption_atomic.py`、`test_point_adoption_host.py` | 31 passed in 9.79s |
| 新增 `test_trial_adoption_execution_anchors.py` | 8 passed |

新增测试使用真实临时 SQLite、报工命令、试调命令和 HTTP 采用路由，证明：

- 两道工序完整闭环：首序实际时间、实际 M2/O2 与原计划 M1/O1 不同，新建正确固定首序；调整后序、保存并正式采用成功。
- 五批完成首序及其后序，再加三条待排工序链，共 16 道工序：6 次真实调整后保存，HTTP 预检和采用成功；新正式行逐行等于保存场景，五份报工、旧正式计划、事件记录及 SQLite 原始类型保留。
- 已开工独立批次固定在实际 09:00，预计完工为原计划三小时后的 12:00，可与其它待排批次一起采用。
- 已开工同链后序仍遵守原有 `predecessor_excluded` 规则：没有可信完工信息时不将预计完工伪装成实际释放，不为通过测试放松此约束。
- 手动更改执行固定任务、旧保存场景使用过时安排、私有固定依据被改、报工随后变化均被拒绝；旧场景保留原样。
- 真实 create/save DTO 通过项目 `PointContract/TrialContract` Node 解析，并拒绝 6 种固定依据伪改。既有前序组件源码编译回归通过。

定向 `git diff --check` 与 Python 3.8 编译检查通过。曾将不存在的额外测试路径带入一次命令，该次没有执行测试；随后只运行上述真实存在的专项文件，结果如表。

## 现场只读验证与手动后续

对实际 5005 数据库使用 URI `mode=ro` 和正式 DATE 转换选项，仅准备新草稿输入，得到五道实际固定时段：14:00–14:15、14:15–14:30、14:30–14:45、14:45–15:00、15:00–15:15；原计划 10:57–11:42 仍保留。连接 `total_changes=0`。

旧场景只读采用复核明确返回五道 `scenario_execution_anchor_outdated`，不再等到统一 payload 校验才报泛化错误。新草稿检查也现在正确揭示五道后序早于实际完工的问题，手动验收需将这些后序安排在各自真实完工之后，并处理 B01 三道工序与实际占用的冲突。

产品与测试已冻结。主代理负责构建、加载最终版本并从当前正式计划新建一次试调完成浏览器验收；本代理没有重启服务、没有操作浏览器、没有写入现场业务数据。

按用户要求未运行全门禁或整仓测试。保留已有未提交修改，不提交、不清理其他文件，上述为专项证据而非 clean-worktree proof。
