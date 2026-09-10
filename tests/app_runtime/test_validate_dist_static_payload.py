"""回归测试：validate_dist_exe 对 static 关键载荷的验收护栏（2026-07-19 盲区扫描 B14）。

static 缺失/半缺失时，static_versioning 只会 _warn_once 后回退原始 URL，页面照常 200，
冷启动验收/健康检查/页面冒烟全部通过——所以验收脚本必须在文件层与 HTTP 层直接断言。
本文件锁三件事：
  1) _assert_static_bundled 的判定行为（缺失/空文件必红，根目录或 _internal 布局均可过）；
  2) 锚点必须存在于真实 manifest、由新入口模板加载，并通过 HTTP 返回原始字节；
  3) main() 验收流程必须真的调用文件层断言并对锚点做 HTTP 冒烟（防止护栏被静默摘除）。
"""

from __future__ import annotations

import ast
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

import pytest
from flask import Flask, render_template

import validate_dist_exe as mod
from tests._support.paths import REPO_ROOT


class _StaticReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.paths = set()

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "script" and values.get("src"):
            self.paths.add(values["src"])
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.paths.add(values["href"])


def _install_anchor_files(exe_dir: Path, base_subdir: str = "") -> None:
    base = exe_dir / base_subdir if base_subdir else exe_dir
    for rel in mod._STATIC_BUNDLE_ANCHORS:
        target = base.joinpath(*rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"payload")


def test_assert_static_bundled_fails_when_all_anchors_missing(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError) as excinfo:
        mod._assert_static_bundled(str(tmp_path))
    message = str(excinfo.value)
    for rel in mod._STATIC_BUNDLE_ANCHORS:
        assert rel in message


def test_assert_static_bundled_fails_when_anchor_is_empty_file(tmp_path: Path) -> None:
    _install_anchor_files(tmp_path)
    empty_rel = mod._STATIC_BUNDLE_ANCHORS[0]
    tmp_path.joinpath(*empty_rel.split("/")).write_bytes(b"")
    with pytest.raises(RuntimeError) as excinfo:
        mod._assert_static_bundled(str(tmp_path))
    assert empty_rel in str(excinfo.value)


def test_assert_static_bundled_passes_with_exe_root_layout(tmp_path: Path) -> None:
    _install_anchor_files(tmp_path)
    mod._assert_static_bundled(str(tmp_path))


def test_assert_static_bundled_passes_with_internal_layout(tmp_path: Path) -> None:
    _install_anchor_files(tmp_path, base_subdir="_internal")
    mod._assert_static_bundled(str(tmp_path))


def test_static_anchors_exist_in_repo_and_are_referenced_by_base_template() -> None:
    assert mod._STATIC_BUNDLE_ANCHORS, "static 验收锚点清单不能为空"
    css_anchors = [rel for rel in mod._STATIC_BUNDLE_ANCHORS if rel.endswith(".css")]
    js_anchors = [rel for rel in mod._STATIC_BUNDLE_ANCHORS if rel.endswith(".js")]
    assert css_anchors and js_anchors, "锚点至少要各覆盖一个核心 css 与 js 载荷"

    manifest = json.loads((REPO_ROOT / "static/workbench/asset-manifest.json").read_text(encoding="utf-8"))
    records = {row["path"]: row for row in manifest["files"]}
    loaded = set(manifest["styles"] + manifest["scripts"] + [manifest["theme_script"]])
    app = Flask(__name__, template_folder=str(REPO_ROOT / "templates"), static_folder=str(REPO_ROOT / "static"))
    references = _StaticReferences()
    with app.test_request_context("/workbench?view=system"):
        references.feed(render_template("workbench/index.html", assets=manifest,
                                        boot={"view": "system", "titles": {"system": "System"}}))
    for rel in mod._STATIC_BUNDLE_ANCHORS:
        assert rel.startswith("static/"), f"锚点必须位于 static/ 下：{rel}"
        source = REPO_ROOT.joinpath(*rel.split("/"))
        assert source.is_file(), f"仓库内缺少 static 锚点：{rel}"
        assert source.stat().st_size > 0, f"static 锚点在仓库内是空文件：{rel}"
        filename = rel[len("static/"):]
        assert filename in loaded and filename in records, f"锚点未在真实入口 manifest 中加载：{rel}"
        payload = source.read_bytes()
        assert records[filename]["bytes"] == len(payload)
        assert records[filename]["sha256"] == hashlib.sha256(payload).hexdigest()
        assert "/" + rel in references.paths, f"新入口模板未实际引用锚点：{rel}"
        response = app.test_client().get("/" + rel)
        assert response.status_code == 200
        assert response.get_data() == payload


def test_validate_main_invokes_static_guards() -> None:
    """main() 必须调用文件层 static 断言，且用 _STATIC_BUNDLE_ANCHORS 做 HTTP 冒烟。"""
    tree = ast.parse((REPO_ROOT / "validate_dist_exe.py").read_text(encoding="utf-8"))
    main_fn = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    called_names = {
        node.func.id
        for node in ast.walk(main_fn)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    used_names = {node.id for node in ast.walk(main_fn) if isinstance(node, ast.Name)}
    assert "_assert_networkx_bundled" in called_names
    assert "_assert_static_bundled" in called_names, "main() 缺少文件层 static 载荷断言（B14 护栏被摘除）"
    assert "_STATIC_BUNDLE_ANCHORS" in used_names, "main() 缺少对 static 锚点的 HTTP 冒烟（B14 护栏被摘除）"
    assert "_http_get_bytes" in called_names, "static HTTP 冒烟必须取原始字节并断言非空"
