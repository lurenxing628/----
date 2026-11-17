"""The two prepared shapes of one snapshot's process-template facts, both built by ``ProcessFactScope``.

``ProcessRawFacts`` is the template rows and the identity rows naming them; ``ProcessFacts`` adds the reference
catalogs those rows are judged against and every part's workflow.
"""

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping

from core.services.process.template_source import TemplateSourceFacts
from core.services.process.workflow_state import project_operation_confirmation, project_part_workflow

Row = Dict[str, Any]


@dataclass(frozen=True)
class ProcessRawFacts:
    """Parts, all their operations (active and deleted) and external groups, with the identity rows naming them.

    In a ``ProcessFacts`` the identities also name the shared op types and suppliers.
    """

    parts: List[Row]
    operations: List[Row]
    groups: List[Row]
    identities: List[Row]


@dataclass(frozen=True)
class PartWorkflow:
    """A part's stage workflow and the confirmations of every one of its operations, by operation id."""

    workflow: Row
    confirmations: Dict[int, Row]


@dataclass(frozen=True)
class ProcessWorkflowFacts:
    source_facts: TemplateSourceFacts
    parts: Dict[str, PartWorkflow]

    def confirmation(self, operation: Mapping[str, Any]) -> Row:
        return self.parts[operation["part_no"]].confirmations[operation["id"]]


@dataclass(frozen=True)
class ProcessFacts:
    raw: ProcessRawFacts
    references: Dict[str, List[Row]]
    workflow: ProcessWorkflowFacts


def workflow_facts(rows: ProcessRawFacts, suppliers: Mapping[str, List[Row]]) -> ProcessWorkflowFacts:
    """Source rules and workflow of ``rows``' parts; ``suppliers`` holds the Suppliers, WorkbenchSupplierOpTypes
    and WorkbenchSupplierProfiles rows those rules read."""
    by_part = defaultdict(list)
    for op in rows.operations:
        by_part[op["part_no"]].append(op)
    source_facts = TemplateSourceFacts(rows.operations, rows.groups, suppliers["Suppliers"],
                                       suppliers["WorkbenchSupplierOpTypes"], suppliers["WorkbenchSupplierProfiles"])
    parts = {}
    for part in rows.parts:
        operations = by_part[part["part_no"]]
        parts[part["part_no"]] = PartWorkflow(
            project_part_workflow(part, any(op["status"] == "active" for op in operations)),
            {op["id"]: project_operation_confirmation(op) for op in operations},
        )
    return ProcessWorkflowFacts(source_facts, parts)
