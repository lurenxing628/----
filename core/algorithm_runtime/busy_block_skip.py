"""Skip only fully occupied time inside a certified constant native work window."""

import inspect
from datetime import datetime


def advance_busy_block(calendar, *, earliest, shift_to, segment_groups, total_base, priority, operator_id, abort_after):
    if total_base <= 0 or abort_after is not None:
        return shift_to
    # An overlay's __getattr__ must not borrow its underlying calendar's proof.
    if inspect.getattr_static(calendar, "certified_slot_window", None) is None:
        return shift_to
    certify = calendar.certified_slot_window
    window = certify(earliest, priority=priority, operator_id=operator_id)
    if window is None:
        return shift_to
    if (type(window) is not tuple or len(window) != 2 or any(type(value) is not datetime for value in window)
            or not window[0] <= earliest < window[1]):
        raise RuntimeError("Calendar returned an invalid constant work-window certificate")
    if shift_to >= window[1]:
        return shift_to
    covered = [index.covered_end(shift_to) for index in segment_groups]
    reachable = [end for end in covered if end is not None and shift_to < end <= window[1]]
    return max(reachable, default=shift_to)
