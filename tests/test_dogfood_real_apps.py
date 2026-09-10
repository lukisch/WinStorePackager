"""Dogfooding regression tests against real Windows Store applications.

Verifies that WinStorePackager correctly generates valid AppxManifest.xml,
staged payloads, and tile icons for the live store applications:
- MethodenAnalyser (Store-ID: 9PD6GNMCZBLF)
- SQLiteViewer (Store-ID: 9P6H501XB8JT)
- CleanMarkdown (Store-ID: 9MW9QN49WQG2)
- PromptBoard (Store-ID: 9N1FNJL2FHLC)
"""

import json
import os
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import WindowsStorePublisher_3 as wsp

# Ensure Pillow Image is bound in wsp module namespace
if getattr(wsp, "Image", None) is None:
    try:
        from PIL import Image as _PILImage
        wsp.Image = _PILImage
    except ImportError:
        pass

# Namespace mappings for AppxManifest XML
NS = {
    "appx": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
    "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
    "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
}

# Local repository and OneDrive mirror bases
ONEDRIVE_SOFTWARE = Path.home() / "OneDrive" / ".TOPICS" / ".SOFTWARE"

# Authoritative reference metadata for live submitted apps
LIVE_APPS_SPEC = {
    "MethodenAnalyser": {
        "store_id": "9PD6GNMCZBLF",
        "app_name": "MethodenAnalyser",
        "publisher": "CN=52596601-BAB4-4F3F-B182-E8F3F273B202",
        "publisher_display": "Geiger",
        "identity_name": "Geiger.MethodenAnalyser",
        "version": "3.0.0.0",
        "description": "Statischer Python-Code-Analyser mit GUI. Findet ungenutzte Imports, Definitionen, Code-Duplikate und Import-Scope-Probleme.",
        "executable": "MethodenAnalyser.exe",
        "capabilities": "internetClient,runFullTrust",
        "category": "Developer Tools",
        "age_rating": "3+",
        "local_paths": [
            Path(r"C:\_Local_DEV\repos\MethodenAnalyser"),
            ONEDRIVE_SOFTWARE / "CODING" / "REL-PUB_MethodenAnalyser",
        ],
    },
    "SQLiteViewer": {
        "store_id": "9P6H501XB8JT",
        "app_name": "SQLite Viewer Pro",
        "publisher": "CN=52596601-BAB4-4F3F-B182-E8F3F273B202",
        "publisher_display": "Geiger",
        "identity_name": "Geiger.SQLiteViewer",
        "version": "1.0.0.0",
        "description": "Leichtgewichtiger SQLite-Datenbank-Browser mit GUI, Read-only-Zugriff sowie CSV- und JSON-Export.",
        "executable": "SQLiteViewer.exe",
        "capabilities": "internetClient,runFullTrust",
        "category": "Developer Tools",
        "age_rating": "3+",
        "local_paths": [
            Path(r"C:\_Local_DEV\repos\SQLiteViewer"),
            ONEDRIVE_SOFTWARE / "DATA" / "REL-PUB_SQLiteViewer",
        ],
    },
    "CleanMarkdown": {
        "store_id": "9MW9QN49WQG2",
        "app_name": "CleanMarkdown",
        "publisher": "CN=52596601-BAB4-4F3F-B182-E8F3F273B202",
        "publisher_display": "Geiger",
        "identity_name": "Geiger.CleanMarkdown",
        "version": "0.3.2.0",
        "description": "Lokaler Markdown-Viewer und -Editor mit Lesemodus, Raw-Editor, PDF-Export, Mathe-Vorschau und DE/EN-Oberfläche.",
        "executable": "CleanMarkdown.exe",
        "capabilities": "runFullTrust",
        "category": "Productivity",
        "age_rating": "3+",
        "local_paths": [
            Path(r"C:\_Local_DEV\repos\CleanMarkdown"),
            ONEDRIVE_SOFTWARE / "DOCS" / "DEV_CleanMarkdown",
        ],
    },
    "PromptBoard": {
        "store_id": "9N1FNJL2FHLC",
        "app_name": "PromptBoard",
        "publisher": "CN=52596601-BAB4-4F3F-B182-E8F3F273B202",
        "publisher_display": "Geiger",
        "identity_name": "Geiger.PromptBoard",
        "version": "1.1.1.0",
        "description": "Lokales Tray-Tool für Prompts, Skills, Workflows, Rollen und Agenten.",
        "executable": "PromptBoard-1.1.1-win64.exe",
        "capabilities": "runFullTrust",
        "category": "Productivity",
        "age_rating": "3+",
        "local_paths": [
            Path(r"C:\_Local_DEV\repos\PromptBoard"),
            ONEDRIVE_SOFTWARE / "DATA" / "REL-PUB_PromptBoard",
        ],
    },
}


class _MockStringVar:
    def __init__(self, value: str = ""):
        self._value = str(value)

    def get(self) -> str:
        return self._value

    def set(self, value: str):
        self._value = str(value)


class _MockTextBox:
    def __init__(self, text: str = ""):
        self._text = text

    def get(self, start, end) -> str:
        return self._text

    def delete(self, start, end):
        self._text = ""

    def insert(self, index, text):
        self._text += str(text)


class _HeadlessStorePackagerApp:
    """Headless stand-in for StorePackagerApp to test packaging without GUI event loop."""
    def __init__(self):
        self.app_name = _MockStringVar()
        self.publisher = _MockStringVar()
        self.publisher_display = _MockStringVar()
        self.identity_name = _MockStringVar()
        self.version = _MockStringVar()
        self.capabilities = _MockStringVar()
        self.languages = _MockStringVar("en-us, de-de")
        self.desc_box = _MockTextBox()

    generate_manifest = wsp.StorePackagerApp.generate_manifest
    stage_payload = wsp.StorePackagerApp.stage_payload
    build_icons = wsp.StorePackagerApp.build_icons


class TestDogfoodRealApps(unittest.TestCase):
    def setUp(self):
        self.app = _HeadlessStorePackagerApp()
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_live_app_manifest_generation_all_four_apps(self):
        """Test manifest generation for all 4 live store apps."""
        for app_key, spec in LIVE_APPS_SPEC.items():
            with self.subTest(app=app_key):
                meta = dict(spec)
                for candidate_root in spec["local_paths"]:
                    sp_file = candidate_root / "store_package.json"
                    if sp_file.is_file():
                        try:
                            disk_data = json.loads(sp_file.read_text(encoding="utf-8"))
                            meta.update(disk_data)
                            break
                        except Exception:
                            pass

                self.app.app_name.set(meta["app_name"])
                self.app.publisher.set(meta["publisher"])
                self.app.publisher_display.set(meta.get("publisher_display", "Geiger"))
                self.app.identity_name.set(meta["identity_name"])
                self.app.version.set(meta["version"])

                caps = meta.get("capabilities", "")
                if isinstance(caps, list):
                    caps = ",".join(caps)
                self.app.capabilities.set(caps)
                self.app.desc_box.delete("1.0", "end")
                self.app.desc_box.insert("1.0", meta["description"])

                app_outdir = os.path.join(self.temp_dir, app_key)
                os.makedirs(app_outdir, exist_ok=True)

                self.app.generate_manifest(app_outdir, meta["executable"])
                manifest_path = os.path.join(app_outdir, "AppxManifest.xml")
                self.assertTrue(os.path.isfile(manifest_path))

                tree = ET.parse(manifest_path)
                root = tree.getroot()

                # Verify root tag
                self.assertTrue(root.tag.endswith("Package"))

                # Verify Identity
                identity = root.find("appx:Identity", NS)
                self.assertIsNotNone(identity)
                self.assertEqual(identity.get("Name"), meta["identity_name"])
                self.assertEqual(identity.get("Publisher"), meta["publisher"])
                self.assertEqual(identity.get("Version"), meta["version"])

                # Verify Properties
                properties = root.find("appx:Properties", NS)
                self.assertIsNotNone(properties)
                display_name = properties.find("appx:DisplayName", NS)
                self.assertIsNotNone(display_name)
                self.assertEqual(display_name.text, meta["app_name"])
                pub_display = properties.find("appx:PublisherDisplayName", NS)
                self.assertIsNotNone(pub_display)
                self.assertEqual(pub_display.text, meta.get("publisher_display", "Geiger"))
                logo = properties.find("appx:Logo", NS)
                self.assertIsNotNone(logo)
                self.assertEqual(logo.text, r"icons\icon_50x50.png")

                # Verify Application
                app_elem = root.find(".//appx:Application", NS)
                self.assertIsNotNone(app_elem)
                self.assertEqual(app_elem.get("Executable"), meta["executable"])
                self.assertEqual(app_elem.get("EntryPoint"), "Windows.FullTrustApplication")

                # Verify Capabilities
                expected_caps = [c.strip() for c in caps.split(",") if c.strip()]
                for cap in expected_caps:
                    if cap in wsp.GENERAL_CAPABILITIES:
                        cap_node = root.find(f'.//appx:Capability[@Name="{cap}"]', NS)
                        self.assertIsNotNone(cap_node, f"General capability {cap} missing")
                    else:
                        cap_node = root.find(f'.//rescap:Capability[@Name="{cap}"]', NS)
                        self.assertIsNotNone(cap_node, f"Restricted capability {cap} missing")

    def test_semantic_parity_with_methodenanalyser_staged_manifest(self):
        """Compare generated manifest against live MethodenAnalyser staged manifest."""
        spec = LIVE_APPS_SPEC["MethodenAnalyser"]
        for candidate_root in spec["local_paths"]:
            staged_manifest = candidate_root / "_WARTUNG" / "msix_staging" / "AppxManifest.xml"
            if staged_manifest.is_file():
                staged_tree = ET.parse(staged_manifest)
                staged_root = staged_tree.getroot()

                staged_identity = staged_root.find("appx:Identity", NS)
                self.assertEqual(staged_identity.get("Publisher"), spec["publisher"])
                self.assertEqual(staged_identity.get("Name"), spec["identity_name"])
                self.assertEqual(staged_identity.get("Version"), spec["version"])

                staged_props = staged_root.find("appx:Properties", NS)
                self.assertEqual(staged_props.find("appx:DisplayName", NS).text, spec["app_name"])
                self.assertEqual(staged_props.find("appx:PublisherDisplayName", NS).text, spec["publisher_display"])

                staged_app = staged_root.find(".//appx:Application", NS)
                self.assertEqual(staged_app.get("Executable"), spec["executable"])
                self.assertEqual(staged_app.get("EntryPoint"), "Windows.FullTrustApplication")
                break

    def test_icon_generation_tile_dimensions(self):
        """Test build_icons generates all required square and wide tile icons."""
        test_icon = os.path.join(self.temp_dir, "test_icon.png")
        img = Image.new("RGBA", (512, 512), color=(40, 80, 120, 255))
        img.save(test_icon)

        icon_dir = os.path.join(self.temp_dir, "staged_icons")
        self.app.build_icons(test_icon, icon_dir)

        expected_files = {
            "icon_44x44.png": (44, 44),
            "icon_50x50.png": (50, 50),
            "icon_150x150.png": (150, 150),
            "icon_310x310.png": (310, 310),
            "icon_310x150.png": (310, 150),
        }

        for filename, expected_size in expected_files.items():
            path = os.path.join(icon_dir, filename)
            self.assertTrue(os.path.isfile(path), f"Missing icon: {filename}")
            with Image.open(path) as generated_img:
                self.assertEqual(generated_img.size, expected_size)

    def test_stage_payload_single_file_and_onedir(self):
        """Test stage_payload copies single exe or full onedir directory tree."""
        # Case 1: Single file exe
        dummy_exe = os.path.join(self.temp_dir, "app.exe")
        with open(dummy_exe, "wb") as f:
            f.write(b"MZ_DUMMY_EXE")

        outdir1 = os.path.join(self.temp_dir, "out1")
        os.makedirs(outdir1, exist_ok=True)
        count1 = self.app.stage_payload(dummy_exe, outdir1)
        self.assertEqual(count1, 1)
        self.assertTrue(os.path.isfile(os.path.join(outdir1, "app.exe")))

        # Case 2: onedir layout with _internal
        onedir_dir = os.path.join(self.temp_dir, "dist_onedir")
        internal_dir = os.path.join(onedir_dir, "_internal")
        os.makedirs(internal_dir, exist_ok=True)
        onedir_exe = os.path.join(onedir_dir, "app_onedir.exe")
        with open(onedir_exe, "wb") as f:
            f.write(b"MZ_DUMMY_ONEDIR")
        with open(os.path.join(internal_dir, "lib.dll"), "wb") as f:
            f.write(b"DUMMY_DLL")

        outdir2 = os.path.join(self.temp_dir, "out2")
        os.makedirs(outdir2, exist_ok=True)
        count2 = self.app.stage_payload(onedir_exe, outdir2)
        self.assertEqual(count2, 2)
        self.assertTrue(os.path.isfile(os.path.join(outdir2, "app_onedir.exe")))
        self.assertTrue(os.path.isfile(os.path.join(outdir2, "_internal", "lib.dll")))


if __name__ == "__main__":
    unittest.main()
