from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _prepare_env(tmpdir: Path) -> None:
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = str(tmpdir / "aps_test.db")
    os.environ["APS_LOG_DIR"] = str(tmpdir / "logs")
    os.environ["APS_BACKUP_DIR"] = str(tmpdir / "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = str(tmpdir / "templates_excel")
    os.environ["SECRET_KEY"] = "aps-excel-entry-consolidation"


def _load_app():
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    for name in list(sys.modules):
        if name == "app" or name.startswith("web.bootstrap.entrypoint") or name.startswith("web.bootstrap.factory"):
            sys.modules.pop(name, None)
        if name.startswith("web.routes.scheduler") or name.startswith("web.routes.domains.scheduler"):
            sys.modules.pop(name, None)
    app_mod = importlib.import_module("app")
    return app_mod.create_app()


def _get(client, path: str, *, ui_mode: str = "v1"):
    return client.get(path, headers={"Cookie": f"aps_ui_mode={ui_mode}"})


def _text(resp) -> str:
    assert resp.status_code == 200, resp.get_data(as_text=True)[:1000]
    return resp.get_data(as_text=True)


def _subnav_text(html: str) -> str:
    start = html.find("scheduler-subnav-main")
    assert start >= 0, "页面缺少二级导航"
    end = html.find("</div>", start)
    assert end >= 0, "二级导航 HTML 不完整"
    return html[start:end]


def _assert_subnav_clean(html: str, *, forbidden: list[str], active_label: str) -> None:
    subnav = _subnav_text(html)
    assert active_label in subnav, f"二级导航缺少业务页入口：{active_label}"
    assert "Excel" not in subnav, subnav
    for item in forbidden:
        assert item not in subnav, f"二级导航不应再出现 Excel 入口：{item}"


def _assert_page_contains(client, path: str, phrases: list[str], *, ui_mode: str = "v1") -> str:
    html = _text(_get(client, path, ui_mode=ui_mode))
    for phrase in phrases:
        assert phrase in html, f"{path} 缺少文案：{phrase}"
    return html


def main() -> None:
    tmpdir = Path(tempfile.mkdtemp(prefix="aps_excel_entry_consolidation_"))
    _prepare_env(tmpdir)
    app = _load_app()

    with app.test_client() as client:
        process_html = _assert_page_contains(
            client,
            "/process/",
            ["批量维护", "零件工艺路线", "零件工序工时", "零件工序模板"],
        )
        _assert_subnav_clean(
            process_html,
            forbidden=["零件工艺路线", "零件工序工时", "零件工序模板", "工种配置（Excel）", "供应商配置（Excel）"],
            active_label="零件工艺模板",
        )

        op_types_html = _assert_page_contains(client, "/process/op-types", ["批量维护", "工种配置"])
        _assert_subnav_clean(op_types_html, forbidden=["工种配置（Excel）"], active_label="工种配置")

        suppliers_html = _assert_page_contains(client, "/process/suppliers", ["批量维护", "供应商配置"])
        _assert_subnav_clean(suppliers_html, forbidden=["供应商配置（Excel）"], active_label="供应商配置")

        equipment_html = _assert_page_contains(client, "/equipment/", ["批量维护", "设备信息", "设备人员关联"])
        _assert_subnav_clean(
            equipment_html,
            forbidden=["设备信息（Excel）", "设备人员关联（Excel）"],
            active_label="设备管理",
        )

        personnel_html = _assert_page_contains(
            client,
            "/personnel/",
            ["批量维护", "人员基本信息", "人员设备关联", "人员专属工作日历"],
        )
        _assert_subnav_clean(
            personnel_html,
            forbidden=["人员基本信息（Excel）", "人员设备关联（Excel）", "人员专属工作日历（Excel）"],
            active_label="人员管理",
        )
        assert "人员专属工作日历功能需要更新版本后使用" not in personnel_html

        batches_html = _assert_page_contains(client, "/scheduler/batches", ["批量维护", "批次信息"])
        _assert_subnav_clean(
            batches_html,
            forbidden=["批次信息（Excel 导入/导出）", "工作日历（Excel 导入/导出）"],
            active_label="批次管理",
        )

        calendar_html = _assert_page_contains(client, "/scheduler/calendar", ["导入/导出工作日历"])
        _assert_subnav_clean(
            calendar_html,
            forbidden=["工作日历（Excel 导入/导出）", "批次信息（Excel 导入/导出）"],
            active_label="工作日历配置",
        )

        # v2 当前有批次管理镜像模板，必须同步出现新的入口卡片。
        batches_v2_html = _assert_page_contains(
            client,
            "/scheduler/batches",
            ["批量维护", "批次信息"],
            ui_mode="v2",
        )
        _assert_subnav_clean(
            batches_v2_html,
            forbidden=["批次信息（Excel 导入/导出）", "工作日历（Excel 导入/导出）"],
            active_label="批次管理",
        )

        excel_pages = [
            ("/process/excel/routes", "批量维护零件工艺路线", "零件工艺模板", "返回零件工艺模板"),
            ("/process/excel/part-operation-hours", "批量维护零件工序工时", "零件工艺模板", "返回零件工艺模板"),
            ("/process/excel/part-operations", "导出零件工序模板", "零件工艺模板", "返回零件工艺模板"),
            ("/process/excel/op-types", "批量维护工种配置", "工种配置", "返回工种配置"),
            ("/process/excel/suppliers", "批量维护供应商配置", "供应商配置", "返回供应商配置"),
            ("/equipment/excel/machines", "批量维护设备信息", "设备管理", "返回设备管理"),
            ("/equipment/excel/links", "批量维护设备人员关联", "设备管理", "返回设备管理"),
            ("/personnel/excel/operators", "批量维护人员基本信息", "人员管理", "返回人员管理"),
            ("/personnel/excel/links", "批量维护人员设备关联", "人员管理", "返回人员管理"),
            ("/personnel/excel/operator_calendar", "批量维护人员专属工作日历", "人员管理", "返回人员管理"),
            ("/scheduler/excel/batches", "批量维护批次信息", "批次管理", "返回批次管理"),
            ("/scheduler/excel/calendar", "批量维护工作日历", "工作日历配置", "返回工作日历配置"),
        ]
        for path, title, active_label, back_label in excel_pages:
            html = _assert_page_contains(client, path, [title, active_label, back_label])
            _assert_subnav_clean(
                html,
                forbidden=["Excel 导入/导出", "（Excel）", "批次信息（Excel 导入/导出）", "工作日历（Excel 导入/导出）"],
                active_label=active_label,
            )

        part_ops_html = _text(_get(client, "/process/excel/part-operations"))
        assert "导出（零件工序模板.xlsx）" in part_ops_html
        assert "上传并预览" not in part_ops_html

        batch_excel_html = _text(_get(client, "/scheduler/excel/batches"))
        assert "导入选项" in batch_excel_html
        assert "自动生成/重建工序" in batch_excel_html
        assert "上传并预览" in batch_excel_html

    print("OK")


if __name__ == "__main__":
    main()
