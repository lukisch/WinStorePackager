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
# 0. Auto-Installation fehlender Pakete (Bootstrapper)
# ------------------------------------------------------------
def install_and_import(package_name, import_name=None):
    """
    Versucht ein Modul zu importieren. Falls es fehlt, wird es per pip installiert.
    """
    if import_name is None:
        import_name = package_name
    
    try:
        importlib.import_module(import_name)
    except ImportError:
        print(f"⚠️  Modul '{import_name}' fehlt. Installiere '{package_name}'...")
        try:
            # sys.executable garantiert, dass wir das pip des aktuellen Interpreters nutzen
            subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
            print(f"✅ '{package_name}' erfolgreich installiert.")
        except Exception as e:
            print(f"❌ Fehler bei der Installation von {package_name}: {e}")
            print("Bitte führen Sie das Skript als Administrator aus oder installieren Sie manuell.")
            input("Drücken Sie Enter zum Beenden...")
            sys.exit(1)
        
        # Cache invalidieren und neu importieren
        try:
            importlib.invalidate_caches()
            importlib.import_module(import_name)
        except ImportError:
            print(f"❌ Import von '{import_name}' nach Installation immer noch nicht möglich.")
            sys.exit(1)

# --- Abhängigkeiten prüfen & installieren ---
print("--- Prüfe Abhängigkeiten ---")
install_and_import("Pillow", "PIL")        # Für Icon-Resizing
install_and_import("pygetwindow")          # Für Screenshots
install_and_import("keyring")              # Für sichere Passwort-Speicherung
print("--- Abhängigkeiten OK ---")

# ------------------------------------------------------------
# 1. Imports der nachgeladenen Module & Standard-Libs
# ------------------------------------------------------------
from PIL import Image, ImageGrab
import pygetwindow as gw
import keyring

# Standard Libs
import json
import shutil
import glob
import re
import time
import threading
import html
from pathlib import Path

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
SETTINGS_FILE = str(Path(__file__).parent / "settings_store_packager.json")
ICON_SIZES = [44, 50, 150, 310]  # Square sizes
WIDE_ICON_SIZE = (310, 150)  # Wide tile
DEFAULT_VERSION = "1.0.0.0"
KEYRING_SERVICE = "WindowsStorePackager"

MANIFEST_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
         xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
         IgnorableNamespaces="uap rescap">

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
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.19041.0" />
  </Dependencies>

  <Capabilities>
{{CAPABILITIES}}
  </Capabilities>

  <Applications>
    <Application Id="{{APPNAME}}App"
                 Executable="{{EXECUTABLE}}"
                 EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements DisplayName="{{APPNAME}}"
                          Description="{{DESCRIPTION}}"
                          Square150x150Logo="icons\\icon_150x150.png"
                          Square44x44Logo="icons\\icon_44x44.png"
                          BackgroundColor="transparent">
        <uap:DefaultTile Wide310x150Logo="icons\\icon_310x150.png" />
      </uap:VisualElements>
    </Application>
  </Applications>
</Package>
"""

CATEGORIES = [
    "Productivity", "Education", "Entertainment", "Games", "Photo & Video",
    "Music", "Business", "Developer Tools", "Utilities", "Social", "Health & Fitness"
]

AGE_RATINGS = ["3+", "7+", "12+", "16+", "18+"]

# -----------------------------------

def which(program):
    """Find executable in PATH"""
    paths = os.environ.get("PATH", "").split(os.pathsep)
    exts = [""] if os.name != "nt" else os.environ.get("PATHEXT", ".EXE;.BAT;.CMD").split(";")
    for p in paths:
        for ext in exts:
            candidate = os.path.join(p, program + ext)
            if os.path.isfile(candidate):
                return candidate
    return None

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
    if not publisher.strip():
        return False, "Publisher darf nicht leer sein"
    if not publisher.startswith("CN="):
        return False, "Publisher muss mit 'CN=' beginnen"
    return True, ""

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

class StorePackagerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Windows Store Packager v2.3 (Auto-Setup)")
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

        # Text widgets
        self.readme_box = None
        self.license_box = None
        self.desc_box = None

        self.load_settings()
        self.build_gui()
        self.autodetect_sdk_tools()

    # ---------- Settings ----------
    def load_settings(self):
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
                
                # Kein Try/Except mehr nötig, da keyring oben installiert wurde
                pwd = keyring.get_password(KEYRING_SERVICE, "pfx_password")
                if pwd:
                    self.pfx_password.set(pwd)

            except Exception as e:
                # Fallback für alte Settings-Files oder Keyring-Fehler
                print(f"Warnung: Einstellungen konnten nicht vollständig geladen werden: {e}")

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
            "age_rating": self.age_rating.get()
        }
            
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            messagebox.showinfo("Gespeichert", "Einstellungen wurden gespeichert.")
        except Exception as e:
            messagebox.showerror("Fehler", f"Einstellungen konnten nicht gespeichert werden:\n{e}")

    # ---------- GUI ----------
    def build_gui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        tab1 = ttk.Frame(notebook)
        notebook.add(tab1, text="Metadaten")
        self.build_metadata_tab(tab1)
        
        tab2 = ttk.Frame(notebook)
        notebook.add(tab2, text="Build-Einstellungen")
        self.build_build_tab(tab2)
        
        tab3 = ttk.Frame(notebook)
        notebook.add(tab3, text="Store-Informationen")
        self.build_store_tab(tab3)
        
        tab4 = ttk.Frame(notebook)
        notebook.add(tab4, text="Aktionen")
        self.build_actions_tab(tab4)

    def build_metadata_tab(self, parent):
        frm = ttk.Frame(parent)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        row = 0

        def add_row(label, var, browse_cmd=None, width=60):
            nonlocal row
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ent = ttk.Entry(frm, textvariable=var, width=width)
            ent.grid(row=row, column=1, sticky="we", pady=3, padx=5)
            if browse_cmd:
                ttk.Button(frm, text="Wählen", command=browse_cmd).grid(row=row, column=2, sticky="w")
            row += 1

        add_row("App-Name:", self.app_name)
        add_row("Publisher (CN=... aus Partner Center):", self.publisher)
        add_row("Publisher Display Name:", self.publisher_display)
        add_row("Identity Name:", self.identity_name)
        add_row("Version (z.B. 1.0.0.0):", self.version)
        
        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=10)
        row += 1

        add_row("Haupt-Skript (.py):", self.script_path, self.choose_script)
        add_row("Icon (PNG, mind. 310x310):", self.icon_path, self.choose_icon)
        add_row("Quelltext (ZIP oder Datei):", self.source_path, self.choose_source)
        add_row("Installer (EXE oder MSIX):", self.installer_path, self.choose_installer)
        add_row("Ausgabeordner:", self.output_dir)
        add_row("EXE-Name (z.B. MyApp.exe):", self.exe_name)

        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=10)
        row += 1

        ttk.Label(frm, text="README (Text oder Datei):").grid(row=row, column=0, sticky="nw", pady=5)
        readme_frame = ttk.Frame(frm)
        readme_frame.grid(row=row, column=1, sticky="we", pady=5, padx=5)
        self.readme_box = scrolledtext.ScrolledText(readme_frame, width=70, height=5)
        self.readme_box.pack(fill="both", expand=True)
        ttk.Button(frm, text="Datei laden", command=self.load_readme_file).grid(row=row, column=2, sticky="nw")
        row += 1

        ttk.Label(frm, text="Lizenz (Text/Dateien):").grid(row=row, column=0, sticky="nw", pady=5)
        license_frame = ttk.Frame(frm)
        license_frame.grid(row=row, column=1, sticky="we", pady=5, padx=5)
        self.license_box = scrolledtext.ScrolledText(license_frame, width=70, height=5)
        self.license_box.pack(fill="both", expand=True)
        lic_btns = ttk.Frame(frm)
        lic_btns.grid(row=row, column=2, sticky="nw")
        ttk.Button(lic_btns, text="Datei +", command=self.add_license_file).pack(anchor="w", pady=2)
        ttk.Button(lic_btns, text="Text +", command=self.add_license_text_entry).pack(anchor="w", pady=2)
        row += 1

        ttk.Label(frm, text="Beschreibung:").grid(row=row, column=0, sticky="nw", pady=5)
        desc_frame = ttk.Frame(frm)
        desc_frame.grid(row=row, column=1, sticky="we", pady=5, padx=5)
        self.desc_box = scrolledtext.ScrolledText(desc_frame, width=70, height=5)
        self.desc_box.pack(fill="both", expand=True)
        ttk.Button(frm, text="Datei laden", command=self.load_desc_file).grid(row=row, column=2, sticky="nw")
        row += 1

        frm.columnconfigure(1, weight=1)

    def build_build_tab(self, parent):
        frm = ttk.Frame(parent)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        row = 0

        def add_row(label, var, browse_cmd=None, width=60, show=None):
            nonlocal row
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ent = ttk.Entry(frm, textvariable=var, width=width, show=show)
            ent.grid(row=row, column=1, sticky="we", pady=3, padx=5)
            if browse_cmd:
                ttk.Button(frm, text="Wählen", command=browse_cmd).grid(row=row, column=2, sticky="w")
            row += 1

        # NEU: Python Environment für externe Builds
        ttk.Label(frm, text="Python Umgebung (für Builds)", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, sticky="w", pady=(5,10))
        row += 1
        
        add_row("Python.exe Pfad:", self.python_path, self.choose_python_exe)
        ttk.Label(frm, text="Wichtig, wenn dieses Tool als EXE läuft. Muss 'pip install pyinstaller' haben.", foreground="gray").grid(row=row, column=1, sticky="w")
        row += 1
        
        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=10)
        row += 1

        ttk.Label(frm, text="Windows SDK Tools", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, sticky="w", pady=(5,10))
        row += 1

        add_row("MakeAppx.exe:", self.makeappx_path, self.choose_makeappx)
        add_row("SignTool.exe:", self.signtool_path, self.choose_signtool)
        add_row("AppCert.exe (WACK):", self.appcert_path, self.choose_appcert)
        
        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=10)
        row += 1
        
        ttk.Label(frm, text="Zertifikat & Signierung", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, sticky="w", pady=(5,10))
        row += 1

        add_row("Zertifikat (.pfx):", self.pfx_path, self.choose_pfx)
        add_row("PFX Passwort:", self.pfx_password, show="*")
        add_row("Timestamp URL:", self.timestamp_url)
        add_row("MSIX Name:", self.msix_name)
        
        ttk.Label(frm, text="✓ Passwort wird sicher im Keyring gespeichert", foreground="green").grid(row=row, column=1, sticky="w", pady=3)
        row += 1
        
        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=3, sticky='ew', pady=10)
        row += 1

        ttk.Checkbutton(frm, text="Sprachmodul automatisch integrieren (i18n)", variable=self.enable_i18n)\
            .grid(row=row, column=0, columnspan=3, sticky="w", pady=8)
        row += 1

        frm.columnconfigure(1, weight=1)

    def build_store_tab(self, parent):
        frm = ttk.Frame(parent)
        frm.pack(fill="both", expand=True, padx=12, pady=12)
        row = 0

        def add_row(label, var, width=60):
            nonlocal row
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ent = ttk.Entry(frm, textvariable=var, width=width)
            ent.grid(row=row, column=1, sticky="we", pady=3, padx=5)
            row += 1

        ttk.Label(frm, text="Store-Pflichtfelder", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", pady=(5,10))
        row += 1

        add_row("Privacy Policy URL:", self.privacy_url)
        add_row("Support URL:", self.support_url)
        add_row("Capabilities (Komma-getrennt):", self.capabilities)
        
        ttk.Label(frm, text="Beispiele: internetClient, microphone, webcam, location").grid(row=row, column=1, sticky="w", pady=2)
        row += 1

        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=10)
        row += 1

        ttk.Label(frm, text="Kategorie:").grid(row=row, column=0, sticky="w", pady=3)
        cat_combo = ttk.Combobox(frm, textvariable=self.category, values=CATEGORIES, state="readonly", width=57)
        cat_combo.grid(row=row, column=1, sticky="w", pady=3, padx=5)
        row += 1

        ttk.Label(frm, text="Altersfreigabe:").grid(row=row, column=0, sticky="w", pady=3)
        age_combo = ttk.Combobox(frm, textvariable=self.age_rating, values=AGE_RATINGS, state="readonly", width=57)
        age_combo.grid(row=row, column=1, sticky="w", pady=3, padx=5)
        row += 1

        ttk.Separator(frm, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=10)
        row += 1

        # Changelog-Generator
        ttk.Label(frm, text="Changelog (Store-Listing)", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=2, sticky="w", pady=(5,10))
        row += 1

        ttk.Label(frm, text="Changelog-Text:").grid(row=row, column=0, sticky="nw", pady=5)
        changelog_frame = ttk.Frame(frm)
        changelog_frame.grid(row=row, column=1, sticky="we", pady=5, padx=5)
        self.changelog_box = scrolledtext.ScrolledText(changelog_frame, width=60, height=6)
        self.changelog_box.pack(fill="both", expand=True)
        self.changelog_box.insert(tk.END, f"Version {self.version.get()}\n- \n- \n- ")
        row += 1

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=row, column=1, sticky="w", pady=5, padx=5)
        ttk.Button(btn_frame, text="Format fuer Store", command=self.format_changelog).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="In Zwischenablage", command=self.copy_changelog).pack(side="left", padx=2)
        row += 1

        frm.columnconfigure(1, weight=1)

    def build_actions_tab(self, parent):
        frm = ttk.Frame(parent)
        frm.pack(fill="both", expand=True, padx=12, pady=12)

        ttk.Label(frm, text="Build-Aktionen", font=("Arial", 12, "bold")).pack(anchor="w", pady=(5,15))

        actions_frame = ttk.Frame(frm)
        actions_frame.pack(fill="x", pady=5)

        ttk.Button(actions_frame, text="1. Preflight-Check", command=self.preflight_check, width=25)\
            .grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(actions_frame, text="Validiert alle Pflichtfelder").grid(row=0, column=1, sticky="w", padx=10)

        ttk.Button(actions_frame, text="2. Paket erzeugen", command=self.build_package, width=25)\
            .grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(actions_frame, text="Erstellt Ausgabeordner mit allen Assets").grid(row=1, column=1, sticky="w", padx=10)

        ttk.Button(actions_frame, text="3. EXE bauen", command=self.build_exe, width=25)\
            .grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(actions_frame, text="PyInstaller-Build mit i18n").grid(row=2, column=1, sticky="w", padx=10)

        ttk.Button(actions_frame, text="4. MSIX bauen & signieren", command=self.build_and_sign_msix, width=25)\
            .grid(row=3, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(actions_frame, text="Erstellt signiertes Store-Paket").grid(row=3, column=1, sticky="w", padx=10)

        ttk.Separator(frm, orient='horizontal').pack(fill='x', pady=15)

        ttk.Label(frm, text="Zusätzliche Aktionen", font=("Arial", 12, "bold")).pack(anchor="w", pady=(5,15))

        extras_frame = ttk.Frame(frm)
        extras_frame.pack(fill="x", pady=5)

        ttk.Button(extras_frame, text="Screenshots erzeugen", command=self.run_screenshots, width=25)\
            .grid(row=0, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(extras_frame, text="Automatische Store-Screenshots").grid(row=0, column=1, sticky="w", padx=10)

        ttk.Button(extras_frame, text="WACK-Test starten", command=self.run_wack_test, width=25)\
            .grid(row=1, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(extras_frame, text="Windows App Certification Kit").grid(row=1, column=1, sticky="w", padx=10)

        ttk.Button(extras_frame, text="Ausgabeordner öffnen", command=self.open_output_folder, width=25)\
            .grid(row=2, column=0, padx=5, pady=5, sticky="ew")
        ttk.Label(extras_frame, text="Zeigt erstellte Dateien").grid(row=2, column=1, sticky="w", padx=10)

        ttk.Separator(frm, orient='horizontal').pack(fill='x', pady=15)

        bottom_frame = ttk.Frame(frm)
        bottom_frame.pack(fill="x", pady=5)

        ttk.Button(bottom_frame, text="Einstellungen speichern", command=self.save_settings)\
            .pack(side="left", padx=5)
        ttk.Button(bottom_frame, text="Beenden", command=self.on_quit)\
            .pack(side="right", padx=5)

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
        outdir = os.path.join(outdir_root, appname)
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
            with open(full_path, "r", encoding="utf-8") as f:
                self.translations = json.load(f)
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
        return entry.get(self.lang, entry.get("de", key))
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
                "Sprache": {"de": "Sprache", "en": "Language"},
                "Deutsch": {"de": "Deutsch", "en": "German"},
                "English": {"de": "Englisch", "en": "English"},
                "Wählen": {"de": "Wählen", "en": "Choose"},
                "Beenden": {"de": "Beenden", "en": "Quit"},
                "Öffnen": {"de": "Öffnen", "en": "Open"},
                "Speichern": {"de": "Speichern", "en": "Save"},
                "Abbrechen": {"de": "Abbrechen", "en": "Cancel"},
                "OK": {"de": "OK", "en": "OK"},
                "Fehler": {"de": "Fehler", "en": "Error"},
                "Warnung": {"de": "Warnung", "en": "Warning"},
                "Info": {"de": "Info", "en": "Info"}
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
    def collect_python_licenses(self, outdir):
        target = os.path.join(outdir, "THIRD_PARTY_LICENSES.txt")
        try:
            python_exe = self.get_build_interpreter() or sys.executable
            subprocess.run([python_exe, "-m", "pip", "install", "pip-licenses"], 
                          check=True, capture_output=True, timeout=60)
            
            with open(target, "w", encoding="utf-8") as f:
                subprocess.run(
                    [python_exe, "-m", "pip_licenses", 
                     "--with-license-file", "--format=plain"],
                    stdout=f,
                    stderr=subprocess.PIPE,
                    check=True,
                    timeout=120
                )
            return True, target
        except subprocess.TimeoutExpired:
            return False, "Timeout beim Sammeln der Lizenzen"
        except Exception as e:
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
                           capture_output=True, check=True)
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
                subprocess.run(cmd, capture_output=True, check=True, startupinfo=startupinfo, env=build_env)
                
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
                
                self.after(0, lambda: messagebox.showinfo("Fertig", msg))
                
            except subprocess.CalledProcessError as e:
                progress.close()
                err_out = e.stderr.decode('utf-8', errors='replace') if e.stderr else "Unbekannter Fehler"
                self.after(0, lambda: messagebox.showerror("PyInstaller Fehler", f"{err_out}"))
            except Exception as e:
                progress.close()
                self.after(0, lambda: messagebox.showerror("Fehler", f"EXE-Erzeugung fehlgeschlagen:\n{e}"))
        
        thread = threading.Thread(target=build_thread, daemon=True)
        thread.start()

    def build_package(self):
        appname = self.app_name.get().strip()
        if not appname:
            messagebox.showerror("Fehler", "Bitte App-Name eingeben.")
            return

        outdir = self.package_dir()
        if os.path.exists(outdir):
            if not messagebox.askyesno("Bestätigung", 
                f"Ausgabeordner existiert bereits:\n{outdir}\n\nÜberschreiben?"):
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
                        messagebox.showwarning("Warnung", 
                            f"Konnte Lizenzdatei nicht kopieren:\n{path}\n{e}")
            
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
                shutil.copy(src, os.path.join(outdir, os.path.basename(src)))

            installer = self.installer_path.get().strip()
            if installer and os.path.exists(installer):
                shutil.copy(installer, os.path.join(outdir, os.path.basename(installer)))

            if self.enable_i18n.get() and staged_script:
                ok, info = self.integrate_i18n(outdir, script_to_patch=staged_script)
                if not ok:
                    messagebox.showwarning("Warnung", 
                        f"Sprachmodul konnte nicht integriert werden:\n{info}")

            exe_name = self.exe_name.get().strip()
            if not exe_name:
                exes = [f for f in os.listdir(outdir) if f.lower().endswith(".exe")]
                exe_name = exes[0] if exes else f"{appname}.exe"

            self.generate_manifest(outdir, exe_name)

            ok_lic, info_lic = self.collect_python_licenses(outdir)
            
            self.save_settings()
            
            msg = f"Paket für {appname} wurde erstellt:\n{outdir}"
            if ok_lic:
                msg += f"\n\nDrittanbieter-Lizenzen gesammelt:\n{info_lic}"
            else:
                msg += f"\n\nLizenzen-Warnung:\n{info_lic}"
            
            messagebox.showinfo("Fertig", msg)
            
        except Exception as e:
            messagebox.showerror("Fehler", f"Paket-Erstellung fehlgeschlagen:\n{e}")

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
                cmd_pack = [makeappx, "pack", "/d", outdir, "/p", msix_path, "/o"]
                result = subprocess.run(cmd_pack, capture_output=True, text=True, check=True)

                pfx = self.pfx_path.get().strip()
                pfx_pw = self.pfx_password.get()
                ts_url = self.timestamp_url.get().strip()

                if not pfx or not os.path.isfile(pfx):
                    progress.close()
                    self.after(0, lambda: messagebox.showerror("Fehler", 
                        "Zertifikat (.pfx) nicht gesetzt oder nicht gefunden."))
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
                subprocess.run(cmd_sign, capture_output=True, text=True, check=True)
                
                progress.close()
                self.after(0, lambda: messagebox.showinfo("Fertig", 
                    f"MSIX gebaut und signiert:\n{msix_path}\n\nBereit für den Store!"))
                    
            except subprocess.CalledProcessError as e:
                progress.close()
                # Passwort aus Fehlermeldung entfernen
                safe_cmd = [x if x != pfx_pw else "***" for x in (e.cmd or [])]
                error_msg = f"Befehl fehlgeschlagen:\n{safe_cmd}\n\nAusgabe:\n{e.stderr if e.stderr else e.stdout}"
                self.after(0, lambda: messagebox.showerror("Fehler", error_msg))
            except Exception as e:
                progress.close()
                self.after(0, lambda: messagebox.showerror("Fehler", 
                    f"MSIX-Build fehlgeschlagen:\n{e}"))
        
        thread = threading.Thread(target=build_thread, daemon=True)
        thread.start()

    # ---------- Manifest ----------
    def generate_manifest(self, outdir, executable_name):
        desc = self.desc_box.get("1.0", tk.END).strip()
        manifest = MANIFEST_TEMPLATE
        
        manifest = manifest.replace("{{IDENTITY_NAME}}", 
            self.identity_name.get().strip() or f"YourCompany.{self.app_name.get().strip()}")
        manifest = manifest.replace("{{PUBLISHER}}", 
            self.publisher.get().strip() or "CN=YourPublisher")
        manifest = manifest.replace("{{APPNAME}}",
            html.escape(self.app_name.get().strip() or "MyApp"))
        manifest = manifest.replace("{{PUBLISHER_DISPLAY}}", 
            self.publisher_display.get().strip() or self.publisher.get().strip().replace("CN=", "") or "YourPublisher")
        manifest = manifest.replace("{{DESCRIPTION}}", 
            desc or "No description provided.")
        manifest = manifest.replace("{{VERSION}}", 
            self.version.get().strip() or DEFAULT_VERSION)
        manifest = manifest.replace("{{EXECUTABLE}}", 
            executable_name or "MyApp.exe")
        
        caps = ""
        if self.capabilities.get().strip():
            from xml.sax.saxutils import escape
            for c in self.capabilities.get().split(","):
                c = c.strip()
                if c:
                    caps += f'    <Capability Name="{escape(c)}"/>\n'
        manifest = manifest.replace("{{CAPABILITIES}}", caps)
        
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
        proc = None
        try:
            proc = subprocess.Popen([exe_path])
            time.sleep(5)
            
            app_name = self.app_name.get()
            windows = gw.getWindowsWithTitle(app_name)
            if windows:
                try:
                    windows[0].activate()
                except:
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
                
            messagebox.showinfo("Screenshots", 
                f"Screenshots in Store-Formaten gespeichert:\n{shots_dir}\n\n" +
                "\n".join([f"• {w}x{h} ({d})" for w, h, d in formats]))
                
        except Exception as e:
            messagebox.showerror("Fehler", f"Screenshots fehlgeschlagen:\n{e}")
            if proc is not None:
                try:
                    proc.terminate()
                except Exception:
                    pass

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
        
        try:
            subprocess.run([appcert, "reset"], capture_output=True, timeout=30)
            
            messagebox.showinfo("WACK-Test", 
                "WACK-Test wird gestartet...\n\nDies kann mehrere Minuten dauern.\n" +
                "Das Ergebnis wird in einem separaten Fenster angezeigt.")
            
            subprocess.Popen([appcert, "test", "/packagepath", msix_path])
            
        except Exception as e:
            messagebox.showerror("Fehler", f"WACK-Test fehlgeschlagen:\n{e}")
    
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
        messagebox.showinfo("Formatiert", "Changelog wurde fuer Store-Listing formatiert.")
    
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
        if messagebox.askyesno("Beenden", "Einstellungen vor dem Beenden speichern?"):
            self.save_settings()
        self.destroy()

# ---------- main ----------
if __name__ == "__main__":
    app = StorePackagerApp()
    app.mainloop()