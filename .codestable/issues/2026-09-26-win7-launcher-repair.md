# Win7 启动复用与专用 Chrome 停止修复

状态：源码与宿主定向回归通过；修复后的冻结包仍须在真实 Win7 上验收。

## 问题与改动

- 原启动 BAT 将 C 风格转义双引号交给 FINDSTR，真实 Win7 出现 `Cannot open >nul`，已有锁实例未被识别。改为读取 tasklist CSV 的前两列，精确匹配 PID 与映像名；同 PID 的其他程序仍按陈旧锁处理，查询失败仍为未知。没有放宽 owner 或健康检查要求。
- 历史 Win7 日志确认合同后备路径的 owner 为空，但没有保存该合同临时输出字节，底层编码原因仍未证实。新实现让 PowerShell 内部完成 owner 的不区分大小写比较，直接写 ASCII 协议文件，并用 UTF-8 Base64 记录身份。cmd 不再从 stdout 或 Unicode 文本还原合同 owner。空 owner、不匹配 owner、无效版本仍不允许复用。
- 原 Chrome 查询真实 stdout 的前38字节记录含 UTF-8 BOM，首行主进程3124被原解析器丢弃。解析入口现在只移除流首的一个 BOM，再读取 ASCII 正整数 PID；profile 精确匹配规则没有改变。行中 BOM 不作为可删除元数据。
- `.gitattributes` 将既有 Windows BAT 入口声明为 CRLF checkout。Git blob 可规范化为 LF；构建源归档仍须在执行前显式转换 CRLF。删除旧测试中“CRLF 会损坏 Win7”的错误断言。启动 BAT 工作副本为 UTF-8 无 BOM、731个 CRLF、0个裸 LF。

## 已执行验证

2026-09-26，独立 Python 3.8.10 宿主环境：

```text
python -s -m pytest -q
  tests/app_runtime/test_launcher_bat_contract.py
  tests/app_runtime/test_launcher_chrome_pid_encoding.py
  tests/app_runtime/test_launcher_bat_windows_execution.py
  tests/app_runtime/test_launcher_process_path_encoding.py
  tests/app_runtime/test_launcher_observability.py
  tests/app_runtime/test_win7_launcher_runtime_paths.py
124 passed in 136.28s
```

真实 Windows cmd 回归执行生产 BAT 的相应标签，使用独立 tasklist fixture EXE，不查询或终止应用进程。覆盖默认/中文映像名、大小写、不同 PID、同 PID 不同映像、查询失败、非法 PID、同账户复用、跨账户阻止、缺少身份时的健康服务阻断、中文 owner、无效合同版本；实际 Windows PowerShell 还执行了 JavaScriptSerializer 旧分支。Chrome 测试固定原38字节及 SHA256 `0aca1bc48c1e9470a326d27d8d4d907de681064cfc83c696339a6965ee3a766f`。

定向 Ruff 和 `git diff --check` 通过。独立只读复核未发现本次改动扩大 Chrome 停止范围或放松身份保护。

## 边界与剩余验收

- 宿主 cmd/PowerShell 测试不能代替 Win7 PS2、冻结 EXE 与实际 Chrome 的首启、再次打开复用、中文路径及停止闭环。原包失败记录应保留。
- BAT 原有延迟展开对含 `!` 的账户名/路径仍有局限；本次未声称支持任意特殊字符。`for /f` 前两列处理针对默认交付映像名，不支持将 EXE 重命名为含逗号的名称。
- 历史中文提示片段被 cmd 当成命令的现象没有足够证据归因，本次未将其标记为已修复；Win7 受控失败分支仍需观察提示。

## 主代理扩展复核与追加修复

扩展回归发现 tasklist / PowerShell 每次探测独立等待，实际停止 7 个用例失败。新增 launcher_win32.py 使用 OpenProcess 的最小查询权限、WaitForSingleObject(handle, 0) 与 QueryFullProcessImageNameW 查询；不依赖控制台编码，也不把访问被拒绝当作已退出。进程退出即使仍有句柄也正确识别。POSIX 及无法提供 Win32 的工具宿主保留原分支。普通停止仍不强杀正在计算/写入的 APS，不清理未知身份锁。

依据微软 API 文档（2026-09-26 查阅）：
- https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew

主代理独立重跑 native-stop.xml：76 passed / 37.56s，含真实 CLI 与写入排空；launcher-native-bat.xml：28 passed / 6.12s，含真实 Windows 生存期与无外部进程探针、权限不足失败保护、生产 BAT 标签和原 BOM 数据。原失败扩展日志保留为 extended-regressions.xml，不能把它当作通过。Win7 冻结包复验仍待执行。
