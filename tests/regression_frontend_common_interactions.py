from __future__ import annotations

import os
from typing import List


def _find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _assert_contains(text: str, needle: str, msg: str) -> None:
    if needle not in text:
        raise RuntimeError(msg + f"（缺少片段: {needle}）")


def _assert_in_order(text: str, snippets: List[str], msg: str) -> None:
    last_idx = -1
    for snip in snippets:
        idx = text.find(snip)
        if idx < 0:
            raise RuntimeError(msg + f"（缺少片段: {snip}）")
        if idx <= last_idx:
            raise RuntimeError(msg + f"（脚本顺序错误: {snip}）")
        last_idx = idx


def _script_tag(filename: str) -> str:
    return f'<script src="{{{{ url_for(\'static\', filename=\'js/{filename}\') }}}}" defer></script>'


def main() -> None:
    repo_root = _find_repo_root()

    common_js = _read(os.path.join(repo_root, "static", "js", "common.js"))
    required_js = _read(os.path.join(repo_root, "static", "js", "common_required.js"))
    confirm_js = _read(os.path.join(repo_root, "static", "js", "common_confirm.js"))
    table_js = _read(os.path.join(repo_root, "static", "js", "common_table.js"))
    toast_js = _read(os.path.join(repo_root, "static", "js", "common_toast.js"))
    excel_js = _read(os.path.join(repo_root, "static", "js", "excel_handler.js"))

    base_html = _read(os.path.join(repo_root, "templates", "base.html"))
    base_v2_html = _read(os.path.join(repo_root, "web_new_test", "templates", "base.html"))
    style_v2_css = _read(os.path.join(repo_root, "web_new_test", "static", "css", "style.css"))
    gantt_html = _read(os.path.join(repo_root, "templates", "scheduler", "gantt.html"))
    personnel_html = _read(os.path.join(repo_root, "templates", "personnel", "list.html"))
    equipment_html = _read(os.path.join(repo_root, "templates", "equipment", "list.html"))
    process_html = _read(os.path.join(repo_root, "templates", "process", "list.html"))
    batches_html = _read(os.path.join(repo_root, "templates", "scheduler", "batches.html"))
    config_html = _read(os.path.join(repo_root, "templates", "scheduler", "config.html"))

    # 1) common.js 核心命名空间契约
    _assert_contains(common_js, "window.__APS_COMMON__", "common.js 应导出 window.__APS_COMMON__ 命名空间")

    # 2) confirm / auto-submit 契约
    _assert_contains(confirm_js, "form[data-confirm]", "common_confirm.js 应处理 form[data-confirm]")
    _assert_contains(
        confirm_js,
        "button[data-confirm], input[type='submit'][data-confirm], a[data-confirm]",
        "common_confirm.js 应处理按钮/链接 data-confirm",
    )
    _assert_contains(confirm_js, "select[data-auto-submit='1']", "common_confirm.js 应处理 data-auto-submit")
    _assert_contains(confirm_js, 'new Event(\"submit\"', "auto-submit 回退应先派发 submit 事件")

    # 3) required label 契约
    _assert_contains(required_js, "markRequiredLabels", "common_required.js 应包含 required label 自动标记逻辑")
    _assert_contains(required_js, "MutationObserver", "common_required.js 应包含 required label 监听兜底")

    # 4) table search 契约
    _assert_contains(table_js, "data-table-search", "common_table.js 应包含表格前端搜索入口")
    _assert_contains(table_js, "debounce(applySearch", "common_table.js 应包含搜索防抖")

    # 5) toast 契约（table_resize.js 与排序提示依赖）
    _assert_contains(toast_js, "window.APS_Toast", "common_toast.js 应暴露 window.APS_Toast")

    # 6) excel_handler.js 验证兜底契约
    _assert_contains(excel_js, "setCustomValidity", "excel_handler 应设置自定义校验提示")
    _assert_contains(excel_js, "reportValidity", "excel_handler 应优先使用 reportValidity")
    _assert_contains(excel_js, "js-file-required-hint", "excel_handler 应包含可见提示兜底")
    _assert_contains(excel_js, "aria-invalid", "excel_handler 应设置 aria-invalid 兜底")

    # 7) 模板契约：脚本加载顺序 + A11y
    expected = [
        _script_tag("common.js"),
        _script_tag("common_manual_popover.js"),
        _script_tag("common_required.js"),
        _script_tag("common_flash.js"),
        _script_tag("common_theme.js"),
        _script_tag("common_toast.js"),
        _script_tag("common_confirm.js"),
        _script_tag("common_table.js"),
        _script_tag("common_draft.js"),
        _script_tag("common_prefetch.js"),
        _script_tag("table_resize.js"),
    ]
    _assert_in_order(base_html, expected, "templates/base.html 脚本应按约定顺序 defer 加载")
    _assert_in_order(base_v2_html, expected, "web_new_test/templates/base.html 脚本应按约定顺序 defer 加载")
    _assert_contains(base_v2_html, "flash-card flash-{{ category }}", "v2 flash 横幅应复用可关闭的 flash-card 合同")
    _assert_contains(base_v2_html, 'class="flash-close"', "v2 flash 横幅应提供关闭按钮，避免持续遮挡页面")
    _assert_contains(style_v2_css, ".flash-close", "v2 样式应定义 flash 关闭按钮")
    _assert_contains(style_v2_css, "padding-right: 3rem;", "v2 flash 横幅应为关闭按钮预留右侧空间")

    _assert_contains(gantt_html, 'role=\"alert\"', "gantt 错误区应具备 alert 语义")
    _assert_contains(gantt_html, 'aria-live=\"assertive\"', "gantt 错误区应具备 aria-live")
    _assert_contains(gantt_html, 'aria-label=\"批次筛选，输入批次号关键词\"', "gantt 批次筛选应具备 aria-label")
    _assert_contains(gantt_html, 'aria-label=\"仅显示超期任务\"', "gantt 复选框应具备 aria-label")

    _assert_contains(personnel_html, 'aria-label=\"搜索人员，输入工号或姓名关键词\"', "人员列表搜索应具备 aria-label")
    _assert_contains(equipment_html, 'aria-label=\"搜索设备，输入设备编号或名称关键词\"', "设备列表搜索应具备 aria-label")
    _assert_contains(process_html, 'aria-label=\"搜索零件，输入图号或名称关键词\"', "工艺列表搜索应具备 aria-label")

    # 8) data-auto-submit 页面契约
    _assert_contains(batches_html, 'data-auto-submit=\"1\"', "批次页应使用 data-auto-submit")
    _assert_contains(config_html, 'data-auto-submit=\"1\"', "配置页应使用 data-auto-submit")

    print("OK")


if __name__ == "__main__":
    main()
