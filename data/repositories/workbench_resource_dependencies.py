"""Shared fixed dependency catalog for single and bulk resource deletion."""

DEPENDENCIES = {
    "op_type": (("Machines", "op_type_id"), ("MachineOpTypes", "op_type_id"), ("Suppliers", "op_type_id"), ("OperatorSkill", "op_type_id"),
                ("WorkbenchSupplierOpTypes", "op_type_id"), ("PartOperations", "op_type_id"), ("BatchOperations", "op_type_id")),
    "machine": (("BatchOperations", "machine_id"), ("Schedule", "machine_id"), ("OperatorMachine", "machine_id"),
                ("MachineDowntimes", "machine_id"), ("OperationExecutionEvents", "actual_machine_id"),
                ("OperationExecutionEvents", "affected_machine_id")),
    "operator": (("BatchOperations", "operator_id"), ("Schedule", "operator_id"), ("OperatorMachine", "operator_id"),
                 ("OperatorCalendar", "operator_id"), ("OperationExecutionEvents", "actual_operator_id"),
                 ("OperationExecutionEvents", "affected_operator_id")),
    "supplier": (("PartOperations", "supplier_id"), ("BatchOperations", "supplier_id"), ("ExternalGroups", "supplier_id")),
}
