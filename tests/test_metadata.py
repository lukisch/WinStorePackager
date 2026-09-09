"""Contract tests for WinStorePackager repository metadata, discoverability, and documentation parity."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_badges_and_quick_nav() -> None:
    """Verify badges and quick navigation in both English and German READMEs."""
    readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (ROOT / "README_de.md").read_text(encoding="utf-8")

    for readme, lang in [(readme_en, "en"), (readme_de, "de")]:
        assert "License-MIT" in readme or "Lizenz-MIT" in readme or "License: MIT" in readme or "Lizenz: MIT" in readme, f"License badge missing in {lang}"
        assert "Version-3.1.0" in readme or "3.1.0" in readme, f"Version badge missing in {lang}"
        assert "Zero--Egress" in readme or "Zero-Egress" in readme or "Local--First" in readme or "Local-First" in readme, f"Privacy badge missing in {lang}"
        assert "file--bricks" in readme or "file-bricks" in readme, f"Ecosystem badge missing in {lang}"
        assert "open--bricks" in readme or "open-bricks" in readme, f"Umbrella badge missing in {lang}"
        assert "llms.txt" in readme, f"llms.txt badge/link missing in {lang}"
        assert "SECURITY.md" in readme, f"SECURITY.md link missing in {lang}"
        assert "CHANGELOG.md" in readme, f"CHANGELOG.md link missing in {lang}"
        assert "PROJECT_PROFILE_FORMAT.md" in readme, f"PROJECT_PROFILE_FORMAT.md link missing in {lang}"


def test_mermaid_diagrams_in_readmes() -> None:
    """Verify Mermaid architecture and sequence lifecycle diagrams exist in READMEs."""
    readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (ROOT / "README_de.md").read_text(encoding="utf-8")

    for readme, lang in [(readme_en, "en"), (readme_de, "de")]:
        assert "```mermaid" in readme, f"Mermaid block missing in {lang}"
        assert "graph TD" in readme or "flowchart TD" in readme, f"Architecture diagram missing in {lang}"
        assert "sequenceDiagram" in readme, f"Sequence lifecycle diagram missing in {lang}"
        assert "makeappx" in readme, f"makeappx step missing in sequence diagram for {lang}"
        assert "signtool" in readme, f"signtool step missing in sequence diagram for {lang}"


def test_visual_showcase_screenshots_exist() -> None:
    """Verify all screenshots referenced in README visual showcase exist on disk."""
    readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
    matches = re.findall(r'!\[.*?\]\((releases/windowsstore/screenshots/[^\)]+)\)', readme_en)
    assert len(matches) >= 4, f"Expected at least 4 showcase screenshots in README.md, found {len(matches)}"

    for rel_path in matches:
        full_path = ROOT / rel_path
        assert full_path.is_file(), f"Screenshot file {rel_path} does not exist"
        assert full_path.stat().st_size > 0, f"Screenshot file {rel_path} is empty"


def test_security_policy_bilingual_integrity() -> None:
    """Verify SECURITY.md contains English and German sections, local-first guarantees, SLAs, and contact emails."""
    security_file = ROOT / "SECURITY.md"
    assert security_file.is_file(), "SECURITY.md must exist"
    content = security_file.read_text(encoding="utf-8")

    assert "## Deutsch" in content or "## German" in content, "German section missing in SECURITY.md"
    assert "## English" in content, "English section missing in SECURITY.md"
    assert "Zero-Egress" in content or "Local-First" in content, "Local-first guarantee missing in SECURITY.md"
    assert "Keyring" in content or "keyring" in content, "Keyring credential security missing in SECURITY.md"
    assert "security@open-bricks.org" in content, "Umbrella security contact email missing in SECURITY.md"
    assert "security@file-bricks.org" in content, "Security contact email missing in SECURITY.md"
    assert "security/advisories/new" in content, "Vulnerability reporting instructions missing"
    assert "48" in content, "48h response SLA missing in SECURITY.md"
    assert "5" in content, "5-day triage commitment missing in SECURITY.md"


def test_llms_txt_integrity() -> None:
    """Verify llms.txt contains updated last-checked timestamp and repository context."""
    llms_file = ROOT / "llms.txt"
    assert llms_file.is_file(), "llms.txt must exist"
    content = llms_file.read_text(encoding="utf-8")

    assert "Last-checked: 2026-09-09" in content, "llms.txt timestamp not updated to 2026-09-09"
    assert "https://github.com/file-bricks/WinStorePackager" in content, "Canonical repo link missing in llms.txt"
    assert "MSIX" in content and "AppxManifest" in content, "Packaging keywords missing in llms.txt"
    assert "SECURITY.md" in content, "SECURITY.md reference missing in llms.txt"


def test_sibling_ecosystem_matrix() -> None:
    """Verify sibling tools matrix linking to file-bricks, doc-bricks, ellmos-ai, and open-bricks."""
    readme_en = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (ROOT / "README_de.md").read_text(encoding="utf-8")

    for readme, lang in [(readme_en, "en"), (readme_de, "de")]:
        assert "ProSync" in readme, f"ProSync sibling link missing in {lang}"
        assert "CleanMarkdown" in readme, f"CleanMarkdown sibling link missing in {lang}"
        assert "DokuZen" in readme, f"DokuZen sibling link missing in {lang}"
        assert "UniversalDocsGrabber" in readme, f"UniversalDocsGrabber sibling link missing in {lang}"
        assert "open-bricks" in readme, f"open-bricks umbrella link missing in {lang}"


def test_pyproject_pep621_metadata() -> None:
    """Verify pyproject.toml PEP 621 metadata, urls, and classifiers."""
    pyproject_file = ROOT / "pyproject.toml"
    assert pyproject_file.is_file(), "pyproject.toml must exist"
    content = pyproject_file.read_text(encoding="utf-8")

    assert 'name = "winstorepackager"' in content
    assert 'version = "3.1.0"' in content
    assert "Security =" in content, "Security URL missing in pyproject.toml"
    assert "Homepage =" in content, "Homepage URL missing in pyproject.toml"
    assert "Repository =" in content, "Repository URL missing in pyproject.toml"
    assert "Documentation =" in content, "Documentation URL missing in pyproject.toml"
    assert "Changelog =" in content, "Changelog URL missing in pyproject.toml"
    assert "Umbrella =" in content, "Umbrella URL missing in pyproject.toml"
    assert '"Parent Organization"' in content, "Parent Organization URL missing in pyproject.toml"
    assert '"Umbrella Ecosystem"' in content, "Umbrella Ecosystem URL missing in pyproject.toml"
    assert "Operating System :: Microsoft :: Windows" in content
    assert "Operating System :: OS Independent" in content, "OS Independent classifier missing"
    assert "Programming Language :: Python :: 3.13" in content, "Python 3.13 classifier missing"
    assert 'addopts = "-v"' in content, "pytest addopts missing in pyproject.toml"


def test_ci_workflow_integrity() -> None:
    """Verify GitHub Actions CI workflows exist, have multi-OS matrix, concurrency, and compileall gate."""
    workflow_dir = ROOT / ".github" / "workflows"
    assert (workflow_dir / "ci.yml").is_file(), "ci.yml missing"

    ci_yml = (workflow_dir / "ci.yml").read_text(encoding="utf-8")
    assert "ubuntu-latest" in ci_yml and "windows-latest" in ci_yml and "macos-latest" in ci_yml
    assert "3.13" in ci_yml, "Python 3.13 missing from CI matrix"
    assert "concurrency:" in ci_yml, "Concurrency block missing in ci.yml"
    assert "cancel-in-progress: true" in ci_yml, "cancel-in-progress missing in ci.yml"
    assert "python -m compileall -q ." in ci_yml, "compileall bytecode gate missing in ci.yml"
    assert "ruff check ." in ci_yml
    assert "pytest -v" in ci_yml


def test_gitignore_hardening() -> None:
    """Verify .gitignore contains multi-host sync conflict patterns and multi-agent locks."""
    gitignore_file = ROOT / ".gitignore"
    assert gitignore_file.is_file(), ".gitignore must exist"
    content = gitignore_file.read_text(encoding="utf-8")

    assert "*.sync-conflict-*" in content, "sync-conflict pattern missing in .gitignore"
    assert "*.conflict" in content, "conflict pattern missing in .gitignore"
    assert "*-CONFLIT-*" in content, "CONFLIT pattern missing in .gitignore"
    assert "LOCK.*" in content, "LOCK.* pattern missing in .gitignore"
    assert "*.lock" in content, "*.lock pattern missing in .gitignore"
    assert "wheelhouse/" in content, "wheelhouse pattern missing in .gitignore"
    assert ".wheel-smoke/" in content, ".wheel-smoke pattern missing in .gitignore"


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main(["-v", __file__]))
