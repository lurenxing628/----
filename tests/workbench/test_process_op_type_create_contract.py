"""新增工种弹窗刷新最新资料后仍可保存：编译组件后用最小 hooks 运行时验证，不开浏览器、不连库。"""

import json
import shutil
import subprocess
from pathlib import Path


def test_refresh_latest_keeps_op_type_create_saveable():
    node = shutil.which("node")
    assert node, "Contract tests require the build-host Node runtime"
    result = subprocess.run([node, str(Path(__file__).with_name("process_op_type_create_contract.cjs"))],
                            check=True, capture_output=True, text=True, timeout=60)
    report = json.loads(result.stdout)
    assert report["checks"] >= 10
    assert report["browser"] is False and report["database"] is False
