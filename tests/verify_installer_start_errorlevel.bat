@echo off
REM T3: 验证 start 命令对无效路径与有效命令的 ERRORLEVEL 行为。
REM 目的：判断 BAT-START-RC-DEAD 是否成立，以及当前启动器里的 start 返回码检查还有多少价值。

setlocal EnableExtensions EnableDelayedExpansion

echo ============================================
echo T3: start 命令 ERRORLEVEL 行为验证
echo ============================================

REM 测试 1: start 一个不存在的可执行文件
set "RC1="
echo.
echo [test1] start 一个不存在的 exe...
ver >nul
start "" "C:\__nonexistent_path_test_12345\fake_app.exe" 2>nul
set "RC1=%ERRORLEVEL%"
echo [test1] start 不存在的 exe，ERRORLEVEL=%RC1%

REM 测试 2: start 一个确定存在且会立即退出的命令
set "RC2="
echo.
echo [test2] start 一个有效命令（cmd.exe /c exit 0）...
ver >nul
start "" /B "%ComSpec%" /c exit 0 2>nul
set "RC2=%ERRORLEVEL%"
echo [test2] start 有效命令，ERRORLEVEL=%RC2%

REM 总结
echo.
echo ============================================
echo 测试结果总结:
echo   不存在的 exe: ERRORLEVEL=%RC1%
echo   有效命令:     ERRORLEVEL=%RC2%
echo ============================================

if not "%RC1%"=="0" if "%RC2%"=="0" goto :EXPECTED
if "%RC1%"=="0" if "%RC2%"=="0" goto :ALL_ZERO
goto :MIXED

:EXPECTED
echo 结论：start 对无效路径会返回非零，对有效命令返回 0。
echo       因此“start 返回码检查完全是死代码”这一结论不成立。
echo       但在当前启动器里，Chrome 路径已提前存在性校验，这个检查只能覆盖极端竞态场景，价值仍然很低。
endlocal & exit /b 0

:ALL_ZERO
echo 结论：当前环境中 start 对无效路径与有效命令都返回 0。
echo       这说明返回码检查确实接近死代码，应重新评估并考虑删除。
endlocal & exit /b 1

:MIXED
echo 结论：当前环境结果与预期模式不完全一致，需要人工复核。
echo       建议在目标机上再次执行本脚本后，再决定是否删除启动器中的返回码检查。
endlocal & exit /b 1
