"""Characterize optional seed values and frozen metadata during helper extraction."""

from copy import deepcopy
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.services.scheduler.run.schedule_input_seed_metadata import with_frozen_external_seed_metadata
from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_result_item


@pytest.mark.parametrize("field", ["machine_id", "operator_id", "op_type_name", "seed_source", "state_revision"])
@pytest.mark.parametrize("value,expected", [(None, None), ("", None), (0, None), (False, None), (42, "42"), (" X ", " X ")])
def test_optional_seed_text_preserves_existing_coercion(field, value, expected):
    start = datetime(2026, 9, 8, 8)
    seed = {"op_id": 1, "batch_id": "B1", "seq": 1, "start_time": start, "end_time": start + timedelta(hours=1),
            field: value}
    before = deepcopy(seed)
    result = coerce_seed_result_item(seed, idx=0)
    assert getattr(result, field) == expected
    assert seed == before


@pytest.mark.parametrize("mode", ["", "separate", "merged"])
def test_seed_enrichment_preserves_order_aliasing_and_input_payload(mode):
    external = {"op_id": 1, "batch_id": "B1", "seq": 1, "source": "external"}
    untouched = {"op_id": 2, "source": "internal"}
    seeds = [untouched, external]
    before = deepcopy(seeds)
    op = SimpleNamespace(id=1, batch_id="B1", seq=1, source="external", ext_merge_mode=mode, ext_group_id="G1")
    result = with_frozen_external_seed_metadata(seeds, frozen_op_ids={1}, algo_ops=[op])
    assert seeds == before
    assert result[0] is untouched
    if mode == "merged":
        assert result[1] is not external
        assert result[1]["_external_group_metadata"] == {"op_id": 1, "batch_id": "B1", "ext_group_id": "G1"}
    else:
        assert result[1] is external
    assert with_frozen_external_seed_metadata(seeds, frozen_op_ids=set(), algo_ops=[]) is seeds
