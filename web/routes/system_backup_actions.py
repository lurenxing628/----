"""Compatibility names for the shared backup restore service."""

from core.services.system.backup_restore import RestoreBackupOutcome, run_backup_restore

__all__ = ["RestoreBackupOutcome", "run_backup_restore"]
