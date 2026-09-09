"""
Vertragstests für Windows Store Metadaten, Assets und Dokumente von WinStorePackager.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestStoreReadiness(unittest.TestCase):

    def test_store_package_json_exists_and_is_valid(self):
        pkg_path = PROJECT_ROOT / "store_package.json"
        self.assertTrue(pkg_path.exists(), "store_package.json fehlt")
        data = json.loads(pkg_path.read_text(encoding="utf-8"))

        required_fields = [
            "app_name",
            "publisher",
            "publisher_display",
            "identity_name",
            "version",
            "description",
            "executable",
            "capabilities",
            "category",
            "age_rating",
            "privacy_url",
            "support_url",
            "license",
            "store_id",
        ]
        for field in required_fields:
            self.assertIn(field, data, f"Pflichtfeld '{field}' fehlt in store_package.json")
            self.assertTrue(str(data[field]).strip(), f"Feld '{field}' darf nicht leer sein")

        self.assertEqual(
            data["publisher"],
            "CN=52596601-BAB4-4F3F-B182-E8F3F273B202",
            "Publisher CN stimmt nicht mit dem Partner-Center-Konto überein",
        )
        self.assertEqual(
            data["identity_name"],
            "Geiger.WinStorePackager",
            "identity_name stimmt nicht mit Geiger.WinStorePackager überein",
        )
        self.assertEqual(
            data["store_id"],
            "9NT273Z50BJR",
            "store_id stimmt nicht mit 9NT273Z50BJR überein",
        )

    def test_version_parity_with_pyproject(self):
        pkg_path = PROJECT_ROOT / "store_package.json"
        pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))

        pyproject_path = PROJECT_ROOT / "pyproject.toml"
        self.assertTrue(pyproject_path.exists(), "pyproject.toml fehlt")
        pyproject_content = pyproject_path.read_text(encoding="utf-8")

        match = re.search(r'version\s*=\s*"([^"]+)"', pyproject_content)
        self.assertIsNotNone(match, "Version konnte nicht aus pyproject.toml gelesen werden")
        pyproject_version = match.group(1)

        expected_store_version = f"{pyproject_version}.0"
        self.assertEqual(
            pkg_data["version"],
            expected_store_version,
            f"store_package.json Version ({pkg_data['version']}) passt nicht zu pyproject.toml ({expected_store_version})",
        )

    def test_documentation_files_exist_and_nonempty(self):
        docs = [
            ("PRIVACY_POLICY.md", 200),
            ("SUPPORT.md", 200),
            ("STORE_LISTING.md", 200),
            ("WINDOWS_STORE_PREP.md", 200),
            ("THIRD_PARTY_LICENSES.txt", 100),
        ]
        for doc_name, min_bytes in docs:
            p = PROJECT_ROOT / doc_name
            self.assertTrue(p.exists(), f"Dokument '{doc_name}' fehlt")
            content = p.read_text(encoding="utf-8")
            self.assertGreaterEqual(
                len(content.encode("utf-8")),
                min_bytes,
                f"Dokument '{doc_name}' ist verdächtig kurz ({len(content)} Zeichen)",
            )

    def test_store_assets_exist_and_dimensions(self):
        assets_dir = PROJECT_ROOT / "store_assets"
        self.assertTrue(assets_dir.exists(), "store_assets/ Verzeichnis fehlt")

        expected_icons = {
            "Square44x44Logo.png": (44, 44),
            "StoreLogo.png": (50, 50),
            "Square150x150Logo.png": (150, 150),
            "Wide310x150Logo.png": (310, 150),
            "Square310x310Logo.png": (310, 310),
        }

        for icon_name, expected_size in expected_icons.items():
            icon_path = assets_dir / icon_name
            self.assertTrue(icon_path.exists(), f"Icon '{icon_name}' fehlt in store_assets/")
            with Image.open(icon_path) as img:
                self.assertEqual(
                    img.size,
                    expected_size,
                    f"Icon '{icon_name}' hat falsche Dimensionen {img.size} (erwartet: {expected_size})",
                )

    def test_store_listing_keyword_limits(self):
        listing_path = PROJECT_ROOT / "STORE_LISTING.md"
        self.assertTrue(listing_path.exists(), "STORE_LISTING.md fehlt")
        content = listing_path.read_text(encoding="utf-8")

        # Find German keywords
        de_match = re.search(r"### Schlüsselwörter\s*\n([^\n#]+)", content)
        self.assertIsNotNone(de_match, "Deutsche Schlüsselwörter nicht gefunden")
        de_keywords = [k.strip() for k in de_match.group(1).split(",") if k.strip()]
        self.assertLessEqual(
            len(de_keywords),
            7,
            f"Zu viele deutsche Keywords ({len(de_keywords)} > 7, Microsoft Partner Center Policy 10.1.3)",
        )

        # Find English keywords
        en_match = re.search(r"### Keywords\s*\n([^\n#]+)", content)
        self.assertIsNotNone(en_match, "Englische Keywords nicht gefunden")
        en_keywords = [k.strip() for k in en_match.group(1).split(",") if k.strip()]
        self.assertLessEqual(
            len(en_keywords),
            7,
            f"Zu viele englische Keywords ({len(en_keywords)} > 7, Microsoft Partner Center Policy 10.1.3)",
        )

    def test_check_store_readiness_script_passes(self):
        from scripts.check_store_readiness import run_store_readiness_check

        success, errors = run_store_readiness_check(PROJECT_ROOT)
        self.assertTrue(success, f"check_store_readiness.py meldet Fehler: {errors}")
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
