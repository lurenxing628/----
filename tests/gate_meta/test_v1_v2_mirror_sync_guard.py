"""镜像逐字节同步守卫：V1/V2 双树的 6 个镜像模板、scheduler_manual.md 与 style.css 双份必须字节级相同。

背景：默认 UI 是 V2 overlay 壳（web_new_test/），其中 6 个页面模板与 V1 同名文件靠人肉双写
维持一致——任何一边单改即漂移，用户在两种界面会看到不同页面。本守卫是双轨拆除
（fusion-dual-track-retirement）前的临时保险，双轨删除后随 web_new_test/ 一并退役。

改了其中一边怎么办：把同一改动应用到另一边（双写），或确认该文件已不再是镜像后
从下方清单移除并在 roadmap aps-frontend-fusion 留痕。

不在清单的同名文件（有意排除，勿补）：base.html——双轨退役步 2 起两边都是 V2 侧栏壳，
但 V1 侧静态链端点是 'static'、V2 overlay 侧是 'ui_v2_static.static'，一行有意差异。
style.css 自步 2 cp 进 static/css/ 后形成临时双份，已入清单（第 8 对），步 4 随守卫整体退役。
"""

from __future__ import annotations

import filecmp

import pytest

from tests._support.paths import REPO_ROOT

_MIRROR_PAIRS = (
    ("templates/dashboard.html", "web_new_test/templates/dashboard.html"),
    ("templates/scheduler/batches.html", "web_new_test/templates/scheduler/batches.html"),
    ("templates/scheduler/batches_manage.html", "web_new_test/templates/scheduler/batches_manage.html"),
    ("templates/scheduler/config.html", "web_new_test/templates/scheduler/config.html"),
    ("templates/scheduler/config_manual.html", "web_new_test/templates/scheduler/config_manual.html"),
    ("templates/scheduler/gantt.html", "web_new_test/templates/scheduler/gantt.html"),
    ("static/docs/scheduler_manual.md", "web_new_test/static/docs/scheduler_manual.md"),
    ("static/css/style.css", "web_new_test/static/css/style.css"),
)


@pytest.mark.parametrize("v1_rel, v2_rel", _MIRROR_PAIRS, ids=[p[0] for p in _MIRROR_PAIRS])
def test_mirror_pair_byte_identical(v1_rel: str, v2_rel: str) -> None:
    v1 = REPO_ROOT / v1_rel
    v2 = REPO_ROOT / v2_rel
    assert v1.is_file(), f"镜像源缺失：{v1_rel}"
    assert v2.is_file(), f"镜像副本缺失：{v2_rel}（若 V2 树已删除，本守卫应随之退役而不是单删文件）"
    assert filecmp.cmp(str(v1), str(v2), shallow=False), (
        f"镜像漂移：{v1_rel} 与 {v2_rel} 内容不同。"
        "两棵模板树靠人肉双写维持一致——请把改动同步到另一边，单边改动会让两种界面行为分叉。"
    )
