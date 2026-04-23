<!-- LIMCODE_SOURCE_ARTIFACT_START -->
{"type":"review","path":".limcode/review/20260407_aps_startup_chrome_launch_review.md","contentHash":"sha256:afa9a8e99437ca32a877a33ca55e8ec7ac242bc07cfeccb73b9597959833b70e"}
<!-- LIMCODE_SOURCE_ARTIFACT_END -->

## TODO LIST

<!-- LIMCODE_TODO_LIST_START -->
- [x] 收紧启动器浏览器判活：只认当前 profile 的 APS 专用浏览器进程  `#p1`
- [x] 收紧浏览器运行时卸载 stop helper：覆盖跨账户 APS 标准 profile 场景  `#p2`
- [ ] 补齐自动回归与现场验收证据：自动守卫/回归已完成，真实机器普通 Chrome 共存与双账户卸载验收待在现场补做  `#p3`
- [x] 必要时补 Python 侧注释或最小条件约束，防止三端语义再次漂移  `#p4`
<!-- LIMCODE_TODO_LIST_END -->

# APS启动链路与Chrome残余问题修复 实施 plan

> **执行方式**：优先使用 `subagent-driven-development`；如果当前环境不适合子代理或用户要求当前会话直接执行，则使用 `executing-plans`。

**目标**：收口当前未提交改动里仍残留的两类假成功：一是启动器在浏览器拉起后把“系统里任意 `chrome.exe` 仍存活”误判为 APS 专用浏览器已拉起；二是浏览器运行时卸载器只按当前卸载账户的 profile 路径匹配进程，导致跨账户场景下可能误判“已关闭 APS Chrome”。

**总体做法**：先用定向失败用例把两个残留问题锁死；然后分别收紧 `assets/启动_排产系统_Chrome.bat` 与 `installer/aps_win7_chrome.iss` 的进程匹配条件，统一到“只认 APS 专用 `--user-data-dir` 命令行”这一条语义；最后补齐自动回归、双账户现场验收与文档口径，确保启动、停机、卸载三条链路不再出现假成功。

**涉及技术 / 模块**：`assets/启动_排产系统_Chrome.bat`、`installer/aps_win7_chrome.iss`、`web/bootstrap/launcher.py`、`tests/test_win7_launcher_runtime_paths.py`、`tests/regression_runtime_stop_cli.py`、`tests/regression_shared_runtime_state.py`、`tests/regression_runtime_contract_launcher.py`、`installer/README_WIN7_INSTALLER.md`、`DELIVERY_WIN7.md`。

---

## 变更边界与文件职责

- `assets/启动_排产系统_Chrome.bat`
  - 正式快捷方式入口。
  - 负责复用现有实例、启动后端、等待就绪、拉起 APS 专用浏览器。
  - 本次只收紧“浏览器拉起后的成功判定”，不改共享数据根、运行时契约、锁判定主流程。
- `installer/aps_win7_chrome.iss`
  - 独立浏览器运行时包卸载逻辑。
  - 本次只收紧“卸载前关闭 APS Chrome”的匹配口径，不改安装目录、注册表、卸载提示交互。
- `web/bootstrap/launcher.py`
  - 作为 Python 侧停机链路的对照实现。
  - 本次原则上不扩散改动；仅在需要统一日志或注释口径时做最小联动。
- `tests/test_win7_launcher_runtime_paths.py`
  - 负责启动器 / 安装器静态守卫与少量定向行为守卫。
  - 本次要把“只认 APS 专用 profile 命令行”与“不能按任意 `chrome.exe` 判活”固化下来。
- `tests/regression_runtime_stop_cli.py`
  - 保证 `--runtime-stop --stop-aps-chrome` 主链路不被破坏。
- `tests/regression_shared_runtime_state.py`
  - 保证共享状态目录、运行时锁、契约镜像不被破坏。
- `tests/regression_runtime_contract_launcher.py`
  - 保证运行时契约字段与启动链路口径不被破坏。
- `installer/README_WIN7_INSTALLER.md` / `DELIVERY_WIN7.md`
  - 对外说明与现场排障口径。
  - 本次必须同步写清“成功判定更严格”和“卸载会尝试关闭任意账户下使用 APS 标准 profile 的 APS Chrome，但不会删除任何账户 profile”。

---

### 任务 1：把启动器浏览器判活从“任意 Chrome 存活”收紧为“APS 专用 profile 存活”

**目标**
- 让 `assets/启动_排产系统_Chrome.bat` 在 `OPEN_CHROME` 后只把“命令行中明确带当前 `CHROME_PROFILE_DIR` 的 APS 专用浏览器进程”视为成功。
- 消除“系统里本来就开着普通 Chrome，APS Chrome 实际瞬退，但脚本仍返回成功”的假成功路径。

**文件**
- 修改：`assets/启动_排产系统_Chrome.bat`
- 测试：`tests/test_win7_launcher_runtime_paths.py`
- 对照：`web/bootstrap/launcher.py`

- [ ] **步骤 1：先补失败用例，锁定当前误判路径**

在 `tests/test_win7_launcher_runtime_paths.py` 新增或拆分一条专门守卫，名称固定为：

```python
def test_launcher_bat_chrome_alive_probe_scopes_to_profile_specific_process():
    text = (Path(_repo_root()) / "assets" / "启动_排产系统_Chrome.bat").read_text(encoding="utf-8")
    assert "--user-data-dir" in text
    assert "CHROME_PROFILE_DIR" in text
    assert "Get-CimInstance Win32_Process" in text or "Get-WmiObject Win32_Process" in text
    assert 'tasklist /FI "IMAGENAME eq chrome.exe" /NH /FO CSV' not in text
    assert 'findstr /I /C:"\\"chrome.exe\\""' not in text
```

要求：
- 这条用例只关注浏览器判活子程序，不与健康检查、锁检查、owner 归一化断言混在一起。
- 保留现有 `test_launcher_bat_contains_json_health_probe_and_owner_fallback`，但把浏览器判活相关断言迁到新用例中，避免一个测试承担太多职责。

- [ ] **步骤 2：运行用例，确认失败原因正确**

运行：`python -m pytest tests/test_win7_launcher_runtime_paths.py -q`

预期：
- 新增用例失败。
- 失败点明确指向批处理里仍残留 `tasklist /FI "IMAGENAME eq chrome.exe"` 这一类宽匹配判活逻辑，而不是测试文件本身有语法问题。

- [ ] **步骤 3：写最小实现，替换宽匹配判活逻辑**

修改 `assets/启动_排产系统_Chrome.bat`：

1. 删除现有 `:probe_chrome_alive` 中“枚举所有 `chrome.exe`，只要有任意一条就算成功”的逻辑。
2. 新增一个只用于 APS 专用浏览器判活的子程序，名称固定为：` :probe_aps_chrome_alive `。
3. 在该子程序里：
   - 只有 `HAS_POWERSHELL` 存在时才执行严格判活；不再回退到按镜像名的 `tasklist` 宽匹配。
   - 使用 `Get-CimInstance Win32_Process`，若不可用再降级 `Get-WmiObject Win32_Process`。
   - 只接受同时满足以下条件的 `chrome.exe` 进程：
     1. `CommandLine` 非空；
     2. 命令行中包含 `--user-data-dir`；
     3. 命令行中包含当前 `CHROME_PROFILE_DIR` 的归一化值。
4. 若没有 `HAS_POWERSHELL`，要明确写日志，例如：`chrome_alive_probe=no_powershell`，并让调用方按失败处理；不要再无声降级到“任意 `chrome.exe` 存活就算成功”。
5. `:OPEN_CHROME` 中把 `call :probe_chrome_alive` 改为 `call :probe_aps_chrome_alive`，失败提示要改成“未能确认 APS 专用浏览器已拉起”，而不是泛泛地说“Chrome did not stay alive”。
6. 不改 `chrome_cmd` 生成方式，不改 `CHROME_PROFILE_DIR` 默认值，不改 `start "" /D "%CHROME_RUN_DIR%" "%CHROME_EXE%" ...` 这一行的参数协议。

- [ ] **步骤 4：重新运行定向验证**

运行：`python -m pytest tests/test_win7_launcher_runtime_paths.py -q`

预期：
- 新增的 profile 定向判活守卫通过。
- 现有关于 `owner` 归一化、`tasklist /FI "PID eq !LOCK_PID!"`、`port_file_invalid`、`chrome_profile_probe` 的断言继续通过。

- [ ] **步骤 5：运行受影响回归**

运行：
- `python tests/regression_runtime_contract_launcher.py`
- `python tests/regression_shared_runtime_state.py`

预期：
- 两条命令都输出 `OK`。
- `aps_runtime.json` 中的 `chrome_profile_dir`、`owner`、`host`、`port` 字段口径不变。

- [ ] **步骤 6：收尾确认**

人工核对以下结果：
- 批处理中不再出现“只按 `chrome.exe` 镜像名判活”的成功分支。
- `chrome_alive_probe` 日志值能区分：查询失败、未找到 profile 定向进程、确认找到 APS 专用浏览器。
- 现有普通 Chrome 已打开时，仍不会仅因普通 Chrome 存在就把 APS 启动判成成功。

---

### 任务 2：把浏览器运行时卸载器从“当前账户路径匹配”收紧为“任意账户 APS 标准 profile 命令行匹配”

**目标**
- 让 `installer/aps_win7_chrome.iss` 在卸载前关闭 APS Chrome 时，不再只按当前卸载账户的 `%LOCALAPPDATA%\APS\Chrome109Profile` 绝对路径匹配。
- 让管理员或其他账户发起卸载时，也能正确识别并关闭“命令行使用 APS 标准 profile 目录”的 APS Chrome 进程；若无法确认，则失败闭合。

**文件**
- 修改：`installer/aps_win7_chrome.iss`
- 测试：`tests/test_win7_launcher_runtime_paths.py`
- 文档：`installer/README_WIN7_INSTALLER.md`、`DELIVERY_WIN7.md`

- [ ] **步骤 1：先补失败用例，锁定跨账户匹配语义**

在 `tests/test_win7_launcher_runtime_paths.py` 新增一条专门守卫，名称固定为：

```python
def test_chrome_installer_stop_helper_matches_profile_argument_not_current_user_only():
    text = (Path(_repo_root()) / "installer" / "aps_win7_chrome.iss").read_text(encoding="utf-8")
    assert "--user-data-dir" in text
    assert "\\aps\\chrome109profile" in text.lower()
    assert "$marker=''chrome109profile''" not in text
```

同时保留现有 `test_chrome_installer_stop_helper_uses_current_user_profile_path_marker`，但把它改成只验证：
- `CurrentUserChromeProfilePath` 仍保留给卸载提示文案使用；
- stop helper 本身不再只依赖当前账户绝对路径作为唯一匹配条件。

- [ ] **步骤 2：运行用例，确认失败原因正确**

运行：`python -m pytest tests/test_win7_launcher_runtime_paths.py -q`

预期：
- 新增用例失败。
- 失败内容表明当前 `installer/aps_win7_chrome.iss` 仍然只把当前账户路径写入匹配 marker，而不是按 `--user-data-dir` + APS 标准 profile 后缀识别任意账户。

- [ ] **步骤 3：写最小实现，改成跨账户 APS profile 匹配**

修改 `installer/aps_win7_chrome.iss`：

1. 保留 `CurrentUserChromeProfilePath()`，但它只用于：
   - 卸载提示文案；
   - 如需要时的日志补充；
   - 不再作为 stop helper 的唯一匹配依据。
2. 新增一个返回 APS 标准 profile 后缀的 helper，名称固定为：`ApsChromeProfileSuffixMarker()`；返回值固定为小写的 `\aps\chrome109profile`。
3. 把 `BuildStopChromePowerShellParams` 改成同时接收：
   - 当前账户 profile 绝对路径（用于日志和精确路径兼容）；
   - APS 标准 profile 后缀 marker（用于跨账户匹配）。
4. 生成的 PowerShell 匹配条件必须同时满足：
   - `CommandLine` 非空；
   - 包含 `--user-data-dir`；
   - 命令行中包含 APS 标准 profile 后缀 marker；
   - 如果当前账户绝对路径也命中，可以继续视为目标，但不能只有“当前账户路径”这一种判法。
5. 停止后重新按同一套条件复查；只要仍存在任何目标进程，就 `exit 1`，保持 silent uninstall 失败闭合语义。
6. 不改 `InitializeUninstall()` 的交互分支，不改“不会自动删除任何账户 profile 目录”的边界。

- [ ] **步骤 4：重新运行定向验证**

运行：`python -m pytest tests/test_win7_launcher_runtime_paths.py -q`

预期：
- 新增跨账户匹配守卫通过。
- 现有关于 `powershell.exe`、`Get-CimInstance Win32_Process`、`Get-WmiObject Win32_Process`、`Stop-Process -Id $procId -Force` 的断言继续通过。

- [ ] **步骤 5：运行受影响回归**

运行：
- `python tests/regression_runtime_stop_cli.py`
- `python tests/regression_shared_runtime_state.py`

预期：
- 两条命令都输出 `OK`。
- Python 停机链路没有因为安装器语义收紧而被连带改坏。

- [ ] **步骤 6：联动更新文档**

同步修改 `installer/README_WIN7_INSTALLER.md` 与 `DELIVERY_WIN7.md`，把以下口径写清：
- 浏览器运行时卸载时，会尝试关闭“任意账户下使用 APS 标准 profile 目录的 APS Chrome 进程”；
- 卸载器仍然不会自动删除任何账户的 `%LOCALAPPDATA%\APS\Chrome109Profile`；
- 如果无法确认或关闭这类 APS Chrome 进程，silent uninstall 会失败闭合。

---

### 任务 3：补齐能真正约束行为的验证证据，而不只停留在字符串守卫

**目标**
- 让本轮修复不只是“文件里有某段字符串”，而是至少有一组自动回归和一组现场验收能证明关键行为已经改变。
- 明确哪些验证必须人工完成，禁止执行者把“批处理 / 安装器不好测”当作跳过验收的理由。

**文件**
- 测试：`tests/test_win7_launcher_runtime_paths.py`
- 回归：`tests/regression_runtime_stop_cli.py`
- 回归：`tests/regression_shared_runtime_state.py`
- 回归：`tests/regression_runtime_contract_launcher.py`
- 文档：`installer/README_WIN7_INSTALLER.md`、`DELIVERY_WIN7.md`

- [ ] **步骤 1：运行自动守卫与回归全集**

运行：
- `python -m pytest tests/test_win7_launcher_runtime_paths.py -q`
- `python tests/regression_runtime_contract_launcher.py`
- `python tests/regression_shared_runtime_state.py`
- `python tests/regression_runtime_stop_cli.py`

预期：
- 四条命令全部通过。
- 不允许只跑第一条静态守卫就宣布完成。

- [ ] **步骤 2：做场景 A 现场验收——普通 Chrome 共存时不能再误判 APS 已拉起**

在一台真实 Windows 机器上按下面步骤执行：
1. 先手工打开一个普通 Chrome 窗口，确保它不是 APS 快捷方式拉起的窗口。
2. 准备一个会让 APS 专用浏览器启动后立即退出的坏现场，例如临时替换为一份故意缺件的测试运行时目录；不要用“路径不存在”这种会在更前面被挡住的场景。
3. 点击 APS 快捷方式。
4. 观察结果：
   - 脚本必须报告“未能确认 APS 专用浏览器已拉起”或等价错误；
   - 不能因为系统里本来就有普通 Chrome 在运行而直接返回成功；
   - `launcher.log` 中必须能看到新的 `chrome_alive_probe` 失败原因。

- [ ] **步骤 3：做场景 B 现场验收——跨账户卸载不能再误判已关闭**

在一台真实 Windows 机器上按下面步骤执行：
1. 账户 A 先通过 APS 快捷方式打开 APS 专用浏览器窗口。
2. 不关闭账户 A 的 APS Chrome，切换到账户 B 或管理员账户。
3. 从账户 B 发起 `APS_Chrome109_Runtime.exe` 卸载，分别覆盖交互卸载与 silent uninstall 两种方式。
4. 观察结果：
   - 卸载器要么成功关闭账户 A 的 APS Chrome 后继续；
   - 要么明确失败闭合；
   - 绝不能出现“账户 A 的 APS Chrome 还在，但卸载器报告成功关闭”的情况。

- [ ] **步骤 4：把现场验收步骤写回文档**

在 `installer/README_WIN7_INSTALLER.md` 与 `DELIVERY_WIN7.md` 中新增一段“残余问题收口验收”，原样包含：
- 普通 Chrome 共存场景；
- 双账户卸载场景；
- 需要检查的日志键：`chrome_alive_probe`、`chrome_cmd`。

- [ ] **步骤 5：整理证据，准备后续 deep review**

把以下结果整理为后续 review 证据清单：
- `python -m pytest tests/test_win7_launcher_runtime_paths.py -q` 的通过结果；
- 三条运行时回归的 `OK` 输出；
- 场景 A 与场景 B 的现场截图或日志片段；
- 更新后的 `installer/README_WIN7_INSTALLER.md` 与 `DELIVERY_WIN7.md`。

- [ ] **步骤 6：收尾确认**

确认本轮修复完成后，后续 review 只需要回答三件事：
1. 启动器是否还可能把任意普通 Chrome 误判为 APS Chrome；
2. 浏览器运行时卸载是否还会在跨账户场景下假成功；
3. 自动回归与现场验收是否都有证据支撑。

---

### 任务 4：如有必要，补一处 Python 侧注释或日志口径，防止三端语义再次漂移

**目标**
- 保证批处理启动器、安装器 stop helper、Python 停机链路对“APS 专用浏览器”的定义保持同一语义：命令行里带 APS 标准 `--user-data-dir`。
- 只在确有必要时改 Python 文件，不把本轮问题扩散成无关重构。

**文件**
- 可选修改：`web/bootstrap/launcher.py`
- 测试：`tests/test_win7_launcher_runtime_paths.py`
- 回归：`tests/regression_runtime_stop_cli.py`

- [ ] **步骤 1：先判断是否真的需要改 Python**

检查 `web/bootstrap/launcher.py:_list_aps_chrome_pids()` 当前逻辑：
- 如果它已经使用“精确 profile 绝对路径包含判断”，且不会导致本轮两个问题复发，则不改代码，只补注释说明它与批处理 / 安装器的关系。
- 只有在你发现它会把非 APS 场景误纳入时，才允许继续改实现。

- [ ] **步骤 2：若只补注释，则写最小注释**

在 `web/bootstrap/launcher.py:_list_aps_chrome_pids()` 附近补一段短注释，写清：
- Python 侧停机链路使用精确 profile 路径；
- 批处理启动器与安装器因上下文限制，一个按当前 profile 精确路径确认、一个按 APS 标准 profile 后缀确认；
- 三者共同目标都是“只认 APS 专用 `--user-data-dir` 命令行”。

- [ ] **步骤 3：若确需改实现，则只加一道 `--user-data-dir` 条件**

只有在步骤 1 证明必须改代码时，才允许修改 `_list_aps_chrome_pids()`：
- 在现有“命令行包含 `target_profile`”基础上，再增加“命令行包含 `--user-data-dir`”；
- 不改返回值协议：成功仍返回 `list[int]`，查询失败仍返回 `None`；
- 不改 `stop_aps_chrome_processes()` 与 `stop_runtime_from_dir()` 的失败闭合语义。

- [ ] **步骤 4：运行定向验证**

运行：
- `python -m pytest tests/test_win7_launcher_runtime_paths.py -q`
- `python tests/regression_runtime_stop_cli.py`

预期：
- 若只补注释，两条命令仍全部通过；
- 若补了实现条件，现有“查询失败返回 `None` → 调用方失败闭合”的行为不能改变。

- [ ] **步骤 5：避免无关扩散**

明确禁止：
- 不修改 `default_chrome_profile_dir()` 的返回协议；
- 不修改 `stop_runtime_from_dir()` 的参数协议；
- 不把本轮问题扩展成新的共用抽象层或大规模重构。

- [ ] **步骤 6：收尾确认**

最终确认三端口径一致：
- 启动器：只把当前 `CHROME_PROFILE_DIR` 的 APS 专用浏览器视为拉起成功；
- 安装器：关闭任意账户下使用 APS 标准 profile 的 APS Chrome；
- Python：停机时只关闭目标 profile 对应的 APS Chrome，且查询失败闭合。

---

## 建议执行顺序

1. 先做任务 1，优先消掉启动器的高风险假成功。
2. 再做任务 2，收口跨账户卸载假成功。
3. 之后做任务 3，把自动回归与现场验收补齐。
4. 最后做任务 4，只在确有必要时补 Python 侧注释或最小条件约束。

## 完成标准

同时满足以下条件，才算本次修复完成：
1. `assets/启动_排产系统_Chrome.bat` 不再通过“任意 `chrome.exe` 存活”判定 APS 启动成功。
2. `installer/aps_win7_chrome.iss` 不再只按当前卸载账户路径匹配 APS Chrome 进程。
3. `tests/test_win7_launcher_runtime_paths.py`、`tests/regression_runtime_contract_launcher.py`、`tests/regression_shared_runtime_state.py`、`tests/regression_runtime_stop_cli.py` 全部通过。
4. 已完成“普通 Chrome 共存”与“双账户卸载”两组真实机器验收。
5. `installer/README_WIN7_INSTALLER.md` 与 `DELIVERY_WIN7.md` 已同步到新的成功判定与卸载语义。
