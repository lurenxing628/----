# 死代码清理 + 架构封装收口 · 结案报告(2026-06-23)

## 来源与方法
体检调用图(`callgraph_extract` 类型感知 attr 消解,确信边 37.3%→46.8%)叠加
**全量运行时交叉验证**(`setprofile` 录 4269 用例真实调用边)交叉锁定:
- 156 个"死代码嫌疑"(全量运行时把孤岛从 590→156,戳穿 224 个假警报)
- 4 条 `web→data` 跨层可疑边

执行链:6 个并行子代理 triage(按目录隔离、grounded 到 file:line)→ Codex 两轮独立
只读核验(结论核验 + 整 diff 对抗)→ 完整门禁 17/17 实跑全量套件背书。

## 净结果
- **删除 53 个死/半截迁移残留符号**(分 core/web/tooling 三个逻辑提交)
- **修 1 处架构封装泄漏**(web→data,收进 `PartService.build_route_reference_snapshot`)
- **假死拦截**:156 候选中约 102 个其实是活代码(Flask 路由入口、Protocol/抽象、
  动态派发、被测域谓词),子代理全部正确挡下——未盲删

## 三重验证(任一不过都不提交)
1. **子代理 triage**:6 并行,每条结论 grounded 到 file:line + grep 证据
2. **完整门禁 17/17 全绿**:full-test-debt 步实跑全量套件 failed=0;过程中**抓出 1 个
   子代理误判**(`ScheduleConfigSnapshot.to_dict` 假死,契约测试真调用)并修复
3. **Codex 独立对抗**:全新会话纯只读,零 REAL-RISK;架构重构用假 repo 实跑两分支确认逐位等价

## 删除清单(53)

### core 层(提交 5b881f99)
- ConfigService 拆子服务后遗留的 19 个零调用私有委派壳
- BaselineResolution.drifted / to_legacy_dict、ExecutionSnapshot.to_summary
- resource_dispatch.positive_row_op_ids、FreezeState.status、AppLogger.get_logger
- transactional 装饰器、errors.success_response、greedy.downtime.get_resource_available
- value_policies.FieldPolicy.allows_compat_read / has_field_policy

### web 层(提交 51b1c2d6)
- 3 个零调用 to_capability(HealthProbeResult / RuntimeLockReadResult / BindProbeResult)
- launcher_stop._parse_chrome_pid_output 转发壳
- 路由本地 helper:_text / _has_text / _get_int_arg / _safe_float

### tooling/scripts/data 层(提交 561e731f)
- run_quality_gate.py:_long_gate_success_result_rel_path、_parse_args_legacy
- benchmark_full_test_debt_shards.py:_load_nodeids、check_full_test_debt.py:load_current_payload
- long_gate_collect.py:load_collect_nodeids、quality_gate_scan.py:_is_name
- quality_gate_shared.py:iter_non_regression_guard_tests 冗余 wrapper + support 的 re-export
- operation_execution_state_builder.py:_label

## 架构修(提交 08378467)
4 条 web→data 可疑边核查结论:
- 边1 core→web(ExcelService.preview_import←_validate_operator_row):**误报**(依赖注入回调)
- 边2 web→data(bootstrap plugins 读配置):**可接受**(启动期轻量、失败降级)
- 边3&4 web→data(process_excel_routes 直取 op_type_repo/supplier_repo):**唯一真违规**,已收口

## 经核实保留(子代理候选里的活代码,未删)
- config_service._builtin_presets(被测试调用)
- ScheduleConfigSnapshot.to_dict(契约测试 test_..._helpers_stay_in_sync 真调用)——门禁抓出
- 各被调用的同名 to_capability(RuntimeContractReadResult/ProbeHealthResult)、
  launcher_chrome._parse_chrome_pid_output 真实现

## 顺带修复(被触碰文件带入扫描范围而暴露的既存问题)
- logging.py 既存 py38 违规 `tuple[str,str]`→`Tuple[str,str]`
- 债务治理台账受控 refresh-auto-fields 重同步(删死代码挪了静默回退条目行号)
