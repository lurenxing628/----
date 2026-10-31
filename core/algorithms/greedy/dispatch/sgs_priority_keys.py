"""The admitted graph-key value shared by normalization and ready-set consumers."""
from typing import FrozenSet, Optional, Tuple


class ValidatedGraphPriorityKeys(dict):
    """Decode-owned normalized keys; admission already checked every number.

    ``schedulable_ids`` is the exact operation-id set admission checked these keys
    against: handing the same object back for an equal set needs no second admission.
    ``preorder`` is the optimizer's memo of the keys' weak order, None until the
    holder first computes it. ``key_width`` is the common key length admission
    measured, 0 when the lengths differ or there are no keys. Keys, the id set and
    the width never change after admission.
    """

    def __init__(self, schedulable_ids: FrozenSet[int]) -> None:
        super().__init__()
        self.schedulable_ids = schedulable_ids
        self.preorder: Optional[Tuple[Tuple[int, ...], ...]] = None
        self.key_width = 0
