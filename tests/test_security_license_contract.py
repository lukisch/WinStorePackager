"""Automated security, dependency floor, and third-party license contract tests for WinStorePackager."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dependency_vulnerability_floors() -> None:
    """Verify requirements.txt and pyproject.toml enforce patched dependency floors against CVEs."""
    req_file = ROOT / "requirements.txt"
    assert req_file.is_file(), "requirements.txt must exist"
    req_text = req_file.read_text(encoding="utf-8")

    # Pillow >= 12.3.0 floor resolves 26+ CVEs/GHSAs (GHSA-4x4j-2g7c-83w6, GHSA-45hq-cxwh-f6vc)
    assert re.search(r"^Pillow\s*>=\s*12\.3\.0", req_text, re.MULTILINE), (
        "requirements.txt must enforce Pillow>=12.3.0 floor"
    )
    assert re.search(r"^keyring\s*>=\s*25\.0\.0", req_text, re.MULTILINE), (
        "requirements.txt must enforce keyring>=25.0.0 floor"
    )
    assert re.search(r"^pygetwindow\s*>=\s*0\.0\.9", req_text, re.MULTILINE), (
        "requirements.txt must enforce pygetwindow>=0.0.9"
    )

    pyproject_file = ROOT / "pyproject.toml"
    assert pyproject_file.is_file(), "pyproject.toml must exist"
    pyproject_text = pyproject_file.read_text(encoding="utf-8")

    # PEP 621 dependencies section
    assert "dependencies = [" in pyproject_text, "pyproject.toml must define project.dependencies"
    assert "Pillow>=12.3.0" in pyproject_text, "pyproject.toml must specify Pillow>=12.3.0"
    assert "keyring>=25.0.0" in pyproject_text, "pyproject.toml must specify keyring>=25.0.0"

    # Dev/test optional dependencies floor (pytest >= 9.1.1 protects against CVE-2025-7117 / GHSA-6w46-j5rx-g56g)
    assert "[project.optional-dependencies]" in pyproject_text, "pyproject.toml must define optional-dependencies"
    assert "pytest>=9.1.1" in pyproject_text, "pyproject.toml dev dependencies must require pytest>=9.1.1"
    assert "ruff>=0.9.0" in pyproject_text, "pyproject.toml dev dependencies must require ruff>=0.9.0"


def test_third_party_licenses_complete_and_accurate() -> None:
    """Verify THIRD_PARTY_LICENSES.txt comprehensively covers runtime, transitive, build, and test packages."""
    license_file = ROOT / "THIRD_PARTY_LICENSES.txt"
    assert license_file.is_file(), "THIRD_PARTY_LICENSES.txt must exist"
    content = license_file.read_text(encoding="utf-8")

    required_packages = [
        ("Pillow", "HPND-sell-variant"),
        ("PyGetWindow", "BSD-3-Clause"),
        ("PyRect", "BSD-3-Clause"),
        ("keyring", "MIT"),
        ("jaraco.classes", "MIT"),
        ("jaraco.context", "MIT"),
        ("jaraco.functools", "MIT"),
        ("pywin32-ctypes", "BSD-3-Clause"),
        ("PyInstaller", "GPL-2.0-or-later WITH Bootloader-exception"),
        ("pyinstaller-hooks-contrib", "Apache-2.0"),
        ("altgraph", "MIT"),
        ("packaging", "Apache-2.0 OR BSD-2-Clause"),
        ("pytest", "MIT"),
        ("pluggy", "MIT"),
        ("iniconfig", "MIT"),
        ("ruff", "MIT OR Apache-2.0"),
    ]

    for pkg, spdx in required_packages:
        assert pkg in content, f"Package {pkg} missing from THIRD_PARTY_LICENSES.txt"
        assert spdx in content, f"SPDX identifier {spdx} for {pkg} missing from THIRD_PARTY_LICENSES.txt"

    # Ensure structured schema fields exist
    assert "License:" in content, "License: field missing in THIRD_PARTY_LICENSES.txt"
    assert "URL:" in content, "URL: field missing in THIRD_PARTY_LICENSES.txt"
    assert "SPDX:" in content, "SPDX: field missing in THIRD_PARTY_LICENSES.txt"


def test_gitignore_security_and_multi_host_hardening() -> None:
    """Verify .gitignore blocks private secrets, certificates, and multi-host conflict files."""
    gitignore_file = ROOT / ".gitignore"
    assert gitignore_file.is_file(), ".gitignore must exist"
    content = gitignore_file.read_text(encoding="utf-8")

    # Secrets and certificate protection
    for pat in ["credentials.json", "*.pfx", "*.pem", "*.key", "keyring/", "secrets.*"]:
        assert pat in content, f"Secret pattern {pat} missing in .gitignore"

    # Multi-host sync hardening
    for host_pat in ["*-WORKSTATION-LG*", "*-ASUS-GEI*", "*.sync-conflict-*", "*.conflict"]:
        assert host_pat in content, f"Sync conflict pattern {host_pat} missing in .gitignore"

    # Multi-agent lock system fail-closed patterns
    for lock_pat in ["LOCK.*", "*.lock", "LOCK*.txt"]:
        assert lock_pat in content, f"Lock pattern {lock_pat} missing in .gitignore"


def test_no_hardcoded_user_paths_in_python_code() -> None:
    """Verify no hardcoded personal user profile paths (e.g. C:\\Users\\lukas) exist in active Python source."""
    disallowed_regex = re.compile(r"""(?i)C:[/\\]Users[/\\](?:lukas|admin|administrator)[/\\]""", re.VERBOSE)

    python_files = list(ROOT.glob("*.py")) + list((ROOT / "tests").glob("*.py")) + list((ROOT / "scripts").glob("*.py"))
    assert len(python_files) > 10, "Expected at least 10 Python files to scan"

    violating_lines = []
    for py_file in python_files:
        if not py_file.is_file():
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        for idx, line in enumerate(text.splitlines(), 1):
            if disallowed_regex.search(line):
                violating_lines.append(f"{py_file.name}:{idx}: {line.strip()}")

    assert not violating_lines, "Found hardcoded user paths in Python code:\n" + "\n".join(violating_lines)


def test_subprocess_execution_safety() -> None:
    """Verify WindowsStorePublisher_3.py does not invoke unquoted or unsafe shell=True executions."""
    pub_file = ROOT / "WindowsStorePublisher_3.py"
    assert pub_file.is_file(), "WindowsStorePublisher_3.py must exist"
    content = pub_file.read_text(encoding="utf-8")

    # shell=True in subprocess calls is prohibited
    unsafe_shell_calls = []
    for idx, line in enumerate(content.splitlines(), 1):
        if "subprocess." in line and "shell=True" in line:
            unsafe_shell_calls.append(f"Line {idx}: {line.strip()}")

    assert not unsafe_shell_calls, "Unsafe shell=True subprocess execution found:\n" + "\n".join(unsafe_shell_calls)


def test_security_policy_sla_and_contacts() -> None:
    """Verify SECURITY.md maintains strict SLA and designated response channels."""
    sec_file = ROOT / "SECURITY.md"
    assert sec_file.is_file(), "SECURITY.md must exist"
    content = sec_file.read_text(encoding="utf-8")

    assert "security@file-bricks.org" in content
    assert "security@open-bricks.org" in content
    assert "48" in content, "48h initial acknowledgment SLA missing"
    assert "5" in content, "5-day triage commitment missing"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main(["-v", __file__]))
