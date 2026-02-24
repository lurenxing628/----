from __future__ import annotations

import os
import re


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


def main() -> None:
    repo_root = _find_repo_root()

    common_js = _read(os.path.join(repo_root, "static", "js", "common.js"))
    excel_js = _read(os.path.join(repo_root, "static", "js", "excel_handler.js"))
    base_html = _read(os.path.join(repo_root, "templates", "base.html"))
    gantt_html = _read(os.path.join(repo_root, "templates", "scheduler", "gantt.html"))
    personnel_html = _read(os.path.join(repo_root, "templates", "personnel", "list.html"))
    equipment_html = _read(os.path.join(repo_root, "templates", "equipment", "list.html"))
    process_html = _read(os.path.join(repo_root, "templates", "process", "list.html"))
    batches_html = _read(os.path.join(repo_root, "templates", "scheduler", "batches.html"))
    config_html = _read(os.path.join(repo_root, "templates", "scheduler", "config.html"))

    # 1) common.js 核心交互契约
    _assert_contains(common_js, "form[data-confirm]", "common.js 应处理 form[data-confirm]")
    _assert_contains(
        common_js,
        "button[data-confirm], input[type='submit'][data-confirm], a[data-confirm]",
        "common.js 应处理按钮/链接 data-confirm",
    )
    _assert_contains(common_js, "select[data-auto-submit='1']", "common.js 应处理 data-auto-submit")
    _assert_contains(common_js, 'new Event("submit"', "auto-submit 回退应先派发 submit 事件")
    _assert_contains(common_js, "markRequiredLabels", "应包含 required label 自动标记逻辑")
    _assert_contains(common_js, "MutationObserver", "应包含 required label 监听兜底")
    _assert_contains(common_js, "data-table-search", "应包含表格前端搜索入口")
    _assert_contains(common_js, "debounce(applySearch", "应包含搜索防抖")

    # 2) excel_handler.js 验证兜底契约
    _assert_contains(excel_js, "setCustomValidity", "excel_handler 应设置自定义校验提示")
    _assert_contains(excel_js, "reportValidity", "excel_handler 应优先使用 reportValidity")
    _assert_contains(excel_js, "js-file-required-hint", "excel_handler 应包含可见提示兜底")
    _assert_contains(excel_js, "aria-invalid", "excel_handler 应设置 aria-invalid 兜底")

    # 3) 模板契约：脚本加载与 A11y
    if re.search(
        r"<script\s+src=\"\{\{\s*url_for\('static',\s*filename='js/common.js'\)\s*\}\}\"\s+defer\s*></script>",
        base_html,
    ) is None:
        raise RuntimeError("base.html 中 common.js 应以 defer 方式加载")

    _assert_contains(gantt_html, 'role="alert"', "gantt 错误区应具备 alert 语义")
    _assert_contains(gantt_html, 'aria-live="assertive"', "gantt 错误区应具备 aria-live")
    _assert_contains(gantt_html, 'aria-label="批次筛选，输入批次号关键词"', "gantt 批次筛选应具备 aria-label")
    _assert_contains(gantt_html, 'aria-label="仅显示超期任务"', "gantt 复选框应具备 aria-label")

    _assert_contains(personnel_html, 'aria-label="搜索人员，输入工号或姓名关键词"', "人员列表搜索应具备 aria-label")
    _assert_contains(equipment_html, 'aria-label="搜索设备，输入设备编号或名称关键词"', "设备列表搜索应具备 aria-label")
    _assert_contains(process_html, 'aria-label="搜索零件，输入图号或名称关键词"', "工艺列表搜索应具备 aria-label")

    # 4) data-auto-submit 页面契约
    _assert_contains(batches_html, 'data-auto-submit="1"', "批次页应使用 data-auto-submit")
    _assert_contains(config_html, 'data-auto-submit="1"', "配置页应使用 data-auto-submit")

    print("OK")


if __name__ == "__main__":
    main()

