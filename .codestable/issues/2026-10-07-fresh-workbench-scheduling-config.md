# 全新用户首次排产缺少默认策略

2026-10-07 的 Win7 SP1 冻结包实机验收发现：源代码 `269346407c0a47fd7b4c40747085cdf0becc4635` 在独立运行目录与空 `user-data` 下，通过公开资源、工艺、批次接口建立可排产工序后，预检成功、排产受理成功，真实 worker 却返回 `candidate_input_invalid`、`缺少“排产策略”配置`。首次排产参数显式包含 `hold_window: null`，没有省略必要业务参数。

原始证据：`output/win7-latest-20261007/suite-business-1791369962.json` 及同目录 `exchange/rpc-in`、`exchange/rpc-out`；这些本地验收材料未提交。

`schema.sql` 只建立 `ScheduleConfig` 表，没有写入配置种子。旧配置读取会懒初始化空表，新工作台的 `run/input_config.py` 则直接严格读取配置，且候选计算要求只读，不能在 worker 中补写配置。因此这是首次使用路径的产品缺陷。

修复将空配置初始化放到 `factory.create_app_core` 的数据库结构检查之后、请求与运行时启动之前。`web/bootstrap/schedule_config.py` 在一个 `BEGIN IMMEDIATE` 事务中调用 `ConfigService.ensure_defaults_if_pristine()`，将默认字段、内置方案和来源记录一起提交。已有非空配置的值、缺项和来源记录保持原样，后续仍按严格规则验证。预检、候选计算和配置快照读取没有引入写入。

Python 3.8 定向验证：

- `tests/config/test_schedule_config_startup.py` 与 `test_config_field_spec_contract.py`：6 项通过。覆盖全新应用不打开旧配置页直接执行真实 worker、候选任务持久化、重启不改配置、历史缺项或坏值不修复、初始化中途失败全部回滚。
- `test_config_snapshot_strict_numeric.py`、`test_run_compute_integration.py`、`test_run_runtime.py`、`test_preflight_api.py`：10 项通过。验证严格数值校验、真实日历/资源计算、后台线程和公开预检协议。
- 相关产品与新增回归文件的 Ruff、`git diff --check` 通过。

本记录只确认源码与主机 Python 3.8 回归；修改后的 Win7 冻结包复测由本轮实机验收记录另行记录，不以修复前失败证据宣称修复后实机通过。
