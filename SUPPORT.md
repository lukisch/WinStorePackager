# Support — WinStorePackager

## Deutsch

### Kontakt & Hilfe

Bei Fragen, Fehlermeldungen oder Funktionswünschen stehen folgende Support-Kanäle zur Verfügung:

- **GitHub Issues** (bevorzugt für Bug-Reports und Feature-Requests): https://github.com/file-bricks/WinStorePackager/issues
- **E-Mail**: lukasgeiger@googlemail.com

### Häufig gestellte Fragen (FAQ)

**Welche Systemvoraussetzungen gelten für WinStorePackager?**
WinStorePackager benötigt Windows 10 (ab Version 1903, Build 18362) oder Windows 11 (64-Bit) sowie eine installierte Python-Umgebung (ab Version 3.10). Für die eigentliche Paketierung und Signierung wird das Microsoft Windows SDK benötigt (mindestens `makeappx.exe` und `signtool.exe`).

**Wie werden Passwörter für Zertifikate (.pfx) gespeichert?**
WinStorePackager verwendet den Windows Anmeldeinformationsspeicher (Windows Credential Manager via `keyring`), um sensible Kennwörter sicher auf Ihrem lokalen Computer abzulegen. Passwörter werden niemals im Klartext in Konfigurations- oder Profildateien gespeichert.

**Funktioniert WinStorePackager offline?**
Ja. Die Kernfunktionen — Manifest-Generierung, Kachelbilderzeugung, PyInstaller-Kompilierung, MSIX-Erstellung und WACK-Audits — laufen zu 100 % lokal auf Ihrem PC. Es werden keinerlei Telemetriedaten, Quelltexte oder Nutzungsdaten an externe Server übertragen (Zero-Egress-Prinzip).

**Was bedeutet die Prüfung mit dem Windows App Certification Kit (WACK)?**
Das Windows App Certification Kit ist ein offizielles Microsoft-Prüfwerkzeug. WinStorePackager integriert WACK direkt in die GUI, sodass Sie Ihr fertiges MSIX-Paket vor dem Hochladen in das Partner Center auf Konformität prüfen können.

**Welche Publisher-ID muss ich eintragen?**
Tragen Sie den Distinguished Name (CN) aus Ihrem Microsoft Partner Center Konto ein (z. B. `CN=52596601-BAB4-4F3F-B182-E8F3F273B202`). Dieser muss exakt mit dem Inhaberzertifikat und Ihren Store-Kontodaten übereinstimmen.

### Versionsverlauf

Details zu Neuerungen und Fehlerbehebungen finden Sie in der Datei `CHANGELOG.md` im Projektverzeichnis.

---

## English

### Contact & Support

For questions, bug reports, or feature requests, the following channels are available:

- **GitHub Issues** (preferred for bug reports and enhancements): https://github.com/file-bricks/WinStorePackager/issues
- **Email**: lukasgeiger@googlemail.com

### Frequently Asked Questions (FAQ)

**What are the system requirements for WinStorePackager?**
WinStorePackager requires Windows 10 (version 1903, build 18362 or higher) or Windows 11 (64-bit) and Python 3.10+. For packaging and signing, the Microsoft Windows SDK is required (at minimum `makeappx.exe` and `signtool.exe`).

**How are certificate (.pfx) passwords stored?**
WinStorePackager uses the Windows Credential Manager (via `keyring`) to store sensitive passwords securely on your local machine. Passwords are never saved in plaintext in project profile or configuration files.

**Does WinStorePackager work offline?**
Yes. All core capabilities — manifest generation, icon building, PyInstaller compilation, MSIX bundling, and WACK audits — run 100% locally on your machine. No telemetry, source code, or application data leaves your computer (zero-egress architecture).

**What is the Windows App Certification Kit (WACK) validation?**
The Windows App Certification Kit is Microsoft's official pre-certification test tool. WinStorePackager integrates WACK directly into the GUI, allowing you to validate your generated MSIX package before uploading it to Partner Center.

**Which Publisher ID should I configure?**
Use the exact Distinguished Name (CN) from your Microsoft Partner Center account (e.g. `CN=52596601-BAB4-4F3F-B182-E8F3F273B202`). It must match your code-signing certificate subject and Partner Center identity.

### Version History

Refer to `CHANGELOG.md` in the project root directory for detailed release notes.
