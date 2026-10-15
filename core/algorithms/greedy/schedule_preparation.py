"""Fixed native inputs prepared for one owned scheduling run."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.algorithm_runtime.checkpoint_calendar import checkpoint_calendar_signature
from core.algorithm_runtime.checkpoint_inputs import input_value


@dataclass(frozen=True)
class NativeSchedulePreparation:
    input_reference: Optional[Dict[str, List[Tuple[datetime, datetime]]]]
    normalized_machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]]
    calendar: Any = None
    _calendar_signature: Optional[Tuple[Any, ...]] = field(init=False, compare=False, repr=False, default=None)

    def checkpoint_calendar_component(self) -> Tuple[Any, ...]:
        """Read and encode the complete fixed calendar only when a checkpoint needs it."""
        component = self._calendar_signature
        if component is None:
            component = input_value(checkpoint_calendar_signature(self.calendar), field="calendar_signature")
            object.__setattr__(self, "_calendar_signature", component)
        return component
