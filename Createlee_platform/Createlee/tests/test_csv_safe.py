"""Tests for CSV formula-injection neutralisation (HI-08)."""
from __future__ import annotations

import csv
import io

import pytest

import core
import csv_safe
import evidence
import handoff
import library


@pytest.mark.parametrize("payload", [
    "=cmd|' /C calc'!A0",
    "+1+1",
    "-2+3",
    "@SUM(A1:A9)",
    "\t=1+1",
    "\r=1+1",
])
def test_every_formula_prefix_is_neutralised(payload):
    escaped = csv_safe.escape_cell(payload)
    assert escaped == "'" + payload
    assert escaped[0] not in csv_safe.FORMULA_PREFIXES


@pytest.mark.parametrize("value", [
    "plain text",
    "a=b",
    "value+1",
    "",
    None,
    42,
    -7,
    3.5,
])
def test_safe_and_numeric_values_are_unchanged(value):
    assert csv_safe.escape_cell(value) == value


def test_plain_writer_escapes_every_row():
    buf = io.StringIO()
    csv_safe.writer(buf, lineterminator="\n").writerows([
        ["=1+1", "ok"],
        ["@x", "-3"],
    ])
    rows = list(csv.reader(io.StringIO(buf.getvalue())))
    assert rows == [["'=1+1", "ok"], ["'@x", "'-3"]]


def test_dict_writer_escapes_values_but_keeps_header():
    buf = io.StringIO()
    writer = csv_safe.dict_writer(buf, ["name", "formula"], lineterminator="\n")
    writer.writeheader()
    writer.writerow({"name": "=HYPERLINK(\"http://x\")", "formula": 5})
    rows = list(csv.reader(io.StringIO(buf.getvalue())))
    assert rows[0] == ["name", "formula"]
    assert rows[1] == ["'=HYPERLINK(\"http://x\")", "5"]


def test_core_csv_export_neutralises_record_values():
    doc = {
        "meta": {
            "document_id": "CL-TEST", "generated_at_iso8601": "2026-11-13T00:00:00Z",
            "time_standard": "ISO-8601 / UTC", "domain": "QA",
            "document_type": "qa_report", "review_status": "DRAFT",
            "source_files": ["=evil.csv"],
        },
        "sections": [],
        "records": [{"note": "=1+1", "count": 3}],
        "disclaimer": "test",
    }
    text = core.to_csv(doc).decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    header = rows[0]
    note = header.index("note")
    assert rows[1][note] == "'=1+1"
    assert rows[1][header.index("count")] == "3"


def test_evidence_handoff_and_library_writers_neutralise(tmp_path):
    evidence._write(tmp_path / "e.csv", ["v"], [["=1+1"]])
    handoff._w(tmp_path / "h.csv", ["v"], [["=1+1"]])
    library._w(tmp_path / "l.csv", ["v"], [["=1+1"]])
    for name in ("e.csv", "h.csv", "l.csv"):
        rows = list(csv.reader((tmp_path / name).open(encoding="utf-8")))
        assert rows[1] == ["'=1+1"], name


def test_generated_evidence_exports_are_inert(tmp_path):
    evidence.generate_exports(tmp_path, as_of="2026-11-06")
    for path in sorted(tmp_path.glob("*.csv")):
        for row in csv.reader(path.open(encoding="utf-8-sig")):
            for cell in row:
                assert not cell.startswith(csv_safe.FORMULA_PREFIXES), (path.name, cell)
