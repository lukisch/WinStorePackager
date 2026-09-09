#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows Store Packager — Version 2.3 (Auto-Setup & Safe Mode)
Complete GUI tool for Microsoft Store app packaging.

Changelog v2.3:
- Added auto-installer for dependencies (Pillow, pygetwindow, keyring).
- Added robust check for Tkinter installation errors.
"""

import sys
import subprocess
import os
import importlib

# ------------------------------------------------------------
# 0. Reproduzierbarer Dependency-Check (Bootstrapper)
# ------------------------------------------------------------
def install_and_import(package_name, import_name=None):
    """
    Prüft ein Modul ohne die Laufzeitumgebung zu verändern.

    Die Installation erfolgt bewusst nur vor dem Start mit requirements.txt:
    eine GUI oder Frozen-EXE darf nicht von Netzwerk, pip oder einem
    interaktiven Admin-Prompt abhängen.
    """
    if import_name is None:
        import_name = package_name

    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False

# ------------------------------------------------------------
# 0b. Abhängigkeiten sicherstellen (nur wenn direkt ausgeführt)
# ------------------------------------------------------------
def ensure_dependencies():
    """Prüft deklarierte Abhängigkeiten ohne Netzwerk- oder pip-Seiteneffekt."""
    print("--- Prüfe Abhängigkeiten ---")
    missing = [
        (package_name, import_name)
        for package_name, import_name in RUNTIME_DEPENDENCIES.items()
        if not install_and_import(package_name, import_name)
    ]
    if missing:
        names = ", ".join(package_name for package_name, _ in missing)
        print(f"❌ Fehlende Abhängigkeiten: {names}")
        print(f"Bitte vor dem Start ausführen: {install_command()}")
        return False
    print("--- Abhängigkeiten OK ---")
    return True

# ------------------------------------------------------------
# 1. Imports der nachgeladenen Module & Standard-Libs
# ------------------------------------------------------------
try:
    from PIL import Image, ImageGrab
    import pygetwindow as gw
    import keyring
except ImportError:
    Image = ImageGrab = None
    gw = None
    keyring = None

# Standard Libs
import json
import shutil
import glob
import re
import time
import threading
import html
import hashlib
import logging
from pathlib import Path
from typing import Optional, Any

from project_profile import read_project_profile, write_project_profile
from release_contract import RUNTIME_DEPENDENCIES, install_command
from runtime_paths import (
    configure_runtime_logging,
    get_log_path,
    get_settings_path,
    migrate_legacy_settings,
    write_json_atomic,
)
try:
    from translator import TranslationSystem, detect_system_language
except ImportError:
    TranslationSystem = None
    def detect_system_language():
        return "de"

SUPPORTED_LANGUAGES = ("de", "en", "es", "zh", "ja", "ru")
DEFAULT_LANGUAGE = "de"

_GLOBAL_TRANSLATOR = None


def get_translator(default_lang: str = None):
    global _GLOBAL_TRANSLATOR
    if _GLOBAL_TRANSLATOR is None and TranslationSystem is not None:
        lang = default_lang or detect_system_language()
        _GLOBAL_TRANSLATOR = TranslationSystem(default_lang=lang, app_dir=Path(__file__).parent)
    return _GLOBAL_TRANSLATOR


def _t(key: str) -> str:
    tr = get_translator()
    if tr is not None:
        return tr.t(key)
    return key

# ------------------------------------------------------------
# 2. Tkinter Sicherheits-Import
# ------------------------------------------------------------
try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
except ImportError:
    print("\n❌ KRITISCHER FEHLER: 'tkinter' fehlt.")
    print("Tkinter ist für die grafische Oberfläche zwingend erforderlich.")
    print("-" * 50)
    if os.name == 'nt':
        print("LÖSUNG (Windows):")
        print("1. Starten Sie den Python-Installer erneut.")
        print("2. Wählen Sie 'Modify' (Ändern).")
        print("3. Stellen Sie sicher, dass der Haken bei 'tcl/tk and IDLE' gesetzt ist.")
    else:
        print("LÖSUNG (Linux):")
        print("Installieren Sie das Paket python3-tk (z.B. 'sudo apt-get install python3-tk').")
    print("-" * 50)
    input("Drücken Sie Enter zum Beenden...")
    sys.exit(1)

# ---------- Configuration ----------
HAS_KEYRING = True # Jetzt garantiert, da oben installiert
OUTPUT_ROOT = str(Path(__file__).parent / "store_package")
LEGACY_SETTINGS_FILE = Path(__file__).parent / "settings_store_packager.json"
SETTINGS_FILE = str(get_settings_path())
LOG_FILE = str(get_log_path())
LOGGER = logging.getLogger("winstorepackager")
ICON_SIZES = [44, 50, 150, 310]  # Square sizes
WIDE_ICON_SIZE = (310, 150)  # Wide tile
DEFAULT_VERSION = "1.0.0.0"
KEYRING_SERVICE = "WindowsStorePackager"

# Sprachen fuer die <Resources>-Sektion des Manifests. Ohne sie loest der Store
# keine sprachabhaengigen Werte auf (Anzeigename, Herausgeber, Logos).
DEFAULT_LANGUAGES = "en-us"

# Faehigkeiten nach Namensraum.
# Allgemein: <Capability>
# UAP: <uap:Capability>
# Geraete: <DeviceCapability>
# Alles andere gilt als eingeschraenkt und wird als <rescap:Capability> geschrieben.
GENERAL_CAPABILITIES = {
    "internetClient", "internetClientServer",
    "privateNetworkClientServer", "allJoyn", "codeGeneration",
}
UAP_CAPABILITIES = {
    "documentsLibrary", "picturesLibrary", "videosLibrary", "musicLibrary",
    "removableStorage", "appointments", "contacts", "userAccountInformation",
    "sharedUserCertificates", "enterpriseAuthentication",
}
DEVICE_CAPABILITIES = {
    "webcam", "microphone", "location", "radios", "bluetooth",
    "serialcommunication", "usb", "lowLevelDevices", "proximity",
    "pointOfService", "gazeInput", "humaninterfacedevice", "custom",
    "wiFiControl", "optical",
}


def sanitize_application_id(app_name):
    """Leitet aus dem App-Namen eine schema-gueltige Application/@Id ab.

    Das AppX-Schema laesst fuer Application/@Id (ST_ApplicationId ueber
    ST_AsciiWindowsId) nur ([A-Za-z][A-Za-z0-9]*)(\\.[A-Za-z][A-Za-z0-9]*)*
    zu, maximal 64 Zeichen. Ein Leerzeichen oder Bindestrich im App-Namen
    ergab bisher Ids wie "SQLite Viewer ProApp" - makeappx weist das Manifest
    dann ab, was erst beim Paketbau auffiel. Punkte bleiben als Trenner
    erhalten, alles andere faellt weg; Segmente muessen mit einem Buchstaben
    beginnen.
    """
    cleaned = re.sub(r"[^A-Za-z0-9.]", "", app_name or "")
    segments = []
    for segment in cleaned.split("."):
        segment = re.sub(r"^[0-9]+", "", segment)
        if segment:
            segments.append(segment)
    return ".".join(segments)[:64].rstrip(".") or "App"


def safe_package_dir_name(app_name):
    """Return a single safe output-folder segment derived from the app name."""
    name = (app_name or "").strip() or "MyApp"
    has_separator = any(sep in name for sep in ("/", "\\"))
    if (
        has_separator
        or os.path.isabs(name)
        or name in {".", ".."}
        or os.path.splitdrive(name)[0]
    ):
        return sanitize_application_id(name)
    return name


MANIFEST_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<Package {{NAMESPACES}}
         IgnorableNamespaces="{{IGNORABLE}}">

  <Identity Name="{{IDENTITY_NAME}}"
            Publisher="{{PUBLISHER}}"
            Version="{{VERSION}}" />

  <Properties>
    <DisplayName>{{APPNAME}}</DisplayName>
    <PublisherDisplayName>{{PUBLISHER_DISPLAY}}</PublisherDisplayName>
    <Description>{{DESCRIPTION}}</Description>
    <Logo>icons\\icon_50x50.png</Logo>
  </Properties>

  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="{{MINVERSION}}" MaxVersionTested="{{MAXVERSION}}" />
  </Dependencies>

  <Resources>
{{RESOURCES}}  </Resources>

  <Capabilities>
{{CAPABILITIES}}
  </Capabilities>

  <Applications>
    <Application Id="{{APPID}}"
                 Executable="{{EXECUTABLE}}"
                 EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="{{APPNAME}}"
                          Description="{{DESCRIPTION}}"
                          Square150x150Logo="icons\\icon_150x150.png"
                          Square44x44Logo="icons\\icon_44x44.png"
                          BackgroundColor="transparent">
        <uap:DefaultTile Wide310x150Logo="icons\\icon_310x150.png" />
      </uap:VisualElements>
{{EXTENSIONS}}    </Application>
  </Applications>
</Package>
"""


# TargetDeviceFamily-Standardwerte. MaxVersionTested steuert, welche
# Manifest-Erweiterungen Windows akzeptiert; der fruehere Festwert
# 10.0.19041.0 (Windows 10 2004) sperrte neuere Erweiterungen aus.
DEFAULT_MIN_VERSION = "10.0.17763.0"
DEFAULT_MAX_VERSION_TESTED = "10.0.22621.0"

NS_BASE_URIS = {
    "": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
    "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
    "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
}
NS_OPTIONAL_URIS = {
    "uap3": "http://schemas.microsoft.com/appx/manifest/uap/windows10/3",
    "desktop": "http://schemas.microsoft.com/appx/manifest/desktop/windows10",
    "rescap3": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities/3",
}


def build_manifest_extensions(config, executable):
    """Baut den <Extensions>-Block aus einer store_package.json-Konfiguration.

    Ohne Konfigurationsfelder entsteht kein Block; das Manifest bleibt dann
    identisch zu frueheren Versionen. Feldnamen sind bewusst dieselben wie in
    ellmos-ai/store-packager (store_packager.py, _build_extensions), damit beide
    Werkzeuge dieselbe Projektkonfiguration lesen.

    Rueckgabe: (xml, set der benoetigten Namensraum-Praefixe)
    """
    from xml.sax.saxutils import escape as _sax_escape

    def _esc(val):
        return _sax_escape(str(val), {'"': "&quot;", "'": "&apos;"})

    parts = []
    ns = set()
    if not isinstance(config, dict):
        return "", ns

    # windows.fileTypeAssociation
    fts = config.get("file_types") or []
    if isinstance(fts, dict):
        fts = [fts]
    for ft in fts:
        exts = [e for e in (ft.get("extensions") or []) if str(e).strip()]
        if not exts:
            continue
        name = re.sub(r"[^a-z0-9]", "", str(ft.get("name") or "files").lower()) or "files"
        body = []
        if ft.get("display_name"):
            body.append("            <uap:DisplayName>%s</uap:DisplayName>" % _esc(str(ft["display_name"])))
        body.append("            <uap:Logo>%s</uap:Logo>" % _esc(str(ft.get("logo") or "icons\\icon_44x44.png")))
        if ft.get("info_tip"):
            body.append("            <uap:InfoTip>%s</uap:InfoTip>" % _esc(str(ft["info_tip"])))
        progids = ft.get("migration_progids") or []
        if progids:
            ns.add("rescap3")
            body.append("            <rescap3:MigrationProgIds>")
            for pid in progids:
                body.append("              <rescap3:MigrationProgId>%s</rescap3:MigrationProgId>" % _esc(str(pid)))
            body.append("            </rescap3:MigrationProgIds>")
        body.append("            <uap:SupportedFileTypes>")
        for e in exts:
            e = str(e).strip().lower()
            if not e.startswith("."):
                e = "." + e
            body.append("              <uap:FileType>%s</uap:FileType>" % _esc(e))
        body.append("            </uap:SupportedFileTypes>")
        parts.append(
            '        <uap:Extension Category="windows.fileTypeAssociation">\n'
            '          <uap:FileTypeAssociation Name="%s">\n%s\n'
            "          </uap:FileTypeAssociation>\n"
            "        </uap:Extension>" % (name, "\n".join(body)))

    # windows.appExecutionAlias
    aliases = config.get("execution_alias") or []
    if isinstance(aliases, str):
        aliases = [aliases]
    aliases = [str(a).strip() for a in aliases if str(a).strip()]
    if aliases:
        ns.update(("uap3", "desktop"))
        inner = "\n".join('            <desktop:ExecutionAlias Alias="%s" />' % _esc(a) for a in aliases)
        parts.append(
            '        <uap3:Extension Category="windows.appExecutionAlias"\n'
            '                        Executable="%s"\n'
            '                        EntryPoint="Windows.FullTrustApplication">\n'
            "          <uap3:AppExecutionAlias>\n%s\n          </uap3:AppExecutionAlias>\n"
            "        </uap3:Extension>" % (_esc(str(executable)), inner))

    # windows.protocol
    protos = config.get("protocols") or []
    if isinstance(protos, dict):
        protos = [protos]
    for pr in protos:
        pname = pr.get("name")
        if not pname:
            continue
        body = []
        if pr.get("display_name"):
            body.append("            <uap:DisplayName>%s</uap:DisplayName>" % _esc(str(pr["display_name"])))
        if pr.get("logo"):
            body.append("            <uap:Logo>%s</uap:Logo>" % _esc(str(pr["logo"])))
        inner = ("\n" + "\n".join(body)) if body else ""
        parts.append(
            '        <uap:Extension Category="windows.protocol">\n'
            '          <uap:Protocol Name="%s">%s\n'
            "          </uap:Protocol>\n"
            "        </uap:Extension>" % (_esc(str(pname)), inner))

    # windows.startupTask
    st = config.get("startup_task")
    if st:
        ns.add("desktop")
        parts.append(
            '        <desktop:Extension Category="windows.startupTask"\n'
            '                           Executable="%s"\n'
            '                           EntryPoint="Windows.FullTrustApplication">\n'
            '          <desktop:StartupTask TaskId="%s" Enabled="%s" DisplayName="%s" />\n'
            "        </desktop:Extension>" % (
                _esc(str(st.get("executable") or executable)),
                _esc(str(st.get("task_id") or "AppStartup")),
                "true" if st.get("enabled") else "false",
                _esc(str(st.get("display_name") or "App"))))

    if not parts:
        return "", ns
    return "      <Extensions>\n%s\n      </Extensions>\n" % "\n".join(parts), ns


def build_manifest_namespaces(extra_ns):
    """Liefert (namespaces_attr, ignorable) fuer den <Package>-Kopf."""
    pairs = [("", NS_BASE_URIS[""]), ("uap", NS_BASE_URIS["uap"])]
    for prefix in ("uap3", "desktop", "rescap3"):
        if prefix in extra_ns:
            pairs.append((prefix, NS_OPTIONAL_URIS[prefix]))
    pairs.append(("rescap", NS_BASE_URIS["rescap"]))
    attrs = []
    for prefix, uri in pairs:
        attrs.append('%s="%s"' % ("xmlns" if not prefix else "xmlns:%s" % prefix, uri))
    return ("\n" + " " * 9).join(attrs), " ".join(p for p, _ in pairs if p)

CATEGORIES = [
    "Productivity", "Education", "Entertainment", "Games", "Photo & Video",
    "Music", "Business", "Developer Tools", "Utilities", "Social", "Health & Fitness"
]

AGE_RATINGS = ["3+", "7+", "12+", "16+", "18+"]

# -----------------------------------

def which(program):
    """Find executable in PATH"""
    return shutil.which(program)

def find_windows_sdk_tools():
    """Auto-detect Windows SDK tools"""
    makeappx = which("makeappx.exe")
    signtool = which("signtool.exe")
    appcert = which("appcert.exe")
    if makeappx and signtool:
        return makeappx, signtool, appcert
    return None, None, None

def validate_publisher_cn(publisher):
    """Validate Publisher CN format"""
    if not publisher or not str(publisher).strip():
        return False, "Publisher darf nicht leer sein"
    pub_str = str(publisher).strip()
    if not pub_str.startswith("CN="):
        return False, "Publisher muss mit 'CN=' beginnen"
    if not pub_str[3:].strip():
        return False, "Publisher darf nach 'CN=' nicht leer sein"
    return True, ""

def validate_signing_credentials(pfx_path, pfx_pw, publisher_cn, timestamp_url):
    """
    Validates PFX certificate path, password, publisher format, and timestamp URL before calling signtool.
    Returns (valid: bool, errors: list[str]).
    """
    errors = []
    if not pfx_path or not os.path.isfile(pfx_path):
        errors.append("PFX-Zertifikatsdatei fehlt oder ist ungültig.")

    val_pub, msg_pub = validate_publisher_cn(publisher_cn or "")
    if not val_pub:
        errors.append(f"Publisher-ID Format ungültig: {msg_pub}")

    if not timestamp_url or not (timestamp_url.startswith("http://") or timestamp_url.startswith("https://")):
        errors.append("Timestamp URL muss mit http:// oder https:// beginnen.")

    return (len(errors) == 0), errors

def parse_wack_report(report_path: str):
    """
    Parses a WACK XML report produced by appcert.exe.
    Returns (passed: bool, summary_message: str, details: dict).
    """
    if not report_path or not os.path.exists(report_path):
        return False, f"WACK-Report nicht gefunden: {report_path}", {}

    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(report_path)
        root = tree.getroot()

        overall = root.attrib.get("OVERALL_RESULT", "").upper()

        failed_tests = []
        passed_tests = []
        for test in root.iter("TEST"):
            name = test.attrib.get("NAME", "Unknown")
            result = test.attrib.get("RESULT", "").upper()
            if result in ("FAIL", "FAILED", "ERROR", "CRASH"):
                failed_tests.append(name)
            elif result in ("PASS", "PASSED"):
                passed_tests.append(name)

        if overall in ("FAIL", "FAILED", "ERROR", "CRASH"):
            passed = False
        elif overall in ("PASS", "PASSED"):
            passed = (len(failed_tests) == 0)
        else:
            passed = (len(failed_tests) == 0 and len(passed_tests) > 0)

        details = {
            "overall": overall,
            "failed_count": len(failed_tests),
            "passed_count": len(passed_tests),
            "failed_tests": failed_tests,
            "passed_tests": passed_tests,
        }

        if passed:
            msg = f"✅ WACK-Test BESTANDEN ({len(passed_tests)} Prüfungen ok)."
        else:
            if failed_tests:
                msg = f"❌ WACK-Test FEHLGESCHLAGEN ({len(failed_tests)} Fehler: {', '.join(failed_tests[:5])})."
            else:
                msg = f"❌ WACK-Test FEHLGESCHLAGEN (Gesamtergebnis: {overall or 'FAIL'})."

        return passed, msg, details
    except Exception as e:
        return False, f"Fehler beim Parsen des WACK-Reports: {e}", {}


class ProgressDialog(tk.Toplevel):
    """Modal progress dialog for long operations - Thread Safe Fix Applied"""
    def __init__(self, parent, title="Verarbeitung..."):
        super().__init__(parent)
        self.title(title)
        self.geometry("400x120")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        ttk.Label(self, text=title, font=("Arial", 10, "bold")).pack(pady=10)
        self.progress = ttk.Progressbar(self, mode='indeterminate', length=350)
        self.progress.pack(pady=10)
        self.progress.start(10)

        self.status_label = ttk.Label(self, text="Bitte warten...")
        self.status_label.pack(pady=5)

        self.protocol("WM_DELETE_WINDOW", lambda: None)  # Prevent closing

    def update_status(self, text):
        """Thread-safe update of the status label"""
        self.after(0, lambda: self.status_label.config(text=text))

    def close(self):
        """Thread-safe close"""
        self.after(0, self._close_internal)

    def _close_internal(self):
        self.progress.stop()
        self.grab_release()
        self.destroy()


class ToolTip:
    """
    Barrierefreies, leichtgewichtiges Tooltip-Widget für Tkinter-Komponenten.
    Unterstützt Maus-Hover (<Enter>/<Leave>) und Tastaturfokus (<FocusIn>/<FocusOut>).
    """

    def __init__(self, widget: tk.Widget, text: str = "", app: Optional[Any] = None, status_text: Optional[str] = None):
        self.widget = widget
        self.text = text
        self.status_text = status_text or text
        self.app = app
        self.tip_window: Optional[tk.Toplevel] = None
        self.widget.bind("<Enter>", self.show_tip, add="+")
        self.widget.bind("<Leave>", self.hide_tip, add="+")
        self.widget.bind("<FocusIn>", self._on_focus_in, add="+")
        self.widget.bind("<FocusOut>", self._on_focus_out, add="+")
        self.widget.bind("<ButtonPress>", self.hide_tip, add="+")

    def set_text(self, text: str, status_text: Optional[str] = None) -> None:
        self.text = text
        if status_text is not None:
            self.status_text = status_text
        if self.tip_window and self.tip_window.winfo_exists():
            for child in self.tip_window.winfo_children():
                if isinstance(child, tk.Label):
                    child.config(text=self.text)

    def _on_focus_in(self, event: Optional[Any] = None) -> None:
        if self.app and hasattr(self.app, "set_status") and self.status_text:
            self.app.set_status(self.status_text)
        self.show_tip(event)

    def _on_focus_out(self, event: Optional[Any] = None) -> None:
        if self.app and hasattr(self.app, "set_status"):
            self.app.set_status("")
        self.hide_tip(event)

    def show_tip(self, event: Optional[Any] = None) -> None:
        if self.tip_window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        except Exception:
            return

        try:
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            try:
                tw.attributes("-topmost", True)
            except Exception:
                pass

            label = tk.Label(
                tw,
                text=self.text,
                justify=tk.LEFT,
                background="#2c3e50",
                foreground="#ffffff",
                relief=tk.SOLID,
                borderwidth=1,
                font=("Segoe UI" if os.name == "nt" else "Arial", 9),
                padx=8,
                pady=4,
            )
            label.pack(ipadx=1)
        except Exception:
            self.tip_window = None

    def hide_tip(self, event: Optional[Any] = None) -> None:
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None


class StorePackagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        app_icon_path = str(Path(__file__).parent / "WinStorePackager.ico")
        if os.path.exists(app_icon_path):
            try:
                self.iconbitmap(default=app_icon_path)
            except tk.TclError:
                pass
        self.title("Windows Store Packager v3.1.0 (Auto-Setup)")
        self.geometry("1200x1000")

        # State variables
        self.app_name = tk.StringVar()
        self.publisher = tk.StringVar()
        self.publisher_display = tk.StringVar()
        self.identity_name = tk.StringVar()
        self.version = tk.StringVar(value=DEFAULT_VERSION)
        self.script_path = tk.StringVar()
        self.icon_path = tk.StringVar()
        self.source_path = tk.StringVar()
        self.installer_path = tk.StringVar()
        self.output_dir = tk.StringVar(value=OUTPUT_ROOT)
        self.exe_name = tk.StringVar()

        # MSIX build settings
        self.makeappx_path = tk.StringVar()
        self.signtool_path = tk.StringVar()
        self.appcert_path = tk.StringVar()
        self.pfx_path = tk.StringVar()
        self.pfx_password = tk.StringVar()
        self.timestamp_url = tk.StringVar(value="http://timestamp.digicert.com")  # Note: signtool requires http://, not https://
        self.msix_name = tk.StringVar()

        # External Python (Recursion Fix)
        self.python_path = tk.StringVar()

        # Store extras
        self.capabilities = tk.StringVar(value="internetClient")
        self.privacy_url = tk.StringVar()
        self.support_url = tk.StringVar()
        self.category = tk.StringVar(value="Productivity")
        self.age_rating = tk.StringVar(value="3+")

        # Changelog
        self.changelog_box = None

        # License files
        self.license_files = []
        self.license_text_entries = []

        # i18n toggle
        self.enable_i18n = tk.BooleanVar(value=True)

        # Language & i18n
        self.language = tk.StringVar(value=detect_system_language())
        self._translatable_items = []
        self._tooltips = []
        self.lang_menu = None
        self.status_bar = None
        self.status_label = None

        # Text widgets
        self.readme_box = None
        self.license_box = None
        self.desc_box = None

        self.load_settings()
        self.build_gui()
        self.autodetect_sdk_tools()

    # ---------- Settings ----------
    def load_settings(self):
        try:
            migrated = migrate_legacy_settings(LEGACY_SETTINGS_FILE, SETTINGS_FILE)
            if migrated:
                LOGGER.info("Checkout-lokale Einstellungen wurden in den Runtime-Pfad migriert.")
            elif LEGACY_SETTINGS_FILE.exists() and Path(SETTINGS_FILE).exists():
                LOGGER.warning(
                    "Legacy-Einstellungen bleiben erhalten, weil Runtime-Einstellungen bereits existieren."
                )
        except Exception as e:
            LOGGER.warning("Legacy-Einstellungen konnten nicht migriert werden: %s", e)

        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.app_name.set(data.get("app_name", ""))
                self.publisher.set(data.get("publisher", ""))
                self.publisher_display.set(data.get("publisher_display", ""))
                self.identity_name.set(data.get("identity_name", ""))
                self.version.set(data.get("version", DEFAULT_VERSION))
                self.script_path.set(data.get("script_path", ""))
                self.icon_path.set(data.get("icon_path", ""))
                self.source_path.set(data.get("source_path", ""))
                self.installer_path.set(data.get("installer_path", ""))
                self.output_dir.set(data.get("output_dir", OUTPUT_ROOT))
                self.exe_name.set(data.get("exe_name", ""))
                self.makeappx_path.set(data.get("makeappx_path", ""))
                self.signtool_path.set(data.get("signtool_path", ""))
                self.appcert_path.set(data.get("appcert_path", ""))
                self.pfx_path.set(data.get("pfx_path", ""))
                self.timestamp_url.set(data.get("timestamp_url", self.timestamp_url.get()))
                self.msix_name.set(data.get("msix_name", ""))
                self.python_path.set(data.get("python_path", ""))
                self.license_files = data.get("license_files", [])
                self.license_text_entries = data.get("license_text_entries", [])
                self.enable_i18n.set(data.get("enable_i18n", True))
                self.capabilities.set(data.get("capabilities", "internetClient"))
                self.privacy_url.set(data.get("privacy_url", ""))
                self.support_url.set(data.get("support_url", ""))
                self.category.set(data.get("category", "Productivity"))
                self.age_rating.set(data.get("age_rating", "3+"))

                saved_lang = data.get("language")
                if saved_lang in SUPPORTED_LANGUAGES:
                    self.language.set(saved_lang)
                    tr = get_translator()
                    if tr is not None:
                        tr.set_language(saved_lang)

                # Kein Try/Except mehr nötig, da keyring oben installiert wurde
                pwd = keyring.get_password(KEYRING_SERVICE, "pfx_password")
                if pwd:
                    self.pfx_password.set(pwd)

            except Exception as e:
                # Fallback für alte Settings-Files oder Keyring-Fehler
                LOGGER.warning("Einstellungen konnten nicht vollständig geladen werden: %s", e)

    def save_settings(self):
        if self.pfx_password.get():
            try:
                keyring.set_password(KEYRING_SERVICE, "pfx_password", self.pfx_password.get())
            except Exception as e:
                messagebox.showwarning("Warnung", f"Passwort konnte nicht im Keyring gespeichert werden:\n{e}")

        data = {
            "app_name": self.app_name.get(),
            "publisher": self.publisher.get(),
            "publisher_display": self.publisher_display.get(),
            "identity_name": self.identity_name.get(),
            "version": self.version.get(),
            "script_path": self.script_path.get(),
            "icon_path": self.icon_path.get(),
            "source_path": self.source_path.get(),
            "installer_path": self.installer_path.get(),
            "output_dir": self.output_dir.get(),
            "exe_name": self.exe_name.get(),
            "makeappx_path": self.makeappx_path.get(),
            "signtool_path": self.signtool_path.get(),
            "appcert_path": self.appcert_path.get(),
            "pfx_path": self.pfx_path.get(),
            "timestamp_url": self.timestamp_url.get(),
            "msix_name": self.msix_name.get(),
            "python_path": self.python_path.get(),
            "license_files": self.license_files,
            "license_text_entries": self.license_text_entries,
            "enable_i18n": self.enable_i18n.get(),
            "capabilities": self.capabilities.get(),
            "privacy_url": self.privacy_url.get(),
            "support_url": self.support_url.get(),
            "category": self.category.get(),
            "age_rating": self.age_rating.get(),
            "language": self.language.get()
        }

        try:
            write_json_atomic(SETTINGS_FILE, data)
            LOGGER.info("Einstellungen wurden atomar im Runtime-Pfad gespeichert.")
            messagebox.showinfo("Gespeichert", "Einstellungen wurden gespeichert.")
        except Exception as e:
            LOGGER.exception("Einstellungen konnten nicht gespeichert werden.")
            messagebox.showerror("Fehler", f"Einstellungen konnten nicht gespeichert werden:\n{e}")

    def _get_text_widget_value(self, widget):
        if widget is None:
            return ""
        return widget.get("1.0", tk.END).strip()

    def _set_text_widget_value(self, widget, value):
        if widget is None:
            return
        widget.delete("1.0", tk.END)
        if value:
            widget.insert(tk.END, value)

    def collect_project_profile_state(self):
        return {
            "app_name": self.app_name.get(),
            "publisher_display": self.publisher_display.get(),
            "identity_name": self.identity_name.get(),
            "version": self.version.get(),
            "script_path": self.script_path.get(),
            "icon_path": self.icon_path.get(),
            "source_path": self.source_path.get(),
            "installer_path": self.installer_path.get(),
            "output_dir": self.output_dir.get(),
            "exe_name": self.exe_name.get(),
            "privacy_url": self.privacy_url.get(),
            "support_url": self.support_url.get(),
            "capabilities": self.capabilities.get(),
            "category": self.category.get(),
            "age_rating": self.age_rating.get(),
            "description": self._get_text_widget_value(self.desc_box),
            "changelog": self._get_text_widget_value(self.changelog_box),
            "readme": self._get_text_widget_value(self.readme_box),
            "license_files": list(self.license_files),
            "license_text_entries": list(self.license_text_entries),
            "enable_i18n": self.enable_i18n.get(),
        }

    def apply_project_profile_state(self, data):
        self.app_name.set(data.get("app_name", ""))
        self.publisher_display.set(data.get("publisher_display", ""))
        self.identity_name.set(data.get("identity_name", ""))
        self.version.set(data.get("version", DEFAULT_VERSION))
        self.script_path.set(data.get("script_path", ""))
        self.icon_path.set(data.get("icon_path", ""))
        self.source_path.set(data.get("source_path", ""))
        self.installer_path.set(data.get("installer_path", ""))
        self.output_dir.set(data.get("output_dir", OUTPUT_ROOT))
        self.exe_name.set(data.get("exe_name", ""))
        self.privacy_url.set(data.get("privacy_url", ""))
        self.support_url.set(data.get("support_url", ""))
        self.capabilities.set(data.get("capabilities", ""))
        self.category.set(data.get("category", "Productivity"))
        self.age_rating.set(data.get("age_rating", "3+"))
        self.enable_i18n.set(data.get("enable_i18n", True))

        self.license_files = list(data.get("license_files", []))
        self.license_text_entries = list(data.get("license_text_entries", []))

        self._set_text_widget_value(self.readme_box, data.get("readme", ""))
        self._set_text_widget_value(self.desc_box, data.get("description", ""))

        changelog = data.get("changelog", "").strip()
        if not changelog:
            changelog = f"Version {self.version.get()}\n- \n- \n- "
        self._set_text_widget_value(self.changelog_box, changelog)

        license_preview_parts = []
        if self.license_files:
            license_preview_parts.append("Lizenzdateien:\n" + "\n".join(self.license_files))
        if self.license_text_entries:
            license_preview_parts.append("\n\n".join(self.license_text_entries))
        self._set_text_widget_value(self.license_box, "\n\n".join(license_preview_parts))

    def export_project_profile(self):
        path = filedialog.asksaveasfilename(
            title=_t("Projektprofil exportieren"),
            defaultextension=".json",
            initialfile="winstorepackager-project-v1.json",
            filetypes=[(_t("JSON-Dateien"), "*.json"), (_t("Alle Dateien"), "*.*")],
        )
        if not path:
            return

        try:
            write_project_profile(path, self.collect_project_profile_state())
            messagebox.showinfo(
                _t("Projektprofil exportiert"),
                _t(
                    "Projektprofil wurde exportiert.\n\n"
                    "Nicht enthalten sind Publisher-ID, SDK-Pfade, Zertifikatspfade und Passwörter."
                ),
            )
        except Exception as e:
            messagebox.showerror(
                _t("Fehler"),
                f"{_t('Projektprofil konnte nicht exportiert werden:')}\n{e}",
            )

    def import_project_profile(self):
        path = filedialog.askopenfilename(
            title=_t("Projektprofil importieren"),
            filetypes=[(_t("JSON-Dateien"), "*.json"), (_t("Alle Dateien"), "*.*")],
        )
        if not path:
            return

        try:
            profile_state = read_project_profile(path)
            self.apply_project_profile_state(profile_state)
            messagebox.showinfo(
                _t("Projektprofil importiert"),
                _t(
                    "Projektprofil wurde geladen.\n\n"
                    "Bitte Publisher-ID, SDK-Pfade und Zertifikat lokal ergänzen."
                ),
            )
        except Exception as e:
            messagebox.showerror(
                _t("Fehler"),
                f"{_t('Projektprofil konnte nicht importiert werden:')}\n{e}",
            )

    def _register_translatable(self, widget, prop, key):
        if not hasattr(self, "_translatable_items") or self._translatable_items is None:
            self._translatable_items = []
        self._translatable_items.append((widget, prop, key))

    def apply_language(self, lang: str):
        """Wechselt die Sprache live, aktualisiert alle UI-Texte und speichert die Konfiguration."""
        if lang not in SUPPORTED_LANGUAGES:
            return
        self.language.set(lang)
        tr = get_translator()
        if tr is not None:
            tr.set_language(lang)
        self.refresh_ui_language()
        try:
            self.save_settings()
        except Exception:
            pass
        msg_map = {
            "de": "Die Sprache wurde auf Deutsch umgestellt.",
            "en": "Language was switched to English.",
            "es": "El idioma se cambió a español.",
            "zh": "语言已切换为中文。",
            "ja": "言語が日本語に切り替わりました。",
            "ru": "Язык переключен на русский.",
        }
        msg = msg_map.get(lang, "Die Sprache wurde auf Deutsch umgestellt.")
        messagebox.showinfo(_t("Sprache gewechselt"), _t(msg))

    def set_status(self, text: str = ""):
        """Aktualisiert die barrierefreie Statusleiste am unteren Fensterrand."""
        if hasattr(self, "status_label") and self.status_label:
            try:
                display_text = text if text else _t("Status: Bereit")
                self.status_label.config(text=display_text)
            except Exception:
                pass

    def select_tab(self, index: int):
        """Wählt den angegebenen Notebook-Reiter über Tastaturkürzel an."""
        if hasattr(self, "notebook") and self.notebook:
            try:
                self.notebook.select(index)
            except Exception:
                pass

    def show_shortcuts_help(self):
        """Zeigt ein modales Dialogfenster mit allen Tastaturkürzeln und Barrierefreiheitsfunktionen."""
        help_text = (
            "WinStorePackager — Tastaturkürzel & Barrierefreiheit\n\n"
            "Globale Tastaturkürzel:\n"
            "• Strg + S : Einstellungen dauerhaft speichern\n"
            "• Strg + O : Projektprofil importieren\n"
            "• Strg + E : Projektprofil exportieren\n"
            "• F5       : 1. Preflight-Check starten\n"
            "• Strg + 1 : Reiter 'Metadaten' aufrufen\n"
            "• Strg + 2 : Reiter 'Build-Einstellungen' aufrufen\n"
            "• Strg + 3 : Reiter 'Store-Informationen' aufrufen\n"
            "• Strg + 4 : Reiter 'Aktionen' aufrufen\n"
            "• F1       : Diese Hilfe anzeigen\n"
            "• Strg + Q : Anwendung beenden\n\n"
            "Tastaturnavigation & Screenreader:\n"
            "• Tab / Umschalt+Tab : Vorwärts / Rückwärts durch alle Steuerelemente springen\n"
            "• Leertaste / Eingabetaste : Fokussierte Schaltfläche aktivieren\n"
            "• Pfeiltasten : Auswahl in Menüs und Kombinationsfeldern ändern\n"
            "• Statusleiste : Zeigt beim Fokussieren kontextuelle Hilfetexte an\n"
            "• Tooltips : Erscheinen sowohl beim Maus-Hover als auch bei Tastatur-Fokus"
        )
        messagebox.showinfo(_t("Tastaturkürzel & Barrierefreiheit"), help_text)

    def show_about_dialog(self):
        """Zeigt Informationen über WinStorePackager an."""
        about_text = (
            "Windows Store Packager — MSIX Creator\n"
            "Version 2.3 (Auto-Setup & Safe Mode)\n\n"
            "Vollständiges GUI-Tool für Microsoft Store Packaging & MSIX-Erstellung.\n"
            "Unterstützt Python-Desktop-Apps, i18n-Mehrsprachigkeit (6 Sprachen),\n"
            "WACK-Validierung und barrierefreie Tastaturbedienung.\n\n"
            "Lizenz: MIT\n"
            "Entwickelt für barrierefreie, sichere Softwarepakete."
        )
        messagebox.showinfo(_t("Über WinStorePackager"), about_text)

    def _add_tooltip(self, widget: tk.Widget, text_key: str, status_key: Optional[str] = None):
        """Erzeugt einen barrierefreien ToolTip und registriert ihn für dynamische Sprachaktualisierung."""
        s_key = status_key or text_key
        tip = ToolTip(widget, text=_t(text_key), app=self, status_text=_t(s_key))
        if not hasattr(self, "_tooltips"):
            self._tooltips = []
        self._tooltips.append((tip, text_key, s_key))
        return tip

    def refresh_ui_language(self):
        """Aktualisiert dynamisch alle registrierten UI-Elemente, Reiter, Menüs und Tooltips."""
        if hasattr(self, "notebook") and self.notebook:
            try:
                self.notebook.tab(0, text=_t("Metadaten"))
                self.notebook.tab(1, text=_t("Build-Einstellungen"))
                self.notebook.tab(2, text=_t("Store-Informationen"))
                self.notebook.tab(3, text=_t("Aktionen"))
            except Exception:
                pass

        for widget, prop, key in getattr(self, "_translatable_items", []):
            try:
                widget.configure(**{prop: _t(key)})
            except Exception:
                pass

        for tip, text_key, status_key in getattr(self, "_tooltips", []):
            try:
                tip.set_text(_t(text_key), _t(status_key))
            except Exception:
                pass

        if hasattr(self, "status_label") and self.status_label:
            try:
                self.status_label.config(text=_t("Status: Bereit"))
            except Exception:
                pass

        self._rebuild_menubar()

    def _rebuild_menubar(self):
        """Erstellt die Menüleiste barrierefrei mit Tastaturkürzeln und Live-Sprachunterstützung neu."""
        menubar = tk.Menu(self)

        # 1. Menü: Datei (File)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label=f"{_t('Profil importieren...')}  (Ctrl+O)", command=self.import_project_profile)
        file_menu.add_command(label=f"{_t('Profil exportieren...')}  (Ctrl+E)", command=self.export_project_profile)
        file_menu.add_command(label=f"{_t('Einstellungen speichern')}  (Ctrl+S)", command=self.save_settings)
        file_menu.add_separator()
        file_menu.add_command(label=f"{_t('Beenden')}  (Ctrl+Q)", command=self.on_quit)
        menubar.add_cascade(label=_t("Datei"), menu=file_menu)

        # 2. Menü: Aktionen (Actions)
        actions_menu = tk.Menu(menubar, tearoff=0)
        actions_menu.add_command(label=f"{_t('1. Preflight-Check')}  (F5)", command=self.preflight_check)
        actions_menu.add_command(label=_t("2. Paket erzeugen"), command=self.build_package)
        actions_menu.add_command(label=_t("3. EXE bauen"), command=self.build_exe)
        actions_menu.add_command(label=_t("4. MSIX bauen & signieren"), command=self.build_and_sign_msix)
        actions_menu.add_separator()
        actions_menu.add_command(label=_t("Screenshots erzeugen"), command=self.run_screenshots)
        actions_menu.add_command(label=_t("WACK-Test starten"), command=self.run_wack_test)
        actions_menu.add_command(label=_t("Ausgabeordner öffnen"), command=self.open_output_folder)
        menubar.add_cascade(label=_t("Aktionen"), menu=actions_menu)

        # 3. Menü: Ansicht (View)
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label=f"{_t('Metadaten')}  (Ctrl+1)", command=lambda: self.select_tab(0))
        view_menu.add_command(label=f"{_t('Build-Einstellungen')}  (Ctrl+2)", command=lambda: self.select_tab(1))
        view_menu.add_command(label=f"{_t('Store-Informationen')}  (Ctrl+3)", command=lambda: self.select_tab(2))
        view_menu.add_command(label=f"{_t('Aktionen')}  (Ctrl+4)", command=lambda: self.select_tab(3))
        menubar.add_cascade(label=_t("Ansicht"), menu=view_menu)

        # 4. Menü: Sprache (Language)
        self.lang_menu = tk.Menu(menubar, tearoff=0)
        lang_options = [
            ("Deutsch", "de"),
            ("English", "en"),
            ("Español", "es"),
            ("简体中文", "zh"),
            ("日本語", "ja"),
            ("Русский", "ru"),
        ]
        for label, code in lang_options:
            self.lang_menu.add_radiobutton(
                label=label, value=code, variable=self.language,
                command=lambda c=code: self.apply_language(c)
            )
        menubar.add_cascade(label=_t("Sprache / Language"), menu=self.lang_menu)

        # 5. Menü: Hilfe (Help)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=f"{_t('Tastaturkürzel & Barrierefreiheit')}  (F1)", command=self.show_shortcuts_help)
        help_menu.add_command(label=_t("Über WinStorePackager"), command=self.show_about_dialog)
        menubar.add_cascade(label=_t("Hilfe"), menu=help_menu)

        self.config(menu=menubar)

    def build_gui(self):
        self._rebuild_menubar()

        # Keyboard shortcuts
        self.bind_all("<Control-s>", lambda e: self.save_settings())
        self.bind_all("<Control-S>", lambda e: self.save_settings())
        self.bind_all("<Control-o>", lambda e: self.import_project_profile())
        self.bind_all("<Control-O>", lambda e: self.import_project_profile())
        self.bind_all("<Control-e>", lambda e: self.export_project_profile())
        self.bind_all("<Control-E>", lambda e: self.export_project_profile())
        self.bind_all("<Control-q>", lambda e: self.on_quit())
        self.bind_all("<Control-Q>", lambda e: self.on_quit())
        self.bind_all("<F5>", lambda e: self.preflight_check())
        self.bind_all("<F1>", lambda e: self.show_shortcuts_help())
        self.bind_all("<Control-Key-1>", lambda e: self.select_tab(0))
        self.bind_all("<Control-Key-2>", lambda e: self.select_tab(1))
        self.bind_all("<Control-Key-3>", lambda e: self.select_tab(2))
        self.bind_all("<Control-Key-4>", lambda e: self.select_tab(3))

        # Status Bar at bottom
        self.status_bar = ttk.Frame(self, relief=tk.SUNKEN, padding=(6, 3))
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_label = ttk.Label(
            self.status_bar,
            text=_t("Status: Bereit"),
            font=("Segoe UI" if os.name == "nt" else "Arial", 9)
        )
        self.status_label.pack(side=tk.LEFT, padx=4)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        self.tab1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text=_t("Metadaten"))
        self.build_metadata_tab(self.tab1)

        self.tab2 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2, text=_t("Build-Einstellungen"))
        self.build_build_tab(self.tab2)

        self.tab3 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab3, text=_t("Store-Informationen"))
        self.build_store_tab(self.tab3)

        self.tab4 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab4, text=_t("Aktionen"))
        self.build_actions_tab(self.tab4)

    def build_metadata_tab(self, parent):
        frm = ttk.Frame(parent)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        row = 0

        def add_row(label, var, browse_cmd=None, browse_label="Wählen", width=60, tooltip_key=None, status_key=None, btn_tooltip_key=None, btn_status_key=None):
            nonlocal row
            lbl = ttk.Label(frm, text=_t(label))
            lbl.grid(row=row, column=0, sticky="w", pady=3)
            self._register_translatable(lbl, "text", label)

            ent = ttk.Entry(frm, textvariable=var, width=width)
            ent.grid(row=row, column=1, sticky="we", pady=3, padx=5)
            if tooltip_key:
                self._add_tooltip(ent, tooltip_key, status_key or tooltip_key)

            if browse_cmd:
                btn = ttk.Button(frm, text=_t(browse_label), command=browse_cmd)
                btn.grid(row=row, column=2, sticky="w")
                self._register_translatable(btn, "text", browse_label)
                if btn_tooltip_key:
                    self._add_tooltip(btn, btn_tooltip_key, btn_status_key or btn_tooltip_key)
            row += 1

        add_row("App-Name:", self.app_name, tooltip_key="Name der Windows-Anwendung für das Store-Paket", status_key="Eingabefeld für den Anwendungsnamen")
        add_row("Publisher (CN=... aus Partner Center):", self.publisher, tooltip_key="Publisher-CN aus dem Partner Center (z.B. CN=12345678-...)", status_key="Eingabefeld für den Publisher-CN")
        add_row("Publisher Display Name:", self.publisher_display, tooltip_key="Öffentlich angezeigter Name des Herausgebers", status_key="Eingabefeld für den Publisher-Anzeigenamen")
        add_row("Identity Name:", self.identity_name, tooltip_key="Paketidentifikator (z.B. MeinUnternehmen.MeinProgramm)", status_key="Eingabefeld für den Identity Name")
        add_row("Version (z.B. 1.0.0.0):", self.version, tooltip_key="Vierstellige Versionsnummer im Format Major.Minor.Build.Revision (z.B. 1.0.0.0)", status_key="Eingabefeld für die Versionsnummer")

        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=10)
        row += 1

        add_row("Haupt-Skript (.py):", self.script_path, self.choose_script, browse_label="Skript wählen", tooltip_key="Pfad zum Python-Hauptskript (.py)", status_key="Eingabefeld für das Hauptskript", btn_tooltip_key="Öffnet den Dateidialog zur Auswahl des Python-Hauptskripts", btn_status_key="Schaltfläche: Skript auswählen")
        add_row("Icon (PNG, mind. 310x310):", self.icon_path, self.choose_icon, browse_label="Icon wählen", tooltip_key="Pfad zur Icon-Grafik (mindestens 310x310 PNG)", status_key="Eingabefeld für das Anwendungsicon", btn_tooltip_key="Öffnet den Dateidialog zur Auswahl des Icons (PNG)", btn_status_key="Schaltfläche: Icon auswählen")
        add_row("Quelltext (ZIP oder Datei):", self.source_path, self.choose_source, browse_label="Quelle wählen", tooltip_key="Pfad zum Quellcode-Verzeichnis oder ZIP-Archiv", status_key="Eingabefeld für den Quellcode", btn_tooltip_key="Öffnet den Dateidialog zur Auswahl des Quellcodes", btn_status_key="Schaltfläche: Quellcode auswählen")
        add_row("Installer (EXE oder MSIX):", self.installer_path, self.choose_installer, browse_label="Installer wählen", tooltip_key="Pfad zu einem bestehenden Installer (EXE oder MSIX)", status_key="Eingabefeld für den Installer", btn_tooltip_key="Öffnet den Dateidialog zur Auswahl des Installers", btn_status_key="Schaltfläche: Installer auswählen")
        add_row("Ausgabeordner:", self.output_dir, tooltip_key="Ausgabeverzeichnis für generierte Store-Pakete", status_key="Eingabefeld für den Ausgabeordner")
        add_row("EXE-Name (z.B. MyApp.exe):", self.exe_name, tooltip_key="Dateiname der ausführbaren Datei (z.B. MyApp.exe)", status_key="Eingabefeld für den EXE-Namen")

        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=10)
        row += 1

        lbl_rm = ttk.Label(frm, text=_t("README (Text oder Datei):"))
        lbl_rm.grid(row=row, column=0, sticky="nw", pady=5)
        self._register_translatable(lbl_rm, "text", "README (Text oder Datei):")

        readme_frame = ttk.Frame(frm)
        readme_frame.grid(row=row, column=1, sticky="we", pady=5, padx=5)
        self.readme_box = scrolledtext.ScrolledText(readme_frame, width=70, height=5)
        self.readme_box.pack(fill="both", expand=True)
        self._add_tooltip(self.readme_box, "README-Inhalt oder Dokumentationsdatei für das Paket", "Textfeld für README-Dokumentation")

        btn_rm = ttk.Button(frm, text=_t("README laden"), command=self.load_readme_file)
        btn_rm.grid(row=row, column=2, sticky="nw")
        self._register_translatable(btn_rm, "text", "README laden")
        self._add_tooltip(btn_rm, "Lädt den Inhalt einer README-Datei in das Textfeld", "Schaltfläche: README-Datei laden")
        row += 1

        lbl_lic = ttk.Label(frm, text=_t("Lizenz (Text/Dateien):"))
        lbl_lic.grid(row=row, column=0, sticky="nw", pady=5)
        self._register_translatable(lbl_lic, "text", "Lizenz (Text/Dateien):")

        license_frame = ttk.Frame(frm)
        license_frame.grid(row=row, column=1, sticky="we", pady=5, padx=5)
        self.license_box = scrolledtext.ScrolledText(license_frame, width=70, height=5)
        self.license_box.pack(fill="both", expand=True)
        self._add_tooltip(self.license_box, "Lizenzvereinbarungen und Third-Party-Lizenzen", "Textfeld für Lizenzen")
        lic_btns = ttk.Frame(frm)
        lic_btns.grid(row=row, column=2, sticky="nw")

        btn_l1 = ttk.Button(lic_btns, text=_t("Datei +"), command=self.add_license_file)
        btn_l1.pack(anchor="w", pady=2)
        self._register_translatable(btn_l1, "text", "Datei +")
        self._add_tooltip(btn_l1, "Fügt eine Lizenzdatei zum Paket hinzu", "Schaltfläche: Lizenzdatei hinzufügen")

        btn_l2 = ttk.Button(lic_btns, text=_t("Text +"), command=self.add_license_text_entry)
        btn_l2.pack(anchor="w", pady=2)
        self._register_translatable(btn_l2, "text", "Text +")
        self._add_tooltip(btn_l2, "Fügt einen benutzerdefinierten Lizenztext hinzu", "Schaltfläche: Lizenztext hinzufügen")
        row += 1

        lbl_desc = ttk.Label(frm, text=_t("Beschreibung:"))
        lbl_desc.grid(row=row, column=0, sticky="nw", pady=5)
        self._register_translatable(lbl_desc, "text", "Beschreibung:")

        desc_frame = ttk.Frame(frm)
        desc_frame.grid(row=row, column=1, sticky="we", pady=5, padx=5)
        self.desc_box = scrolledtext.ScrolledText(desc_frame, width=70, height=5)
        self.desc_box.pack(fill="both", expand=True)
        self._add_tooltip(self.desc_box, "Ausführliche Store-Produktbeschreibung", "Textfeld für die Produktbeschreibung")

        btn_desc = ttk.Button(frm, text=_t("Beschreibung laden"), command=self.load_desc_file)
        btn_desc.grid(row=row, column=2, sticky="nw")
        self._register_translatable(btn_desc, "text", "Beschreibung laden")
        self._add_tooltip(btn_desc, "Lädt eine Beschreibung aus einer Textdatei", "Schaltfläche: Beschreibung laden")
        row += 1

        frm.columnconfigure(1, weight=1)

    def build_build_tab(self, parent):
        frm = ttk.Frame(parent)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        row = 0

        def add_row(label, var, browse_cmd=None, browse_label="Wählen", width=60, show=None, tooltip_key=None, status_key=None, btn_tooltip_key=None, btn_status_key=None):
            nonlocal row
            lbl = ttk.Label(frm, text=_t(label))
            lbl.grid(row=row, column=0, sticky="w", pady=3)
            self._register_translatable(lbl, "text", label)

            ent = ttk.Entry(frm, textvariable=var, width=width, show=show)
            ent.grid(row=row, column=1, sticky="we", pady=3, padx=5)
            if tooltip_key:
                self._add_tooltip(ent, tooltip_key, status_key or tooltip_key)
            if browse_cmd:
                btn = ttk.Button(frm, text=_t(browse_label), command=browse_cmd)
                btn.grid(row=row, column=2, sticky="w")
                self._register_translatable(btn, "text", browse_label)
                if btn_tooltip_key:
                    self._add_tooltip(btn, btn_tooltip_key, btn_status_key or btn_tooltip_key)
            row += 1

        # NEU: Python Environment für externe Builds
        lbl_hdr1 = ttk.Label(frm, text=_t("Python Umgebung (für Builds)"), font=("Arial", 10, "bold"))
        lbl_hdr1.grid(row=row, column=0, columnspan=3, sticky="w", pady=(5,10))
        self._register_translatable(lbl_hdr1, "text", "Python Umgebung (für Builds)")
        row += 1

        add_row("Python.exe Pfad:", self.python_path, self.choose_python_exe, browse_label="Python wählen", tooltip_key="Pfad zur python.exe mit installiertem PyInstaller", status_key="Eingabefeld für den Python-Interpreter-Pfad", btn_tooltip_key="Wählt den Python-Interpreter aus", btn_status_key="Schaltfläche: Python-Pfad auswählen")
        lbl_hint = ttk.Label(frm, text=_t("Wichtig, wenn dieses Tool als EXE läuft. Muss 'pip install pyinstaller' haben."), foreground="gray")
        lbl_hint.grid(row=row, column=1, sticky="w")
        self._register_translatable(lbl_hint, "text", "Wichtig, wenn dieses Tool als EXE läuft. Muss 'pip install pyinstaller' haben.")
        row += 1

        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=10)
        row += 1

        lbl_hdr2 = ttk.Label(frm, text=_t("Windows SDK Tools"), font=("Arial", 10, "bold"))
        lbl_hdr2.grid(row=row, column=0, columnspan=3, sticky="w", pady=(5,10))
        self._register_translatable(lbl_hdr2, "text", "Windows SDK Tools")
        row += 1

        add_row("MakeAppx.exe:", self.makeappx_path, self.choose_makeappx, browse_label="MakeAppx wählen", tooltip_key="Pfad zu makeappx.exe aus dem Windows SDK", status_key="Eingabefeld für den MakeAppx-Pfad", btn_tooltip_key="Wählt makeappx.exe aus", btn_status_key="Schaltfläche: MakeAppx auswählen")
        add_row("SignTool.exe:", self.signtool_path, self.choose_signtool, browse_label="SignTool wählen", tooltip_key="Pfad zu signtool.exe aus dem Windows SDK", status_key="Eingabefeld für den SignTool-Pfad", btn_tooltip_key="Wählt signtool.exe aus", btn_status_key="Schaltfläche: SignTool auswählen")
        add_row("AppCert.exe (WACK):", self.appcert_path, self.choose_appcert, browse_label="AppCert wählen", tooltip_key="Pfad zu appcert.exe (Windows App Certification Kit)", status_key="Eingabefeld für den AppCert-Pfad", btn_tooltip_key="Wählt appcert.exe für WACK aus", btn_status_key="Schaltfläche: AppCert auswählen")

        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=10)
        row += 1

        lbl_hdr3 = ttk.Label(frm, text=_t("Zertifikat & Signierung"), font=("Arial", 10, "bold"))
        lbl_hdr3.grid(row=row, column=0, columnspan=3, sticky="w", pady=(5,10))
        self._register_translatable(lbl_hdr3, "text", "Zertifikat & Signierung")
        row += 1

        add_row("Zertifikat (.pfx):", self.pfx_path, self.choose_pfx, browse_label="Zertifikat wählen", tooltip_key="Pfad zum Code-Signing-Zertifikat (.pfx)", status_key="Eingabefeld für die Zertifikatsdatei", btn_tooltip_key="Wählt die PFX-Zertifikatsdatei aus", btn_status_key="Schaltfläche: Zertifikat auswählen")
        add_row("PFX Passwort:", self.pfx_password, show="*", tooltip_key="Passwort für das PFX-Zertifikat (wird sicher im Keyring abgelegt)", status_key="Eingabefeld für das Zertifikatspasswort")
        add_row("Timestamp URL:", self.timestamp_url, tooltip_key="RFC-3161 Zeitstempel-Server (z.B. http://timestamp.digicert.com)", status_key="Eingabefeld für die Timestamp-URL")
        add_row("MSIX Name:", self.msix_name, tooltip_key="Zieldateiname des MSIX-Pakets (z.B. MyApp.msix)", status_key="Eingabefeld für den MSIX-Paketnamen")

        lbl_keyring = ttk.Label(frm, text=_t("✓ Passwort wird sicher im Keyring gespeichert"), foreground="green")
        lbl_keyring.grid(row=row, column=1, sticky="w", pady=3)
        self._register_translatable(lbl_keyring, "text", "✓ Passwort wird sicher im Keyring gespeichert")
        row += 1

        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=10)
        row += 1

        chk_i18n = ttk.Checkbutton(frm, text=_t("Sprachmodul automatisch integrieren (i18n)"), variable=self.enable_i18n)
        chk_i18n.grid(row=row, column=0, columnspan=3, sticky="w", pady=8)
        self._register_translatable(chk_i18n, "text", "Sprachmodul automatisch integrieren (i18n)")
        self._add_tooltip(chk_i18n, "Bindet das universelle 6-Sprachen-Modul automatisch in die EXE ein", "Checkbox: Sprachmodul integrieren")
        row += 1

        frm.columnconfigure(1, weight=1)

    def build_store_tab(self, parent):
        frm = ttk.Frame(parent)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        row = 0

        def add_row(label, var, width=60, tooltip_key=None, status_key=None):
            nonlocal row
            lbl = ttk.Label(frm, text=_t(label))
            lbl.grid(row=row, column=0, sticky="w", pady=3)
            self._register_translatable(lbl, "text", label)

            ent = ttk.Entry(frm, textvariable=var, width=width)
            ent.grid(row=row, column=1, sticky="we", pady=3, padx=5)
            if tooltip_key:
                self._add_tooltip(ent, tooltip_key, status_key or tooltip_key)
            row += 1

        lbl_hdr = ttk.Label(frm, text=_t("Store-Pflichtfelder"), font=("Arial", 10, "bold"))
        lbl_hdr.grid(row=row, column=0, columnspan=2, sticky="w", pady=(5,10))
        self._register_translatable(lbl_hdr, "text", "Store-Pflichtfelder")
        row += 1

        add_row("Privacy Policy URL:", self.privacy_url, tooltip_key="Öffentliche HTTPS-URL zur Datenschutzerklärung", status_key="Eingabefeld für die Privacy-Policy-URL")
        add_row("Support URL:", self.support_url, tooltip_key="Öffentliche HTTPS-URL für Benutzer-Support und Anfragen", status_key="Eingabefeld für die Support-URL")
        add_row("Capabilities (Komma-getrennt):", self.capabilities, tooltip_key="Kommagetrennte Liste erforderlicher Windows-Rechte (z.B. internetClient)", status_key="Eingabefeld für Capabilities")

        lbl_cap = ttk.Label(frm, text=_t("Beispiele: internetClient, microphone, webcam, location"))
        lbl_cap.grid(row=row, column=1, sticky="w", pady=2)
        self._register_translatable(lbl_cap, "text", "Beispiele: internetClient, microphone, webcam, location")
        row += 1

        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=10)
        row += 1

        lbl_cat = ttk.Label(frm, text=_t("Kategorie:"))
        lbl_cat.grid(row=row, column=0, sticky="w", pady=3)
        self._register_translatable(lbl_cat, "text", "Kategorie:")

        cat_combo = ttk.Combobox(frm, textvariable=self.category, values=CATEGORIES, state="readonly", width=57)
        cat_combo.grid(row=row, column=1, sticky="w", pady=3, padx=5)
        self._add_tooltip(cat_combo, "Hauptkategorie im Microsoft Store", "Auswahlliste für Store-Kategorie")
        row += 1

        lbl_age = ttk.Label(frm, text=_t("Altersfreigabe:"))
        lbl_age.grid(row=row, column=0, sticky="w", pady=3)
        self._register_translatable(lbl_age, "text", "Altersfreigabe:")

        age_combo = ttk.Combobox(frm, textvariable=self.age_rating, values=AGE_RATINGS, state="readonly", width=57)
        age_combo.grid(row=row, column=1, sticky="w", pady=3, padx=5)
        self._add_tooltip(age_combo, "Altersfreigabe (z.B. 3+, 7+, 12+, 16+, 18+)", "Auswahlliste für Altersfreigabe")
        row += 1

        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=10)
        row += 1

        # Changelog-Generator
        lbl_chdr = ttk.Label(frm, text=_t("Changelog (Store-Listing)"), font=("Arial", 10, "bold"))
        lbl_chdr.grid(row=row, column=0, columnspan=2, sticky="w", pady=(5,10))
        self._register_translatable(lbl_chdr, "text", "Changelog (Store-Listing)")
        row += 1

        lbl_ctxt = ttk.Label(frm, text=_t("Changelog-Text:"))
        lbl_ctxt.grid(row=row, column=0, sticky="nw", pady=5)
        self._register_translatable(lbl_ctxt, "text", "Changelog-Text:")

        changelog_frame = ttk.Frame(frm)
        changelog_frame.grid(row=row, column=1, sticky="we", pady=5, padx=5)
        self.changelog_box = scrolledtext.ScrolledText(changelog_frame, width=60, height=6)
        self.changelog_box.pack(fill="both", expand=True)
        self.changelog_box.insert(tk.END, f"Version {self.version.get()}\n- \n- \n- ")
        self._add_tooltip(self.changelog_box, "Changelog-Eintrag für dieses Release", "Textfeld für Release-Hinweise")
        row += 1

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=row, column=1, sticky="w", pady=5, padx=5)

        btn_cf = ttk.Button(btn_frame, text=_t("Format für Store"), command=self.format_changelog)
        btn_cf.pack(side="left", padx=2)
        self._register_translatable(btn_cf, "text", "Format für Store")
        self._add_tooltip(btn_cf, "Formatiert den Text passend für das Microsoft Store Listing", "Schaltfläche: Changelog formatieren")

        btn_cc = ttk.Button(btn_frame, text=_t("In Zwischenablage"), command=self.copy_changelog)
        btn_cc.pack(side="left", padx=2)
        self._register_translatable(btn_cc, "text", "In Zwischenablage")
        self._add_tooltip(btn_cc, "Kopiert den formatierten Changelog in die Zwischenablage", "Schaltfläche: In Zwischenablage kopieren")
        row += 1

        frm.columnconfigure(1, weight=1)

    def build_actions_tab(self, parent):
        frm = ttk.Frame(parent)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        lbl_hdr1 = ttk.Label(frm, text=_t("Build-Aktionen"), font=("Arial", 12, "bold"))
        lbl_hdr1.pack(anchor="w", pady=(5,15))
        self._register_translatable(lbl_hdr1, "text", "Build-Aktionen")

        actions_frame = ttk.Frame(frm)
        actions_frame.pack(fill="x", pady=5)

        btn_a1 = ttk.Button(actions_frame, text=_t("1. Preflight-Check"), command=self.preflight_check, width=25)
        btn_a1.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self._register_translatable(btn_a1, "text", "1. Preflight-Check")
        self._add_tooltip(btn_a1, "Prüft alle Pflichtfelder und Pfade vor dem Paketbau (F5)", "Schaltfläche: Preflight-Prüfung starten")

        lbl_a1 = ttk.Label(actions_frame, text=_t("Validiert alle Pflichtfelder"))
        lbl_a1.grid(row=0, column=1, sticky="w", padx=10)
        self._register_translatable(lbl_a1, "text", "Validiert alle Pflichtfelder")

        btn_a2 = ttk.Button(actions_frame, text=_t("2. Paket erzeugen"), command=self.build_package, width=25)
        btn_a2.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        self._register_translatable(btn_a2, "text", "2. Paket erzeugen")
        self._add_tooltip(btn_a2, "Erstellt den Ausgabeordner, konvertiert Icons und generiert AppxManifest.xml", "Schaltfläche: Paket erzeugen")

        lbl_a2 = ttk.Label(actions_frame, text=_t("Erstellt Ausgabeordner mit allen Assets"))
        lbl_a2.grid(row=1, column=1, sticky="w", padx=10)
        self._register_translatable(lbl_a2, "text", "Erstellt Ausgabeordner mit allen Assets")

        btn_a3 = ttk.Button(actions_frame, text=_t("3. EXE bauen"), command=self.build_exe, width=25)
        btn_a3.grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        self._register_translatable(btn_a3, "text", "3. EXE bauen")
        self._add_tooltip(btn_a3, "Führt PyInstaller-Build mit allen Assets und i18n durch", "Schaltfläche: Standalone-EXE kompilieren")

        lbl_a3 = ttk.Label(actions_frame, text=_t("PyInstaller-Build mit i18n"))
        lbl_a3.grid(row=2, column=1, sticky="w", padx=10)
        self._register_translatable(lbl_a3, "text", "PyInstaller-Build mit i18n")

        btn_a4 = ttk.Button(actions_frame, text=_t("4. MSIX bauen & signieren"), command=self.build_and_sign_msix, width=25)
        btn_a4.grid(row=3, column=0, padx=5, pady=5, sticky="ew")
        self._register_translatable(btn_a4, "text", "4. MSIX bauen & signieren")
        self._add_tooltip(btn_a4, "Erstellt das MSIX-Paket mit makeappx und signiert es mit signtool", "Schaltfläche: MSIX bauen und signieren")

        lbl_a4 = ttk.Label(actions_frame, text=_t("Erstellt signiertes Store-Paket"))
        lbl_a4.grid(row=3, column=1, sticky="w", padx=10)
        self._register_translatable(lbl_a4, "text", "Erstellt signiertes Store-Paket")

        ttk.Separator(frm, orient='horizontal').pack(fill='x', pady=15)

        lbl_hdr2 = ttk.Label(frm, text=_t("Zusätzliche Aktionen"), font=("Arial", 12, "bold"))
        lbl_hdr2.pack(anchor="w", pady=(5,15))
        self._register_translatable(lbl_hdr2, "text", "Zusätzliche Aktionen")

        extras_frame = ttk.Frame(frm)
        extras_frame.pack(fill="x", pady=5)

        btn_e1 = ttk.Button(extras_frame, text=_t("Screenshots erzeugen"), command=self.run_screenshots, width=25)
        btn_e1.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        self._register_translatable(btn_e1, "text", "Screenshots erzeugen")
        self._add_tooltip(btn_e1, "Erstellt automatisierte Screenshots für den Store", "Schaltfläche: Screenshots aufnehmen")

        lbl_e1 = ttk.Label(extras_frame, text=_t("Automatische Store-Screenshots"))
        lbl_e1.grid(row=0, column=1, sticky="w", padx=10)
        self._register_translatable(lbl_e1, "text", "Automatische Store-Screenshots")

        btn_e2 = ttk.Button(extras_frame, text=_t("WACK-Test starten"), command=self.run_wack_test, width=25)
        btn_e2.grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        self._register_translatable(btn_e2, "text", "WACK-Test starten")
        self._add_tooltip(btn_e2, "Führt den Microsoft Windows App Certification Kit Test durch", "Schaltfläche: WACK-Zertifizierungstest ausführen")

        lbl_e2 = ttk.Label(extras_frame, text=_t("Windows App Certification Kit"))
        lbl_e2.grid(row=1, column=1, sticky="w", padx=10)
        self._register_translatable(lbl_e2, "text", "Windows App Certification Kit")

        btn_e3 = ttk.Button(extras_frame, text=_t("Ausgabeordner öffnen"), command=self.open_output_folder, width=25)
        btn_e3.grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        self._register_translatable(btn_e3, "text", "Ausgabeordner öffnen")
        self._add_tooltip(btn_e3, "Öffnet den Ausgabeordner im Windows-Explorer", "Schaltfläche: Ausgabeordner anzeigen")

        lbl_e3 = ttk.Label(extras_frame, text=_t("Zeigt erstellte Dateien"))
        lbl_e3.grid(row=2, column=1, sticky="w", padx=10)
        self._register_translatable(lbl_e3, "text", "Zeigt erstellte Dateien")

        btn_e4 = ttk.Button(extras_frame, text=_t("Projektprofil exportieren"), command=self.export_project_profile, width=25)
        btn_e4.grid(row=3, column=0, padx=5, pady=5, sticky="ew")
        self._register_translatable(btn_e4, "text", "Projektprofil exportieren")
        self._add_tooltip(btn_e4, "Speichert die Konfiguration ohne Geheimnisse als JSON (Strg+E)", "Schaltfläche: Profil exportieren")

        lbl_e4 = ttk.Label(extras_frame, text=_t("Export ohne Publisher- und Zertifikatsgeheimnisse"))
        lbl_e4.grid(row=3, column=1, sticky="w", padx=10)
        self._register_translatable(lbl_e4, "text", "Export ohne Publisher- und Zertifikatsgeheimnisse")

        btn_e5 = ttk.Button(extras_frame, text=_t("Projektprofil importieren"), command=self.import_project_profile, width=25)
        btn_e5.grid(row=4, column=0, padx=5, pady=5, sticky="ew")
        self._register_translatable(btn_e5, "text", "Projektprofil importieren")
        self._add_tooltip(btn_e5, "Lädt ein gespeichertes JSON-Projektprofil (Strg+O)", "Schaltfläche: Profil importieren")

        lbl_e5 = ttk.Label(extras_frame, text=_t("Lädt Web-/Desktop-Vorarbeit aus JSON"))
        lbl_e5.grid(row=4, column=1, sticky="w", padx=10)
        self._register_translatable(lbl_e5, "text", "Lädt Web-/Desktop-Vorarbeit aus JSON")

        ttk.Separator(frm, orient='horizontal').pack(fill='x', pady=15)

        bottom_frame = ttk.Frame(frm)
        bottom_frame.pack(fill="x", pady=5)

        btn_b1 = ttk.Button(bottom_frame, text=_t("Einstellungen speichern"), command=self.save_settings)
        btn_b1.pack(side="left", padx=5)
        self._register_translatable(btn_b1, "text", "Einstellungen speichern")
        self._add_tooltip(btn_b1, "Speichert alle Einstellungen und Pfade dauerhaft (Strg+S)", "Schaltfläche: Einstellungen speichern")

        btn_b2 = ttk.Button(bottom_frame, text=_t("Beenden"), command=self.on_quit)
        btn_b2.pack(side="right", padx=5)
        self._register_translatable(btn_b2, "text", "Beenden")
        self._add_tooltip(btn_b2, "Beendet das Programm nach Sicherheitsabfrage (Strg+Q)", "Schaltfläche: Programm beenden")

    # ---------- SDK autodetect ----------
    def autodetect_sdk_tools(self):
        if not self.makeappx_path.get() or not self.signtool_path.get() or not self.appcert_path.get():
            mk, sg, ac = find_windows_sdk_tools()
            if mk and not self.makeappx_path.get():
                self.makeappx_path.set(mk)
            if sg and not self.signtool_path.get():
                self.signtool_path.set(sg)
            if ac and not self.appcert_path.get():
                self.appcert_path.set(ac)

    # ---------- Logic: Determine Interpreter ----------
    def get_build_interpreter(self):
        """
        Ermittelt den Python-Interpreter für den Build-Prozess.
        Priorität:
        1. Benutzer-Einstellung (python_path)
        2. System PATH (shutil.which)
        3. Aktueller sys.executable (nur wenn NICHT als EXE laufend)
        """
        user_path = self.python_path.get().strip()
        if user_path and os.path.exists(user_path):
            return user_path

        system_python = shutil.which("python") or shutil.which("python3")
        if system_python:
            return system_python

        if not getattr(sys, 'frozen', False):
            return sys.executable

        return None

    # ---------- File Choosers ----------
    def choose_python_exe(self):
        path = filedialog.askopenfilename(filetypes=[("Executable", "python.exe"), ("All Files", "*.*")])
        if path:
            self.python_path.set(path)

    def choose_script(self):
        path = filedialog.askopenfilename(filetypes=[("Python Files", "*.py")])
        if path:
            self.script_path.set(path)

    def choose_icon(self):
        path = filedialog.askopenfilename(filetypes=[("PNG Files", "*.png")])
        if path:
            self.icon_path.set(path)

    def choose_source(self):
        path = filedialog.askopenfilename(filetypes=[("Source Files", "*.zip;*.py;*.txt;*.md"), ("All Files", "*.*")])
        if path:
            self.source_path.set(path)

    def choose_installer(self):
        path = filedialog.askopenfilename(filetypes=[("Installer", "*.exe;*.msix;*.msixbundle"), ("All Files", "*.*")])
        if path:
            self.installer_path.set(path)

    def load_readme_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt;*.md"), ("All Files", "*.*")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.readme_box.delete("1.0", tk.END)
                    self.readme_box.insert(tk.END, f.read())
            except Exception as e:
                messagebox.showerror("Fehler", f"Datei konnte nicht geladen werden:\n{e}")

    def load_desc_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt;*.md"), ("All Files", "*.*")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.desc_box.delete("1.0", tk.END)
                    self.desc_box.insert(tk.END, f.read())
            except Exception as e:
                messagebox.showerror("Fehler", f"Datei konnte nicht geladen werden:\n{e}")

    def choose_makeappx(self):
        path = filedialog.askopenfilename(filetypes=[("Executable", "*.exe"), ("All Files", "*.*")])
        if path:
            self.makeappx_path.set(path)

    def choose_signtool(self):
        path = filedialog.askopenfilename(filetypes=[("Executable", "*.exe"), ("All Files", "*.*")])
        if path:
            self.signtool_path.set(path)

    def choose_appcert(self):
        path = filedialog.askopenfilename(filetypes=[("Executable", "*.exe"), ("All Files", "*.*")])
        if path:
            self.appcert_path.set(path)

    def choose_pfx(self):
        path = filedialog.askopenfilename(filetypes=[("Certificate", "*.pfx"), ("All Files", "*.*")])
        if path:
            self.pfx_path.set(path)

    def add_license_file(self):
        path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt;*.md"), ("All Files", "*.*")])
        if path:
            self.license_files.append(path)
            messagebox.showinfo("Lizenz hinzugefügt", f"Datei hinzugefügt:\n{path}\n\nGesamt: {len(self.license_files)} Dateien")

    def add_license_text_entry(self):
        txt = self.license_box.get("1.0", tk.END).strip()
        if txt:
            self.license_text_entries.append(txt)
            self.license_box.delete("1.0", tk.END)
            messagebox.showinfo("Lizenz hinzugefügt", f"Text als zusätzliche Lizenz gespeichert.\n\nGesamt: {len(self.license_text_entries)} Texteinträge")
        else:
            messagebox.showwarning("Hinweis", "Bitte Lizenztext eingeben und erneut klicken.")

    def open_output_folder(self):
        outdir = self.package_dir()
        if os.path.exists(outdir):
            if sys.platform == "win32":
                os.startfile(outdir)
            else:
                subprocess.run(["xdg-open", outdir])
        else:
            messagebox.showwarning("Hinweis", f"Ausgabeordner existiert noch nicht:\n{outdir}")

    # ---------- Helpers ----------
    def build_icons(self, icon_src, icon_dir):
        img = Image.open(icon_src)
        os.makedirs(icon_dir, exist_ok=True)

        for size in ICON_SIZES:
            resized = img.resize((size, size), Image.LANCZOS)
            out_path = os.path.join(icon_dir, f"icon_{size}x{size}.png")
            resized.save(out_path)

        wide = img.resize(WIDE_ICON_SIZE, Image.LANCZOS)
        wide.save(os.path.join(icon_dir, "icon_310x150.png"))

    def write_text_file(self, path, content):
        if content:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content.strip())

    def package_dir(self):
        appname = (self.app_name.get().strip() or "MyApp")
        outdir_root = os.path.abspath(self.output_dir.get().strip() or OUTPUT_ROOT)
        package_leaf = safe_package_dir_name(appname)
        outdir = os.path.abspath(os.path.join(outdir_root, package_leaf))
        if os.path.commonpath([outdir_root, outdir]) != outdir_root:
            raise ValueError("Ausgabeordner muss innerhalb des gewählten Output-Ordners liegen.")
        return outdir

    # ---------- i18n integration ----------
    def integrate_i18n(self, outdir, script_to_patch=None):
        """
        Create i18n folder and files, and patch the given script.
        """
        try:
            i18n_dir = os.path.join(outdir, "i18n")
            os.makedirs(os.path.join(i18n_dir, "locales"), exist_ok=True)

            # translator.py - FIX: Handle frozen path
            translator_code = '''import json
import os, sys

class Translator:
    def __init__(self, lang="de", file_path="i18n/locales/translations.json"):
        # Detect if running as PyInstaller OneFile
        if hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.abspath(".")

        full_path = os.path.join(base_path, file_path)

        if os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    self.translations = json.load(f)
            except (json.JSONDecodeError, OSError):
                self.translations = {}
                print(f"Warning: Translation file could not be parsed: {full_path}")
        else:
            self.translations = {}
            print(f"Warning: Translation file not found at {full_path}")

        self.lang = lang

    def set_lang(self, lang):
        self.lang = lang

    def t(self, key: str) -> str:
        entry = self.translations.get(key)
        if not entry:
            return key
        return entry.get(self.lang, entry.get("en", entry.get("de", key)))
'''
            with open(os.path.join(i18n_dir, "translator.py"), "w", encoding="utf-8") as f:
                f.write(translator_code)

            # translator_patch.py
            patch_code = '''import tkinter as tk
from tkinter import ttk

def patch_widgets(translator):
    def wrap_factory(widget_cls):
        class Wrapped(widget_cls):
            def __init__(self, master=None, **kw):
                if "text" in kw:
                    kw["text"] = translator.t(kw["text"])
                super().__init__(master, **kw)
        return Wrapped

    tk.Label = wrap_factory(tk.Label)
    ttk.Label = wrap_factory(ttk.Label)
    ttk.Button = wrap_factory(ttk.Button)
    ttk.Checkbutton = wrap_factory(ttk.Checkbutton)
    ttk.Radiobutton = wrap_factory(ttk.Radiobutton)
'''
            with open(os.path.join(i18n_dir, "translator_patch.py"), "w", encoding="utf-8") as f:
                f.write(patch_code)

            # translations.json
            translations = {
                "Sprache": {"de": "Sprache", "en": "Language", "es": "Idioma", "zh": "语言", "ja": "言語", "ru": "Язык"},
                "Deutsch": {"de": "Deutsch", "en": "German", "es": "Alemán", "zh": "德语", "ja": "ドイツ語", "ru": "Немецкий"},
                "English": {"de": "Englisch", "en": "English", "es": "Inglés", "zh": "英语", "ja": "英語", "ru": "Английский"},
                "Wählen": {"de": "Wählen", "en": "Choose", "es": "Elegir", "zh": "选择", "ja": "選択", "ru": "Выбрать"},
                "Beenden": {"de": "Beenden", "en": "Quit", "es": "Salir", "zh": "退出", "ja": "終了", "ru": "Выход"},
                "Öffnen": {"de": "Öffnen", "en": "Open", "es": "Abrir", "zh": "打开", "ja": "開く", "ru": "Открыть"},
                "Speichern": {"de": "Speichern", "en": "Save", "es": "Guardar", "zh": "保存", "ja": "保存", "ru": "Сохранить"},
                "Abbrechen": {"de": "Abbrechen", "en": "Cancel", "es": "Cancelar", "zh": "取消", "ja": "キャンセル", "ru": "Отмена"},
                "OK": {"de": "OK", "en": "OK", "es": "Aceptar", "zh": "确定", "ja": "OK", "ru": "ОК"},
                "Fehler": {"de": "Fehler", "en": "Error", "es": "Error", "zh": "错误", "ja": "エラー", "ru": "Ошибка"},
                "Warnung": {"de": "Warnung", "en": "Warning", "es": "Advertencia", "zh": "警告", "ja": "警告", "ru": "Предупреждение"},
                "Info": {"de": "Info", "en": "Info", "es": "Información", "zh": "信息", "ja": "情報", "ru": "Информация"}
            }
            with open(os.path.join(i18n_dir, "locales", "translations.json"), "w", encoding="utf-8") as f:
                json.dump(translations, f, indent=2, ensure_ascii=False)

            # Patch the staged script
            if script_to_patch and os.path.isfile(script_to_patch):
                with open(script_to_patch, "r", encoding="utf-8") as f:
                    code = f.read()

                needs_import = ("from i18n.translator import Translator" not in code)
                needs_enable = ("patch_widgets(" not in code)

                class_regex = r"(\nclass\s+\w+(?:\(.*\))?:)"

                if needs_import:
                    if re.search(class_regex, code):
                        code = re.sub(
                            class_regex,
                            "\nfrom i18n.translator import Translator\nfrom i18n.translator_patch import patch_widgets\\1",
                            code,
                            count=1
                        )
                    else:
                        code = f"from i18n.translator import Translator\nfrom i18n.translator_patch import patch_widgets\n{code}"

                if needs_enable:
                    if re.search(r"(super\(\)\.__init__\(\))", code):
                        code = re.sub(
                            r"(super\(\)\.__init__\(\))",
                            r"\1\n        self.translator = Translator(lang=\"de\")\n        patch_widgets(self.translator)",
                            code,
                            count=1
                        )
                    else:
                        pass

                with open(script_to_patch, "w", encoding="utf-8") as f:
                    f.write(code)

            return True, "Sprachmodul integriert."
        except Exception as e:
            return False, str(e)

    # ---------- License collection ----------
    def _get_requirements_hash(self) -> str:
        """Berechnet MD5-Hash der requirements.txt fuer Cache-Invalidierung."""
        req_file = os.path.join(os.path.dirname(self.script_path.get() or __file__), "requirements.txt")
        if not os.path.exists(req_file):
            return ""
        try:
            with open(req_file, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except OSError:
            return ""

    def collect_python_licenses(self, outdir):
        target = os.path.join(outdir, "THIRD_PARTY_LICENSES.txt")
        cache_file = os.path.join(outdir, ".licenses_cache.json")

        # Cache pruefen: nur neu sammeln wenn requirements.txt sich geaendert hat
        req_hash = self._get_requirements_hash()
        if os.path.exists(cache_file) and os.path.exists(target):
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cache_meta = json.load(f)
                if cache_meta.get("req_hash") == req_hash and req_hash != "":
                    return True, target  # Cache gueltig
            except (OSError, json.JSONDecodeError, KeyError):
                pass  # Cache defekt -> neu sammeln

        try:
            python_exe = self.get_build_interpreter() or sys.executable
            with open(target, "w", encoding="utf-8") as f:
                subprocess.run(
                    [python_exe, "-m", "pip_licenses",
                     "--with-license-file", "--format=plain"],
                    stdout=f,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=120
                )

            # Cache-Metadaten speichern
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"req_hash": req_hash}, f)

            return True, target
        except subprocess.TimeoutExpired:
            if os.path.exists(target):
                os.remove(target)
            return False, "Timeout beim Sammeln der Lizenzen"
        except subprocess.CalledProcessError:
            if os.path.exists(target):
                os.remove(target)
            return False, (
                "pip-licenses konnte nicht ausgeführt werden. Installiere das Werkzeug vorab "
                "in einer kontrollierten Build-Umgebung und starte die Lizenzsammlung erneut."
            )
        except Exception as e:
            if os.path.exists(target):
                os.remove(target)
            return False, str(e)

    # ---------- Builders ----------
    def build_exe(self):
        script = self.script_path.get().strip()
        if not script or not os.path.exists(script):
            messagebox.showerror("Fehler", "Bitte gültiges Haupt-Skript auswählen.")
            return

        # --- FIX: Benutze externen Interpreter statt sys.executable (vermeidet Rekursion)
        python_exe = self.get_build_interpreter()
        if not python_exe:
            messagebox.showerror("Konfiguration fehlt",
                "Kein Python-Interpreter gefunden!\n\n"
                "Da dieses Tool als EXE läuft, kann es sich nicht selbst zum Bauen verwenden.\n"
                "Bitte gib im Reiter 'Build-Einstellungen' den Pfad zu deiner python.exe an.")
            return

        # Check if PyInstaller is available in that environment
        try:
            subprocess.run([python_exe, "-m", "PyInstaller", "--version"],
                           capture_output=True, check=True, timeout=10)
        except Exception:
            if not messagebox.askyesno("Warnung",
                f"Es scheint, als sei PyInstaller in diesem Python nicht installiert:\n{python_exe}\n\n"
                "Trotzdem versuchen fortzufahren?"):
                return

        appname = self.app_name.get().strip() or "MyApp"
        outdir = self.package_dir()
        os.makedirs(outdir, exist_ok=True)

        progress = ProgressDialog(self, "EXE wird gebaut...")

        def build_thread():
            try:
                progress.update_status("Staging Skript...")
                staged_script = os.path.join(outdir, os.path.basename(script))
                shutil.copy(script, staged_script)

                # i18n integration
                i18n_data_arg = []
                if self.enable_i18n.get():
                    progress.update_status("Integriere i18n-Modul...")
                    ok, info = self.integrate_i18n(outdir, script_to_patch=staged_script)
                    if not ok:
                        self.after(0, lambda: messagebox.showwarning("Warnung",
                            f"Sprachmodul konnte nicht integriert werden:\n{info}"))
                    else:
                        i18n_path = os.path.join(outdir, "i18n")
                        i18n_data_arg = ["--add-data", f"{i18n_path};i18n"]

                exe_name = self.exe_name.get().strip() or f"{appname}.exe"

                progress.update_status("PyInstaller läuft...")
                icon_arg = []
                if self.icon_path.get() and os.path.exists(self.icon_path.get()):
                    icon_arg = ["--icon", self.icon_path.get()]

                # --- FIX: Verwende python_exe Variable ---
                cmd = [
                    python_exe, "-m", "PyInstaller",
                    "--onefile",
                    "--name", os.path.splitext(exe_name)[0],
                    "--distpath", outdir,
                    *icon_arg,
                    *i18n_data_arg,
                    staged_script
                ]

                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                build_env = os.environ.copy()
                build_env["PYTHONIOENCODING"] = "utf-8"
                # Bugsweep 25: grosszuegiger Timeout (30 min) als Notbremse gegen einen haengenden
                # PyInstaller-Lauf; normale Builds bleiben weit darunter. TimeoutExpired -> Fehlerdialog.
                subprocess.run(cmd, capture_output=True, check=True, startupinfo=startupinfo, env=build_env, timeout=1800)

                progress.update_status("Aufräumen...")
                # Cleanup relativ zum Output-Verzeichnis (nicht cwd!)
                cleanup_base = os.path.dirname(staged_script) if staged_script else os.getcwd()
                for pattern in ["build", "*.spec"]:
                    for item in glob.glob(os.path.join(cleanup_base, pattern)):
                        try:
                            if os.path.isdir(item):
                                shutil.rmtree(item)
                            else:
                                os.remove(item)
                        except OSError:
                            pass

                final = os.path.join(outdir, exe_name)
                if not os.path.exists(final):
                    possible = os.path.join(outdir, os.path.splitext(exe_name)[0] + ".exe")
                    if os.path.exists(possible):
                        final = possible

                progress.update_status("Sammle Drittanbieter-Lizenzen...")
                ok_lic, info_lic = self.collect_python_licenses(outdir)

                progress.close()

                msg = f"EXE erzeugt:\n{final}\n\nErstellt mit:\n{python_exe}"
                if ok_lic:
                    msg += f"\n\nDrittanbieter-Lizenzen:\n{info_lic}"
                else:
                    msg += f"\n\nLizenzen-Warnung:\n{info_lic}"

                self.after(0, lambda m=msg: messagebox.showinfo("Fertig", m))

            except subprocess.CalledProcessError as e:
                progress.close()
                err_out = e.stderr.decode('utf-8', errors='replace') if e.stderr else "Unbekannter Fehler"
                self.after(0, lambda err=err_out: messagebox.showerror("PyInstaller Fehler", f"{err}"))
            except Exception as e:
                err_str = str(e)
                progress.close()
                self.after(0, lambda err=err_str: messagebox.showerror("Fehler", f"EXE-Erzeugung fehlgeschlagen:\n{err}"))

        thread = threading.Thread(target=build_thread, daemon=True)
        thread.start()

    def build_package(self):
        appname = self.app_name.get().strip()
        if not appname:
            messagebox.showerror(_t("Fehler"), _t("Bitte App-Name eingeben."))
            return

        outdir = self.package_dir()
        if os.path.exists(outdir):
            if not messagebox.askyesno(
                _t("Bestätigung"),
                f"{_t('Ausgabeordner existiert bereits:')}\n{outdir}\n\n{_t('Überschreiben?')}",
            ):
                return
            shutil.rmtree(outdir)
        os.makedirs(outdir, exist_ok=True)

        try:
            script = self.script_path.get().strip()
            staged_script = None
            if script and os.path.exists(script):
                staged_script = os.path.join(outdir, os.path.basename(script))
                shutil.copy(script, staged_script)

            icon = self.icon_path.get().strip()
            if icon and os.path.exists(icon):
                self.build_icons(icon, os.path.join(outdir, "icons"))

            readme_content = self.readme_box.get("1.0", tk.END).strip()
            if readme_content:
                self.write_text_file(os.path.join(outdir, "README.txt"), readme_content)

            if self.license_files:
                for i, path in enumerate(self.license_files, 1):
                    try:
                        shutil.copy(path, os.path.join(outdir, f"LICENSE_{i}.txt"))
                    except Exception as e:
                        messagebox.showwarning(
                            _t("Warnung"),
                            f"{_t('Konnte Lizenzdatei nicht kopieren:')}\n{path}\n{e}",
                        )

            for i, txt in enumerate(self.license_text_entries, 1):
                self.write_text_file(os.path.join(outdir, f"LICENSE_TEXT_{i}.txt"), txt)

            if not self.license_files and not self.license_text_entries:
                lic = self.license_box.get("1.0", tk.END).strip()
                if lic:
                    self.write_text_file(os.path.join(outdir, "LICENSE.txt"), lic)

            desc_content = self.desc_box.get("1.0", tk.END).strip()
            if desc_content:
                self.write_text_file(os.path.join(outdir, "DESCRIPTION.txt"), desc_content)

            src = self.source_path.get().strip()
            if src and os.path.exists(src):
                self.stage_payload(src, outdir)

            installer = self.installer_path.get().strip()
            if installer and os.path.exists(installer):
                self.stage_payload(installer, outdir)

            if self.enable_i18n.get() and staged_script:
                ok, info = self.integrate_i18n(outdir, script_to_patch=staged_script)
                if not ok:
                    messagebox.showwarning(
                        _t("Warnung"),
                        f"{_t('Sprachmodul konnte nicht integriert werden:')}\n{info}",
                    )

            exe_name = self.exe_name.get().strip()
            if not exe_name:
                exes = [f for f in os.listdir(outdir) if f.lower().endswith(".exe")]
                exe_name = exes[0] if exes else f"{appname}.exe"

            self.generate_manifest(outdir, exe_name)

            ok_lic, info_lic = self.collect_python_licenses(outdir)

            self.save_settings()

            msg = f"{_t('Paket erstellt:')} {appname}\n{outdir}"
            if ok_lic:
                msg += f"\n\n{_t('Drittanbieter-Lizenzen gesammelt:')}\n{info_lic}"
            else:
                msg += f"\n\n{_t('Lizenzen-Warnung:')}\n{info_lic}"

            messagebox.showinfo(_t("Fertig"), msg)

        except Exception as e:
            messagebox.showerror(
                _t("Fehler"),
                f"{_t('Paket-Erstellung fehlgeschlagen:')}\n{e}",
            )

    # ---------- MSIX Build & Sign ----------
    def build_and_sign_msix(self):
        outdir = self.package_dir()
        if not os.path.isdir(outdir):
            messagebox.showerror("Fehler", "Bitte zuerst das Paket erzeugen.")
            return

        manifest_path = os.path.join(outdir, "AppxManifest.xml")
        if not os.path.exists(manifest_path):
            messagebox.showerror("Fehler", "AppxManifest.xml nicht gefunden. Bitte Paket erzeugen.")
            return

        makeappx = self.makeappx_path.get().strip()
        signtool = self.signtool_path.get().strip()

        if not (makeappx and os.path.isfile(makeappx)):
            messagebox.showerror("Fehler", "MakeAppx.exe nicht gefunden. Bitte Pfad setzen.")
            return
        if not (signtool and os.path.isfile(signtool)):
            messagebox.showerror("Fehler", "SignTool.exe nicht gefunden. Bitte Pfad setzen.")
            return

        msix_name = self.msix_name.get().strip()
        if not msix_name:
            appname = self.app_name.get().strip() or "MyApp"
            msix_name = f"{appname}.msix"
            self.msix_name.set(msix_name)

        msix_path = os.path.join(outdir, msix_name)

        progress = ProgressDialog(self, "MSIX wird gebaut...")

        def build_thread():
            try:
                progress.update_status("Erstelle MSIX-Paket...")
                # Das Paket entsteht IM Verzeichnis, das gepackt wird. Bleibt das
                # MSIX des letzten Laufs liegen, wandert es in das neue hinein und
                # die Paketgroesse verdoppelt sich bei jedem Build.
                if os.path.exists(msix_path):
                    os.remove(msix_path)
                cmd_pack = [makeappx, "pack", "/d", outdir, "/p", msix_path, "/o"]
                # Bugsweep 25 BUG-msix (KRITISCH): timeout, sonst kann makeappx/signtool haengen und
                # die App friert dauerhaft ein (signtool wartet ggf. auf Timestamp-Server uebers Netz).
                subprocess.run(cmd_pack, capture_output=True, text=True, check=True, timeout=300)

                pfx = self.pfx_path.get().strip()
                pfx_pw = self.pfx_password.get()
                ts_url = self.timestamp_url.get().strip()

                valid_cred, cred_errs = validate_signing_credentials(pfx, pfx_pw, self.publisher.get(), ts_url)
                if not valid_cred:
                    progress.close()
                    err_msg = "Zertifikats- und Signatur-Prüfung fehlgeschlagen:\n\n" + "\n".join(cred_errs)
                    self.after(0, lambda msg=err_msg: messagebox.showerror("Fehler", msg))
                    return

                progress.update_status("Signiere MSIX...")
                cmd_sign = [
                    signtool, "sign",
                    "/f", pfx,
                    "/p", pfx_pw,
                    "/fd", "SHA256",
                    "/tr", ts_url,
                    "/td", "SHA256",
                    "/v", msix_path
                ]
                subprocess.run(cmd_sign, capture_output=True, text=True, check=True, timeout=120)

                progress.close()
                self.after(0, lambda: messagebox.showinfo("Fertig",
                    f"MSIX gebaut und signiert:\n{msix_path}\n\nBereit für den Store!"))

            except subprocess.CalledProcessError as e:
                progress.close()
                # Passwort aus Fehlermeldung entfernen
                safe_cmd = [x if x != pfx_pw else "***" for x in (e.cmd or [])]
                error_msg = f"Befehl fehlgeschlagen:\n{safe_cmd}\n\nAusgabe:\n{e.stderr if e.stderr else e.stdout}"
                self.after(0, lambda msg=error_msg: messagebox.showerror("Fehler", msg))
            except Exception as e:
                err_str = str(e)
                progress.close()
                self.after(0, lambda err=err_str: messagebox.showerror("Fehler",
                    f"MSIX-Build fehlgeschlagen:\n{err}"))

        thread = threading.Thread(target=build_thread, daemon=True)
        thread.start()

    # ---------- Staging ----------
    def stage_payload(self, path, outdir):
        """Kopiert eine Datei ins Staging - bei onedir-Builds den ganzen Ordner.

        PyInstaller kennt zwei Bauformen: bei --onefile genuegt die EXE, bei
        --onedir liegen Laufzeit und Bibliotheken daneben in _internal/. Kopiert
        man dort nur die EXE, laesst sich das MSIX zwar installieren, die App
        startet aber nicht. Rueckgabe: Anzahl kopierter Dateien.
        """
        app_dir = os.path.dirname(os.path.abspath(path))
        if path.lower().endswith(".exe") and os.path.isdir(os.path.join(app_dir, "_internal")):
            shutil.copytree(app_dir, outdir, dirs_exist_ok=True)
            return sum(len(files) for _, _, files in os.walk(app_dir))
        shutil.copy(path, os.path.join(outdir, os.path.basename(path)))
        return 1

    # ---------- Manifest ----------
    def generate_manifest(self, outdir, executable_name):
        desc = self.desc_box.get("1.0", tk.END).strip()
        manifest = MANIFEST_TEMPLATE

        # Bugsweep 25 BUG-manifest (KRITISCH): ALLE user-kontrollierten Felder XML-escapen, nicht nur
        # APPNAME. Ein '&', '<' oder '"' in Publisher/Description/Identity/Executable brach sonst das
        # AppxManifest.xml -> ungueltiges MSIX. (Der Cert-DN in {{PUBLISHER}} ist nach XML-Parse
        # semantisch identisch -> Cert-Matching bleibt korrekt.)
        sanitized_app_id = sanitize_application_id(self.app_name.get().strip() or "MyApp")
        manifest = manifest.replace("{{IDENTITY_NAME}}",
            html.escape(self.identity_name.get().strip() or f"YourCompany.{sanitized_app_id}"))
        manifest = manifest.replace("{{PUBLISHER}}",
            html.escape(self.publisher.get().strip() or "CN=YourPublisher"))
        manifest = manifest.replace("{{APPNAME}}",
            html.escape(self.app_name.get().strip() or "MyApp"))
        # Die Id ist NICHT der Anzeigename: sie muss dem AppX-Schema genuegen
        # (keine Leerzeichen/Bindestriche). Bereits veroeffentlichte Pakete
        # nutzen den bereinigten Namen ohne Suffix - dieselbe Ableitung, damit
        # ein Neupacken die Id einer publizierten App nicht veraendert.
        manifest = manifest.replace("{{APPID}}",
            html.escape(sanitized_app_id))
        manifest = manifest.replace("{{PUBLISHER_DISPLAY}}",
            html.escape(self.publisher_display.get().strip() or self.publisher.get().strip().replace("CN=", "") or "YourPublisher"))
        manifest = manifest.replace("{{DESCRIPTION}}",
            html.escape(desc or "No description provided."))
        manifest = manifest.replace("{{VERSION}}",
            html.escape(self.version.get().strip() or DEFAULT_VERSION))
        manifest = manifest.replace("{{EXECUTABLE}}",
            html.escape(executable_name or "MyApp.exe"))

        # Faehigkeiten liegen je nach Art in verschiedenen Namensraeumen. Schreibt
        # man alle als <Capability>, weist makeappx das GANZE Manifest ab, sobald
        # eine eingeschraenkte Faehigkeit wie runFullTrust dabei ist
        # ("verstoesst gegen enumeration-Einschraenkung").
        # Geraetefaehigkeiten (webcam, microphone, etc.) gehoeren zu <DeviceCapability>.
        caps = ""
        if self.capabilities.get().strip():
            for c in self.capabilities.get().split(","):
                c = c.strip()
                if not c:
                    continue
                if c in GENERAL_CAPABILITIES:
                    tag = "Capability"
                elif c in UAP_CAPABILITIES:
                    tag = "uap:Capability"
                elif c in DEVICE_CAPABILITIES:
                    tag = "DeviceCapability"
                else:
                    # runFullTrust, broadFileSystemAccess & Co. sind eingeschraenkt.
                    tag = "rescap:Capability"
                caps += f'    <{tag} Name="{html.escape(c)}"/>\n'
        manifest = manifest.replace("{{CAPABILITIES}}", caps)

        # Ohne <Resources> kennt das Paket keine Sprache. Der Store kann dann
        # DisplayName, PublisherDisplayName und die Logos nicht aufloesen und
        # meldet sie als leer bzw. "not found" - obwohl sie im Manifest stehen.
        # Zugriff ueber __dict__, nicht ueber hasattr/getattr: Tk delegiert
        # unbekannte Attribute an self.tk weiter und laeuft dabei in eine
        # Endlosschleife, wenn das Objekt ohne __init__ erzeugt wurde.
        languages_var = self.__dict__.get("languages")
        languages = (languages_var.get().strip() if languages_var else "") or DEFAULT_LANGUAGES
        res = ""
        for lang in languages.split(","):
            lang = lang.strip()
            if lang:
                res += f'    <Resource Language="{html.escape(lang)}"/>\n'
        manifest = manifest.replace("{{RESOURCES}}", res)

        # Erweiterungen (Dateizuordnung, Alias, Protokoll, Autostart) stammen aus
        # der Projektkonfiguration store_package.json - dieselbe Quelle wie beim
        # CLI-Werkzeug store-packager, damit kein zweiter Standard entsteht.
        project_config = {}
        try:
            src = (self.source_path.get() or "").strip()
            candidates = []
            if src:
                base = src if os.path.isdir(src) else os.path.dirname(src)
                if base:
                    candidates.append(os.path.join(base, "store_package.json"))
            candidates.append(os.path.join(outdir, "store_package.json"))
            for cfg_path in candidates:
                if os.path.isfile(cfg_path):
                    with open(cfg_path, encoding="utf-8-sig") as cf:
                        project_config = json.load(cf)
                    print("[i] Projektkonfiguration gelesen: %s" % cfg_path)
                    break
        except Exception as exc:  # Konfiguration darf den Build nie brechen
            print("[!] store_package.json nicht lesbar: %s" % exc)

        extensions, extra_ns = build_manifest_extensions(project_config, executable_name or "MyApp.exe")
        if "rescap3" in extra_ns:
            print("[!] Hinweis: MigrationProgIds nutzen die eingeschraenkte Faehigkeit "
                  "rescap3. Der Microsoft Store verlangt dafuer eine vorherige Freigabe.")
        ns_attr, ignorable = build_manifest_namespaces(extra_ns)
        manifest = manifest.replace("{{EXTENSIONS}}", extensions)
        manifest = manifest.replace("{{NAMESPACES}}", ns_attr)
        manifest = manifest.replace("{{IGNORABLE}}", ignorable)
        manifest = manifest.replace("{{MINVERSION}}",
            html.escape(str(project_config.get("min_version") or DEFAULT_MIN_VERSION)))
        manifest = manifest.replace("{{MAXVERSION}}",
            html.escape(str(project_config.get("max_version_tested") or DEFAULT_MAX_VERSION_TESTED)))

        with open(os.path.join(outdir, "AppxManifest.xml"), "w", encoding="utf-8") as f:
            f.write(manifest)

    # ---------- Screenshots ----------
    def run_screenshots(self):
        if not gw:
            messagebox.showerror("Fehler",
                "pygetwindow nicht verfügbar. Installieren Sie: pip install pygetwindow")
            return

        exe_name = self.exe_name.get() or f"{self.app_name.get()}.exe"
        exe_path = os.path.join(self.package_dir(), exe_name)

        if not os.path.exists(exe_path):
            messagebox.showerror("Fehler", f"EXE nicht gefunden:\n{exe_path}\n\nBitte zuerst EXE bauen.")
            return

        outdir = self.package_dir()
        app_name = self.app_name.get()

        def _do_screenshots():
            proc = None
            try:
                proc = subprocess.Popen([exe_path])
                time.sleep(5)

                windows = gw.getWindowsWithTitle(app_name)
                if windows:
                    try:
                        windows[0].activate()
                    except Exception:
                        pass
                    time.sleep(1)

                img = ImageGrab.grab()
                shots_dir = os.path.join(outdir, "screenshots")
                os.makedirs(shots_dir, exist_ok=True)

                formats = [
                    (1240, 600, "Desktop 16:9"),
                    (2480, 1200, "Desktop 16:9 @2x"),
                    (1080, 1920, "Mobile Portrait"),
                    (1920, 1080, "Desktop Landscape")
                ]

                for width, height, desc in formats:
                    resized = img.resize((width, height), Image.LANCZOS)
                    filename = f"screenshot_{width}x{height}.png"
                    resized.save(os.path.join(shots_dir, filename))

                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=3)

                info_msg = (
                    f"Screenshots in Store-Formaten gespeichert:\n{shots_dir}\n\n"
                    + "\n".join([f"• {w}x{h} ({d})" for w, h, d in formats])
                )
                self.after(0, lambda m=info_msg: messagebox.showinfo("Screenshots", m))

            except Exception as e:
                if proc is not None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except Exception:
                        pass
                err_msg = f"Screenshots fehlgeschlagen:\n{e}"
                self.after(0, lambda err=err_msg: messagebox.showerror("Fehler", err))

        t = threading.Thread(target=_do_screenshots, daemon=True)
        t.start()

    # ---------- WACK ----------
    def run_wack_test(self):
        appcert = self.appcert_path.get().strip()
        if not appcert or not os.path.exists(appcert):
            appcert = which("appcert.exe")
            if not appcert:
                messagebox.showerror("Fehler",
                    "appcert.exe nicht gefunden. Windows SDK erforderlich.")
                return
            self.appcert_path.set(appcert)

        msix_name = self.msix_name.get().strip() or f"{self.app_name.get()}.msix"
        msix_path = os.path.join(self.package_dir(), msix_name)

        if not os.path.exists(msix_path):
            messagebox.showerror("Fehler",
                f"MSIX-Datei nicht gefunden:\n{msix_path}\n\nBitte zuerst MSIX bauen.")
            return

        appcert_path = appcert
        msix_path_captured = msix_path
        report_path = os.path.join(self.package_dir(), "WACK_Report.xml")

        def _run_wack():
            try:
                subprocess.run([appcert_path, "reset"], capture_output=True, timeout=30)
                self.after(0, _launch_test)
            except Exception as exc:
                err_msg = f"WACK-Test Reset fehlgeschlagen:\n{exc}"
                self.after(0, lambda err=err_msg: messagebox.showerror("Fehler", err))

        def _launch_test():
            try:
                messagebox.showinfo("WACK-Test",
                    f"WACK-Test wird gestartet...\n\nDies kann mehrere Minuten dauern.\n"
                    f"Ergebnisbericht wird gespeichert unter:\n{report_path}")
                cmd = [appcert_path, "test", "-apptype", "uap", "-packagepath", msix_path_captured, "-reportpath", report_path]
                subprocess.Popen(cmd)
            except Exception as exc:
                messagebox.showerror("Fehler", f"WACK-Test Start fehlgeschlagen:\n{exc}")

        threading.Thread(target=_run_wack, daemon=True).start()

    # ---------- Changelog Generator ----------
    def format_changelog(self):
        """Format changelog for Microsoft Store listing."""
        text = self.changelog_box.get("1.0", tk.END).strip()
        if not text:
            text = f"Version {self.version.get()}"

        lines = text.split('\n')
        formatted = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Add bullet if not already present
            if line and not line.startswith(('-', '*', 'Version', 'v')):
                line = f"- {line}"
            formatted.append(line)

        # Ensure version header
        if formatted and not formatted[0].lower().startswith('version'):
            formatted.insert(0, f"Version {self.version.get()}")

        result = '\n'.join(formatted)
        self.changelog_box.delete("1.0", tk.END)
        self.changelog_box.insert(tk.END, result)
        messagebox.showinfo("Formatiert", "Changelog wurde für Store-Listing formatiert.")

    def copy_changelog(self):
        """Copy changelog to clipboard."""
        text = self.changelog_box.get("1.0", tk.END).strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Kopiert", "Changelog in Zwischenablage kopiert.")

    # ---------- Preflight Check ----------
    def preflight_check(self):
        issues = []

        if not self.app_name.get().strip():
            issues.append("❌ App-Name fehlt")

        valid, msg = validate_publisher_cn(self.publisher.get())
        if not valid:
            issues.append(f"❌ Publisher: {msg}")

        if not self.script_path.get().strip() or not os.path.exists(self.script_path.get()):
            issues.append("❌ Haupt-Skript fehlt oder existiert nicht")

        if not self.icon_path.get().strip() or not os.path.exists(self.icon_path.get()):
            issues.append("❌ Icon fehlt oder existiert nicht")
        else:
            try:
                img = Image.open(self.icon_path.get())
                if img.width < 310 or img.height < 310:
                    issues.append(f"⚠️  Icon zu klein ({img.width}x{img.height}), mindestens 310x310 empfohlen")
            except Exception as e:
                issues.append(f"Warnung: Icon konnte nicht gelesen werden: {e}")

        if not self.privacy_url.get().strip():
            issues.append("❌ Privacy Policy URL fehlt")
        elif not self.privacy_url.get().startswith(("http://", "https://")):
            issues.append("⚠️  Privacy Policy URL sollte mit http:// oder https:// beginnen")

        if not self.support_url.get().strip():
            issues.append("❌ Support URL fehlt")
        elif not self.support_url.get().startswith(("http://", "https://")):
            issues.append("⚠️  Support URL sollte mit http:// oder https:// beginnen")

        if not self.pfx_path.get().strip() or not os.path.exists(self.pfx_path.get()):
            issues.append("❌ Zertifikat (.pfx) fehlt oder existiert nicht")

        if not self.capabilities.get().strip():
            issues.append("⚠️  Capabilities nicht gesetzt (z.B. internetClient)")

        if not self.desc_box.get("1.0", tk.END).strip():
            issues.append("⚠️  Beschreibung fehlt")

        if not self.readme_box.get("1.0", tk.END).strip():
            issues.append("⚠️  README fehlt")

        if not self.license_box.get("1.0", tk.END).strip() and not self.license_files:
            issues.append("⚠️  Lizenz fehlt")

        if not self.makeappx_path.get().strip() or not os.path.exists(self.makeappx_path.get()):
            issues.append("❌ MakeAppx.exe nicht gefunden")

        if not self.signtool_path.get().strip() or not os.path.exists(self.signtool_path.get()):
            issues.append("❌ SignTool.exe nicht gefunden")

        version = self.version.get().strip()
        if not re.match(r'^\d+\.\d+\.\d+\.\d+$', version):
            issues.append(f"⚠️  Version hat falsches Format: {version} (erwartet: X.X.X.X)")

        if not self.publisher_display.get().strip():
            issues.append("⚠️  Publisher Display Name fehlt")

        if not self.identity_name.get().strip():
            issues.append("⚠️  Identity Name fehlt")

        if issues:
            critical = [i for i in issues if i.startswith("❌")]
            warnings = [i for i in issues if i.startswith("⚠️")]

            msg = ""
            if critical:
                msg += "KRITISCHE FEHLER (müssen behoben werden):\n\n"
                msg += "\n".join(critical)

            if warnings:
                if msg:
                    msg += "\n\n"
                msg += "WARNUNGEN (sollten behoben werden):\n\n"
                msg += "\n".join(warnings)

            messagebox.showwarning("Preflight-Check", msg)
        else:
            messagebox.showinfo("Preflight-Check",
                "✅ Alle Pflichtfelder sind ausgefüllt!\n\n" +
                "Bereit für:\n" +
                "1. Paket erzeugen\n" +
                "2. EXE bauen\n" +
                "3. MSIX bauen & signieren\n" +
                "4. WACK-Test durchführen")

    # ---------- Exit ----------
    def on_quit(self):
        if messagebox.askyesno(_t("Beenden"), _t("Möchten Sie die Einstellungen vor dem Beenden speichern?")):
            self.save_settings()
        self.destroy()

# ---------- main ----------
if __name__ == "__main__":
    if not ensure_dependencies():
        sys.exit(1)
    runtime_logger = configure_runtime_logging(LOG_FILE)
    runtime_logger.info("WinStorePackager wird gestartet.")
    app = StorePackagerApp()
    app.mainloop()
