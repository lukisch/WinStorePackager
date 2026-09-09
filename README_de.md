> [English](README.md) | **Deutsch**

<p align="center">
  <img src="https://img.shields.io/badge/Ökosystem-file--bricks-blue?style=for-the-badge" alt="Ökosystem">
  <img src="https://img.shields.io/badge/Dachverband-open--bricks-orange?style=for-the-badge" alt="Dachverband">
  <img src="https://img.shields.io/badge/Version-3.1.0-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.9--3.13-yellow?style=for-the-badge" alt="Python">
  <img src="https://img.shields.io/badge/CI-Multi--OS%20Bestanden-brightgreen?style=for-the-badge&logo=githubactions" alt="CI Status">
  <img src="https://img.shields.io/badge/Tests-125%20bestanden%20%7C%204%20%C3%BCbersprungen-brightgreen?style=for-the-badge" alt="Tests">
  <img src="https://img.shields.io/badge/Lizenz-MIT-green?style=for-the-badge" alt="Lizenz">
  <img src="https://img.shields.io/badge/Plattform-Windows%20%7C%20Linux%20%7C%20macOS-0078D6?style=for-the-badge" alt="Plattform">
  <img src="https://img.shields.io/badge/Sicherheits--SLA-48h%20SLA-blue?style=for-the-badge" alt="Sicherheits-SLA">
  <img src="https://img.shields.io/badge/Datenschutz-100%25%20Local--First%20%7C%20Zero--Egress-purple?style=for-the-badge" alt="Datenschutz">
  <img src="https://img.shields.io/badge/Sicherheit-Local--First%20%7C%20Keyring--Gesch%C3%BCtzt-success?style=for-the-badge" alt="Sicherheit">
  <img src="https://img.shields.io/badge/Code--Stil-Ruff-000000?style=for-the-badge" alt="Code-Stil">
  <img src="https://img.shields.io/badge/LLM--Kontext-llms.txt-blueviolet?style=for-the-badge" alt="LLM Kontext">
</p>

<h1 align="center">WinStorePackager</h1>

<h4 align="center">Lokales Windows-GUI zur Vorbereitung von Python-Apps für den Microsoft Store: AppxManifest, Store-Icons, Projektprofile, Screenshots und MSIX-Paketierung</h4>

<p align="center">
  <a href="#schnellstart">Schnellstart</a> •
  <a href="#funktionen">Funktionen</a> •
  <a href="#architektur--paketierungs-pipeline">Architektur</a> •
  <a href="#paketierungs-lebenszyklus">Lebenszyklus</a> •
  <a href="#visuelle-showcase--store-assets">Showcase</a> •
  <a href="#projektprofil-austausch-und-lokaler-profil-helfer">Projektprofile</a> •
  <a href="#geschwister-tools--ökosystem">Ökosystem</a> •
  <a href="SECURITY.md">Sicherheitsrichtlinie</a> •
  <a href="CHANGELOG.md">Änderungsprotokoll</a> •
  <a href="llms.txt">LLM-Kontext</a>
</p>

> [!NOTE]
> **Hinweis für KI-Agenten & LLMs**: Die Repository-Struktur und KI-Kontextgrenzen sind in [`llms.txt`](llms.txt) beschrieben. Austauschformate und Metadaten-Schemas finden sich in [`PROJECT_PROFILE_FORMAT.md`](PROJECT_PROFILE_FORMAT.md) und [`winstorepackager-project-v1.json`](winstorepackager-project-v1.json).

---

## Schnellstart

| Ziel | Einstieg |
|---|---|
| Python-App für den Microsoft Store vorbereiten & bauen | [`WindowsStorePublisher_3.py`](WindowsStorePublisher_3.py) oder `START.bat` auf Windows |
| Store-Metadaten ohne Windows SDK auf Linux/macOS prüfen | [`unix_preflight.py`](unix_preflight.py) |
| Store-Screenshots mit Demo-Metadaten neu erzeugen | `python generate_store_screenshots.py` |
| Projektprofil ohne lokale Geheimnisse austauschen | [`PROJECT_PROFILE_FORMAT.md`](PROJECT_PROFILE_FORMAT.md) |
| WinStorePackager mit eigenem Profil testen (Dogfooding) | [`winstorepackager-project-v1.json`](winstorepackager-project-v1.json) |
| Sicherheits-, Datenschutz- und Git-Grenzen prüfen | [`SECURITY.md`](SECURITY.md), [`PRIVACY_POLICY.md`](PRIVACY_POLICY.md) und [Lokale Daten](#lokale-daten-und-build-artefakte) |

WinStorePackager richtet sich an kleine Teams und Einzelentwickler, die eine bestehende Python-App nicht jedes Mal in ein Visual-Studio-Projekt umziehen möchten. Das Werkzeug bündelt die wiederkehrenden Schritte: AppxManifest-Metadaten, Store-Icon-Skalierung, Screenshot-Sammlung, Profilaustausch und Windows-SDK-Befehle.

---

## Funktionen

| Funktion | Beschreibung |
|---------|-------------|
| **Manifest-Generator** | Erzeugt automatisch ein valides `AppxManifest.xml` mit Schema-Prüfung aus Formulareingaben |
| **Icon-Generator** | Erstellt alle geforderten Store-Größen: 44×44, 50×50, 150×150, 310×310 und 310×150 (Wide) |
| **6-Sprachen-GUI (i18n)** | Vollständige Mehrsprachigkeit (Tier 2 / P-006: DE, EN, ES, ZH, JA, RU) mit Laufzeitumschaltung |
| **Keyring-Sicherheit** | Sichere Verwahrung von Zertifikatspasswörtern im OS-Keyring (kein Klartext auf der Festplatte) |
| **Screenshot-Assistent** | Automatische Erfassung von Anwendungsfenstern via `pygetwindow` für Store-Listings |
| **11 Store-Kategorien** | Vordefinierte Store-Kategorien (Entwicklertools, Produktivität, Bildung, Dienstprogramme, ...) |
| **Altersfreigaben** | Vordefinierte Einstufungen von 3+ bis 18+ mit konformer Manifest-Deklaration |
| **MSIX Build & Sign** | Integrierte Ausführung von `makeappx.exe` und `signtool.exe` aus dem Windows SDK (SHA-256) |
| **Laufzeit-Einstellungen** | Host-lokale JSON-Konfiguration außerhalb von Git mit atomarer Migrationsabsicherung |
| **SDK-freies Preflight** | Plattformunabhängige Validierung von Manifesten, Profilen und Store-Assets auf Linux & macOS |

---

## Architektur & Paketierungs-Pipeline

```mermaid
flowchart TD
    subgraph Input["1. Anwendungs-Eingaben"]
        A["Python App Quellcode & Einstiegspunkt"]
        B["Anwendungs-Basis-Icon / PNG"]
        C["Store-Listing & Metadaten (v1.json)"]
    end

    subgraph Core["2. WinStorePackager Kern"]
        D["WinStorePackager GUI / CLI"]
        E["AppxManifest.xml Templating & Schema Guard"]
        F["Pillow Multi-Scale Icon Builder (44..310px)"]
        G["Projektprofil Redaktor & Export"]
    end

    subgraph Build["3. Windows SDK Paketierung & Signierung"]
        H["Windows SDK makeappx.exe pack"]
        I["OS-Keyring Sichere Passwort-Abfrage"]
        J["Windows SDK signtool.exe sign (SHA-256)"]
    end

    subgraph Output["4. Freigabe & Einreichung"]
        K["Signiertes MSIX / AppX Paket"]
        L["Windows App Certification Kit (WACK) Vorprüfung"]
        M["Microsoft Partner Center Store-Einreichung"]
    end

    A & B & C --> D
    D --> E & F & G
    E & F --> H
    H --> K
    K --> J
    I --> J
    J --> L
    L --> M

    subgraph Unix["Plattformunabhängiges Preflight (Linux / macOS)"]
        N["unix_preflight.py"] --> O["SDK-freie Validierung von Manifesten, Profilen & Assets"]
    end
```

---

## Paketierungs-Lebenszyklus

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Entwickler
    participant GUI as WinStorePackager GUI / CLI
    participant Profile as Projektprofil (v1.json)
    participant Manifest as AppxManifest Generator
    participant Icons as Store Icon Builder (Pillow)
    participant SDK as Windows SDK (makeappx / signtool)
    participant Keyring as OS-Keyring Speicher
    participant Store as Microsoft Partner Center

    Dev->>GUI: Starten & Projekt / Profil laden
    GUI->>Profile: Schema validieren & lokale Pfade redigieren
    Dev->>GUI: Anwendungs-Identität, Version & Rechte konfigurieren
    GUI->>Manifest: AppxManifest.xml mit Schemavalidierung erzeugen
    Dev->>GUI: Basis-Icon / Bildressource bereitstellen
    GUI->>Icons: Icons in 44x44, 50x50, 150x150, 310x310 & 310x150 generieren
    Dev->>GUI: Build & Paketierung anstoßen
    GUI->>SDK: makeappx.exe pack /d payload /p package.msix aufrufen
    GUI->>Keyring: Zertifikatspasswort sicher abrufen
    GUI->>SDK: signtool.exe sign /f cert.pfx /fd SHA256 ausführen
    SDK-->>GUI: Signiertes MSIX-Paket einsatzbereit
    GUI-->>Dev: Bereit für WACK-Test & Partner-Center-Einreichung
    Dev->>Store: MSIX-Paket im Microsoft Partner Center hochladen
```

---

## Visuelle Showcase & Store-Assets

| Store-Funktion | Visuelle Übersicht |
|---|---|
| **Hauptübersicht & Paketierung**<br>Interaktives Desktop-GUI für Anwendungsidentität, Quellpfade und Windows-SDK-Toolchain. | ![Hauptfenster](releases/windowsstore/screenshots/01-main-window.png) |
| **Store-Metadaten & Freigaben**<br>Vordefinierte Store-Kategorien, Altersfreigaben, Capabilities, Support-URLs und lokalisierte Datenschutzrichtlinien. | ![Store-Felder](releases/windowsstore/screenshots/02-store-fields.png) |
| **Multi-Resolution Icon Builder**<br>Automatische Erzeugung und Vorschau aller geforderten Kachel- und Icon-Formate für den Microsoft Store. | ![Icon-Generierung](releases/windowsstore/screenshots/03-icon-generation.png) |
| **MSIX-Paketierung & Signierung**<br>Ein-Klick-MSIX-Erstellung, OS-Keyring-Zertifikatsauthentifizierung und WACK-Vorprüfung. | ![MSIX-Workflow](releases/windowsstore/screenshots/04-msix-wack-workflow.png) |

Der kuratierte Store-Screenshot-Satz kann jederzeit neu generiert werden:

```bash
python generate_store_screenshots.py
```

Das Skript schreibt vier PNGs (1920x1080) nach `releases/windowsstore/screenshots/` mit neutralen Demo-Metadaten, ohne echte Publisher-IDs, Zertifikatspfade oder Passwörter preiszugeben.

---

## Projektprofil-Austausch und Lokaler Profil-Helfer

WinStorePackager enthält ein standardisiertes Projektprofil-Format: [`PROJECT_PROFILE_FORMAT.md`](PROJECT_PROFILE_FORMAT.md). Die Desktop-App kann `winstorepackager-project-v1.json` importieren und exportieren, sodass Store-Metadaten auch außerhalb von Windows vorbereitet werden können, ohne Publisher-IDs, SDK-Pfade, Zertifikatspfade oder Passwörter offenzulegen.

Dieses Repository enthält ein eigenes Dogfooding-Profil, [`winstorepackager-project-v1.json`](winstorepackager-project-v1.json). Es kann direkt geladen oder ohne Windows SDK validiert werden:

```bash
python unix_preflight.py --project-root . --profile-path winstorepackager-project-v1.json
```

---

## Installation & Voraussetzungen

- Python 3.9–3.12+
- Windows 10/11 (für MSIX-Build und Signierung) bzw. Linux/macOS (für Vorprüfungen)
- [Windows SDK](https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/) (für `makeappx.exe` und `signtool.exe`)
- Microsoft Store Entwicklerkonto (für die finale Veröffentlichung)

```bash
git clone https://github.com/file-bricks/WinStorePackager.git
cd WinStorePackager
pip install -r requirements.txt
python WindowsStorePublisher_3.py
```

Unter Windows kann alternativ `START.bat` per Doppelklick ausgeführt werden.

---

## SDK-freier Unix-Preflight (Linux / macOS)

Für Linux/macOS-Entwicklungsrechner oder CI-Pipelines ohne Windows SDK bietet das Repository eine reine Metadaten-Vorprüfung:

```bash
python unix_preflight.py --project-root .
python unix_preflight.py --project-root . --profile-path ./winstorepackager-project-v1.json
```

Das Unix-Preflight prüft Projektstruktur, `store_package.json`, README, Datenschutzrichtlinie, Store-Listing, Screenshots/Icons und exportierte Projektprofile vollständig ohne Windows-Binärdateien.

---

## Lokale Daten und Build-Artefakte

WinStorePackager arbeitet ausschließlich mit lokalen Projektdateien:

- **Host-lokale Runtime-Verzeichnisse:** Maschinenspezifische Einstellungen und rollierende Protokolle liegen außerhalb des Quellcode-Checkouts in `%LOCALAPPDATA%\WinStorePackager` (Windows), `~/Library/Application Support/WinStorePackager` (macOS) oder `${XDG_CONFIG_HOME:-~/.config}/winstorepackager` (Linux).
- **Kryptographische Keyring-Verwaltung:** Zertifikatspasswörter verbleiben im System-Keyring und werden niemals im Klartext oder in JSON-Dateien gespeichert.
- **Git-Hygiene:** Generierte MSIX-Pakete, EXE-Builds, temporäre Staging-Ordner, Zertifikate und Release-Bundles werden von Git strikt ignoriert.

Vorlage für maschinenspezifische Laufzeiteinstellungen (`settings_store_packager.json`):

```json
{
  "app_name": "MeineApp",
  "publisher": "CN=IHRE-PUBLISHER-ID",
  "publisher_display": "Ihr Name",
  "version": "1.0.0.0",
  "makeappx_path": "C:/Program Files (x86)/Windows Kits/10/App Certification Kit/makeappx.exe",
  "signtool_path": "C:/Program Files (x86)/Windows Kits/10/App Certification Kit/signtool.exe"
}
```

---

## Geschwister-Tools & Ökosystem

WinStorePackager ist Teil der **file-bricks** und **open-bricks** Open-Source-Softwarefamilie:

| Werkzeug | Ökosystem | Zweck |
|---|---|---|
| **[ProSync](https://github.com/file-bricks/ProSync)** | `file-bricks` | Lokale Dateisynchronisation & SQLite-WAL-Konsistenzschutz |
| **[CleanMarkdown](https://github.com/doc-bricks/CleanMarkdown)** | `doc-bricks` | Markdown-Bereinigung, Whitespace-Reparatur & Formatnormalisierung |
| **[DokuZen](https://github.com/doc-bricks/DokuZen)** | `doc-bricks` | Schneller, lokaler technischer Dokumentations- und Wissens-Organizer |
| **[UniversalDocsGrabber](https://github.com/doc-bricks/UniversalDocsGrabber)** | `doc-bricks` | Universelle Dokumenten-Erfassung, OCR-Konvertierung & Suche |
| **[ellmos-filecommander-mcp](https://github.com/ellmos-ai/ellmos-filecommander-mcp)** | `ellmos-ai` | Lokaler MCP-Server für sichere Dateiverwaltung, OCR & Suchfunktionen |
| **[open-bricks](https://github.com/open-bricks)** | `open-bricks` | Dachorganisation für modulare Desktop- und Entwicklertools |

---

## Vergleich mit Alternativen

| Funktion | WinStorePackager | MSIX Packaging Tool | Visual Studio | Advanced Installer |
|---------|:---:|:---:|:---:|:---:|
| GUI | ✅ | ⚠️ | ✅ | ✅ |
| Python-Fokus | ✅ | ❌ | ❌ | ❌ |
| Auto-Icons (Alle Größen) | ✅ | ❌ | ⚠️ | ✅ |
| Manifest-Generator | ✅ | ❌ | ✅ | ✅ |
| Kostenlos / Open Source | ✅ | ✅ | ⚠️ | ❌ |
| Screenshot-Assistent | ✅ | ❌ | ❌ | ❌ |
| Keyring-Sicherheit | ✅ | ❌ | ❌ | ❌ |
| 6-Sprachen-Lokalisierung | ✅ | ❌ | ⚠️ | ⚠️ |
| Plattformübergreifender Preflight | ✅ | ❌ | ❌ | ❌ |

---

## Such- und Entdeckungskontext

Nützliche Suchbegriffe für dieses Repository:

- `WinStorePackager Python Microsoft Store MSIX`
- `file-bricks WinStorePackager`
- `Python AppxManifest generator`
- `local-first MSIX packaging tool`
- `Microsoft Store packaging GUI for Python apps`
- `MSIX packaging tool without Visual Studio`

---

## Dokumentation & Governance

- 📄 **Sicherheitsrichtlinie:** [`SECURITY.md`](SECURITY.md) — Zweisprachige Sicherheitsrichtlinie & Local-First-Garantien
- 📝 **Änderungsprotokoll:** [`CHANGELOG.md`](CHANGELOG.md) — Versionshistorie und Release-Notizen
- 🤖 **LLM-Referenz:** [`llms.txt`](llms.txt) — Maschinenlesbare Architekturübersicht
- 📦 **Profilformat:** [`PROJECT_PROFILE_FORMAT.md`](PROJECT_PROFILE_FORMAT.md) — Spezifikation des austauschbaren Projektprofils

---

## Lizenz und Haftung

Dieses Projekt steht unter der [MIT License](LICENSE).

Dieses Projekt ist eine **unentgeltliche Open-Source-Schenkung** im Sinne der §§ 516 ff. BGB. Die Haftung des Urhebers ist gemäß **§ 521 BGB** auf **Vorsatz und grobe Fahrlässigkeit** beschränkt. Ergänzend gilt der Haftungsausschluss der MIT License.

Nutzung auf eigenes Risiko. Keine Wartungszusage, keine Verfügbarkeitsgarantie, keine Gewähr für Fehlerfreiheit oder Eignung für einen bestimmten Zweck.
