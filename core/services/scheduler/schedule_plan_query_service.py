"""Compatibility exports from the shared read-only plan owner."""

from __future__ import annotations

from core.services.common.plan_query import (
    ROLE_ADOPTED as ROLE_ADOPTED,
)
from core.services.common.plan_query import (
    ROLE_BASELINE_BEST as ROLE_BASELINE_BEST,
)
from core.services.common.plan_query import (
    ROLE_CRITICAL_BEST as ROLE_CRITICAL_BEST,
)
from core.services.common.plan_query import (
    SOURCE_ADJUSTMENT_SCENARIO_ROWS as SOURCE_ADJUSTMENT_SCENARIO_ROWS,
)
from core.services.common.plan_query import (
    SOURCE_CANDIDATE_ROWS as SOURCE_CANDIDATE_ROWS,
)
from core.services.common.plan_query import (
    SOURCE_SCHEDULE as SOURCE_SCHEDULE,
)
from core.services.common.plan_query import (
    VALID_PLAN_ROLES as VALID_PLAN_ROLES,
)
from core.services.common.plan_query import (
    Any as Any,
)
from core.services.common.plan_query import (
    Dict as Dict,
)
from core.services.common.plan_query import (
    List as List,
)
from core.services.common.plan_query import (
    Optional as Optional,
)
from core.services.common.plan_query import (
    ScheduleDetailRow as ScheduleDetailRow,
)
from core.services.common.plan_query import (
    ScheduleDispatchRow as ScheduleDispatchRow,
)
from core.services.common.plan_query import (
    SchedulePlanQueryRepository as SchedulePlanQueryRepository,
)
from core.services.common.plan_query import (
    SchedulePlanQueryService as SchedulePlanQueryService,
)
from core.services.common.plan_query import (
    SchedulePlanResolution as SchedulePlanResolution,
)
from core.services.common.plan_query import (
    SchedulePlanRoleOption as SchedulePlanRoleOption,
)
from core.services.common.plan_query import (
    ScheduleTimeSpanRow as ScheduleTimeSpanRow,
)
from core.services.common.plan_query import _normalize_role as _normalize_role
from core.services.common.plan_query import (
    build_plan_identity as build_plan_identity,
)
from core.services.common.plan_query import (
    is_comparison_plan as is_comparison_plan,
)
from core.services.common.plan_query import (
    latest_official_version as latest_official_version,
)
from core.services.common.plan_query import (
    normalize_overdue_resource_filter as normalize_overdue_resource_filter,
)
from core.services.common.plan_query import (
    plan_candidate_label as plan_candidate_label,
)
from core.services.common.plan_query import (
    plan_role_label as plan_role_label,
)
from core.services.common.plan_query import (
    replace as replace,
)
from core.services.common.plan_query import (
    sqlite3 as sqlite3,
)
