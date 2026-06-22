@echo off
rem Win7 build script (onedir)
rem Requirements:
rem - Python 3.8.x
rem - PyInstaller 4.10

setlocal EnableExtensions EnableDelayedExpansion
pushd "%~dp0" >nul 2>&1

rem Keep UTF-8 console for non-ASCII app name/path
chcp 65001 >nul 2>&1

echo [build] repo: %CD%

rem 1) Check Python and PyInstaller before deleting build artifacts
python -c "import platform, sys, PyInstaller; ok=sys.version_info[:2]==(3,8) and platform.architecture()[0]=='64bit' and PyInstaller.__version__=='4.10'; print('Python {}.{}.{} {}, PyInstaller {}'.format(sys.version_info[0], sys.version_info[1], sys.version_info[2], platform.architecture()[0], PyInstaller.__version__)); sys.exit(0 if ok else 1)"
if not %errorlevel%==0 (
  echo [build] Win7 package must use Python 3.8 x64 and PyInstaller==4.10. Please fix the active python first.
  popd >nul 2>&1
  endlocal & exit /b 2
)

rem 1.5) Install NetworkX offline from the in-repo wheel BEFORE freezing.
rem      PyInstaller freezes networkx only if it exists in the build env;
rem      install it from vendor/wheels so the package never silently ships without it.
set "NX_WHEEL="
for %%f in (vendor\wheels\networkx-3.1-*.whl) do set "NX_WHEEL=%%f"
if not defined NX_WHEEL (
  echo [build] 缺少离线 wheel：vendor\wheels\networkx-3.1-*.whl，无法保证离线包含 NetworkX。
  popd >nul 2>&1
  endlocal & exit /b 5
)
echo [build] install NetworkX offline from "%NX_WHEEL%"
python -m pip install --no-index --no-deps --force-reinstall "%NX_WHEEL%"
if not %errorlevel%==0 (
  echo [build] 离线安装 NetworkX 失败。
  popd >nul 2>&1
  endlocal & exit /b 6
)
python -c "import networkx, sys; sys.exit(0 if networkx.__version__=='3.1' else 1)"
if not %errorlevel%==0 (
  echo [build] NetworkX 版本校验失败（期望 3.1）。
  popd >nul 2>&1
  endlocal & exit /b 7
)

rem 2) Clean old artifacts (optional)
if exist build rmdir /s /q build >nul 2>&1
if exist build (
  echo [build] 清理 build 目录失败。
  popd >nul 2>&1
  endlocal & exit /b 3
)
if exist dist rmdir /s /q dist >nul 2>&1
if exist dist (
  echo [build] 清理 dist 目录失败。
  popd >nul 2>&1
  endlocal & exit /b 4
)

rem 3) Build
echo [build] Run PyInstaller (onedir)...
if exist vendor (
  echo [build] include vendor directory.
  python -m PyInstaller --noconfirm --clean --onedir --windowed ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "templates_excel;templates_excel" ^
    --add-data "plugins;plugins" ^
    --add-data "vendor;vendor" ^
    --add-data "schema.sql;." ^
    --hidden-import web.routes.domains.scheduler.scheduler_analysis ^
    --hidden-import web.routes.domains.scheduler.scheduler_batch_detail ^
    --hidden-import web.routes.domains.scheduler.scheduler_batches ^
    --hidden-import web.routes.domains.scheduler.scheduler_calendar_pages ^
    --hidden-import web.routes.domains.scheduler.scheduler_config ^
    --hidden-import web.routes.domains.scheduler.scheduler_excel_batches ^
    --hidden-import web.routes.domains.scheduler.scheduler_excel_calendar ^
    --hidden-import web.routes.domains.scheduler.scheduler_gantt ^
    --hidden-import web.routes.domains.scheduler.scheduler_gantt_adjustments ^
    --hidden-import networkx ^
    --hidden-import web.routes.domains.scheduler.scheduler_ops ^
    --hidden-import web.routes.domains.scheduler.scheduler_resource_dispatch ^
    --hidden-import web.routes.domains.scheduler.scheduler_resource_dispatch_execution_routes ^
    --hidden-import web.routes.domains.scheduler.scheduler_run ^
    --hidden-import web.routes.domains.scheduler.scheduler_week_plan ^
    --name "排产系统" ^
    app.py
) else (
  echo [build] vendor 目录不存在，跳过 vendor 数据目录。
  python -m PyInstaller --noconfirm --clean --onedir --windowed ^
    --add-data "templates;templates" ^
    --add-data "static;static" ^
    --add-data "templates_excel;templates_excel" ^
    --add-data "plugins;plugins" ^
    --add-data "schema.sql;." ^
    --hidden-import web.routes.domains.scheduler.scheduler_analysis ^
    --hidden-import web.routes.domains.scheduler.scheduler_batch_detail ^
    --hidden-import web.routes.domains.scheduler.scheduler_batches ^
    --hidden-import web.routes.domains.scheduler.scheduler_calendar_pages ^
    --hidden-import web.routes.domains.scheduler.scheduler_config ^
    --hidden-import web.routes.domains.scheduler.scheduler_excel_batches ^
    --hidden-import web.routes.domains.scheduler.scheduler_excel_calendar ^
    --hidden-import web.routes.domains.scheduler.scheduler_gantt ^
    --hidden-import web.routes.domains.scheduler.scheduler_gantt_adjustments ^
    --hidden-import networkx ^
    --hidden-import web.routes.domains.scheduler.scheduler_ops ^
    --hidden-import web.routes.domains.scheduler.scheduler_resource_dispatch ^
    --hidden-import web.routes.domains.scheduler.scheduler_resource_dispatch_execution_routes ^
    --hidden-import web.routes.domains.scheduler.scheduler_run ^
    --hidden-import web.routes.domains.scheduler.scheduler_week_plan ^
    --name "排产系统" ^
    app.py
)
set "RC=%ERRORLEVEL%"

echo.
if %RC%==0 (
  echo [build] PASS. dist folder created.
  echo [build] Next: python validate_dist_exe.py
) else (
  echo [build] FAIL (exit=%RC%)
)

popd >nul 2>&1
endlocal & exit /b %RC%
