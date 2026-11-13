"""CSV formula-injection defence.

Excel, LibreOffice and Google Sheets evaluate a cell whose text starts with
``=``, ``+``, ``-`` or ``@``. A leading TAB or CR is also treated as a formula
continuation by some importers. Any exported cell can therefore run a formula
(or a DDE/`=HYPERLINK` payload) on the reviewer's machine when the CSV is
opened — the "CSV injection" class of bug.

Every CSV this platform writes goes through :func:`escape_cell`, which prefixes
such a cell with a single quote. Spreadsheet applications then show the literal
text instead of evaluating it. Numeric values are left untouched so real
numbers (including negatives) keep their type.
"""
from __future__ import annotations

import csv
from typing import Any, Iterable, Sequence

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
NEUTRALISER = "'"


def escape_cell(value: Any) -> Any:
    """Neutralise a spreadsheet formula prefix on a string cell.

    Non-string values (int, float, None, dates) pass through unchanged so
    numeric columns stay numeric.
    """
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        return NEUTRALISER + value
    return value


def escape_row(row: Iterable[Any]) -> list[Any]:
    return [escape_cell(value) for value in row]


class _SafeWriter:
    """Thin proxy around ``csv.writer`` that escapes every cell it writes."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def writerow(self, row: Sequence[Any]):
        return self._inner.writerow(escape_row(row))

    def writerows(self, rows: Iterable[Sequence[Any]]):
        return self._inner.writerows(escape_row(row) for row in rows)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


class DictWriter(csv.DictWriter):
    """``csv.DictWriter`` whose values are escaped before serialisation."""

    def _dict_to_list(self, rowdict):  # type: ignore[override]
        return [escape_cell(value) for value in super()._dict_to_list(rowdict)]


def writer(fileobj: Any, **kwargs: Any) -> _SafeWriter:
    """Drop-in replacement for ``csv.writer`` with escaping enabled."""
    return _SafeWriter(csv.writer(fileobj, **kwargs))


def dict_writer(fileobj: Any, fieldnames: Sequence[str], **kwargs: Any) -> DictWriter:
    """Drop-in replacement for ``csv.DictWriter`` with escaping enabled."""
    return DictWriter(fileobj, fieldnames=fieldnames, **kwargs)
