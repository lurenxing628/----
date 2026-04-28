---
doc_type: feature-acceptance
feature: 2026-04-28-runtime-launcher-stop-contract
status: accepted
roadmap: p1-scheduler-debt-cleanup
roadmap_item: runtime-launcher-stop-contract
accepted_at: 2026-04-28
---

# runtime launcher stop contract 验收

## 1. 验收结论

M7-A 已完成。`web/bootstrap/launcher.py` 已从 1204 行降到 177 行，保留公开门面；具体实现下沉到 `launcher_network.py`、`launcher_paths.py`、`launcher_processes.py`、`launcher_contracts.py` 和 `launcher_stop.py`。

Chrome 停止链路已改成按最终复查判断：旧 pid 关闭过程中如果已经被连带带走，不再误报失败；如果最终仍能查到同 profile 的 Chrome 进程，则继续失败。

## 2. 改动范围

- `web/bootstrap/launcher.py`：保留公开函数、测试兼容转调和旧私有探针别名。
- `web/bootstrap/launcher_*.py`：分别承接端口、路径、进程、合同/锁、runtime stop/Chrome stop。
- `installer/aps_win7_chrome.iss`：Chrome 独立卸载辅助脚本改为记录失败 pid 后做最终复查。
- `tests/test_win7_launcher_runtime_paths.py`：补 Chrome stop 红灯测试、CLI 参数测试和门面公开入口测试。
- `tools/quality_gate_shared.py`、`开发文档/技术债务治理台账.md`：更新启动链样本点、台账和 accepted risk 引用。

## 3. 债务口径

- P1-20：`oversize:web-bootstrap-launcher` 已关闭，启动链超长登记从 9 降到 8。
- P1-21：`_classify_runtime_state` 复杂度登记已关闭。
- P1-22：`_list_aps_chrome_pids`、`stop_runtime_from_dir` 复杂度登记已关闭；同批处理了 `acquire_runtime_lock` 这个 launcher 复杂度兄弟项。
- 本轮不声明 full-test-debt 减少，active xfail 仍为 5。

## 4. 已运行验证

- `tests/test_win7_launcher_runtime_paths.py`：32 passed。
- `tests/regression_runtime_contract_launcher.py tests/regression_shared_runtime_state.py tests/regression_runtime_lock_reloader_parent_skip.py tests/regression_runtime_stop_cli.py`：4 passed。
- `tests/test_architecture_fitness.py` 启动链相关 5 项：5 passed。
- `scripts/sync_debt_ledger.py check`：通过，`complexity_count=32`，`oversize_count=8`，`silent_fallback_count=154`。

## 5. 复审结果

- 兜底审查未发现新增失败默认成功、静默吞错或新 fallback；Chrome stop 仍按 APS 专用 profile 最终复查。
- 启动入口审查确认 `entrypoint.py`、`app.py`、`scripts/run_quality_gate.py`、安装包和 `--runtime-stop / --stop-aps-chrome` 返回码合同保持一致。
- 台账审查发现 accepted risk 说明仍有乱码，已修成中文说明，并重新通过 `scripts/sync_debt_ledger.py check`。
