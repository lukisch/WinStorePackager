#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for WACK report parsing and signing credentials validation in WinStorePackager.
"""

import os
import tempfile

from WindowsStorePublisher_3 import (
    parse_wack_report,
    validate_signing_credentials,
    validate_publisher_cn,
)


def test_validate_publisher_cn():
    valid, msg = validate_publisher_cn("CN=TestPublisher")
    assert valid is True
    assert msg == ""

    valid_empty, msg_empty = validate_publisher_cn("")
    assert valid_empty is False
    assert "leer" in msg_empty.lower()

    valid_invalid, msg_invalid = validate_publisher_cn("TestPublisher")
    assert valid_invalid is False
    assert "CN=" in msg_invalid


def test_validate_signing_credentials():
    with tempfile.NamedTemporaryFile(suffix=".pfx", delete=False) as tf:
        pfx_file = tf.name

    try:
        # Valid credentials
        valid, errors = validate_signing_credentials(
            pfx_path=pfx_file,
            pfx_pw="Secret123",
            publisher_cn="CN=TestCorp",
            timestamp_url="http://timestamp.digicert.com",
        )
        assert valid is True
        assert len(errors) == 0

        # Invalid credentials (missing PFX file, bad URL format)
        valid_bad, errors_bad = validate_signing_credentials(
            pfx_path="non_existent_file.pfx",
            pfx_pw="",
            publisher_cn="InvalidPublisher",
            timestamp_url="invalid-url",
        )
        assert valid_bad is False
        assert len(errors_bad) == 3
    finally:
        if os.path.exists(pfx_file):
            os.remove(pfx_file)


def test_parse_wack_report_pass(tmp_path):
    report_xml = tmp_path / "WACK_Report_Pass.xml"
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<REPORT OVERALL_RESULT="PASS">
  <TEST NAME="Bytecode generation" RESULT="PASS" />
  <TEST NAME="Optimized binding references" RESULT="PASS" />
</REPORT>
"""
    report_xml.write_text(xml_content, encoding="utf-8")

    passed, msg, details = parse_wack_report(str(report_xml))
    assert passed is True
    assert "BESTANDEN" in msg
    assert details["overall"] == "PASS"
    assert details["passed_count"] == 2
    assert details["failed_count"] == 0


def test_parse_wack_report_fail(tmp_path):
    report_xml = tmp_path / "WACK_Report_Fail.xml"
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<REPORT OVERALL_RESULT="FAIL">
  <TEST NAME="Bytecode generation" RESULT="PASS" />
  <TEST NAME="Binary analyzer" RESULT="FAIL" />
</REPORT>
"""
    report_xml.write_text(xml_content, encoding="utf-8")

    passed, msg, details = parse_wack_report(str(report_xml))
    assert passed is False
    assert "FEHLGESCHLAGEN" in msg
    assert details["overall"] == "FAIL"
    assert details["failed_count"] == 1
    assert "Binary analyzer" in details["failed_tests"]


def test_parse_wack_report_nonexistent():
    passed, msg, details = parse_wack_report("non_existent_wack_report.xml")
    assert passed is False
    assert "nicht gefunden" in msg.lower()
    assert details == {}


def test_parse_wack_report_overall_fail_without_individual_failures(tmp_path):
    report_xml = tmp_path / "WACK_Report_Fail_Overall.xml"
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<REPORT OVERALL_RESULT="FAIL">
  <TEST NAME="Bytecode generation" RESULT="PASS" />
</REPORT>
"""
    report_xml.write_text(xml_content, encoding="utf-8")

    passed, msg, details = parse_wack_report(str(report_xml))
    assert passed is False
    assert "FEHLGESCHLAGEN" in msg
    assert "FAIL" in msg
    assert details["overall"] == "FAIL"
    assert details["failed_count"] == 0
    assert details["passed_count"] == 1


def test_parse_wack_report_overall_error(tmp_path):
    report_xml = tmp_path / "WACK_Report_Error.xml"
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<REPORT OVERALL_RESULT="ERROR">
  <TEST NAME="Bytecode generation" RESULT="PASS" />
</REPORT>
"""
    report_xml.write_text(xml_content, encoding="utf-8")

    passed, msg, details = parse_wack_report(str(report_xml))
    assert passed is False
    assert "FEHLGESCHLAGEN" in msg
    assert "ERROR" in msg
    assert details["overall"] == "ERROR"


def test_parse_wack_report_test_error_and_failed_statuses(tmp_path):
    report_xml = tmp_path / "WACK_Report_Error_Tests.xml"
    xml_content = """<?xml version="1.0" encoding="utf-8"?>
<REPORT OVERALL_RESULT="PASS">
  <TEST NAME="Bytecode generation" RESULT="PASS" />
  <TEST NAME="Crashed check" RESULT="ERROR" />
  <TEST NAME="Security manifest" RESULT="FAILED" />
</REPORT>
"""
    report_xml.write_text(xml_content, encoding="utf-8")

    passed, msg, details = parse_wack_report(str(report_xml))
    assert passed is False
    assert "FEHLGESCHLAGEN" in msg
    assert details["failed_count"] == 2
    assert "Crashed check" in details["failed_tests"]
    assert "Security manifest" in details["failed_tests"]
