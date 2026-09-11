"""Read/construct review payload in memory; no product-file mutation."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[3]
PAYLOAD = ROOT / "draft-payload"
RENDER_TARGETS = (
    ("web/routes/excel_demo.py", "excel/demo.html", "workbench/legacy_result.html"),
    ("web/routes/personnel_excel_links.py", "personnel/excel_import_operator_machine.html", "workbench/legacy_result.html"),
    ("web/routes/personnel_excel_operator_calendar.py", "personnel/excel_import_operator_calendar.html", "workbench/legacy_result.html"),
    ("web/routes/personnel_excel_operators.py", "personnel/excel_import_operator.html", "workbench/legacy_result.html"),
    ("web/routes/equipment_excel_links.py", "equipment/excel_import_machine_operator.html", "workbench/legacy_result.html"),
    ("web/routes/equipment_excel_machines.py", "equipment/excel_import_machine.html", "workbench/legacy_result.html"),
    ("web/routes/process_excel_op_types.py", "process/excel_import_op_types.html", "workbench/legacy_result.html"),
    ("web/routes/process_excel_part_operation_hours.py", "process/excel_import_part_operation_hours.html", "workbench/legacy_result.html"),
    ("web/routes/process_excel_routes.py", "process/excel_import_routes.html", "workbench/legacy_result.html"),
    ("web/routes/process_excel_suppliers.py", "process/excel_import_suppliers.html", "workbench/legacy_result.html"),
    ("web/routes/domains/scheduler/scheduler_excel_batches.py", "scheduler/excel_import_batches.html", "workbench/legacy_result.html"),
    ("web/routes/domains/scheduler/scheduler_excel_calendar.py", "scheduler/excel_import_calendar.html", "workbench/legacy_result.html"),
    ("web/routes/domains/scheduler/scheduler_week_plan_print.py", "scheduler/week_plan_print.html", "workbench/print.html"),
    ("web/routes/domains/scheduler/scheduler_config.py", "scheduler/config_manual.html", "workbench/manual.html"),
)


def render_source(path, old, new):
    before = (REPO / path).read_text(encoding="utf-8")
    source = ast.parse(before)
    matches = [node for node in ast.walk(source) if isinstance(node, ast.Call)
               and isinstance(node.func, ast.Name) and node.func.id == "render_template"
               and node.args and isinstance(node.args[0], ast.Str) and node.args[0].s == old]
    if len(matches) != 1:
        raise ValueError("Expected one explicit template renderer: " + path)
    literal = ast.get_source_segment(before, matches[0].args[0])
    if literal is None or before.count(literal) != 1:
        raise ValueError("Template replacement is ambiguous: " + path)
    replacement = repr(new)
    after = before.replace(literal, replacement, 1)
    restored = after.replace(replacement, literal, 1)
    if ast.dump(ast.parse(restored)) != ast.dump(source):
        raise AssertionError("Candidate changed behavior beyond a template target.")
    return before, after, matches[0].lineno
