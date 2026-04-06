@echo off
REM T2: 验证 WMIC 在当前环境的可用性。
REM 审查发现 BAT-WMIC-FAIL-UNSAFE 指出 WMIC 失败时锁检查降级为 fail-open。
REM 本脚本在当前机器上测试 wmic 可用性与 ERRORLEVEL。
REM 注意：此脚本在 Win10/Win11 上可作为基线，最终仍建议在实际 Win7 目标机上执行。

setlocal EnableExtensions EnableDelayedExpansion
set "FINAL_RC=0"
set "RC_WHERE=1"
set "RC_WMIC=1"
set "RC3=0"

echo ============================================
echo T2: WMIC 可用性验证
echo ============================================

REM 测试 1: wmic 命令本身是否可用
echo.
echo [test1] wmic 命令是否存在...
where wmic >nul 2>&1
set "RC_WHERE=%ERRORLEVEL%"
if "%RC_WHERE%"=="0" (
  echo [test1] wmic 命令存在 ✓
) else (
  echo [test1] wmic 命令不存在 ✗
  echo [test1] 结论：在当前环境中 wmic 已不可用。
  set "FINAL_RC=1"
  goto :SUMMARY
)

REM 测试 2: 对一个已知存在的进程 ID 执行 wmic 查询
echo.
echo [test2] wmic 查询当前 cmd 进程...
for /f "tokens=2" %%P in ('tasklist /fi "IMAGENAME eq cmd.exe" /nh /fo table 2^>nul ^| findstr /R "[0-9]"') do (
  set "TEST_PID=%%P"
  goto :GOT_PID
)
:GOT_PID
if not defined TEST_PID (
  echo [test2] 无法获取测试 PID，跳过
  goto :TEST3
)
echo [test2] 测试 PID=%TEST_PID%
wmic process where "ProcessId=%TEST_PID%" get ProcessId /value 2>nul | findstr /I /C:"ProcessId=" >nul
set "RC_WMIC=%ERRORLEVEL%"
if "%RC_WMIC%"=="0" (
  echo [test2] wmic 查询已存在进程成功，ERRORLEVEL=0 ✓
) else (
  echo [test2] wmic 查询已存在进程失败，ERRORLEVEL=%RC_WMIC% ✗
  set "FINAL_RC=1"
)

:TEST3
REM 测试 3: 对一个不存在的进程 ID 执行 wmic 查询
echo.
echo [test3] wmic 查询不存在的进程 (PID=99999999)...
set "FOUND_NONEXIST="
for /f "tokens=2 delims==" %%A in ('wmic process where "ProcessId=99999999" get ProcessId /value 2^>nul ^| findstr /I /C:"ProcessId="') do (
  if /I not "%%A"=="" set "FOUND_NONEXIST=1"
)
set "RC3=%ERRORLEVEL%"
if defined FOUND_NONEXIST (
  echo [test3] 异常：wmic 声称不存在的进程存在 ✗
  set "FINAL_RC=1"
) else (
  echo [test3] wmic 未找到不存在的进程（符合预期）✓
  echo [test3] 注意：此时 ERRORLEVEL=%RC3%，若启动器代码未显式处理，LOCK_ACTIVE 可能保持未定义。
)

REM 测试 4: 记录 WMI 服务状态
echo.
echo [test4] WMI 服务状态:
sc query winmgmt | findstr /I "STATE"
echo [test4] 注意：如果 WMI 服务未运行，wmic 查询会失败。

:SUMMARY
echo.
echo ============================================
echo 总结:
echo   wmic 命令在当前环境: %RC_WHERE% (0=存在)
echo   wmic 查询现有进程:   %RC_WMIC% (0=成功)
echo   建议：无论 WMIC 常见与否，启动器都应对查询失败显式 fail-closed。
if "%FINAL_RC%"=="0" (
  echo 结论：当前机器未复现 WMIC 缺失，但仍应保留失败闭合防护。
) else (
  echo 结论：当前机器已经能复现 WMIC 缺失/不可靠，M3 必须保持高优先级。
)
echo ============================================

endlocal & exit /b %FINAL_RC%
