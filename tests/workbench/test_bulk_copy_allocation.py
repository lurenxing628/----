"""Copy numbering keeps the nearest available suffix without rescanning occupied runs."""

import re

import pytest

from core.models.workbench_batch import MAX_INTEGER
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch.bulk import WorkbenchBatchBulkService


def _nearest(code, used):
    match = re.search(r"([0-9]+)$", code)
    prefix, width = (code[:match.start()], len(match[1])) if match else (code + "-copy-", 1)
    for serial in range((int(match[1]) if match else 0) + 1, MAX_INTEGER + 1):
        candidate = prefix + str(serial).zfill(width)
        if len(candidate) > 200:
            break
        if candidate not in used:
            return candidate
    raise WorkbenchCommandRejected("constraint_conflict", "编号已用完")


def test_copy_numbering_preserves_holes_order_and_colliding_padding_widths():
    sources = ["B099", "B99", "A", "A-copy-1", "B09", "B009", "B099", "B001"]
    initial = {"B100", "B102", "B010", "B10", "B002", *sources}
    used, expected, successors = set(initial), set(initial), {}
    for source in sources:
        actual = WorkbenchBatchBulkService._copy_code(source, used, successors)
        assert actual == _nearest(source, expected)
        used.add(actual)
        expected.add(actual)


def test_copy_numbering_checks_occupied_codes_linearly(record_property):
    class Occupied(set):
        checks = 0

        def __contains__(self, code):
            self.checks += 1
            return super().__contains__(code)

    count = 1000
    used = Occupied("B" + str(index).zfill(5) for index in range(1, count + 1))
    successors = {}
    for index in range(1, count + 1):
        actual = WorkbenchBatchBulkService._copy_code("B" + str(index).zfill(5), used, successors)
        assert actual == "B" + str(count + index).zfill(5)
        used.add(actual)
    assert used.checks < 3 * count
    record_property("copy_code_membership_checks", used.checks)


def test_copy_numbering_keeps_integer_and_length_limits():
    used, successors = {"B" + str(MAX_INTEGER - 1)}, {}
    assert WorkbenchBatchBulkService._copy_code("B" + str(MAX_INTEGER - 1), used, successors) == "B" + str(MAX_INTEGER)
    used.add("B" + str(MAX_INTEGER))
    with pytest.raises(WorkbenchCommandRejected, match="无法为复制批次分配"):
        WorkbenchBatchBulkService._copy_code("B" + str(MAX_INTEGER - 1), used, successors)
    with pytest.raises(WorkbenchCommandRejected, match="无法为复制批次分配"):
        WorkbenchBatchBulkService._copy_code("A" * 200, set(), {})
