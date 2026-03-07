<p align="center">
  <img src="https://img.shields.io/badge/Version-2.3-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.10+-yellow?style=for-the-badge" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge" alt="Windows">
  <img src="https://img.shields.io/badge/Target-Microsoft%20Store-orange?style=for-the-badge" alt="Microsoft Store">
</p>

<h1 align="center">WinStorePackager</h1>

<h4 align="center">GUI-Tool zur Vorbereitung von Python-Apps fuer den Microsoft Store — Manifest, Icons und MSIX-Paket auf Knopfdruck</h4>

---

## Features

| Feature | Beschreibung |
|---------|-------------|
| **Manifest-Generator** | Erstellt `AppxManifest.xml` automatisch aus Formulareingaben |
| **Icon-Generator** | Alle Store-Pflichtgroessen: 44×44, 50×50, 150×150, 310×310, 310×150 (Wide) |
| **Keyring-Integration** | Sichere Speicherung von Zertifikat-Passwoertern (kein Klartext) |
| **Screenshot-Assistent** | Erstellt App-Screenshots direkt via `pygetwindow` |
| **11 Store-Kategorien** | Vordefiniert (Games, Productivity, Developer Tools, ...) |
| **Altersfreigaben** | 3+ bis 18+ Ratings |
| **MSIX-Build** | Ruft `makeappx.exe` und `signtool.exe` aus dem Windows SDK auf |
| **Settings-Persistenz** | Konfiguration wird in JSON gespeichert und beim naechsten Start geladen |
| **Auto-Install** | Fehlende Abhaengigkeiten werden automatisch nachinstalliert |

---

## Voraussetzungen

- Python 3.10+
- Windows 10/11
- [Windows SDK](https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/) (fuer `makeappx.exe` und `signtool.exe`)
- Microsoft Store Entwicklerkonto (fuer Submission)

```bash
pip install -r requirements.txt
```

---

## Installation

```bash
git clone https://github.com/lukisch/WinStorePackager.git
cd WinStorePackager
pip install -r requirements.txt
python WindowsStorePublisher_3.py
```

Oder unter Windows per Doppelklick auf `START.bat`.

---

## Erste Schritte

1. **Tool starten** — `python WindowsStorePublisher_3.py` oder `START.bat`
2. **App-Daten eintragen** — Name, Publisher-ID, Version, Pfad zur `.py`-Datei
3. **Icon auswaehlen** — das Tool generiert automatisch alle Store-Groessen
4. **Manifest generieren** — `AppxManifest.xml` wird erstellt
5. **MSIX bauen** — Tool ruft `makeappx.exe` auf und erstellt das Paket
6. **Signieren** — Zertifikat auswaehlen, Passwort via Keyring sicher eingeben

---

## Konfiguration

Beim ersten Start wird `settings_store_packager.json` erstellt (im `.gitignore` — enthaelt persoenliche Daten). Vorlage:

```json
{
  "app_name": "MyApp",
  "publisher": "CN=YOUR-PUBLISHER-ID",
  "publisher_display": "Your Name",
  "version": "1.0.0.0",
  "makeappx_path": "C:/Program Files (x86)/Windows Kits/10/App Certification Kit/makeappx.exe",
  "signtool_path": "C:/Program Files (x86)/Windows Kits/10/App Certification Kit/signtool.exe"
}
```

Die Publisher-ID findest du im [Microsoft Partner Center](https://partner.microsoft.com/dashboard).

---

## Vergleich mit Alternativen

| Feature | WinStorePackager | MSIX Packaging Tool | Visual Studio | Advanced Installer |
|---------|:---:|:---:|:---:|:---:|
| GUI | ✅ | ⚠️ | ✅ | ✅ |
| Python-Fokus | ✅ | ❌ | ❌ | ❌ |
| Auto-Icons | ✅ | ❌ | ⚠️ | ✅ |
| Manifest-Template | ✅ | ❌ | ✅ | ✅ |
| Kostenlos | ✅ | ✅ | ⚠️ | ❌ |
| Screenshot-Assistent | ✅ | ❌ | ❌ | ❌ |
| Keyring-Sicherheit | ✅ | ❌ | ❌ | ❌ |

---

## Lizenz

Dieses Projekt steht unter der [MIT License](LICENSE).

---

🇬🇧 [English version](README.md)
