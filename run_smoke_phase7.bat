@echo off
REM Phase7（排产算法 / M3）冒烟测试一键执行脚本
REM 作用：运行 tests\smoke_phase7.py，并自动生成 evidence\Phase7\smoke_phase7_report.md

setlocal
cd /d %~dp0

echo [Phase7] 开始运行冒烟测试...
echo - 项目目录：%cd%
echo.

python tests\smoke_phase7.py

echo.
if %errorlevel%==0 (
  echo [Phase7] 冒烟测试完成：通过
  echo - 报告：evidence\Phase7\smoke_phase7_report.md
) else (
  echo [Phase7] 冒烟测试完成：失败（错误码=%errorlevel%）
  echo - 请打开报告查看详情：evidence\Phase7\smoke_phase7_report.md
)

endlocal

