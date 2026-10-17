"""Trial conflict checks retain ordered evidence without outside/outside work."""

from datetime import datetime, timedelta

from core.models.workbench_trial import issue
from core.services.workbench.trial.constraints import _overlap_issues


def test_overlap_issues_preserve_order_same_operation_exclusion_and_touching_edges():
    start = datetime(2026, 10, 17, 8)

    def interval(left, right, operation, task):
        return start + timedelta(hours=left), start + timedelta(hours=right), operation, task

    intervals = [interval(0, 4, "outside-a", None), interval(1, 3, "trial-a", "task-a"),
                 interval(1, 4, "trial-a", "task-a"), interval(2, 5, "outside-b", None),
                 interval(4, 6, "trial-b", "task-b")]
    expected = [issue("machine_overlap", "设备安排重叠。", "task-a"),
                issue("machine_overlap", "设备安排重叠。", "task-a"),
                issue("machine_overlap", "设备安排重叠。", "task-a"),
                issue("machine_overlap", "设备安排重叠。", "task-a"),
                issue("machine_overlap", "设备安排重叠。", "task-b")]
    assert _overlap_issues({("machine", "M1"): list(reversed(intervals))}) == expected


def test_outside_intervals_are_never_paired_with_each_other():
    class Operation:
        def __init__(self, key, *, trial=False):
            self.key, self.trial = key, trial

        def __ne__(self, other):
            assert self.trial or other.trial, "Outside work must not be compared with outside work"
            return self.key != other.key

    start = datetime(2026, 10, 17, 8)
    outside = [(start, start + timedelta(hours=4), Operation(index), None) for index in range(100)]
    trial = (start + timedelta(hours=4), start + timedelta(hours=5), Operation("trial", trial=True), "task")
    assert _overlap_issues({("machine", "unused"): outside,
                            ("machine", "used"): outside + [trial]}) == []
