"""Missing frozen context stops both scheduling modes; no live-template fallback."""

import pytest

from core.errors import ValidationError
from core.services.scheduler.run.schedule_input_builder import build_algo_operations
from tests.schedule.service.external_context_support import SnapshotService, external_operation


@pytest.mark.parametrize("strict", [False, True])
def test_schedule_input_builder_missing_context_fails_closed(strict):
    with pytest.raises(ValidationError) as error:
        build_algo_operations(SnapshotService(None), [external_operation()], strict_mode=strict)
    assert error.value.field == "external_context"
