"""Effective processing hours: one stored text per report, exact decimal totals, one public encoding.

A report's hours are an admitted ``int`` or ``float`` (``is_stored_number``). Its stored text is ``str()`` of
that value (``hours_text``), the only text reading accepts, and also the value's exact decimal amount. Totals
are summed exactly in ``Decimal`` and kept as canonical decimal text. A total or a derived amount is not held
to the one-entry upper bound; it only has to be finite and non-negative. Public DTOs carry a total as a number
(``public_hours``).
"""

import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from typing import Iterable, List, NoReturn, Optional, Union

from core.models.workbench_command import WorkbenchCommandRejected
from core.shared.strict_parse import is_stored_number

Hours = Union[int, float]
# An hours amount: one report's admitted value, or an exact Decimal amount such as a stored total.
HoursAmount = Union[int, float, Decimal]


@dataclass(frozen=True)
class HourTotals:
    """Exact hours of a set of reports: ``known`` sums the known hours (None when no report's hours are
    known) and ``unknown`` counts the reports whose hours are unknown."""

    known: Optional[Decimal]
    unknown: int

    @property
    def total(self) -> Optional[Decimal]:
        """The whole set's hours: ``known`` when no report is unknown, None otherwise and for an empty set."""
        return self.known if self.unknown == 0 else None


def _corrupt() -> NoReturn:
    raise WorkbenchCommandRejected("storage_failure", "保存的报工工时已损坏，请核对报工数据；仍不行请联系维护人员。", 500)


def hours_text(value: Hours) -> str:
    """The stored text of one report's admitted hours."""
    return str(value)


def stored_hours(text: object) -> Hours:
    """One report's stored hours text as its value, the one admission of stored report hours: ``int`` when
    the text has no fraction or exponent, ``float`` otherwise, accepted by ``is_stored_number`` and with the
    text exactly its ``hours_text``. Any other spelling (signs, padding, rounded or overlong digits) is corrupt."""
    if type(text) is str:
        try:
            value = int(text) if "." not in text and "e" not in text else float(text)
        except ValueError:
            pass
        else:
            if is_stored_number(value) and hours_text(value) == text:
                return value
    _corrupt()


def stored_exact_hours(text: object) -> Decimal:
    """A stored exact amount (an operation's known total) restored straight to ``Decimal``: finite,
    non-negative and within the range of a public number; no one-entry upper bound."""
    if type(text) is str:
        try:
            amount = Decimal(text)
        except InvalidOperation:
            pass
        else:
            if amount.is_finite() and amount >= 0 and math.isfinite(float(amount)):
                return amount
    _corrupt()


def _exact(amount: HoursAmount) -> Decimal:
    return amount if isinstance(amount, Decimal) else Decimal(hours_text(amount))


def _exact_sum(amounts: List[Decimal]) -> Decimal:
    # The context precision covers every digit of the sum, so no addition rounds.
    with localcontext() as context:
        context.prec = max(
            28,
            max(amount.adjusted() for amount in amounts)
            - min(int(amount.as_tuple().exponent) for amount in amounts)
            + len(str(len(amounts)))
            + 4,
        )
        total = Decimal(0)
        for amount in amounts:
            total += amount
        return total


def sum_hours(amounts: Iterable[Optional[HoursAmount]]) -> HourTotals:
    """Exact totals over a set: ``None`` is one report with unknown hours; any other item is a known amount."""
    known: List[Decimal] = []
    unknown = 0
    for amount in amounts:
        if amount is None:
            unknown += 1
        else:
            known.append(_exact(amount))
    return HourTotals(_exact_sum(known) if known else None, unknown)


def exact_hours_text(amount: HoursAmount) -> str:
    """Canonical decimal text of an amount: no exponent, no trailing fractional zeros, zero is ``"0"``."""
    exact = _exact(amount)
    if exact.is_zero():
        return "0"
    text = format(exact, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def public_hours(amount: Optional[Decimal]) -> Optional[float]:
    """The public number of an exact amount; None (unknown) stays None."""
    return None if amount is None else float(amount)
