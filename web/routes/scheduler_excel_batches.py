from __future__ import annotations

# Behavior-compatible root facade. Patch internals at the domain module path.
from ._scheduler_compat import load_scheduler_route_module

_impl = load_scheduler_route_module(".domains.scheduler.scheduler_excel_batches")

_batch_baseline_extra_state = _impl._batch_baseline_extra_state
_build_parts_cache = _impl._build_parts_cache
_build_template_ops_snapshot = _impl._build_template_ops_snapshot
bp = _impl.bp
excel_batches_confirm = _impl.excel_batches_confirm
excel_batches_export = _impl.excel_batches_export
excel_batches_page = _impl.excel_batches_page
excel_batches_preview = _impl.excel_batches_preview
excel_batches_template = _impl.excel_batches_template

__all__ = [
    "_batch_baseline_extra_state",
    "_build_parts_cache",
    "_build_template_ops_snapshot",
    "bp",
    "excel_batches_confirm",
    "excel_batches_export",
    "excel_batches_page",
    "excel_batches_preview",
    "excel_batches_template",
]
