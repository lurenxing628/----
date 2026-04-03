@echo off
REM T4: 验证 PowerShell 与 ConvertFrom-Json 是否可用。
REM 目的：为 M6“删除健康检查正则回退”提供目标机证据。
REM 只有在目标机确认存在 PowerShell 且 ConvertFrom-Json 可用时，才建议删除当前兼容回退。

setlocal EnableExtensions EnableDelayedExpansion
set "FINAL_RC=0"
set "PS_VERSION="
set "RC_PS=1"
set "RC_CMDLET=1"
set "RC_PARSE=1"

echo ============================================
echo T4: PowerShell JSON 能力验证
echo ============================================

REM 测试 1: PowerShell 命令是否存在
echo.
echo [test1] powershell 命令是否存在...
where powershell >nul 2>&1
set "RC_PS=%ERRORLEVEL%"
if not "%RC_PS%"=="0" (
  echo [test1] powershell 不存在 ✗
  set "FINAL_RC=1"
  goto :SUMMARY
)
for /f "usebackq delims=" %%V in (`powershell -NoProfile -Command "$PSVersionTable.PSVersion.ToString()"`) do (
  if not defined PS_VERSION set "PS_VERSION=%%V"
)
echo [test1] powershell 存在，版本=!PS_VERSION! ✓

REM 测试 2: ConvertFrom-Json 命令是否存在
echo.
echo [test2] ConvertFrom-Json 是否可用...
powershell -NoProfile -Command "if (Get-Command ConvertFrom-Json -ErrorAction SilentlyContinue) { exit 0 } else { exit 7 }" >nul 2>&1
set "RC_CMDLET=%ERRORLEVEL%"
if "%RC_CMDLET%"=="0" (
  echo [test2] ConvertFrom-Json 可用 ✓
) else (
  echo [test2] ConvertFrom-Json 不可用 ✗
  set "FINAL_RC=1"
)

REM 测试 3: JSON 解析最小样例
echo.
echo [test3] 解析最小健康检查 JSON...
powershell -NoProfile -Command "try { '{\"app\":\"aps\",\"status\":\"ok\",\"contract_version\":1}' | ConvertFrom-Json | Out-Null; exit 0 } catch { exit 8 }" >nul 2>&1
set "RC_PARSE=%ERRORLEVEL%"
if "%RC_PARSE%"=="0" (
  echo [test3] JSON 解析成功 ✓
) else (
  echo [test3] JSON 解析失败 ✗
  set "FINAL_RC=1"
)

:SUMMARY
echo.
echo ============================================
echo 总结:
echo   powershell 命令:      %RC_PS% (0=存在)
echo   ConvertFrom-Json:     %RC_CMDLET% (0=可用)
echo   JSON 最小样例解析:   %RC_PARSE% (0=成功)
if "%RC_PS%"=="0" echo   PowerShell 版本:       !PS_VERSION!
if "%FINAL_RC%"=="0" (
  echo 结论：当前机器满足 ConvertFrom-Json 路径，可以考虑删除健康检查中的正则回退。
  echo       但请务必在实际 Win7 目标机上再跑一次，确认不是只在当前开发机成立。
) else (
  echo 结论：当前机器不满足 ConvertFrom-Json 依赖，不能直接删除健康检查正则回退。
  echo       若仍要收敛分支，应改为“缺少 PowerShell 或缺少 ConvertFrom-Json 时显式失败”，而不是盲删回退。
)
echo ============================================

endlocal & exit /b %FINAL_RC%
