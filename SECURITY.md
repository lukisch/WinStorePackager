# Security Policy / Sicherheitsrichtlinie

## Deutsch

### Sicherheitsphilosophie & Leitlinien

`file-bricks/WinStorePackager` ist als rein lokale Desktop- und CLI-Anwendung zur Vorbereitung, Validierung und Paketierung von Python-Anwendungen für den Microsoft Store konzipiert. Sicherheit, Datenschutz und Geheimnisschutz basieren auf folgenden Kernprinzipien:

- **Local-First & kontrollierter Egress:** WinStorePackager überträgt keine Telemetriedaten, Nutzungsstatistiken oder Projektinhalte. Fehlende Build-Werkzeuge werden niemals automatisch aus dem Netzwerk installiert. Nur eine ausdrücklich konfigurierte Signatur-Zeitstempelung kann den gewählten Zeitstempeldienst kontaktieren.
- **Keine Cloud-Zwangsverbindung:** Es existieren keine Zwangsverbindungen zu Cloud-Diensten. Der Paketierungsworkflow nutzt die lokal auf dem System installierten Windows SDK-Tools (`makeappx.exe`, `signtool.exe`) bzw. das SDK-freie Unix-Preflight.
- **Unprivilegierter User-Mode (Non-Elevation):** WinStorePackager benötigt und verlangt keine Administratorrechte. Alle Dateioperationen, Manifest-Erzeugungen und Hilfsskripte laufen streng im unprivilegierten Benutzerkontext ab.
- **OS-Keyring-Geheimnisschutz:** Zertifikatspasswörter werden ausschließlich über den sicheren Keyring des Betriebssystems (`keyring`-Bibliothek) verwaltet. Passwörter werden niemals im Klartext, in JSON-Konfigurationsdateien oder im Git-Repository gespeichert.
- **Host-lokale Datenisolation:** Maschinenspezifische Einstellungen (`settings_store_packager.json`), Publisher-IDs, Zertifikatspfade und Logs liegen außerhalb des Quellcode-Checkouts im benutzereigenen AppData-/Config-Verzeichnis (`%LOCALAPPDATA%\WinStorePackager`, `~/.config/winstorepackager`, `~/Library/Application Support/WinStorePackager`).
- **Sanitärer Profil-Export:** Das Projektprofil-Format (`winstorepackager-project-v1.json`) ist so ausgelegt, dass sensible Publisher-DNs, Zertifikatspfade, SDK-Pfade und Passwörter beim Teilen von Metadaten ausgeschlossen bleiben.

### Unterstützte Versionen

| Version | Unterstützt | Anmerkungen |
| ------- | ----------- | ----------- |
| 3.1.x   | Ja          | Aktuelle Hauptversion mit 6-Sprachen-GUI (i18n), Tier-2-Fallback & Preflight-Härtung |
| < 3.1.0 | Eingeschränkt | Bitte auf die aktuelle Version aktualisieren |

### Sicherheitslücken melden

Wenn Sie eine Sicherheitslücke oder ein kritisches Integritätsproblem in WinStorePackager entdecken:

1. **Bevorzugter Meldeweg:** Nutzen Sie die private Vulnerability-Reporting-Funktion direkt auf GitHub:
   - Öffnen Sie den Tab **Security** in diesem Repository
   - Wählen Sie **Report a vulnerability** ([Direktlink](https://github.com/file-bricks/WinStorePackager/security/advisories/new))
   - Beschreiben Sie das Verhalten, Schritte zur Reproduktion und mögliche Auswirkungen
2. **Direkter E-Mail-Kontakt:** Alternativ können Sie sich direkt an unsere Sicherheitskoordinatoren wenden:
   - `security@open-bricks.org`
   - `security@file-bricks.org`
   - `security@ellmos.ai`
   - `support@lukasgeiger.com`
   - `lukas@open-bricks.org`

### Reaktionszeiten & SLAs

- **Erste Eingangsbestätigung:** Verbindlich innerhalb von 48 Stunden nach Eingang der Meldung.
- **Erste Risikobewertung & Triage:** Innerhalb von 5 Werktagen.
- **Sicherheits-Patch:** Nach Priorität und Kritikalität im schnellstmöglichen Turnus.

Bitte öffnen Sie für Sicherheitslücken **keine öffentlichen Issues** und veröffentlichen Sie keine sensiblen Publisher-IDs, Zertifikate oder Pfade. Bestätigte Sicherheitsprobleme werden mit höchster Priorität behoben.

---

## English

### Security Principles & Core Guarantees

`file-bricks/WinStorePackager` is engineered as a strictly local desktop GUI and CLI tool for preparing, validating, and packaging Python applications for the Microsoft Store. Security, privacy, and secret protection are grounded in the following guarantees:

- **Local-First & Controlled Egress:** WinStorePackager does not transmit project files, telemetry, or analytics. Missing build tools are never installed automatically from the network. Only explicitly configured signature timestamping may contact the selected timestamp service.
- **Zero Cloud Requirement:** No mandatory cloud accounts or external telemetry endpoints. The build workflow utilizes local Windows SDK binaries (`makeappx.exe`, `signtool.exe`) or SDK-free Unix preflight scripts.
- **Unprivileged User-Mode Operation (Non-Elevation):** WinStorePackager operates strictly within standard user privileges and does not require elevated administrator rights.
- **OS Keyring Cryptographic Isolation:** Code-signing certificate passwords are encrypted and managed exclusively through the operating-system Keyring. Passwords are never written to disk in plaintext, configuration JSONs, or Git-tracked files.
- **Host-Local Runtime Settings & Logs:** Machine-specific settings, Publisher IDs, SDK paths, and diagnostic logs live outside the source checkout in host-local directories (`%LOCALAPPDATA%\WinStorePackager`, `~/.config/winstorepackager`, `~/Library/Application Support/WinStorePackager`).
- **Sanitized Project Profile Exchange:** The shared exchange format (`winstorepackager-project-v1.json`) intentionally omits sensitive Publisher IDs, certificate paths, SDK paths, and passwords to enable safe metadata sharing across teams.

### Supported Versions

| Version | Supported | Notes |
| ------- | --------- | ----- |
| 3.1.x   | Yes       | Active production release with 6-language GUI (i18n), Tier-2 fallback & preflight |
| < 3.1.0 | Deprecated | Upgrade to the latest version recommended |

### Reporting a Vulnerability

If you discover a security vulnerability or sensitive data exposure in WinStorePackager:

1. **Preferred Method:** Report privately via GitHub's Security Advisories flow:
   - Navigate to the **Security** tab of this repository
   - Click **Report a vulnerability** ([Direct Link](https://github.com/file-bricks/WinStorePackager/security/advisories/new))
   - Provide reproduction steps, affected environment, and potential impact
2. **Direct Security Email:** Alternatively, email our security coordinators directly:
   - `security@open-bricks.org`
   - `security@file-bricks.org`
   - `security@ellmos.ai`
   - `support@lukasgeiger.com`
   - `lukas@open-bricks.org`

### Response SLAs & Vulnerability Handling

- **Initial Acknowledgment:** Guaranteed within 48 hours of receipt.
- **Triage & Risk Assessment:** Within 5 business days.
- **Remediation & Patching:** Deployed with highest priority according to severity.

Please **do not disclose vulnerabilities in public issues**. Confirmed security patches are prioritized and released promptly.
