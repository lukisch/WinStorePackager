# Windows Store — Vorbereitung WinStorePackager

Stand: 2026-09-09

---

## Identität & Partner Center Metadaten

| Feld | Wert | Anmerkung |
|---|---|---|
| **App Name** | `WinStorePackager` | Öffentlicher Anzeigename im Store |
| **Package Identity** | `Geiger.WinStorePackager` | Eindeutige Paket-Identität |
| **Publisher DN** | `CN=52596601-BAB4-4F3F-B182-E8F3F273B202` | Kanonische Partner Center Herausgeber-ID |
| **Publisher Display Name** | `Lukas Geiger` | Herausgeberanzeige im Store |
| **Version** | `3.1.0.0` | Quad-Dot Windows Package Version |
| **Store ID** | `9NT273Z50BJR` | Partner Center Produkt-ID |
| **Executable** | `WinStorePackager.exe` | Hauptprogramm |
| **Category** | `Developer Tools` | Primärkategorie im Microsoft Store |
| **Age Rating** | `3+` | IARC-Einstufung (Allgemein freigegeben) |
| **Lizenz** | `MIT` | Open Source Lizenzmodell |

Die Publisher-Identität ist identisch mit dem Microsoft Partner Center Konto von Lukas Geiger. Die Werte stimmen exakt mit `store_package.json` und der Store-Pipeline überein.

---

## Checkliste: Vor Store-Einreichung

### Pflichtartefakte & Dokumente

- [x] `store_package.json` gepflegt, mit kanonischer Publisher-DN und Store-ID validiert
- [x] `STORE_LISTING.md` gepflegt — DE + EN Beschreibung, Richtlinie 10.1.3 konform (max. 7 Keywords je Sprache)
- [x] `PRIVACY_POLICY.md` offline-first / Zero-Egress Erklärung vorhanden und öffentlich erreichbar
- [x] `SUPPORT.md` zweisprachig DE/EN mit Support-Kontakt und FAQ erstellt
- [x] `THIRD_PARTY_LICENSES.txt` vollständige Lizenzdokumentation der Abhängigkeiten
- [x] Store-Kacheln in `store_assets/` (44x44, 50x50, 150x150, 310x150, 310x310) vollständig vorhanden
- [x] Store-Readiness-Gate `scripts/check_store_readiness.py` & Testsuite `tests/test_store_readiness.py`

### GitHub-Repository

- [x] Repository `file-bricks/WinStorePackager` auf GitHub vorhanden (`origin/master`)
- [x] Privacy-URL und Support-URL in `store_package.json` auf das GitHub-Repository verifiziert
- [x] Open-Source-Lizenz `LICENSE` (MIT) vorhanden

### Paketierung, WACK & Freigabe

- [x] Windows-Quellpreflight `python unix_preflight.py` erfolgreich (0 Befunde)
- [x] Screenshot-Set (4 Screenshots 1920x1080) generiert und verifiziert
- [x] Pytest-Testsuite vollständig grün
- [ ] Windows-EXE bauen (`build_exe.bat` oder PyInstaller)
- [ ] MSIX-Paket erstellen (`WindowsStorePublisher_3.py` oder WinStorePackager-Dogfooding)
- [ ] WACK-Zertifizierungstest ausführen
- [ ] Paket im Microsoft Partner Center hochladen (Nutzer-Freigabe erforderlich)

---

## Technische Parameter

### Capabilities

- `runFullTrust`: Erforderlich für Desktop-Bridge, Ausführung von SDK-Tools (`makeappx.exe`, `signtool.exe`) und lokalen Dateisystemzugriff.
- `internetClient`: Erlaubt optionale Prüfung auf GitHub-Updates und Hilfeverlinkungen.

### Systemanforderungen

- Windows 10 Version 1903 (Build 18362) oder Windows 11 (64-Bit)
- x64-Architektur
- Mindestens 4 GB RAM
- Ca. 150 MB freier Festplattenspeicher
- Microsoft Windows SDK (für `makeappx.exe` und `signtool.exe` Paketierungsfunktionen)

---

## Verwandte Dateien

- `store_package.json` — Strukturierte Metadaten für Packaging & Store
- `STORE_LISTING.md` — Mehrsprachige Produktbeschreibungen und Keywords
- `PRIVACY_POLICY.md` — Datenschutzerklärung
- `SUPPORT.md` — Support- und FAQ-Dokumentation
- `THIRD_PARTY_LICENSES.txt` — Lizenzdokumentation externer Pakete
- `scripts/check_store_readiness.py` — Automatisierter Preflight-Prüfer
- `tests/test_store_readiness.py` — Pytest-Vertragstests für Store-Metadaten
