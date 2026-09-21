"""真机部分：排产配置与批次提示在浏览器里渲染出来必须是规范中文。

从 test_frontend_ui_language_polish.py 拆出来（2026-09-21）。原来两者在同一个文件里，
而浏览器车道是**按文件**判定的（tools/browser_lane_files.py:180-193）：整文件因为
import 了一个需要浏览器的支持模块就被标 perf，连带 17 条纯读文件的用例一起被踢出所有
门禁。2026-09-18 删旧路由层后那 17 条里烂了 8 条，三天没人发现。

拆开之后：纯读文件的那一半进日常门禁，真机这一半留在浏览器车道。
"""

from __future__ import annotations

from tests._support.paths import REPO_ROOT
from tests._support.workbench_browser_contract import browser_contract


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def test_scheduler_config_and_batch_hints_are_user_facing_chinese() -> None:
    browser_contract("""
const value = {type:'work',hours:'8',eff:'100',allowNormal:'yes',allowUrgent:'no',note:''};
expect(window.APSCalendarContract.input(value).eff === 100);
for (const eff of ['', '0', '-1', 'bad', '201']) {
  let message = '';
  try { window.APSCalendarContract.input({...value,eff}); } catch(error) { message = error.message; }
  expect(message === '效率须大于 0 且不超过 200%。', 'Bad efficiency was accepted or leaked an internal field name');
}
const node = await render(React.createElement(window.PreflightControls.Rules,
  {value:{ready_check:true,missing_resource_policy:'auto_assign'},onChange:()=>{},disabled:false}));
expect(node.textContent.includes('缺资源工序'));
expect(node.textContent.includes('自动分配') && node.textContent.includes('暂不排'));
expect(node.textContent.includes('已开工工序：保留记录（不可修改）'));
expect(!node.textContent.includes('missing_resource_policy') && !node.textContent.includes('strict_mode'));
return true;
""", scripts=("static/workbench/app/resource-contract.js", "static/workbench/app/ResourceControls.js",
              "static/workbench/app/CalendarContract.js", "static/workbench/app/PreflightControls.js"))
    batch = _read("frontend/workbench/app/BatchDetail.jsx")
    assert "刷新详情" in batch
    assert "B.label('status', entity.status)" in batch
    assert "解析器不支持 strict_mode" not in batch
    calendar = _read("frontend/workbench/app/CalendarFields.jsx")
    assert "效率（%）" in calendar and "可排工时（小时）" in calendar
    assert "假期安排生产但未单独设置效率时" not in calendar


def test_process_source_labels_render_chinese_in_the_browser() -> None:
    """工艺归属的中文映射在真机上成立。

    原来挂在 test_process_excel_current_tables_render_chinese_display_fields 里，
    那条用例的主体（旧 Excel 预览页）已整体退役，只有这一段还有对象。
    """
    browser_contract("""
expect(window.APSProcessContract.sourceLabel('internal') === '自制');
expect(window.APSProcessContract.sourceLabel('external') === '外协');
expect(window.APSProcessContract.sourceLabel('unknown') === '未归类');
return true;
""", scripts=("static/workbench/app/resource-contract.js", "static/workbench/app/ProcessContract.js"))
