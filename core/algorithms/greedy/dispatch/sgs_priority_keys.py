"""The admitted graph-key value shared by normalization and ready-set consumers."""
from typing import Dict, FrozenSet, Tuple


class ValidatedGraphPriorityKeys(dict):
    """Normalized keys admitted once against an exact operation-id set, with their static orders.

    ``schedulable_ids`` is the id set admission checked: handing the same object back for that set
    needs no second admission. Admission fixes one common key width, so ``order`` (ids sorted by
    key, then op_id) and ``preorder`` (that order grouped into equal-key classes) preserve every SGS
    comparison. Keys, the id set and both orders never change after admission.
    """

    def __init__(self, keys: Dict[int, Tuple[float, ...]], *, schedulable_ids: FrozenSet[int],
                 order: Tuple[int, ...], preorder: Tuple[Tuple[int, ...], ...]) -> None:
        super().__init__(keys)
        self.schedulable_ids = schedulable_ids
        self.order = order
        self.preorder = preorder
