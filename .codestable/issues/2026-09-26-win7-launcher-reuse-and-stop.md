# Win7 原启动器复用与 Chrome 停止验收问题

> 历史记录归档（2026-09-27）：本文保留初始调查、验收失败及当时的判断；正文中的“未修复”“未提交”“尚未安装”等描述均为记录时的状态。后续修复已提交于 `0b9a682f` 至 `d1307cb8`，原 Win7 的安装、复验和交付结果以[最终验收记录](2026-09-26-win7-fixes-acceptance.md)为准。打包验收脚本及两份专测已包含在 `0b9a682f` 中。本文原存于 `codestable/`，现归档至 `.codestable/`；引用的本机日志、数据库和截图不随 Git 上传。

- 状态：原 BAT 复用失败、Chrome 停止漏主进程均已确认，未修改产品。Chrome PID 输出 BOM 已取得真实字节；合同 owner 为空已取得真实日志，其更底层编码原因仍未知。
- 验收源码：`4df78c5330f8c0cb819ecf5a8678dc46b1340e58`。
- 环境：真实 Win7 SP1 x64 来宾、PowerShell 2.0、随包 Chrome 109；目标机未安装 Python。
- 原包启动 BAT SHA256：`36D4330EDEE808FC8DA5295BF5AB739ECAC047B0BD9F388158F04265DBE46825`。本机再次核对相符。
- 边界：宿主无害复现用于解释原因；实际 Win7 成败以 transport 的来宾收据为准，两者不得互换。
- 本文按本轮主代理明确指定的 `codestable/issues/` 路径保存。仅写问题文档，不修改 BAT、Python 产品源码、虚拟机或业务数据。

## 1. 原 BAT 第二次启动无法复用现有实例

### 实际 Win7 证据

原包 BAT 首次启动成功：APS PID 3424、Chrome PID 3124，均为交互会话 Session 1。

2026-09-26 17:16:20，验收助手再次核验 407 个不可变交付文件后，运行同一 BAT 进行复用。已有 APS PID 3424、创建时间 `20260926171458.326763+480`。原生 wrapper PID 1444 停在 BAT 的官方 `pause`。原生控制台内容包括：

```text
FINDSTR: Cannot open >nul
[launcher] 无法确认现有实例归属，已阻止新实例启动。
... is not recognized as an internal or external command,
Press any key to continue . . .
```

验收助手于 17:19:20 记录等待 180 秒未退出，保留现场，没有强制终止 APS。这个 180 秒是助手等待官方 `pause` 的结果，不能解释为 APS 后台业务停止耗时。

证据文件：

- `C:\Users\lurenxing\AppData\Local\Temp\aps-win7-acceptance-20260926\target-installed-reuse-native-live-console.txt`
- `C:\Users\lurenxing\AppData\Local\Temp\aps-win7-acceptance-20260926\target-installed-reuse-pause.png`
- `C:\Users\lurenxing\AppData\Local\Temp\aps-win7-acceptance-20260926\target-final-official-reuseinstalled-console.txt`
- `C:\Users\lurenxing\AppData\Local\Temp\aps-win7-acceptance-20260926\target-official-delivery-logs\ReuseInstalled-20260926-171618-3084\operation.txt`

用户影响：运行中的程序再次通过官方入口打开时，被错误阻止，现有实例复用验收不通过。首启成功不能覆盖这个失败。

### 中文路径再次复现，取得 BAT 的实际 exit 9

在 `C:\APS 验收\排产系统` 的原407文件交付副本中，首启后 APS PID 3744 正常运行。17:25:48 再运行原 BAT 复用，控制台同样出现 `FINDSTR: Cannot open >nul`、归属不明阻止和中文片段被当成命令。

现场确认处于官方 `pause` 后，按 Enter 正常结束这一 BAT。17:26:41 收据为 `OfficialCommandExitCode=9 WrapperExitCode=9 ElapsedMilliseconds=53312`，原 APS 3744 未另开。53,312 ms 包含等待人工确认 pause 的时间，不能当作应用性能耗时。与 Installed 那次助手等候180秒的结果分开，这次有 BAT 自己的实际退出码。

已归档原生 console、exit 与 operation 收据到 `evidence/Win7Acceptance/20260926/target/launcher-reuse-stop-evidence/official/ReuseChinese-20260926-172546-2364/`。

### 已确认原因：FINDSTR 引号使锁身份检查失败

`assets/启动_排产系统_Chrome.bat:589` 的 `:lock_is_active` 在 618、620、622 行使用以下命令：

```bat
echo !LOCK_QUERY_ROW! | findstr /R /C:"^\"" >nul
echo !LOCK_QUERY_ROW! | findstr /C:",\"!LOCK_PID!\"," >nul
echo !LOCK_QUERY_ROW! | findstr /I /C:"\"!APP_EXE_NAME!\",\"!LOCK_PID!\"," >nul
```

这组反斜杠和双引号的组合不能按 C/Python 字符串的直觉用于 cmd 参数与重定向。第一条会将 `>nul` 交给 FINDSTR 作为文件名；后续匹配也未匹配正确的 CSV。

只读宿主复现使用 Python 3.8 启动独立 `cmd.exe /d /s /c`，输入是固定的虚构 CSV，不查询或操作任何产品进程、不写文件。三条命令分别执行：

```python
commands = [
    r'echo "aps.exe","3424","Console","1","123 K" | findstr /R /C:"^\"" >nul',
    r'echo "aps.exe","3424","Console","1","123 K" | findstr /C:",\"3424\"," >nul',
    r'echo "aps.exe","3424","Console","1","123 K" | findstr /I /C:"\"aps.exe\",\"3424\"," >nul',
]
for command in commands:
    result = subprocess.run(
        ['cmd.exe', '/d', '/s', '/c', command],
        stdin=subprocess.DEVNULL, capture_output=True, timeout=5,
    )
```

观察结果：第一条 `returncode=1`、stderr 为 `FINDSTR: Cannot open >nul\r\n`；第二、第三条 `returncode=1` 且 stdout/stderr 为空。第一条错误与真实 Win7 控制台一致。这一缺陷不需要中文路径或 PS2 BOM 才能发生。

### 已确认后备路径被空 owner 阻断；空 owner 的编码原因仍未知

锁检查失败后，BAT 仍尝试 `:try_reuse_by_contract`。随后补取的同轮 `launcher.log` 已闭合这段行为：

```text
17:16:20.72 current_owner="SK-20260125PYIA\Administrator"
17:16:21.08 contract_owner_normalized=""
17:16:21.31 health_ok="http://127.0.0.1:5000/system/health"
17:16:21.33 existing_reuse_blocked=healthy_without_owner_proof
17:16:21.33 blocked_by_uncertain=healthy_without_owner_proof
```

因此，实际后备路径在健康检查成功时仍未取得 owner 身份，最终按归属不明阻止复用。原日志已保存到 `evidence/Win7Acceptance/20260926/target/launcher-reuse-stop-evidence/target-installed-official-launcher-live.log`，SHA256 为 `28D924614690A76F9BF90EC7938E0EB3454801D482BC085B37F6F590770D0C13`。

`assets/启动_排产系统_Chrome.bat:537` 的 `:read_runtime_contract` 将 PowerShell 输出写入临时文件，首行是 `owner=...`，再由 `for /f` 逐项读取。首行若带 BOM，可能无法匹配 `owner`，但当前还没有该临时文件的真实原始字节；不能宣称本次空 owner 已证实由 BOM 造成。

尚缺的是合同解析临时输出原始字节，不能把 Chrome 查询的 BOM 证据直接套到合同解析输出上。本轮不为此重复来宾操作。将来如补验，只在独立证据文件中保存原命令输出字节，不改运行契约、锁文件或产品 BAT。契约中的 shutdown token 不应复制到报告正文。

控制台另外两条中文片段被当作命令的现象也须单独记录。原包 CRLF 已由主代理核验，不能把现象直接归于换行；目前没有足够证据确定其编码/解析根因。

## 2. Stop 关闭了 Chrome 子进程，却遗漏仍存活的主进程

### 实际 Win7 证据

2026-09-26 16:05:38 左右，对 `browser-4df78c53` 槽执行原冻结 EXE 的 `--runtime-stop ... --stop-aps-chrome`。外部助手此时已经提供有效 stdin，不再出现此前的 WinError 6。命令耗时 4,433 ms、退出码 1，最终日志为：

```text
chrome_stop_failed status=profile_processes_still_running
initial pids=[3060,2652,1472,1176,2352,2168,3328,4008,3280,3496,3784,1720]
failed_pids=[]
remaining_pids=[1592,3892,3128]
```

WMI 快照说明：

- 主 Chrome PID 1340 创建于 15:42:26，仍监听 `127.0.0.1:9222`，但未进入产品首轮匹配列表。
- 主进程的完整命令行含精确匹配的 `--user-data-dir="C:\APS-Acceptance\browser-4df78c53\user-data\chrome109_profile"`。
- 三个新子进程的父 PID 都是 1340，创建于 16:05:40–41，分别为 network、storage、GPU 类型。
- APS 运行进程已经退出；5000 无监听，运行契约、壳锁、DB 锁、端点指针和 WAL/SHM/journal 共9项全部不存在。

因此本次真实失败是专用 Chrome 未关闭，不能归为单纯退出码误报；也没有证据支持 APS 被强杀、业务写入未排空或发生数据丢失。`launcher_stop.py:398-403` 已进入 APS 停止后的 Chrome 收尾阶段，发现剩余 Chrome 后返回 1。

已持久化证据目录：

`D:\Github\----\evidence\Win7Acceptance\20260926\target\target-browser-stop-failure-20260926-160542\`

其中 `normal-stop-native-console.txt`、进程/锁/端口 CSV 是实际来宾证据。含创建时间的完整快照另位于：

`C:\Users\lurenxing\AppData\Local\Temp\aps-win7-acceptance-20260926\target-browser-stop-failure-20260926-160542\chrome-processes-complete.csv`

### 已确认：真实 UTF-8 BOM 使首个 PID 被丢弃

`web/bootstrap/launcher_processes.py:119` 使用 `encoding="utf-8"`；`web/bootstrap/launcher_chrome.py:80-92` 对每行仅 `strip()` 后判断 `isdigit()`。U+FEFF 不会被 `strip()` 去掉。

从原 HEAD AST 只读提取原 `_parse_chrome_pid_output` 函数，在宿主 Python 3.8 中以内存字符串复现：

| 输入 | 原解析器输出 |
|---|---|
| `1340\r\n1592\r\n3892\r\n3128` | `[1340,1592,3892,3128]` |
| `\ufeff1340\r\n1592\r\n3892\r\n3128` | `[1592,3892,3128]` |

上述内存复现当时只能形成推断。17:19:22，transport 在正式原 BAT 启动的 Installed `--app` 场景执行了同一原查询，保存了真实 stdout 原始字节，现已闭合该推断。

实际 `stdout.bin` 为38字节，SHA256 为 `0ACA1BC48C1E9470A326D27D8D4D907DE681064CFC83C696339A6965EE3A766F`，开头是：

```text
EF BB BF 33 31 32 34 0D 0A
```

按 UTF-8 原样解码得到 `\ufeff3124\r\n596\r\n3812\r\n3444\r\n3004\r\n1712\r\n`。首行3124正是本轮原 BAT 启动的 Chrome 主进程。把这份实际字节交给原 HEAD 解析器，结果是 `[596,3812,3444,3004,1712]`，遗漏主 PID；仅在宿主对照中改为 `utf-8-sig` 解码，结果包含3124。未修改产品或重复查询。

同目录保存的 `query.ps1` SHA256 为 `D5058BC06C4B00CFCBA031F527D9B83ED57002BD7B4823BA7DAD62A2113DF4E8`，与原 HEAD 对固定 Installed profile 生成的查询完全相同。`stderr.bin` 为0字节。

原始文件已逐文件核对哈希并归档到：

`D:\Github\----\evidence\Win7Acceptance\20260926\target\target-chrome-query-raw\Installed-20260926-171922-2504-cf985111\`

同目录的 `host-byte-analysis.json` 明确标注为宿主对已保存来宾字节的分析，不是来宾成功收据。

#### 采样助手自身失败与证据限制

PS2 采样助手在已经写入 `stdout.bin` / `stderr.bin` 后，调用 `JavaScriptSerializer.Serialize` 写 metadata 时，因 `PSParameterizedProperty` 循环引用报错，外部助手 exit 2。原错误全文保留在 `capture-error.txt`；没有删除或改写这个失败。

这次采样未留下独立的查询子进程退出码、超时标志或 stdout EOF 完整性收据，因此这些字段在宿主分析中为 unknown/null，不能声称原查询 exit 0 或完整捕获。该限制不影响38个已保存字节中实际存在 BOM、首行主 PID 被原解析器丢弃的直接证据。

#### 正式 `--app` 停止也失败

17:23:47，再次核验407个交付文件后，使用有效 NUL stdin 执行原冻结 EXE StopInstalled。来宾收据记录 `OfficialCommandExitCode=1 WrapperExitCode=1 ElapsedMilliseconds=3341`。这说明停止失败也发生在正式原 BAT 的 `--app` 场景，不能只归为 CDP 普通浏览器测试方式。

同次 Stop 原生控制台列出的 `pids=[596,3812,3444,3004,1712]`，与真实 raw stdout 交给原解析器后的结果完全相同：主3124被遗漏；`failed_pids=[]`，随后 `remaining_pids=[816,3732,2216]`。原查询字节、原解析器行为、实际停止选择的 PID 在同一正式启动实例中相互对应。原生控制台及退出收据保存到 `launcher-reuse-stop-evidence/official/StopInstalled-20260926-172344-2396/`。

正常关闭专用 Chrome 后，17:24:28 的 Stop 幂等收尾为 exit 0、1,682 ms，且 APS/Chrome、运行契约和 DB 锁均不存在。该收尾不覆盖首次停止失败。两个实际收据已归档到 `evidence/Win7Acceptance/20260926/target/launcher-reuse-stop-evidence/` 的 `target-final-official-stopinstalled-console.txt` 与 `target-final-official-stopinstalled-after-close-console.txt`。

中文路径正式 `--app` 场景也复现：17:26:44 原 Stop 在2,988 ms后 exit 1，`pids=[1940,2492,852,568,3692]`、`failed_pids=[]`，剩余新子PID为 `[3508,3972,3920]`。正常关闭专用 Chrome 后，17:27:13 的幂等 Stop 为 exit 0、1,013 ms，且 APS/Chrome 与双锁均消失。此场景没有再次执行 raw 采样，不应宣称取得第二份中文路径 BOM 原字节；记录的是实际同类停止失败及后续正常收尾。收据分别保存到 `launcher-reuse-stop-evidence/official/StopChinese-20260926-172642-3256/` 和 `StopChinese-20260926-172711-3708/`。

为后续正式 BAT 的 `--app` 场景准备了只读采样 helper：

`C:\Users\lurenxing\AppData\Local\Temp\aps-win7-acceptance-20260926\target-chrome-query-raw.ps1`

- helper SHA256：`0ED803227E42A3742EA7E7C3478AE28FB6B4661E3138578C0CF5F5E5F85DF411`。
- 仅允许 Installed / Chinese 两个固定 profile；嵌入的查询逐字等于原 HEAD 函数输出。
- 用 C# 线程直接读取 `StandardOutput.BaseStream` / `StandardError.BaseStream`，保存 `stdout.bin` / `stderr.bin`；不通过文本重编码制造 BOM。
- 记录首32字节、首行码元、退出码、查询 PID 和完整性；8秒预算，超时不终止任何进程。
- 宿主语法检查、C# 编译、查询一致性检查已通过；准备阶段没有执行查询或操作来宾。之后由 transport 执行一次，原始字节证据及 metadata 失败如上，未重复采样。

## 3. 不应混入上述产品问题的两个历史现象

1. functional 槽最初 1,799 ms 的 Stop exit 1 来自隐藏验收助手继承无效 stdin，所有进程子探针报 WinError 6。只修外部助手的合法 stdin/EOF 后，同一产品 EXE 的真实 Stop A/B 为 exit 0、2,532 ms，运行进程、契约和 DB 锁自然消失，数据库导出成功。此项属于验收助手问题，不计作已确认产品 Stop 缺陷。
2. 宿主源码测试的7个停止失败属于独立的等待预算问题：初次分类在 deadline 前、循环前后重复完整分类、底层子探针固定8秒预算。32–36秒宿主实测不能代替本次 Win7 4,433 ms Chrome 收尾失败；pending-write 测试还出现等待 `accepted` 标记超时，不能据此描述为提交后丢写。

## 后续最小验证与修复建议

1. 保留当前原包失败及 metadata 助手错误。Chrome 首 PID BOM 已确认；合同 owner 为空及归属阻止链已确认，其更底层编码原因另行调查，不将两种输出混为同一证据。
2. 修复 BAT 的 CSV 身份匹配时，使用能在真实 cmd 中验证的参数/解析方式；保持 PID 与映像名校验，不能退回仅判断 PID 存活。必须复测首启、同账户复用、他账户阻止、陈旧锁及中文路径。
3. Chrome BOM 的最小修复可使用 `utf-8-sig` 解码或在协议解析入口仅移除流首 BOM；保留 profile 精确匹配。补充首行 BOM、相邻 profile 不匹配及真实 Win7 原包普通/`--app` Chrome 关闭验证。
4. 若需继续验收，先正常关闭已核对身份的本槽 Chrome 主窗口，再做产品 Stop 幂等复核；该收尾不能把首次 Stop+Chrome 失败改记为通过。禁止用盲目重复杀子进程、删锁或强杀 APS 代替定位。
