# Gate07完整测试夹具修复

2026-10-14，主对话亲读六条原始longrepr、四份测试、共同采用来源／归档原内容／计划身份／前端构建依赖后确定。第七轮共收集758节点，716通过、36跳过、6个call失败、收集错误0；前15步通过，第16步失败，第17步未执行。失败原件保留于 `evidence/decision-integration-acceptance/2026-10-14/full-gate/attempt07-v4/`，诊断见同目录外 `type-repair/full-pytest-attempt07-diagnosis.json`。

本批仅修改以下四份测试。产品现行身份、原内容校验及前端挂载链保持；测试数量、参数化范围、所有业务断言和原始数据保全断言保持。不恢复哈希校验、不增加产品兜底、不把失败登记为新债务、不放宽门禁。

## 1. 同请求采用来源隔离与新请求重新核对

文件：`tests/workbench/test_adoption_source_read_reuse.py`。

### 调用方历史错绑

`test_caller_version_and_history_cannot_reuse_another_adoption` 第一个wrong version拒绝已经通过。第二个故障当前向content_refs_v1凭据额外添加candidate_hash，未破坏现行身份，因此未触发拒绝。

只把该故障注入替换为：

```python
audit["proof"]["run_ref"] = first["source_run_ref"]
```

顶层audit.run_ref仍为second，其他历史内容保持。两次采用有不同真实run身份，`facts/adoption_baseline_sources.py::_candidate_source`仍对proof.run_ref与实际第二次来源逐值比较。保留两个raises以及最后数据库快照不变断言；read_evidence_scope与当前缓存键不改。

### capture真实内容漂移

`test_new_request_rechecks_broken_source_and_rejects_old_snapshot` 的capture分支当前只改facts_hash；新来源直接读取保存原文，旧摘要为历史值，不再承担校验。该分支应精准修改第二次采用的baseline_json原内容：

```python
mutate_json(case.conn, "WorkbenchRunJobs", "baseline_json",
            lambda value: value["rows"][0].update(end_time="2026-09-09T15:59:00"),
            "run_ref=?", (second["source_run_ref"],))
```

第二次采用已拥有第一次的非空正式基准；现有 `ArchivedAdmissionPlan._check_baseline_rows` 会将这个基准原文与同次facts_text内的Schedule逐项比较，真实错配应被识别。使用已有mutate_json／corrupt_update故障工具；不以ORDER BY最新作业猜目标，不改facts_hash。其余receipt、arrangement分支保持。保留quantity=None、plan_target_unavailable、baseline unavailable、旧snapshot_ref返回409/snapshot_stale及读取不写库的全部断言。

## 2. 外协供应商来源与冻结历史

文件：`tests/workbench/test_run_candidate_api.py`。

`test_adopted_external_supplier_uses_original_lineage_and_null_resources_are_known` 的candidate分支，把原 `audit["proof"]["candidate_hash"] = ...` 一行替换为：

```python
audit["proof"]["candidate_ref"] = changed
```

changed是同用例已生成的另一真实candidate；顶层audit.candidate_ref仍为原采用来源。`adoption_baseline_sources._candidate_source`与`decision_baseline_source._candidate_evidence`分别核对实时正式来源和后续运行保存来源，均会识别这次身份错绑。保留原164／166／170附近三层断言：当前读取出现adoption_snapshot_invalid、已有运行冻结分析保持完全相同、新运行保存该来源缺口。其他候选／试调参数、供应商身份、空设备人员为已知事实和指标断言保持。

## 3. 值班台前端测试加载真实共享契约

文件：`tests/workbench/test_dashboard_source_types.py`。

FRONTEND_LIST中的VM加载列表，在DashboardAnalysisAPI.js前加入 `ResourceProjectionContract.js`，形成与现有dashboard_list_probe.cjs相同的四文件列表：DashboardContract.js、RunCandidateAPI.js、ResourceProjectionContract.js、DashboardAnalysisAPI.js。

生产 `scripts/workbench/build-order.json` 已在43行加载共享契约、265行加载分析API，实际包次序正确。共享契约只依赖自身函数和JS内建能力；测试应加载原实现，不制作假window/window_metrics对象。保留两项analysis_error is None及全部历史source可读、原值保留、资源／停机／执行、物流未知和写入拒绝断言。

## 4. 延期诊断场景绑定真实基础角色

文件：`tests/scheduler_analysis/test_scheduler_delay_diagnosis_contract.py`。

`_seed_candidates`已经为adopted建立真实selection，`_seed_scenario`仍写 `(schedule, None, adopted)`。真实 `_validate_scenario` 要求base_source_table／base_candidate_id／base_candidate_key与该角色绑定完全一致，拒绝这份不完整场景正确。

在 `_seed_scenario` 插入之前，通过现有 `SchedulePlanQueryService(conn).resolve_existing_plan(VERSION, ROLE_ADOPTED)` 取得基础角色（补齐该类的实际导入），用返回对象source_table／candidate_id／candidate_key填入三个base字段。保留原scenario_id、版本、角色、工序和时间。不要使用 `_seed_candidates()` 返回的baseline_best ID冒充adopted；不新增备用ID或修改生产校验。保留只读快照、scenario source、预览权限、16:00完成时间、链接无scenario_id及缺明细报错断言。

## 5. 验证与交接

- 四文件改完先运行原六个失败nodeid，采用上方原诊断JSON的完整名字，不新增测试函数／文件／参数矩阵。若仍失败，保留原longrepr回主对话核对实际契约，不逐次弱化断言。
- 六项通过后继续原完整dirty Gate：`.venv/bin/python scripts/run_quality_gate.py --allow-dirty-worktree --no-resume --no-long-gate-cache`。前15步有效修复继续复用其事实，原完整命令负责全量测试及第17步required核销；全量结果按实际数量记录。
- 本批产品源码与静态包不变，已通过UI、数值、事务、原始导出、迁移、20k读取证据保持。最终正常实例仍按既定要求做一次加载最终模块的同库冷启，由主对话亲自核对身份与受影响读取。
- 旧四轮类型／依赖／文档／台账失败及Gate07全量失败原件全部保留。主对话审查实际diff并维护验收状态，Git与A/B/C顺序保持原授权。

## 6. Gate08校准用例的可修正来源前提

第八轮原六项全部通过，758节点中721通过、36跳过，唯一失败为 `test_calibration_adoption_transactions.py::test_report_revision_change_rejects_preview_with_the_same_recommendation`。主对话亲读该测试、ready_adoption_case／completed、报工require_current和校准_select_recent：ready夹具有5条version2报工，新建16条version3后正式计划只覆盖新16道工序。两组最早记录的confirmed_finish同为10:00，最近20条以sample_ref断平，唯一未入选记录可能落在旧version2；原测试从两组合并列表取它，correct因此在触及校准预览之前被plan_not_writable拒绝。第七轮通过与第八轮失败由该身份排序差异解释。

只改 `tests/workbench/test_calibration_adoption_transactions.py` 此用例的两个前置条件：

1. 从现有 `core.models.workbench_calibration` 导入MAX_SAMPLES；同一completed调用的hours改为 `[3] * (MAX_SAMPLES + 1)`，版本仍3、其余参数保持。当前正式计划由此拥有21条合格样本，校准最多选20条，必有一条当前可修正的未入选样本。
2. `unselected` 只从extra_reports筛选未在selected_reports中的记录，移除 `case.reports +`。用同一ledger.get_report取得最新revision，再沿原case.command实际修正remark。

保留原after可采用、suggestion与before完全相同、confirm旧token抛stale_write、adoptions数量0的全部断言。校准仍比较所有来源revision而不只比较当前推荐；这次真正验证未入选但可修正报工的版本变化。无需更改产品写入条件、样本排序、编号生成或共享fixture helper；不重试到通过、不固定随机值、不新增用例或参数矩阵。

保留attempt08原件，先运行这一原失败node，随后继续原完整dirty Gate。此前原六项及四文件源码复核结果继续有效，当前只有此测试前置变化，无需单独重跑它们或整套UI／性能／导出。
