"""Workbench adapter for the shared process quota protection contract."""

from core.services.process.quota_protection import (
    ProcessQuotaProtection,
    quota_skip,
    quota_skip_summary,
    read_quota_locks,
    require_adoption_schema,
)

__all__ = ["ProcessQuotaProtection", "quota_skip", "quota_skip_summary", "read_quota_locks", "require_adoption_schema"]
