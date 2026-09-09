# -*- coding: utf-8 -*-
"""Tests fuer die Manifest-Erweiterungen (Dateizuordnung, Alias, Protokoll,
Autostart).

Hintergrund: Das Manifest-Template erzeugte bis 2026-08-23 nie einen
<Extensions>-Block. Aus dem Store installierte Apps registrierten dadurch
keinen Dateityp und erschienen nicht im Dialog "Oeffnen mit".

Die Konfigurationsfelder sind bewusst identisch zu ellmos-ai/store-packager,
damit beide Werkzeuge dieselbe store_package.json lesen.
"""
from __future__ import annotations

import os
import sys
from xml.dom import minidom

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import html
import WindowsStorePublisher_3 as wsp  # noqa: E402


def _render(config, executable="TestApp.exe"):
    """Baut ein vollstaendiges Manifest wie generate_manifest es tut."""
    ext, ns = wsp.build_manifest_extensions(config, executable)
    ns_attr, ignorable = wsp.build_manifest_namespaces(ns)
    m = wsp.MANIFEST_TEMPLATE
    for key, val in (
        ("{{NAMESPACES}}", ns_attr), ("{{IGNORABLE}}", ignorable),
        ("{{EXTENSIONS}}", ext),
        ("{{MINVERSION}}", wsp.DEFAULT_MIN_VERSION),
        ("{{MAXVERSION}}", wsp.DEFAULT_MAX_VERSION_TESTED),
        ("{{IDENTITY_NAME}}", "Tester.TestApp"), ("{{PUBLISHER}}", "CN=TEST"),
        ("{{APPNAME}}", "TestApp"), ("{{APPID}}", "TestApp"),
        ("{{PUBLISHER_DISPLAY}}", "Tester"), ("{{DESCRIPTION}}", "Beschreibung"),
        ("{{VERSION}}", "1.0.0.0"), ("{{EXECUTABLE}}", html.escape(executable)),
        ("{{CAPABILITIES}}", '    <rescap:Capability Name="runFullTrust"/>'),
        ("{{RESOURCES}}", '    <Resource Language="de-DE"/>\n'),
    ):
        m = m.replace(key, val)
    return m


def test_empty_config_yields_no_extensions():
    """Ohne Konfiguration bleibt das Manifest wie vor der Erweiterung."""
    doc = _render({})
    assert "<Extensions>" not in doc
    assert "xmlns:uap3" not in doc and "xmlns:desktop" not in doc
    minidom.parseString(doc)


def test_file_type_association():
    doc = _render({"file_types": {"name": "markdown", "display_name": "Markdown",
                                  "extensions": [".md", "markdown"]}})
    assert 'Category="windows.fileTypeAssociation"' in doc
    assert "<uap:FileType>.md</uap:FileType>" in doc
    assert "<uap:FileType>.markdown</uap:FileType>" in doc  # Punkt wird ergaenzt
    assert "<uap:Logo>" in doc  # laut Schema Pflicht
    minidom.parseString(doc)


def test_execution_alias_adds_namespaces():
    doc = _render({"execution_alias": "testapp.exe"})
    assert 'Category="windows.appExecutionAlias"' in doc
    assert "xmlns:uap3" in doc and "xmlns:desktop" in doc
    ignorable = doc.split('IgnorableNamespaces="')[1].split('"')[0]
    assert "uap3" in ignorable and "desktop" in ignorable
    minidom.parseString(doc)


def test_protocol_and_startup_task():
    doc = _render({"protocols": [{"name": "testapp"}],
                   "startup_task": {"task_id": "T", "enabled": True}})
    assert 'Category="windows.protocol"' in doc
    assert 'Category="windows.startupTask"' in doc
    assert 'Enabled="true"' in doc
    minidom.parseString(doc)


def test_migration_progids_pull_restricted_namespace():
    """rescap3 ist eingeschraenkt - der Store verlangt vorherige Freigabe."""
    doc = _render({"file_types": {"name": "m", "extensions": [".md"],
                                  "migration_progids": ["Old.ProgId"]}})
    assert "xmlns:rescap3" in doc
    assert "<rescap3:MigrationProgId>Old.ProgId</rescap3:MigrationProgId>" in doc
    minidom.parseString(doc)


def test_target_device_family_default_is_modern():
    """Der alte Festwert 10.0.19041.0 sperrte neuere Erweiterungen aus."""
    doc = _render({})
    assert 'MaxVersionTested="%s"' % wsp.DEFAULT_MAX_VERSION_TESTED in doc
    assert wsp.DEFAULT_MAX_VERSION_TESTED != "10.0.19041.0"


def test_config_field_names_match_store_packager():
    """Beide Werkzeuge muessen dieselbe store_package.json verstehen."""
    for field in ("file_types", "execution_alias", "protocols", "startup_task"):
        doc = _render({field: {"name": "x", "extensions": [".a"], "enabled": True}
                       if field in ("file_types", "startup_task") else
                       ([{"name": "x"}] if field == "protocols" else "x.exe")})
        minidom.parseString(doc)


def test_manifest_extensions_attribute_escaping_and_lowercase_filetypes():
    """Manifest-Erweiterungen muessen Attribute gegen Anfuehrungszeichen absichern und FileTypes in Kleinbuchstaben fuehren."""
    config = {
        "file_types": [
            {
                "name": "custom",
                "display_name": 'Format "Pro" & <Lite>',
                "extensions": [".MD", "TXT"],
                "logo": 'icons\\logo "dark".png',
                "info_tip": 'Info "Tip"',
                "migration_progids": ['ProgId "Old"'],
            }
        ],
        "execution_alias": ['app "cli"'],
        "protocols": [{"name": "myproto", "display_name": 'Proto "Link"', "logo": 'proto "icon".png'}],
        "startup_task": {
            "task_id": "Task1",
            "enabled": True,
            "display_name": 'AutoStart "App" & Service',
            "executable": 'app "run".exe',
        },
    }
    doc = _render(config, executable='app "run".exe')
    parsed = minidom.parseString(doc)
    file_types = [node.firstChild.nodeValue for node in parsed.getElementsByTagName("uap:FileType")]
    assert ".md" in file_types
    assert ".txt" in file_types
    startup_tasks = parsed.getElementsByTagName("desktop:StartupTask")
    assert len(startup_tasks) == 1
    assert startup_tasks[0].getAttribute("DisplayName") == 'AutoStart "App" & Service'
