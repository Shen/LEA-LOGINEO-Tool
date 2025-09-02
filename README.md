# LEA‑LOGINEO‑Tool

Ein GUI‑Tool zur Konvertierung von LEA‑Exporten für LOGINEO NRW sowie zum Erzeugen personalisierter Zugangsdaten‑PDFs.

- Standardstart: GUI (kein Terminal nötig)
- Optionaler Modus: Konsole per `--cli`
- Konfiguration: `config.xml` im Programmverzeichnis

## Voraussetzungen

- Windows oder macOS
- Python 3.10+ (für den Build). Die Endnutzer benötigen kein Python.
- Internetzugang für Abhängigkeitsinstallation beim Build (Pip/PyInstaller)

## Build (Windows)

- Einfach (Doppelklick): `build_win.bat` (Fenster bleibt offen, zeigt ggf. Fehler)
- Alternativ PowerShell im Projektordner öffnen:
  - Ein‑Datei‑Build (empfohlen): `scripts/build_win_utf8.ps1 -OneFile`
  - Ordner‑Build: `scripts/build_win_utf8.ps1 -OneDir`
- Ergebnis: `LEA-LOGINEO-Tool.exe` (im Projektordner)

Hinweise:
- Falls die Ausführung blockiert ist: `powershell -ExecutionPolicy Bypass -File scripts/build_win_utf8.ps1 -OneFile`
- Fenster schließt sich sofort? Verwende `build_win.bat` (startet PowerShell mit `-NoExit`).
- Das Skript ist pfadsicher (Leerzeichen im Pfad werden unterstützt).

## Build (macOS)

- Terminal im Projektordner öffnen
- Skript ausführbar machen (einmalig):
  - `chmod +x scripts/build_mac.sh`
- Ein‑Datei‑Binary:
  - `ONEFILE=1 scripts/build_mac.sh`
- App‑Ordner (.app, empfohlen für Verteilung):
  - `ONEFILE=0 scripts/build_mac.sh`
- Ergebnis: `LEA-LOGINEO-Tool` (Binary) oder `LEA-LOGINEO-Tool.app` (im Projektordner)

Hinweise:
- Pfade mit Leerzeichen werden unterstützt.
- Gatekeeper: Beim ersten Start ggf. Rechtsklick → Öffnen (oder signieren/notarisieren, falls verteilt).

## Nutzung

- `config.xml` neben die ausführbare Datei legen.
- Start per Doppelklick auf `LEA-LOGINEO-Tool(.exe|.app)`.
- Optional Konsole statt GUI:
  - Windows/macOS: `LEA-LOGINEO-Tool --cli`

## Icons

- Aktuell ist kein Icon eingebettet. Bei Bedarf kann ein `.ico` (Windows) bzw. `.icns` (macOS) integriert werden.

## Lizenz & Hinweise

- Lizenz: GNU GPLv3, siehe `LICENSE`.
- DISCLAIMER: Dieses Programm wird ohne jegliche Garantie bereitgestellt. Freie Software; Weitergabe unter den Bedingungen der GPLv3.
- Markenrecht: Alle genannten Produktnamen, Logos und Marken sind Eigentum der jeweiligen Rechteinhaber. Die Verwendung dient ausschließlich der Identifikation und impliziert keine Verbindung, Unterstützung oder Billigung durch die Rechteinhaber.
