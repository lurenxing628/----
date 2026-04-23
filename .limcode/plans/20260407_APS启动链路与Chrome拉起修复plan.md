<!-- LIMCODE_SOURCE_ARTIFACT_START -->
{"type":"review","path":".limcode/review/aps启动链路修复plan与代码实现三轮深度审查.md","contentHash":"sha256:5aaeb94b39056075de746e17f618ef2713e3d7390cdc93ab61313e3ea47fd403"}
<!-- LIMCODE_SOURCE_ARTIFACT_END -->

## TODO LIST

<!-- LIMCODE_TODO_LIST_START -->
- [x] 先修复启动器就绪循环中的延迟展开BUG，避免首次启动固定等待  `#p0`
- [x] 收口启动器中的 owner 反转义、tasklist 锁探测、主程序短时存活探测与 profile 可写性校验  `#p1`
- [x] 扩展 Python 运行时链路，替换残留 wmic 并消除浏览器清理静默回退  `#p2`
- [x] 为 package_win7.ps1 增加浏览器运行时最小冒烟，并补齐阻断条件与静态守卫  `#p3`
- [x] 同步修正文档与现场验收清单，明确 validate_dist_exe.py 的边界和新增排障口径  `#p4`
<!-- LIMCODE_TODO_LIST_END -->

# APS启动链路与Chrome拉起修复plan

## 一、修订背景与结论

本 plan 已根据 `.limcode/review/aps启动链路修复plan与代码实现三轮深度审查.md` 的结论重新修订。

经核实，原 plan 的总体方向是正确的，但存在以下必须先修正的缺口：
1. **新增 P0**：`assets/启动_排产系统_Chrome.bat` 的就绪循环存在延迟展开 BUG；首次启动路径会固定等待完整超时。
2. 原 A3 范围过窄；不仅批处理侧 `:lock_is_active`，`web/bootstrap/launcher.py` 中 `_query_process_executable_path` 与 `_list_aps_chrome_pids` 也仍依赖 `wmic`。
3. 原 A4 未说明中文镜像名场景下的可靠策略；直接按镜像名做短时探测存在编码与兼容性风险。
4. 原 A6 方案过度设计；不再采用“PowerShell 主路径 + profile 锁痕迹降级”的复杂双路径。
5. `validate_dist_exe.py` 只覆盖后端冷启动与页面可达，这一点文档已写明；本轮不再重复追加同义文案，而是聚焦正式出包入口与浏览器最小冒烟。

## 二、核实后的实际引用链

### 1. 启动入口链
1. `installer/aps_win7.iss` 的 `[Icons]` 使用 `cmd /c "{app}\启动_排产系统_Chrome.bat"` 作为正式入口。
2. `assets/启动_排产系统_Chrome.bat` 负责：
   - 定位主程序 `APP_EXE`
   - 解析共享数据根并注入 `APS_DB_PATH`、`APS_LOG_DIR`、`APS_BACKUP_DIR`、`APS_EXCEL_TEMPLATE_DIR`
   - 读取/复用 `aps_runtime.lock` 与 `aps_runtime.json`
   - 启动 `排产系统.exe`
   - 轮询 `aps_host.txt`、`aps_port.txt` 与 `/system/health`
   - 拉起 `chrome.exe --app=http://{HOST}:{PORT}/`
3. `app.py -> web/bootstrap/entrypoint.py:app_main()` 负责后端正式启动。
4. `web/bootstrap/factory.py:_apply_runtime_config()` 将数据目录统一落到共享数据根。
5. `web/bootstrap/launcher.py` 负责写入：
   - `aps_runtime.lock`
   - `aps_host.txt` / `aps_port.txt` / `aps_db_path.txt`
   - `aps_runtime.json`
6. `web/routes/system_health.py` 的 `/system/health` 为启动器与验收脚本提供统一健康探测口径。

### 2. 已核实的一致性关系
- `assets/启动_排产系统_Chrome.bat` 中的 `CURRENT_OWNER` 组装逻辑，与 `web/bootstrap/launcher.py:current_runtime_owner()` 的语义一致，都是“域或机器名 + 用户名”。
- `assets/启动_排产系统_Chrome.bat` 中的 `CHROME_PROFILE_DIR` 默认值，与 `web/bootstrap/launcher.py:default_chrome_profile_dir()` 一致，都是 `%LOCALAPPDATA%\APS\Chrome109Profile`；无 `LOCALAPPDATA` 时都回退到运行目录下的 `chrome109_profile`。
- `web/bootstrap/entrypoint.py:configure_runtime_contract()` 会把 `chrome_profile_dir`、`owner`、`exe_path`、`host`、`port` 写入 `aps_runtime.json`；安装器与启动器都依赖这些字段。
- `installer/aps_win7.iss` / `installer/aps_win7_legacy.iss` 已内置 `UnescapeJsonString` 与 `ExtractJsonStringValue`，说明安装器侧已经意识到 JSON 转义问题；批处理侧目前没有等价处理。

### 3. 已核实的实际问题面
1. `assets/启动_排产系统_Chrome.bat:read_runtime_contract` 只做了逗号与引号剥离，**没有把 JSON 中的 `\\` 还原为 `\`**，因此 `CONTRACT_OWNER` 可能与 `CURRENT_OWNER` 比较失败。
2. `assets/启动_排产系统_Chrome.bat:lock_is_active` 仍依赖 `wmic`；而 `web/bootstrap/launcher.py:_pid_exists()` 已改为 `tasklist /FI "PID eq ..." /NH /FO CSV`。
3. `web/bootstrap/launcher.py:_query_process_executable_path` 与 `_list_aps_chrome_pids` 仍直接依赖 `wmic`，其中后者在异常时静默返回空列表，造成浏览器清理假成功。
4. `assets/启动_排产系统_Chrome.bat:OPEN_CHROME` 只判断 `start` 返回码，**没有验证浏览器是否真的拉起并短时存活**。
5. `assets/启动_排产系统_Chrome.bat` 仅 `mkdir` `CHROME_PROFILE_DIR`，**没有验证目录是否可写**。
6. `assets/启动_排产系统_Chrome.bat` 的就绪循环内部使用 `%FILE_HOST%` / `%FILE_PORT%` / `%LAUNCH_ERROR%`，导致首次启动路径的延迟展开失效。
7. `validate_dist_exe.py` 与 `package_win7.ps1` 当前只覆盖“后端冷启动 + 页面可达”，**不覆盖浏览器运行时与快捷方式拉起链路**。

## 三、本轮修复边界

### 必须保持不变的兼容面
- 保持 `aps_runtime.json` 的 `contract_version=1` 不变。
- 保持 `owner`、`host`、`port`、`exe_path`、`chrome_profile_dir` 字段名不变。
- 保持浏览器 profile 目录名 `Chrome109Profile` 不变；安装器卸载文案、浏览器运行时卸载逻辑、文档说明均依赖该名字。
- 不改动安装器 `--runtime-stop` 参数协议。
- 不把浏览器重新并回主程序安装包；继续维持双包交付边界。

### 本轮目标
1. 让“首次启动固定等待 45 秒”和“Chrome 没真正拉起却静默成功”都变为**显式失败且可排障**。
2. 收口 bat / Python / 安装器在 owner 解析、锁活跃判断、浏览器清理上的实现分叉。
3. 把浏览器运行时最小冒烟纳入正式出包阻断条件。
4. 补齐自动化与现场验收，避免同类问题再次直接流入目标机。

## 四、实施方案

### 阶段 P0：先消除首次启动必定超时的直接 BUG

#### P0.1 修复就绪循环延迟展开
**文件**：`assets/启动_排产系统_Chrome.bat`

- 将就绪循环内的：
  - `set "HOST=%FILE_HOST%"` 改为 `set "HOST=!FILE_HOST!"`
  - `set "PORT=%FILE_PORT%"` 改为 `set "PORT=!FILE_PORT!"`
  - `call :log launch_error="%LAUNCH_ERROR%"` 改为 `call :log launch_error="!LAUNCH_ERROR!"`
- 不改变 45 秒等待窗口、不改变健康探测口径，只修复批处理延迟展开错误。
- 该项优先级最高，允许先于后续所有优化单独提交。

#### P0.2 补一条静态守卫
**文件**：`tests/test_win7_launcher_runtime_paths.py`

- 新增或合并文本守卫，确保就绪循环中的 `FILE_HOST` / `FILE_PORT` / `LAUNCH_ERROR` 读取使用延迟展开形式。
- 与现有同类文本断言保持同一风格，避免重复散落。

### 阶段 A：批处理启动器收口

#### A1. 编码与日志前置保护
**文件**：`assets/启动_排产系统_Chrome.bat`

- 在脚本开头增加 `chcp 65001 >nul 2>&1`。
- 保持已有 ASCII 友好结构，不改动运行时契约路径与日志文件名。
- 新增更细粒度日志键，至少包含：
  - `contract_owner_normalized`
  - `app_spawn_probe`
  - `chrome_profile_probe`
  - `chrome_alive_probe`

#### A2. 运行时契约 owner 反转义归一化
**文件**：`assets/启动_排产系统_Chrome.bat`

- 在 `:read_runtime_contract` 完成 `CONTRACT_OWNER` 提取后，增加最小反转义子程序。
- 第一优先只处理本问题真正需要的 `\\ -> \`；若实现成本可控，再补 `\"` 与 `\/` 的最小兼容。
- 归一化后再参与：
  - `if /I "%CONTRACT_OWNER%"=="%CURRENT_OWNER%"`
  - `LOCK_OWNER=%CONTRACT_OWNER%`
- **不改 JSON 结构，不改字段名，只修补 bat 读取层。**

#### A3. 锁文件进程探测与 Python 残留 wmic 统一收口
**文件**：`assets/启动_排产系统_Chrome.bat`、`web/bootstrap/launcher.py`

- 批处理侧：用 `tasklist /FI "PID eq ..." /NH /FO CSV` 重写 `:lock_is_active`。
- Python 侧：同步处理两处残留：
  1. `_query_process_executable_path`
  2. `_list_aps_chrome_pids`
- 统一原则：
  - 锁活跃判断保持失败闭合；无法确认时宁可阻止复用，也不能误判锁失效。
  - 浏览器清理不能静默回退；当无法枚举 APS 专用浏览器进程时，必须显式记录并向调用方返回失败。
- 推荐实现口径：
  - `_query_process_executable_path` 优先用 PowerShell 读取进程路径，失败时返回 `None`，由上层维持失败闭合。
  - `_list_aps_chrome_pids` 可采用“PowerShell 按命令行 marker 枚举”为主路径；若所有可用方案都失败，则返回失败态而不是空列表成功态。
- 本阶段的目标不是把所有进程枚举都改成同一条命令，而是消除 `wmic` 硬依赖与静默假成功。

#### A4. 主程序拉起后的短时存活探测
**文件**：`assets/启动_排产系统_Chrome.bat`

- 在 `start "" "%APP_EXE%"` 之后增加 1~2 秒的短时探测。
- 目标不是替代 45 秒就绪等待，而是尽早识别“进程刚启动就崩”。
- **不采用“按中文镜像名 tasklist 过滤”作为主策略。**
- 调整后的实现建议：
  1. 先调用 `start` 拉起主程序。
  2. 等待 1~2 秒。
  3. 优先检查 `aps_launch_error.txt` 是否已经生成且有内容。
  4. 若已有明确错误，则直接提示查看 `launcher.log` 与 `aps_launch_error.txt`，不要再继续完整等待。
  5. 若无错误文件，再进入原有 host/port/health 轮询。
- 如确需补进程存在性判断，应优先基于启动后可获取的 PID 或错误文件，而不是依赖中文镜像名筛选。

#### A5. 浏览器 profile 目录创建与可写性校验
**文件**：`assets/启动_排产系统_Chrome.bat`

- 当前只有 `mkdir`，需补两个层次：
  1. 目录存在性确认。
  2. 临时探针文件写入/删除确认。
- 若目录不可写：
  - 写日志。
  - 控制台明确提示 `%CHROME_PROFILE_DIR%`。
  - `pause` 后退出，而不是继续执行 `start chrome.exe`。

#### A6. 浏览器拉起后的短时存活确认（简化版）
**文件**：`assets/启动_排产系统_Chrome.bat`

- 原先的“双路径 + profile 锁痕迹”方案取消，改为单一、可维护的最小确认策略。
- 在 `OPEN_CHROME` 成功调用 `start` 之后：
  1. 等待 2~3 秒。
  2. 用 `tasklist /FI "IMAGENAME eq chrome.exe"` 检查是否至少存在 `chrome.exe`。
  3. 若不存在，则判定“浏览器完全未拉起”，直接 `pause` 报错。
  4. 若存在，则视为最小成功，不再追加复杂的 profile 锁判定。
- 失败时输出：
  - `launcher.log` 路径。
  - 建议手工执行的 `chrome_cmd`。
  - profile 目录路径。
- 成功时才走 `exit /b 0`。
- 说明：该策略无法区分 APS 专用浏览器与用户已开的普通 Chrome，但能覆盖当前最核心的“Chrome 完全没启动仍静默成功”问题，复杂度可控。

### 阶段 B：出包与验收链路补强

#### B1. 为浏览器运行时新增最小冒烟
**文件**：`.limcode/skills/aps-package-win7/scripts/package_win7.ps1`

- 新增“浏览器最小冒烟”函数，覆盖两类对象：
  1. `build\chrome109_runtime_payload\chrome.exe`
  2. legacy 路径下 `dist\...\tools\chrome109\chrome.exe`
- 推荐实现口径：
  - 临时起一个本地最小 HTTP 服务。
  - 用独立临时 profile 启动 `chrome.exe --app=http://127.0.0.1:{port}/`。
  - 轮询确认浏览器进程出现且短时存活。
  - 测试结束后主动清理浏览器进程与临时 profile。
- 冒烟失败则中断出包。

#### B2. 正式出包入口与阻断条件统一
**文件**：`.limcode/skills/aps-package-win7/scripts/package_win7.ps1`，必要时补少量说明到 `installer/README_WIN7_INSTALLER.md` / `DELIVERY_WIN7.md`

- 明确“正式双包交付”以 `package_win7.ps1` 为主入口。
- `validate_dist_exe.py` 继续保留其当前职责：仅覆盖后端冷启动与页面可达。
- 本轮文档调整只做“入口与阻断条件澄清”，不再重复抄写已有的边界说明。
- 如保留 `build_win7_installer.bat`，需在文档中注明它不是完整双包验收入口，避免误用。

### 阶段 C：自动化回归与现场验收补齐

#### C1. 静态守卫补强
**文件**：`tests/test_win7_launcher_runtime_paths.py`

新增或补强以下守卫：
- 就绪循环中的延迟展开修复存在。
- `tasklist /FI "PID eq` 替代 `wmic` 的锁检测实现存在。
- `CONTRACT_OWNER` 反转义逻辑存在。
- `CHROME_PROFILE_DIR` 可写性探针存在。
- `OPEN_CHROME` 后存在浏览器短时存活探测。
- `package_win7.ps1` 中存在浏览器最小冒烟步骤。
- 如新增 Python 侧进程枚举降级逻辑，可补一条针对“失败不再静默成功”的断言。

#### C2. 现有回归继续保留并作为基线
**需重新执行**：
- `python tests/regression_runtime_contract_launcher.py`
- `python tests/regression_shared_runtime_state.py`
- `python tests/regression_runtime_stop_cli.py`
- `pytest tests/test_win7_launcher_runtime_paths.py -q`

这些用来确保：
- 共享日志目录契约仍然成立。
- `owner` / `runtime_dir` / `chrome_profile_dir` 字段没有被破坏。
- `--runtime-stop` 链路仍可工作。

#### C3. 新增现场验收清单
**建议补充文档**：`installer/README_WIN7_INSTALLER.md`、`DELIVERY_WIN7.md`

至少覆盖：
1. 目标机先装 `APS_Chrome109_Runtime.exe`，再装 `APS_Main_Setup.exe`。
2. 点击桌面快捷方式，确认不是直接双击 `排产系统.exe`。
3. 若浏览器未打开，确认命令行不再“静默消失”，而是给出日志路径/排障提示。
4. 检查 `launcher.log` 中新增探针键是否完整。
5. 复制 `chrome_cmd` 到命令行复现时，能定位到 profile 不可写、浏览器瞬退或路径缺件中的具体一类。
6. 验证 `--runtime-stop --stop-aps-chrome` 在无 `wmic` 环境下不会再把浏览器清理误报为成功。

## 五、建议改动文件清单

### 必改
- `assets/启动_排产系统_Chrome.bat`
- `web/bootstrap/launcher.py`
- `.limcode/skills/aps-package-win7/scripts/package_win7.ps1`
- `tests/test_win7_launcher_runtime_paths.py`
- `installer/README_WIN7_INSTALLER.md`
- `DELIVERY_WIN7.md`

### 按实现细节择需补改
- `build_win7_installer.bat`
- `开发文档/系统速查表.md`

## 六、实施顺序

1. **先做 P0**：修复批处理就绪循环延迟展开 BUG，并补最小静态守卫。
2. 实施 A1-A2：先收口编码、日志与 owner 归一化，避免后续排障缺失信息。
3. 实施 A3：同步处理 bat 与 Python 的残留 `wmic`，先消除不一致与静默回退。
4. 实施 A4-A6：完成主程序短时探测、profile 可写性校验、浏览器最小存活确认。
5. 实施 B1-B2：把浏览器最小冒烟纳入正式出包阻断条件，并收口出包入口说明。
6. 实施 C1-C3：补齐静态守卫、执行回归、同步现场验收清单。

## 七、风险与控制点

1. **批处理引号与转义风险高**
   - 控制：把新增逻辑拆成子程序，不在主流程内堆叠长命令。
2. **不能破坏安装器/停机 helper 对现有契约的读取**
   - 控制：不改 `aps_runtime.json` 字段名、不改版本号、不改 profile 目录名。
3. **Python 侧进程枚举改造容易引入“误杀普通 Chrome”或“误判锁失效”**
   - 控制：锁探测保持失败闭合；浏览器清理改为“无法确认则显式失败”，不要再静默成功。
4. **浏览器最小存活确认存在误判上限**
   - 控制：A6 只解决“完全没启动仍静默成功”，不在本轮追求完美区分 APS 专用浏览器。
5. **出包脚本补冒烟后运行时间会增加**
   - 控制：只做最小本地页打开与短时存活，不做完整页面巡检。

## 八、完成标准

满足以下条件方可视为本次修复完成：
1. 首次启动场景不再因为批处理延迟展开错误而固定等待 45 秒超时。
2. 快捷方式触发时，Chrome 运行时缺件、profile 不可写、Chrome 瞬退三类场景都不会再表现为“CMD 闪一下就没了且无信息”。
3. bat 侧不再依赖 `wmic` 做锁 PID 存活判断；Python 侧残留 `wmic` 已被收口或至少不再导致静默假成功。
4. bat 侧读取 `aps_runtime.json` 的 `owner` 后能正确与 `CURRENT_OWNER` 对齐。
5. 正式出包流程中，浏览器运行时最小冒烟成为阻断项。
6. 共享日志契约、安装器 `--runtime-stop`、现有回归全部通过。
