from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd

from .io_utils import resolve_path, ensure_dir, pause
from .settings import Settings
from .mapping import LEHRAEMTER, LEHRAMTGRUPPEN


_ym_re = re.compile(r"(\d{4})-(\d{2})")


def _extract_year_month(s: str) -> str:
    if not s:
        return "???"
    m = _ym_re.search(s)
    return f"{m.group(1)}-{m.group(2)}" if m else "???"


def _read_str(src: pd.Series, col: str) -> str:
    try:
        val = src.get(col, "")
        return "" if val is None else str(val)
    except Exception:
        return ""


def _to_int_like(s: str) -> int | None:
    """Toleriert '27' wie auch '27.0'."""
    try:
        return int(float(s))
    except Exception:
        return None


def _normalize_numeric_text(value: str) -> str:
    """
    Gibt numerische Strings (auch '123.0') als saubere Textwerte zurück.
    Das verhindert, dass Excel sie später als Gleitkommazahlen speichert
    und 8-stellige IDs in die wissenschaftliche Notation zwingt.
    """
    if not value:
        return ""
    cleaned = value.strip()
    if not cleaned:
        return ""
    as_int = _to_int_like(cleaned)
    return f"{as_int:d}" if as_int is not None else cleaned


@dataclass
class OutputRow:
    LEAID: Any = ""
    IdentNr: str = ""
    Nachname: str = ""
    Vorname: str = ""
    Typ: str = "LAA"
    Seminar: str = ""
    Lehramt: str = ""
    Jahrgang: str = ""
    Kernseminar: str = ""
    Fachseminar_1: str = ""
    Fachseminar_2: str = ""

    @staticmethod
    def from_source(src: pd.Series, s: Settings) -> "OutputRow":
        row = OutputRow()

        # LEAID
        leaid_raw = _read_str(src, "LAA_Logineo")
        row.LEAID = _normalize_numeric_text(leaid_raw)

        # IdentNr
        ident = _read_str(src, "LAA_IdentNr")
        if ident and len(ident) > 9:
            row.IdentNr = ("0" + ident) if len(ident) == 10 else ident
        else:
            row.IdentNr = "IdentNr fehlt"

        # Namen
        row.Nachname = _read_str(src, "LAA_Name")
        row.Vorname = _read_str(src, "LAA_Vorname")

        # Lehramtslabel (G, HRSGe, SF, GyGe, BK, ???)
        la_code = _read_str(src, "Lehramt")
        lag_code = _read_str(src, "Lehramtgruppe")
        la_label = "???"
        if la_code:
            key = _to_int_like(la_code)
            la_label = LEHRAEMTER.get(key, "???") if key is not None else "???"
        elif lag_code:
            key = _to_int_like(lag_code)
            la_label = LEHRAMTGRUPPEN.get(key, "???") if key is not None else "???"

        # Seminar & Lehramt (nur wenn aktiviert)
        if s.lea_gruppe_laa_lehramt == "ja":
            row.Seminar = f"Seminar_{la_label}" if la_label != "" else "Seminar_???"
            row.Lehramt = f"LAA_{la_label}" if la_label != "" else "LAA_???"
        else:
            row.Seminar = ""
            row.Lehramt = ""

        # Jahrgang (nur wenn aktiviert)
        if s.lea_gruppe_laa_lehramt_jg == "ja":
            vd_von = _read_str(src, "VDVon")
            row.Jahrgang = f"LAA_{la_label}_{_extract_year_month(vd_von)}"
        else:
            row.Jahrgang = ""

        # Seminare/Fachseminare (nur wenn aktiviert)
        if s.lea_gruppe_laa_seminare == "ja":
            ks_raw = (_read_str(src, "KursSeminarSchluessel")).strip()
            fs1_raw = (_read_str(src, "KursFach1Schluessel")).strip()
            fs2_raw = (_read_str(src, "KursFach2Schluessel")).strip()

            ks = re.sub(r"\s+", "_", ks_raw)
            fs1 = re.sub(r"\s+", "_", fs1_raw)
            fs2 = re.sub(r"\s+", "_", fs2_raw)

            row.Kernseminar = f"Seminar_{ks}" if ks else ""
            row.Fachseminar_1 = f"Seminar_{fs1}" if fs1 else ""
            row.Fachseminar_2 = f"Seminar_{fs2}" if fs2 else ""
        else:
            row.Kernseminar = ""
            row.Fachseminar_1 = ""
            row.Fachseminar_2 = ""

        return row

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FailRow:
    LEAID: Any = ""
    IdentNr: str = ""
    Nachname: str = ""
    Vorname: str = ""
    Typ: str = "LAA"
    Lehramt: str = ""  # immer nützlich in der Fehlerliste

    @staticmethod
    def from_source(src: pd.Series) -> "FailRow":
        fr = FailRow()
        # LEAID
        leaid_raw = _read_str(src, "LAA_Logineo")
        fr.LEAID = _normalize_numeric_text(leaid_raw)

        # IdentNr
        ident = _read_str(src, "LAA_IdentNr")
        if ident and len(ident) > 9:
            fr.IdentNr = ("0" + ident) if len(ident) == 10 else ident
        else:
            fr.IdentNr = "IdentNr fehlt"

        fr.Nachname = _read_str(src, "LAA_Name")
        fr.Vorname = _read_str(src, "LAA_Vorname")

        # Lehramt
        la_code = _read_str(src, "Lehramt")
        lag_code = _read_str(src, "Lehramtgruppe")
        la_label = "???"
        if la_code:
            key = _to_int_like(la_code)
            la_label = LEHRAEMTER.get(key, "???") if key is not None else "???"
        elif lag_code:
            key = _to_int_like(lag_code)
            la_label = LEHRAMTGRUPPEN.get(key, "???") if key is not None else "???"
        fr.Lehramt = f"LAA_{la_label}" if la_label else "LAA_???"
        return fr

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LEAConverter:
    """
    Liest LEA-Excel (.xlsx), baut LOGINEO-Importtabelle und schreibt (abhängig von
    der Einstellung) eine Ausgabe-Datei (.csv oder .xlsx) sowie optional eine
    Fehlerliste als Excel-Datei.
    """

    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.now = datetime.now()
        self.dt_string = self.now.strftime("%Y-%m-%d_%H-%M-%S")
        # Ausgabeordner aus den Einstellungen (Default: "output")
        self.output_dir = resolve_path(self.s.lea_outputpath or "output")
        ensure_dir(self.output_dir)

    def _ok_columns(self) -> List[str]:
        """
        Spalten, die wirklich ausgegeben werden sollen – dynamisch gemäß config.
        """
        cols = ["LEAID", "IdentNr", "Nachname", "Vorname", "Typ"]
        if self.s.lea_gruppe_laa_lehramt == "ja":
            cols += ["Seminar", "Lehramt"]
        if self.s.lea_gruppe_laa_lehramt_jg == "ja":
            cols += ["Jahrgang"]
        if self.s.lea_gruppe_laa_seminare == "ja":
            cols += ["Kernseminar", "Fachseminar_1", "Fachseminar_2"]
        return cols

    def _output_format(self) -> str:
        fmt = getattr(self.s, "lea_output_format", "csv") or "csv"
        fmt = fmt.strip().lower()
        return fmt if fmt in {"csv", "xlsx"} else "csv"

    def convert(self) -> None:
        print("\nIhre LEA-Excel-Datei wird nun eingelesen.\n")

        lea_path = resolve_path(self.s.lea_xlsx_file)
        if not os.path.isfile(lea_path):
            print("FEHLER!")
            print(f"Die LEA-Datei ({lea_path}) wurde nicht gefunden.")
            pause("\nDrücken Sie eine beliebige Taste, um zu bestätigen und den Prozess zu beenden.")
            raise FileNotFoundError(lea_path)

        if not lea_path.lower().endswith((".xls", ".xlsx")):
            print("FEHLER! Die Datei hat kein zulässiges Dateiformat. zulässig sind: .xls / .xlsx")
            pause()
            raise ValueError("Ungültiges Dateiformat")

        df_src = pd.read_excel(lea_path, dtype=str)
        df_src.fillna("", inplace=True)

        rows_ok: List[Dict[str, Any]] = []
        rows_err: List[Dict[str, Any]] = []

        primary = self.s.lea_primary_key  # "LEAID" oder "IdentNr"

        for _, src in df_src.iterrows():
            try:
                if primary == "IdentNr":
                    ident = _read_str(src, "LAA_IdentNr")
                    if ident and len(ident) > 9:
                        rows_ok.append(OutputRow.from_source(src, self.s).to_dict())
                    else:
                        rows_err.append(FailRow.from_source(src).to_dict())

                elif primary == "LEAID":
                    leaid_raw = _read_str(src, "LAA_Logineo")
                    if leaid_raw != "":
                        rows_ok.append(OutputRow.from_source(src, self.s).to_dict())
                    else:
                        rows_err.append(FailRow.from_source(src).to_dict())
                else:
                    raise ValueError("lea_primary_key muss 'LEAID' oder 'IdentNr' sein.")

            except Exception as e:
                print("\nFEHLER - FEHLER - FEHLER (#convert).")
                print("Bei der Ausführung ist etwas schiefgelaufen.")
                print("Überprüfen Sie die Einstellungen (config.xml) und die Quell-Datei.")
                print(f"Details: {e}")
                pause("\nDrücken Sie eine beliebige Taste, um das Programm zu beenden.")
                raise

        # >>> HIER: Spalten dynamisch wählen – nur aktivierte Spalten erscheinen im Output
        ok_cols = self._ok_columns()

        # DataFrames bauen
        df_ok = pd.DataFrame(rows_ok, columns=ok_cols)
        df_err = pd.DataFrame(rows_err, columns=["LEAID", "IdentNr", "Nachname", "Vorname", "Typ", "Lehramt"])

        # Sicherstellen, dass ID-Spalten wirklich als Text exportiert werden
        for target in (df_ok, df_err):
            for col in ("LEAID", "IdentNr"):
                if col in target.columns:
                    target[col] = target[col].apply(
                        lambda v: "" if (v is None or pd.isna(v)) else str(v)
                    )

        if not df_err.empty:
            print("\nEinige importierte Zeilen weisen Probleme auf (siehe unten):")
            print(df_err)
            err_name = f"{self.dt_string}_Referendare_FEHLER.xlsx"
            df_err.to_excel(os.path.join(self.output_dir, err_name), sheet_name="Referendare-FEHLER", index=False)
            print(f"\nEs wurde eine Excel-Datei mit der Fehlerliste im Ordner '{self.output_dir}' erstellt.")
            pause("\nWenn Sie die Fehler ignorieren möchten, Drücken Sie eine beliebige Taste, um fortzufahren. "
                  "Wenn nicht, Drücken Sie Strg+C, um abzubrechen.")

        if not df_ok.empty:
            print("\nHier eine Übersicht der finalen Tabellen-Struktur und der anzulegenden Nutzer:\n")
            print(df_ok)

            pause("\nÜberprüfen Sie die Daten. Wenn alles gut aussieht, Drücken Sie eine beliebige Taste, um fortzufahren.")
            out_name_xlsx = f"{self.dt_string}_referendare.xlsx"
            out_name_csv = f"{self.dt_string}_referendare.csv"
            out_path_xlsx = os.path.join(self.output_dir, out_name_xlsx)
            out_path_csv = os.path.join(self.output_dir, out_name_csv)

            output_format = self._output_format()
            created_desc: List[str] = []
            if output_format == "xlsx":
                df_ok.to_excel(out_path_xlsx, sheet_name="Referendare", index=False)
                created_desc.append(f"- {out_name_xlsx}")
            else:
                df_ok.to_csv(out_path_csv, index=False, encoding="utf-8-sig", lineterminator="\n")
                created_desc.append(f"- {out_name_csv} (UTF-8-BOM, Zeilenende LF)")

            print(f"\nDie Datei wurde im Ordner '{self.output_dir}' angelegt:")
            for desc in created_desc:
                print(desc)
            print("Sie können diese Dateien nun in der Nutzerverwaltung LOGINEO NRW importieren.")
            print(f"Ergebnisse wurden im Output-Ordner abgelegt: '{self.output_dir}'.")
            pause("\nDrücken Sie eine beliebige Taste, um das Programm zu beenden.")
            return
        else:
            print("\nIhre Tabelle enthält keine gültigen Werte. Der Prozess wird abgebrochen.")
            pause()
            return





