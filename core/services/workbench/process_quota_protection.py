"""Workbench adapter for the shared process quota protection contract."""

from core.services.process.quota_protection import ProcessQuotaProtection, quota_skip, quota_skip_summary

__all__ = ["ProcessQuotaProtection", "quota_skip", "quota_skip_summary"]
