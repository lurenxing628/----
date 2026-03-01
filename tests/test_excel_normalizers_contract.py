from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_regression_excel_normalizers_mixed_case_script_smoke() -> None:
    """
    契约测试：确保 regression 脚本在 pytest 下也会被执行（避免只靠手工运行）。

    说明：
    - regression 脚本本身负责断言真值表一致性与边界行为
    - 这里仅负责把它纳入 pytest 的可发现范围
    """
    script = Path(__file__).resolve().parent / "regression_excel_normalizers_mixed_case.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
    )
    output = (result.stdout or "") + ("\n" + result.stderr if result.stderr else "")
    assert result.returncode == 0, output
    assert "OK" in (result.stdout or ""), output

