"""UI 截图基线采集（手跑工具，fusion-anchor-baseline-prep）。

用法：.venv/bin/python tests/_scripts_e2e/capture_ui_baseline.py

复用几何探针管线的脚手架（browser_support 造数起服 + Chrome 探测 + CDP），
遍历 FULL_UI_CONTRACT_PATHS 20 页 × 亮/暗双主题 ≈ 40 张 PNG，
落 output/ui_baseline/<时间戳>/（.gitignore + git hook 双重拉黑，不入库）。
比对方式：人工 A/B（改版前后各跑一次，并排翻图）——刻意无像素 diff。
退出码非 0 当且仅当任一页面截图失败（失败清单打印，不静默跳过）。
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
from datetime import datetime

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tests" / "app_runtime"))

import pytest  # noqa: E402  （MonkeyPatch.context 适配 _build_app 的 fixture 签名）
from ui_geometry_browser_support import _build_app, _serve_app, _shutdown_served_app  # noqa: E402
from ui_geometry_contract_data import FULL_UI_CONTRACT_PATHS  # noqa: E402
from ui_geometry_runtime_support import _resolve_chrome, _resolve_node_with_browser_runtime  # noqa: E402

from tests._support.excel_templates import publish_shared_dir, reset_shared_dir  # noqa: E402


def main() -> int:
    # 纯探测函数（_find_* 系是 pytest fail/skip 语义，手跑工具不适用）
    chrome = _resolve_chrome()
    # exists=True 但 failure_kind 非空（如 browser_env_chrome_version_failed：Chrome 在但
    # --version 超时/OSError）也是不可用——与下方 Node 用 failure_kind 同口径，别截到坏环境
    if not chrome.exists or chrome.failure_kind:
        print(f"Chrome 运行时不可用：{chrome.message}", file=sys.stderr)
        return 2
    node = _resolve_node_with_browser_runtime()
    if node.failure_kind:
        print(f"Node 运行时不可用：{node.message}", file=sys.stderr)
        return 2

    output_dir = REPO_ROOT / "output" / "ui_baseline" / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_str:
        tmp_path = pathlib.Path(tmp_str)
        # _build_app 依赖 session autouse fixture 发布的共享 Excel 模板目录——
        # 手跑无 pytest session，此处显式发布/回收
        publish_shared_dir(str(tmp_path / "excel_templates"))
        try:
            with pytest.MonkeyPatch.context() as monkeypatch:
                app = _build_app(tmp_path, monkeypatch)
                served = _serve_app(app)
                try:
                    results = _run_capture(
                        node.node_path, chrome.chrome_path, served.base_url, tmp_path, output_dir
                    )
                finally:
                    _shutdown_served_app(served)
        finally:
            reset_shared_dir()

    failed = [r for r in results if not r.get("ok")]
    _write_index(output_dir, results)
    print(f"\n产物目录：{output_dir}")
    print(f"成功 {len(results) - len(failed)} 页 / 失败 {len(failed)} 页")
    if failed:
        print("失败清单：")
        for r in failed:
            print(f"  {r['path']}: {r.get('error', '?')}")
        return 1
    return 0


def _run_capture(node_path, chrome_path, base_url, tmp_path, output_dir):
    proc = subprocess.run(
        [
            node_path,
            str(REPO_ROOT / "tests" / "ui_baseline_capture.mjs"),
            chrome_path,
            base_url,
            json.dumps(list(FULL_UI_CONTRACT_PATHS)),
            str(tmp_path / "chrome-profiles"),
            str(output_dir),
        ],
        capture_output=True,
        text=True,
        timeout=600,
    )
    results = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            results.append(json.loads(line))
    if not results:
        raise RuntimeError(f"capture mjs 零输出（rc={proc.returncode}），stderr={proc.stderr[-2000:]}")
    # 结果路径集合必须与输入路径集合严格相等：少输出几页（mjs 漏行/中途崩）会被后续成功统计
    # 吞掉，基线缺页却记成功是验收证据掺假——此处对齐输入清单，缺页/重复/串页即 fail loud
    # （用集合比对而非仅计数：一缺一重时计数相等仍能抓出）。
    expected_paths = set(FULL_UI_CONTRACT_PATHS)
    # 缺 path 键的异常行规范成空串（不直接用 None）：空串不在 expected 里会按「多页」报错、
    # 仍 fail loud，但避免 None 与 str 混排在 sorted() 里触发 TypeError 把结构化报错退化成崩溃。
    got_paths = [str(r.get("path") or "") for r in results]
    got_set = set(got_paths)
    if got_set != expected_paths or len(got_paths) != len(FULL_UI_CONTRACT_PATHS):
        missing = sorted(expected_paths - got_set)
        unexpected = sorted(got_set - expected_paths)
        duplicated = sorted({p for p in got_paths if got_paths.count(p) > 1})
        raise RuntimeError(
            f"capture mjs 结果页与输入页不一致（缺页={missing} 多页={unexpected} 重复={duplicated}），"
            f"stderr={proc.stderr[-2000:]}"
        )
    # mjs 退出码非 0 而逐页 JSON 全 ok：进程级失败（profile 清理炸等）必须 fail loud，不静默
    if proc.returncode != 0 and all(r.get("ok") for r in results):
        raise RuntimeError(f"capture mjs 退出码 {proc.returncode} 但逐页全成功，stderr={proc.stderr[-2000:]}")
    return results


def _write_index(output_dir, results):
    lines = ["# UI 截图基线对照表", "", "| 页面路径 | 亮色 | 暗色 |", "|---|---|---|"]
    for r in results:
        if r.get("ok"):
            light, dark = r["files"]
            lines.append(f"| {r['path']} | {light} | {dark} |")
        else:
            lines.append(f"| {r['path']} | （失败：{r.get('error', '?')}） | — |")
    (output_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
