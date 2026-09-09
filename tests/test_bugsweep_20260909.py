# -*- coding: utf-8 -*-
"""Regressionstests — WinStorePackager Bugsweep-Iteration 2026-09-09.

Prüft:
1. WACK XML-Report Parsing Gesamtergebnis (OVERALL_RESULT):
   Reports mit OVERALL_RESULT="FAIL", "FAILED", "ERROR" oder "CRASH" werden
   strikt als nicht bestanden (passed = False) bewertet, selbst wenn keine einzelnen
   <TEST RESULT="FAIL">-Knoten vorliegen oder vor dem Abbruch Prüfungen bestanden wurden.
2. WACK Testknoten-Fehlerstati:
   Prüfungen mit RESULT="FAILED", RESULT="ERROR" oder RESULT="CRASH" werden
   zuverlässig in failed_tests aufgenommen und führen zum Nichtbestehen.
3. Aussagekräftige Fehlermeldung bei leerem failed_tests:
   Wenn das Gesamtergebnis FAIL/ERROR ist, aber keine einzelnen Testknoten fehlschlugen,
   wird das Gesamtergebnis sauber im Text ausgegeben statt '0 Fehler: '.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import WindowsStorePublisher_3 as wsp


def test_bugsweep_wack_overall_fail_is_not_passed(tmp_path):
    report_file = tmp_path / "wack_overall_fail.xml"
    report_file.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<REPORT OVERALL_RESULT="FAIL">
  <TEST NAME="CheckA" RESULT="PASS" />
  <TEST NAME="CheckB" RESULT="PASS" />
</REPORT>
""",
        encoding="utf-8",
    )

    passed, msg, details = wsp.parse_wack_report(str(report_file))
    assert passed is False
    assert "FEHLGESCHLAGEN" in msg
    assert details["overall"] == "FAIL"
    assert details["failed_count"] == 0
    assert details["passed_count"] == 2


def test_bugsweep_wack_overall_error_is_not_passed(tmp_path):
    report_file = tmp_path / "wack_overall_error.xml"
    report_file.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<REPORT OVERALL_RESULT="ERROR">
  <TEST NAME="CheckA" RESULT="PASS" />
</REPORT>
""",
        encoding="utf-8",
    )

    passed, msg, details = wsp.parse_wack_report(str(report_file))
    assert passed is False
    assert "FEHLGESCHLAGEN" in msg
    assert "ERROR" in msg


def test_bugsweep_wack_failed_and_error_test_results(tmp_path):
    report_file = tmp_path / "wack_test_results.xml"
    report_file.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<REPORT OVERALL_RESULT="PASS">
  <TEST NAME="TestPassing" RESULT="PASS" />
  <TEST NAME="TestPassed" RESULT="PASSED" />
  <TEST NAME="TestFailed" RESULT="FAILED" />
  <TEST NAME="TestError" RESULT="ERROR" />
</REPORT>
""",
        encoding="utf-8",
    )

    passed, msg, details = wsp.parse_wack_report(str(report_file))
    assert passed is False
    assert details["failed_count"] == 2
    assert "TestFailed" in details["failed_tests"]
    assert "TestError" in details["failed_tests"]
    assert details["passed_count"] == 2
    assert "TestPassing" in details["passed_tests"]
    assert "TestPassed" in details["passed_tests"]
