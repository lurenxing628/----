"""Native policy fields include the exact immutable prepared period offsets."""

import operator

from core.algorithm_runtime.native_snapshot import UNSUPPORTED, scalar_tuple_snapshot


def policy_field_snapshot(fields, values, previous=None):
    if previous is not None and len(values) == len(previous[0]) and all(map(operator.is_, values, previous[0])):
        return previous
    if any(type(field) is not str for field in fields):
        return UNSUPPORTED
    scalar_values = []
    for field, value in zip(fields, values):
        if field == "_period_offsets" and value is not None:
            if (type(value) is not tuple or any(type(pair) is not tuple or len(pair) != 2
                                              or any(type(point) is not int for point in pair) for pair in value)):
                return UNSUPPORTED
        else:
            scalar_values.append(value)
    if scalar_tuple_snapshot(tuple(scalar_values)) is UNSUPPORTED:
        return UNSUPPORTED
    return values, tuple(map(type, values))
