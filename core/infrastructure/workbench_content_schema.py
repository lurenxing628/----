"""Declared content representation; business identities are unchanged."""

from .workbench_dashboard_external_schema import workbench_dashboard_external_objects
from .workbench_dashboard_schema import workbench_dashboard_objects
from .workbench_metadata_schema import metadata_objects
from .workbench_process_workflow_schema import workflow_objects
from .workbench_run_schema import workbench_run_objects
from .workbench_template_lineage_schema import template_lineage_objects
from .workbench_trial_schema import workbench_trial_objects

CONTENT_TABLES = (
    "WorkbenchCommandReceipts",
    "WorkbenchProcessWorkflow", "WorkbenchProcessOperationConfirmations",
    "WorkbenchRunJobs", "WorkbenchRunReceipts", "WorkbenchRunCandidates", "WorkbenchRunCandidateTasks",
    "WorkbenchTrialDrafts", "WorkbenchTrialRows", "WorkbenchTrialChanges",
    "WorkbenchTrialScenarios", "WorkbenchTrialScenarioRows",
    "WorkbenchDashboardHistory", "WorkbenchDashboardExternalHistory",
    "WorkbenchTemplateLineageOrigins",
)


def content_objects():
    result = {}
    for source in (metadata_objects, workflow_objects,
                   workbench_run_objects, workbench_trial_objects,
                   workbench_dashboard_objects, workbench_dashboard_external_objects, template_lineage_objects):
        result.update(source())
    return result
