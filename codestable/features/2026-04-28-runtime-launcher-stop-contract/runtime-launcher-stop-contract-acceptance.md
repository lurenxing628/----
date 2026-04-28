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

本轮复审后又补了三个收口点：Chrome 进程匹配不再在整条命令行里搜文本，而是先拆成真实参数，只认真正的 `--user-data-dir`；runtime 强杀仍保留给安装/卸载场景，但必须先通过系统进程表确认 pid 的真实可执行文件；Win7 目标脚本不再使用 PowerShell 2.0 不支持的空字符串判断。

对抗复审又补了一次转义引号场景：如果其它参数里包含 `\" --user-data-dir=... \"` 这种文本，也不能被误切成真实参数。legacy 打包删除 `dist` 前也只按旧 `dist\tools\chrome109\chrome.exe` 的真实进程路径做定点清理，不回到全局关闭所有 Chrome。

## 2. 改动范围

- `web/bootstrap/launcher.py`：保留公开函数、测试兼容转调和旧私有探针别名。
- `web/bootstrap/launcher_*.py`：分别承接端口、路径、进程、合同/锁、runtime stop/Chrome stop；pid 身份改用 CIM/WMI 的 `ExecutablePath` 确认，兼顾管理员和域账户停机场景。
- `assets/启动_排产系统_Chrome.bat`：启动后存活探针只认真实 `--user-data-dir` 参数，不再被别的参数里的伪造文本命中。
- `installer/aps_win7_chrome.iss`：Chrome 独立卸载辅助脚本改为记录失败 pid 后做最终复查；profile 判断同步改成真实参数匹配。
- `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`：打包 smoke 只按 APS profile 查 Chrome pid；legacy 打包路径不再全局关闭所有 Chrome。
- `tests/test_win7_launcher_runtime_paths.py`：补 Chrome stop 红灯测试、CLI 参数测试、门面公开入口测试、真实参数匹配测试、PowerShell 2.0 静态守卫和 legacy 全局杀 Chrome 守卫。
- `tools/quality_gate_shared.py`、`开发文档/技术债务治理台账.md`：更新启动链样本点、台账和 accepted risk 引用。

## 3. 债务口径

- P1-20：`oversize:web-bootstrap-launcher` 已关闭，启动链超长登记从 9 降到 8。
- P1-21：`_classify_runtime_state` 复杂度登记已关闭。
- P1-22：`_list_aps_chrome_pids`、`stop_runtime_from_dir` 复杂度登记已关闭；同批处理了 `acquire_runtime_lock` 这个 launcher 复杂度兄弟项。
- 本轮不声明 full-test-debt 减少，active xfail 仍为 5。

## 4. 已运行验证

- `tests/test_win7_launcher_runtime_paths.py`：38 passed。
- `tests/regression_runtime_contract_launcher.py tests/regression_shared_runtime_state.py tests/regression_runtime_lock_reloader_parent_skip.py tests/regression_runtime_stop_cli.py`：4 passed。
- `tests/test_architecture_fitness.py` 启动链相关 5 项：5 passed。
- `scripts/sync_debt_ledger.py check`：通过，`complexity_count=32`，`oversize_count=8`，`silent_fallback_count=154`。
- `tools/check_full_test_debt.py`：通过，active xfail 仍为 5。
- `codestable/tools/validate-yaml.py` 校验 roadmap 与 feature 目录：通过。
- `git diff --check && git diff --cached --check`：通过。

## 5. 复审结果

- 兜底审查未发现新增失败默认成功、静默吞错或新 fallback；Chrome stop 仍按 APS 专用 profile 最终复查，且 profile 判断只认真实参数。
- 启动入口审查确认 `entrypoint.py`、`app.py`、`scripts/run_quality_gate.py`、安装包和 `--runtime-stop / --stop-aps-chrome` 返回码合同保持一致。
- 台账审查发现 accepted risk 说明仍有乱码，已修成中文说明，并重新通过 `scripts/sync_debt_ledger.py check`。
