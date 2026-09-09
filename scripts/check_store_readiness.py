"""
Store Readiness Preflight Check for WinStorePackager.

Validates that all necessary metadata, documentation files, licenses,
and icon assets required for Windows Store release are present and valid.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def check_store_package_json(project_root: Path) -> List[str]:
    errors = []
    file_path = project_root / "store_package.json"
    if not file_path.exists():
        errors.append("store_package.json is missing.")
        return errors

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"store_package.json is invalid JSON: {e}")
        return errors

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
    ]
    for field in required_fields:
        val = data.get(field)
        if not val or (isinstance(val, str) and not val.strip()):
            errors.append(f"store_package.json field '{field}' is missing or empty.")
        elif field == "publisher" and (val.startswith("CN=YOUR-PUBLISHER-ID") or "YOUR-PUBLISHER" in val):
            errors.append("store_package.json publisher is still placeholder.")

    return errors


def check_documentation_files(project_root: Path) -> List[str]:
    errors = []
    docs = [
        ("PRIVACY_POLICY.md", 200),
        ("SUPPORT.md", 100),
        ("STORE_LISTING.md", 200),
        ("WINDOWS_STORE_PREP.md", 100),
        ("THIRD_PARTY_LICENSES.txt", 100),
    ]

    for filename, min_len in docs:
        p = project_root / filename
        if not p.exists():
            errors.append(f"Required document '{filename}' is missing.")
        elif p.stat().st_size < min_len:
            errors.append(f"Document '{filename}' is suspiciously small ({p.stat().st_size} bytes).")

    return errors


def check_store_icon_assets(project_root: Path) -> List[str]:
    errors = []
    asset_dir = project_root / "store_assets"
    if not asset_dir.exists():
        asset_dir = project_root / "releases" / "windowsstore" / "icons"

    if not asset_dir.exists():
        errors.append("Store icon directory (store_assets/ or releases/windowsstore/icons/) is missing.")
        return errors

    expected_icons = [
        "Square44x44Logo.png",
        "Square150x150Logo.png",
        "Wide310x150Logo.png",
        "Square310x310Logo.png",
        "StoreLogo.png",
    ]

    for icon_name in expected_icons:
        icon_path = asset_dir / icon_name
        if not icon_path.exists():
            errors.append(f"Store icon '{icon_name}' is missing in {asset_dir.name}.")
        elif icon_path.stat().st_size < 100:
            errors.append(f"Store icon '{icon_name}' is suspiciously small ({icon_path.stat().st_size} bytes).")

    return errors


def check_store_listing_keywords(project_root: Path) -> List[str]:
    errors = []
    listing_path = project_root / "STORE_LISTING.md"
    if not listing_path.exists():
        return errors

    content = listing_path.read_text(encoding="utf-8")
    de_match = re.search(r"### Schlüsselwörter\s*\n([^\n#]+)", content)
    if de_match:
        de_keywords = [k.strip() for k in de_match.group(1).split(",") if k.strip()]
        if len(de_keywords) > 7:
            errors.append(
                f"STORE_LISTING.md has {len(de_keywords)} German keywords (max 7 allowed under Policy 10.1.3)."
            )

    en_match = re.search(r"### Keywords\s*\n([^\n#]+)", content)
    if en_match:
        en_keywords = [k.strip() for k in en_match.group(1).split(",") if k.strip()]
        if len(en_keywords) > 7:
            errors.append(
                f"STORE_LISTING.md has {len(en_keywords)} English keywords (max 7 allowed under Policy 10.1.3)."
            )

    return errors


def check_url_reachability(project_root: Path) -> List[str]:
    """Checks that privacy_url/support_url from store_package.json actually resolve."""
    import urllib.error
    import urllib.request

    errors = []
    file_path = project_root / "store_package.json"
    if not file_path.exists():
        return errors

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return errors

    for field in ("privacy_url", "support_url"):
        url = data.get(field)
        if not url or not isinstance(url, str) or not url.strip():
            continue
        req = urllib.request.Request(url, headers={"User-Agent": "store-readiness-check/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        except Exception as e:
            errors.append(f"store_package.json field '{field}' ({url}) could not be checked (network error: {e}).")
            continue
        if status >= 400:
            errors.append(f"store_package.json field '{field}' ({url}) returned HTTP {status} -- not reachable.")

    return errors


def run_store_readiness_check(project_root: Path = PROJECT_ROOT) -> Tuple[bool, List[str]]:
    all_errors = []
    all_errors.extend(check_store_package_json(project_root))
    all_errors.extend(check_documentation_files(project_root))
    all_errors.extend(check_store_icon_assets(project_root))
    all_errors.extend(check_store_listing_keywords(project_root))
    all_errors.extend(check_url_reachability(project_root))

    success = len(all_errors) == 0
    return success, all_errors


def main() -> None:
    print(f"Running Store Readiness Preflight for WinStorePackager in: {PROJECT_ROOT}\n")
    success, errors = run_store_readiness_check(PROJECT_ROOT)

    if success:
        print("STORE READINESS: OK — All 0 findings. Ready for packaging and Store submission.")
        sys.exit(0)
    else:
        print(f"STORE READINESS: FAILED ({len(errors)} findings):")
        for err in errors:
            print(f"  - [FAIL] {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
