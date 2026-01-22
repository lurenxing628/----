@echo off
REM Phase5（工艺管理模块）冒烟测试一键执行脚本
REM 作用：运行 tests\smoke_phase5.py，并自动生成 evidence\Phase5\smoke_phase5_report.md

setlocal
cd /d %~dp0

echo [Phase5] 开始运行冒烟测试...
echo - 项目目录：%cd%
echo.

python tests\smoke_phase5.py

echo.
if %errorlevel%==0 (
  echo [Phase5] 冒烟测试完成：通过
  echo - 报告：evidence\Phase5\smoke_phase5_report.md
) else (
  echo [Phase5] 冒烟测试完成：失败（错误码=%errorlevel%）
  echo - 请打开报告查看详情：evidence\Phase5\smoke_phase5_report.md
)

endlocal

