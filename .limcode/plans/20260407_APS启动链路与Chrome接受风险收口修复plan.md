<!-- LIMCODE_SOURCE_ARTIFACT_START -->
{"type":"review","path":".limcode/review/aps启动链路与chrome拉起修复-三轮深度审查.md","contentHash":"sha256:0d5ffffd51fd3fc95fa24d91221292d9d82147eb49726693725bd46c27283743"}
<!-- LIMCODE_SOURCE_ARTIFACT_END -->

## TODO LIST

<!-- LIMCODE_TODO_LIST_START -->
- [x] 把打包脚本的清理语义显式拆成“严格停止”和“容错清理”  `#task-1`
- [x] 把浏览器运行时卸载器的 marker 收口到当前账户 profile 绝对路径  `#task-2`
- [x] 回归验证并关闭当前 review 中的两条接受风险  `#task-3`
<!-- LIMCODE_TODO_LIST_END -->

# APS启动链路与 Chrome 接受风险收口修复 实施 plan

> **执行方式**：优先使用 `subagent-driven-development`；如果当前环境不适合子代理或用户要求当前会话直接执行，则使用 `executing-plans`。

**目标**：把当前 review 中两条低等级接受风险真正收口：一是让打包脚本的浏览器清理语义显式区分“严格停止”和“容错清理”；二是让浏览器运行时卸载器不再使用裸字串 `chrome109profile`，而是与运行时 profile 路径口径一致。

**总体做法**：先在 `tests/test_win7_launcher_runtime_paths.py` 增加两个定向失败用例，分别锁定 PowerShell 冒烟清理包装层和安装器 stop helper 的 marker 来源；然后只改 `.limcode/skills/aps-package-win7/scripts/package_win7.ps1` 与 `installer/aps_win7_chrome.iss` 两个实现文件，以最小改动完成收口；最后重跑既有启动链路、契约链路与停机链路回归，并基于新证据重新做一次 deep review 收尾。

**涉及技术 / 模块**：`.limcode/skills/aps-package-win7/scripts/package_win7.ps1`、`installer/aps_win7_chrome.iss`、`web/bootstrap/launcher.py`、`tests/test_win7_launcher_runtime_paths.py`、`tests/regression_shared_runtime_state.py`、`tests/regression_runtime_contract_launcher.py`、`tests/regression_runtime_stop_cli.py`、`.limcode/review/aps启动链路与chrome拉起修复-三轮深度审查.md`。

---

### 任务 1：把打包脚本的清理语义显式拆成“严格停止”和“容错清理”

**目标**
- 让 `.limcode/skills/aps-package-win7/scripts/package_win7.ps1` 中的 `finally` 清理不再依赖外层 `catch` 吞异常。
- 保留正式失败路径的严格语义，但把清理路径的 best-effort 语义写成显式 helper。

**文件**
- 修改：`.limcode/skills/aps-package-win7/scripts/package_win7.ps1`
- 测试：`tests/test_win7_launcher_runtime_paths.py`

- [ ] **步骤 1：写失败用例**

```python
def test_package_script_exposes_explicit_best_effort_cleanup_wrapper():
    text = (Path(_repo_root()) / ".limcode" / "skills" / "aps-package-win7" / "scripts" / "package_win7.ps1").read_text(encoding="utf-8")
    assert "function Stop-ProcessTreeByIdsBestEffort" in text
    assert "Stop-ProcessTreeByIdsBestEffort $cleanupChromeIds" in text
    assert "Stop-ProcessTreeByIds $cleanupChromeIds" not in text
```

- [ ] **步骤 2：运行用例，确认失败原因正确**

运行：`python -m pytest tests/test_win7_launcher_runtime_paths.py -q`
预期：新增断言失败，且失败点明确指向缺少 best-effort wrapper，而不是测试文件语法错误。

- [ ] **步骤 3：写最小实现**

修改 `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`：
1. 保留 `Stop-ProcessTreeByIds` 作为严格 helper，不改变其 `taskkill` 非零即 `throw` 的语义。
2. 紧挨其后新增一个显式 wrapper：

```powershell
function Stop-ProcessTreeByIdsBestEffort([int[]]$targetIds) {
    try {
        Stop-ProcessTreeByIds $targetIds
    } catch {
    }
}
```

3. 把 `Invoke-ChromeRuntimeSmoke` 的 `finally` 中这段：

```powershell
if ($cleanupChromeIds.Count -gt 0) {
    Stop-ProcessTreeByIds $cleanupChromeIds
}
```

改成：

```powershell
if ($cleanupChromeIds.Count -gt 0) {
    Stop-ProcessTreeByIdsBestEffort $cleanupChromeIds
}
```

4. 删除 `finally` 外层仅用于吞异常的空 `catch`，或至少让 `catch` 不再包住“严格 helper 直接调用”这一层。
5. 不改 `Invoke-ChromeRuntimeBuild` / `Invoke-LegacyPackageBuild` 的失败阻断语义。

- [ ] **步骤 4：重新运行定向验证**

运行：`python -m pytest tests/test_win7_launcher_runtime_paths.py -q`
预期：新增静态守卫通过，现有 `test_package_script_contains_browser_smoke_for_runtime_and_legacy_paths` 仍通过。

- [ ] **步骤 5：运行受影响回归**

运行：`python tests/regression_runtime_contract_launcher.py`
预期：输出 `OK`。

- [ ] **步骤 6：收尾确认**

确认 `.limcode/skills/aps-package-win7/scripts/package_win7.ps1` 中只剩两种明确语义：
- 严格停止：`Stop-ProcessTreeByIds`
- 容错清理：`Stop-ProcessTreeByIdsBestEffort`

### 任务 2：把浏览器运行时卸载器的 marker 收口到当前账户 profile 绝对路径

**目标**
- 让 `installer/aps_win7_chrome.iss` 不再使用裸字串 `chrome109profile`。
- 让卸载器的 Chrome 进程枚举口径与 Python 侧 `_list_aps_chrome_pids()`、打包脚本 `Get-ChromeIdsByMarker()` 一致，都基于 profile 路径而不是固定子串。

**文件**
- 修改：`installer/aps_win7_chrome.iss`
- 测试：`tests/test_win7_launcher_runtime_paths.py`
- 对照：`web/bootstrap/launcher.py`

- [ ] **步骤 1：写失败用例**

在 `tests/test_win7_launcher_runtime_paths.py` 新增一条静态守卫：

```python
def test_chrome_installer_stop_helper_uses_current_user_profile_path_marker():
    text = (Path(_repo_root()) / "installer" / "aps_win7_chrome.iss").read_text(encoding="utf-8")
    assert "$marker=''chrome109profile''" not in text
    assert "CurrentUserChromeProfilePath" in text
    assert "ExpandConstant('{localappdata}\\APS\\Chrome109Profile')" in text
```

再补一条行为守卫，锁定 Python 侧 profile 来源不变：

```python
def test_default_chrome_profile_dir_prefers_localappdata_profile_name(monkeypatch, tmp_path):
    launcher = _import_launcher()
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\alice\AppData\Local")
    got = launcher.default_chrome_profile_dir(str(tmp_path))
    assert got == os.path.abspath(r"C:\Users\alice\AppData\Local\APS\Chrome109Profile")
```

- [ ] **步骤 2：运行用例，确认失败原因正确**

运行：`python -m pytest tests/test_win7_launcher_runtime_paths.py -q`
预期：新增 installer marker 断言失败，失败内容显示当前实现仍包含 `$marker='chrome109profile'`。

- [ ] **步骤 3：写最小实现**

修改 `installer/aps_win7_chrome.iss`：
1. 新增一个 helper：

```pascal
function CurrentUserChromeProfilePath: String;
begin
  Result := ExpandConstant('{localappdata}\APS\Chrome109Profile');
end;
```

2. 把 `BuildStopChromePowerShellParams` 改成接收 profile 路径参数：

```pascal
function BuildStopChromePowerShellParams(const ChromeProfilePath: String): String;
```

3. 在拼 PowerShell 命令之前，先把 `ChromeProfilePath` 做与 PowerShell 单引号兼容的转义，再把**完整绝对路径**写入 `$marker`；不要再出现 `$marker='chrome109profile'`。
4. `TryStopApsChromeProcesses` 调用改为：

```pascal
Params := BuildStopChromePowerShellParams(CurrentUserChromeProfilePath);
```

5. 保持 `Get-CimInstance -> Get-WmiObject` 降级链不变，保持 silent uninstall 失败闭合语义不变。
6. 不修改 `installer/aps_win7.iss` 与 `installer/aps_win7_legacy.iss`。

- [ ] **步骤 4：重新运行定向验证**

运行：`python -m pytest tests/test_win7_launcher_runtime_paths.py -q`
预期：新增两条守卫通过，现有 `test_installers_fail_closed_on_silent_uninstall_and_retry_delete` 与 `test_chrome_installer_remains_non_target_for_precleanup` 继续通过。

- [ ] **步骤 5：运行受影响回归**

运行：
- `python tests/regression_runtime_stop_cli.py`
- `python tests/regression_shared_runtime_state.py`

预期：两条命令都输出 `OK`，且没有引入 `--runtime-stop` 链路回退。

- [ ] **步骤 6：收尾确认**

人工检查以下口径保持一致：
- `web/bootstrap/launcher.py:default_chrome_profile_dir()` → `%LOCALAPPDATA%\\APS\\Chrome109Profile`
- `assets/启动_排产系统_Chrome.bat` → `%LOCALAPPDATA%\\APS\\Chrome109Profile`
- `installer/aps_win7_chrome.iss` stop helper → 当前账户 profile 绝对路径 marker
- 无 `LOCALAPPDATA` 时，Python / 批处理仍回退到 `chrome109_profile`，本任务不改变该回退协议

### 任务 3：回归验证并关闭当前 review 中的两条接受风险

**目标**
- 用现有基线回归证明这次收口没有破坏启动、契约、停机与浏览器清理主链路。
- 为后续重新做 review 准备一套完整证据。

**文件**
- 测试：`tests/test_win7_launcher_runtime_paths.py`
- 回归：`tests/regression_shared_runtime_state.py`
- 回归：`tests/regression_runtime_contract_launcher.py`
- 回归：`tests/regression_runtime_stop_cli.py`
- review：`.limcode/review/aps启动链路与chrome拉起修复-三轮深度审查.md`

- [ ] **步骤 1：运行启动链路与安装器静态守卫全集**

运行：`python -m pytest tests/test_win7_launcher_runtime_paths.py -q`
预期：全部通过；特别关注新加的两条守卫与现有 silent uninstall / PowerShell / profile 名称断言。

- [ ] **步骤 2：运行运行时共享状态回归**

运行：`python tests/regression_shared_runtime_state.py`
预期：输出 `OK`。

- [ ] **步骤 3：运行运行时契约回归**

运行：`python tests/regression_runtime_contract_launcher.py`
预期：输出 `OK`。

- [ ] **步骤 4：运行停机链路回归**

运行：`python tests/regression_runtime_stop_cli.py`
预期：输出 `OK`。

- [ ] **步骤 5：整理证据并发起新的 deep review**

在实现完成后，基于上述通过结果重新执行 `aps-deep-review`，重点核对：
- `Stop-ProcessTreeByIdsBestEffort` 是否只用于 `finally` 清理
- `installer/aps_win7_chrome.iss` 是否已完全移除 `chrome109profile` 裸 marker
- 三处 Chrome 进程枚举口径是否都以 profile 路径为基准

- [ ] **步骤 6：更新 review 结论**

如果新的 deep review 结论确认两条风险已收口：
- 复用 `.limcode/review/aps启动链路与chrome拉起修复-三轮深度审查.md` 追加里程碑，或新建后续 review
- 将 `ps1-cleanup-throw-in-finally` 与 `cross-lang-chrome-enum-sync` 的跟踪状态改为 `fixed`
- 保留本次回归命令作为证据清单
