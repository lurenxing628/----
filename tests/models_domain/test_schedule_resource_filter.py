"""回归测试：派工资源筛选 collar 保留 team 双 join、人员/设备空 id 全量、空班组全量，并且不污染旧报表/超期过滤器的缺 id 拦截。"""

from __future__ import annotations

import pytest

from core.infrastructure.errors import ValidationError
from core.models.schedule_resource_filter import (
    normalize_dispatch_resource_filter,
    normalize_schedule_resource_filter,
)


def test_dispatch_resource_filter_builds_team_join_predicate() -> None:
    resource_filter = normalize_dispatch_resource_filter("team", "TEAM-OP")

    assert resource_filter.sql_fragment == "((o.team_id = ?) OR (m.team_id = ?))"
    assert resource_filter.params == ("TEAM-OP", "TEAM-OP")
    assert resource_filter.include_team_context is True
    assert resource_filter.has_filter is True


@pytest.mark.parametrize(
    ("resource_type", "expected_sql"),
    (
        ("operator", "TRIM(COALESCE(s.operator_id, '')) <> ''"),
        ("machine", "TRIM(COALESCE(s.machine_id, '')) <> ''"),
    ),
)
def test_dispatch_resource_filter_empty_operator_or_machine_id_means_all(resource_type: str, expected_sql: str) -> None:
    resource_filter = normalize_dispatch_resource_filter(resource_type, "")

    assert resource_filter.sql_fragment == expected_sql
    assert resource_filter.params == ()
    assert resource_filter.include_team_context is False
    assert resource_filter.has_filter is True


def test_dispatch_resource_filter_empty_team_id_means_all() -> None:
    resource_filter = normalize_dispatch_resource_filter("team", "")

    assert resource_filter.sql_fragment == ""
    assert resource_filter.params == ()
    assert resource_filter.include_team_context is False
    assert resource_filter.has_filter is False


def test_dispatch_resource_filter_rejects_bad_scope_type_loudly() -> None:
    with pytest.raises(ValidationError) as exc_info:
        normalize_dispatch_resource_filter("bad", "R-1")

    assert exc_info.value.field == "resource_type"


def test_dispatch_resource_filter_does_not_loosen_shared_schedule_filter() -> None:
    with pytest.raises(ValidationError) as missing_id:
        normalize_schedule_resource_filter("operator", "")
    with pytest.raises(ValidationError) as unsupported_team:
        normalize_schedule_resource_filter("team", "TEAM-OP")

    assert missing_id.value.field == "resource_id"
    assert unsupported_team.value.field == "resource_type"
