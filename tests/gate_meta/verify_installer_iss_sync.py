"""Check that both Win7 entry scripts consume one shared installer implementation."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT_FOR_IMPORT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT_FOR_IMPORT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT_FOR_IMPORT))

from tests._support.paths import REPO_ROOT

MAIN_ISS = REPO_ROOT / "installer" / "aps_win7.iss"
LEGACY_ISS = REPO_ROOT / "installer" / "aps_win7_legacy.iss"
SHARED_ISS = REPO_ROOT / "installer" / "aps_win7_shared.iss"


def installer_source(entry: Path) -> str:
    """Read the entry and its shared body for source-level packaging checks."""
    return entry.read_text(encoding="utf-8") + SHARED_ISS.read_text(encoding="utf-8")


def main() -> int:
    errors = []
    for entry, output_name, legacy in ((MAIN_ISS, "APS_Main_Setup", 0), (LEGACY_ISS, "APS_Legacy_Full_Setup", 1)):
        if not entry.is_file():
            errors.append(f"缺少安装入口：{entry}")
            continue
        actual = [line.strip() for line in entry.read_text(encoding="utf-8").splitlines()
                  if line.strip() and not line.lstrip().startswith(";")]
        expected = [f'#define InstallerOutputName "{output_name}"', f"#define LegacyFullInstaller {legacy}",
                    '#include "aps_win7_shared.iss"']
        if actual != expected:
            errors.append(f"安装入口应只声明包名、legacy 浏览器行为并引用共同主体：{entry}")
    if not SHARED_ISS.is_file():
        errors.append(f"缺少共同主体：{SHARED_ISS}")
    else:
        shared = SHARED_ISS.read_text(encoding="utf-8")
        if "[Setup]" not in shared or "[Code]" not in shared or "OutputBaseFilename={#InstallerOutputName}" not in shared:
            errors.append("共同主体缺少安装配置、运行代码或入口包名绑定。")
        browser_switch = '#if LegacyFullInstaller\n#define UninstallStopApsChrome "True"\n#else\n#define UninstallStopApsChrome "False"\n#endif'
        if browser_switch not in shared or shared.count("TryStopKnownApsRuntime({#UninstallStopApsChrome})") != 2:
            errors.append("卸载必须使用入口的浏览器停止策略，静默和交互卸载均需遵循。")
    if errors:
        for message in errors:
            print(f"[installer] ✗ {message}")
        return 1
    print("[installer] 通过：两个入口引用同一主体，主程序/legacy 包名及卸载浏览器职责保持区分。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
