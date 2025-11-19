#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import sys
import threading
import traceback
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont
from tkinter.scrolledtext import ScrolledText

from .io_utils import appdir, resolve_path, ensure_dir
import pandas as pd
from .settings import load_settings, Settings, save_settings
from .converter import LEAConverter
from .pdf_generator import PDFGenerator


class _TextStream:
    """A lightweight stream wrapper that pushes text to a queue for GUI consumption."""

    def __init__(self, q: "queue.Queue[str]") -> None:
        self._q = q

    def write(self, s: str) -> int:
        if s:
            self._q.put(s)
        return len(s)

    def flush(self) -> None:  # pragma: no cover - noop
        pass


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("LEA-LOGINEO-Tool – GUI")
        self._configure_fonts()

        # Load settings from config.xml
        try:
            self.settings = load_settings(os.path.join(appdir, "config.xml"))
        except Exception as e:
            messagebox.showerror(
                "Konfiguration",
                (
                    "config.xml konnte nicht geladen werden.\n\n"
                    "Bitte stellen Sie sicher, dass sich die Programmdatei "
                    "(LEA-LOGINEO-Tool) und die config.xml im selben Ordner befinden.\n"
                    f"Gesuchter Pfad: {os.path.join(appdir, 'config.xml')}\n\n"
                    f"Details: {e}"
                ),
            )
            self.settings = Settings(
                lea_xlsx_file="",
                lea_primary_key="LEAID",
                lea_gruppe_laa_lehramt="ja",
                lea_gruppe_laa_lehramt_jg="ja",
                lea_gruppe_laa_seminare="ja",
                lea_outputpath="output",
                lea_output_format="csv",
                logineo_csv_file="",
                logineo_xml_file="",
                logineo_csv_delimiter=",",
                pdf_outputpath="pdf-files",
                pdf_logineolink="",
                pdf_supportname="",
                pdf_supportmail="",
                pdf_einzeln="ja",
                pdf_lehramt="nein",
            )
        # Ensure output directories exist at startup
        self._ensure_output_dirs()

        # UI State
        self._running = False
        self._log_q: "queue.Queue[str]" = queue.Queue()

        self._build_ui()
        self._set_initial_geometry()
        self.after(50, self._drain_log_queue)

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
        padx = 10
        pady = 8

        # Header (ohne globalen Einstellungen-Button)
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=10, pady=6)

        # Tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=padx, pady=pady)

        # Small color swatches for tabs (for subtle color hints)
        def _mk_swatch(color: str) -> tk.PhotoImage:
            img = tk.PhotoImage(width=10, height=10)
            img.put(color, to=(0, 0, 10, 10))
            return img
        self._img_start = _mk_swatch("#e8e8e8")
        self._img_lea = _mk_swatch("#6aa9ff")
        self._img_log = _mk_swatch("#5cc98a")
        self._img_info = _mk_swatch("#d7d7d7")

        # Subtle color accents for better separation
        lea_bg = "#eef6ff"   # light blue tint
        log_bg = "#eefaf2"   # light green tint

        # LEA Tab
        # Start Tab (first)
        start_tab = ttk.Frame(notebook)
        notebook.add(start_tab, text="Start", image=self._img_start, compound="left")

        start_text = ScrolledText(start_tab, wrap=tk.WORD, height=14)
        start_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        start_text.insert(tk.END, (
            "Willkommen im LEA-LOGINEO-Tool für ZfsL!\n\n"
            "Dieses Programm hat zwei Bereiche:\n"
            "1) LEA → LOGINEO: Das Programm wandelt eine im Verwaltungsprogramm LEA per Seriendruck-Funktion erzeugte Excel-Datei in eine in LOGINEO NRW importierbare Datei um.\n"
            "   Es werden automatisch Gruppen generiert (LAA, LAA_Lehramt, Lehramt_Seminar), die in LOGINEO verwendet weden können.\n\n"
            "2) LOGINEO PDF-Generator: Das Programm erzeugt aus einer LOGINEO-Ausgabedatei (Excel oder CSV) personenbezogene PDF Dateien mit den Zugangsdaten.\n"
            "   Es besteht die Möglichkeit, alle Zugangsdaten in einer PDF-Datei auszugeben oder für jede Person einzeln.\n\n"
            "So gehen Sie vor:\n"
            "- Prüfen Sie im jeweiligen Tab zuerst die Einstellungen.\n"
            "- Wählen Sie die passende Quelldatei aus (LEA-Excel oder LOGINEO-CSV/XLS).\n"
            "- Starten Sie die Aktion und öffnen Sie danach den jeweiligen Ausgabe-Ordner.\n\n"
            "Tipps:\n"
            "- Bei LEA ist ‘LEAID’ in der Regel die beste Wahl als Kennung.\n"
            "- Achten Sie bei CSV auf das richtige Trennzeichen (meist ,).\n"
            "- Ihre Ausgabe-Ordner können Sie in den Einstellungen anpassen.\n"
        ))
        start_text.configure(state=tk.DISABLED)

        lea_tab = tk.Frame(notebook, bg=lea_bg)
        notebook.add(lea_tab, text="LEA → LOGINEO", image=self._img_lea, compound="left")
        lea_head = tk.Frame(lea_tab, bg=lea_bg)
        lea_head.pack(fill=tk.X, padx=6, pady=(6, 6))
        lbl_lea_desc = tk.Label(
            lea_head,
            text="Konvertiert eine LEA-Excel-Datei in eine LOGINEO-Importtabelle (XLSX) mit optionalen Gruppen.",
            bg=lea_bg,
            fg="#444",
            wraplength=820,
            anchor="w",
            justify=tk.LEFT,
        )
        lbl_lea_desc.pack(anchor=tk.W, padx=2, pady=(0, 4))
        lea_head_row = tk.Frame(lea_head, bg=lea_bg)
        lea_head_row.pack(fill=tk.X)
        ttk.Button(lea_head_row, text="Einstellungen (LEA)", command=self._open_settings_lea).pack(side=tk.LEFT)
        tk.Label(lea_head_row, text="Hinweis: Bitte vor dem Ausführen die LEA-Einstellungen prüfen und ggf. anpassen.", bg=lea_bg, fg="#555").pack(side=tk.LEFT, padx=(8, 0))

        lea_frame = tk.Frame(lea_tab, bg=lea_bg)
        lea_frame.pack(fill=tk.X, padx=6, pady=6)
        tk.Label(lea_frame, text="LEA-Excel (.xlsx):", bg=lea_bg).grid(row=0, column=0, sticky=tk.W)
        self.var_lea = tk.StringVar(value=self._resolved(self.settings.lea_xlsx_file))
        ttk.Entry(lea_frame, textvariable=self.var_lea, width=80).grid(row=0, column=1, sticky=tk.W)
        ttk.Button(lea_frame, text="Durchsuchen…", command=self._pick_lea).grid(row=0, column=2, padx=6)
        self.btn_run_lea = ttk.Button(lea_frame, text="Konvertiere LEA → LOGINEO", command=self._run_convert)
        self.btn_run_lea.grid(row=0, column=3, padx=6)

        lea_actions = tk.Frame(lea_tab, bg=lea_bg)
        lea_actions.pack(fill=tk.X, padx=6, pady=(0, 6))
        ttk.Button(lea_actions, text="LEA-Output öffnen", command=self._open_output).pack(side=tk.LEFT)

        # LOGINEO Tab
        log_tab = tk.Frame(notebook, bg=log_bg)
        notebook.add(log_tab, text="LOGINEO PDF-Generator", image=self._img_log, compound="left")
        log_head = tk.Frame(log_tab, bg=log_bg)
        log_head.pack(fill=tk.X, padx=6, pady=(6, 6))
        lbl_log_desc = tk.Label(
            log_head,
            text="Erzeugt personalisierte Zugangsdaten-PDFs aus LOGINEO CSV/XLS. Ausgabe nach Lehramt/Seminar konfigurierbar.",
            bg=log_bg,
            fg="#444",
            wraplength=820,
            anchor="w",
            justify=tk.LEFT,
        )
        lbl_log_desc.pack(anchor=tk.W, padx=2, pady=(0, 4))
        log_head_row = tk.Frame(log_head, bg=log_bg)
        log_head_row.pack(fill=tk.X)
        ttk.Button(log_head_row, text="Einstellungen (LOGINEO)", command=self._open_settings_logineo).pack(side=tk.LEFT)
        tk.Label(log_head_row, text="Hinweis: Bitte vor dem Ausführen die LOGINEO-Einstellungen prüfen und ggf. anpassen.", bg=log_bg, fg="#555").pack(side=tk.LEFT, padx=(8, 0))

        pdf_frame = tk.Frame(log_tab, bg=log_bg)
        pdf_frame.pack(fill=tk.X, padx=6, pady=6)
        tk.Label(pdf_frame, text="LOGINEO CSV oder XLS (.csv/.xls):", bg=log_bg).grid(row=0, column=0, sticky=tk.W)
        initial_logineo = getattr(self.settings, "logineo_xml_file", "") or self.settings.logineo_csv_file
        self.var_logineo = tk.StringVar(value=self._resolved(initial_logineo))
        ttk.Entry(pdf_frame, textvariable=self.var_logineo, width=80).grid(row=0, column=1, sticky=tk.W)
        ttk.Button(pdf_frame, text="Durchsuchen…", command=self._pick_logineo).grid(row=0, column=2, padx=6)
        self.btn_run_pdf = ttk.Button(pdf_frame, text="PDFs erzeugen", command=self._run_pdf)
        self.btn_run_pdf.grid(row=0, column=3, padx=6)

        pdf_actions = tk.Frame(log_tab, bg=log_bg)
        pdf_actions.pack(fill=tk.X, padx=6, pady=6)
        ttk.Button(pdf_actions, text="LOGINEO-Output öffnen", command=self._open_logineo_output).pack(side=tk.LEFT)

        # Info Tab (rechts)
        info_tab = ttk.Frame(notebook)
        notebook.add(info_tab, text="Info", image=self._img_info, compound="left")
        info_text = ScrolledText(info_tab, wrap=tk.WORD, height=14)
        info_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        info_content = (
            "Inoffizielles LEA-LOGINEO NRW Tool\n\n"
            "Erstellt durch:\n"
            "Johannes Schirge\n"
            "ZfsL Bielefeld\n"
            "johannes.schirge@zfsl-bielefeld.nrw.schule\n\n"
            "Hinweis:\n"
            "Dieses Programm wird OHNE JEGLICHE GARANTIE bereitgestellt. Eine Nutzung erfolgt auf eigene Verantwortung.\n"
            "Dies ist freie Software; Sie dürfen sie unter bestimmten Bedingungen weiterverbreiten.\n"
            "Einzelheiten finden Sie in der Datei LICENSE (GNU GPLv3).\n\n"
            "Rechtlicher Hinweis:\n"
            "Alle genannten Produktnamen, Logos und Marken sind Eigentum der jeweiligen Rechteinhaber.\n"
            "Die Verwendung dient ausschließlich der Identifikation und impliziert keine Verbindung, Unterstützung oder Billigung durch die Rechteinhaber."
        )
        info_text.insert(tk.END, info_content)
        info_text.configure(state=tk.DISABLED)

        # Select Start tab initially
        notebook.select(start_tab)

        # Keyboard shortcuts
        self.bind_all("<Alt-l>", lambda e: self._open_settings_lea())
        self.bind_all("<Alt-L>", lambda e: self._open_settings_lea())
        self.bind_all("<Alt-g>", lambda e: self._open_settings_logineo())
        self.bind_all("<Alt-G>", lambda e: self._open_settings_logineo())
        self.bind_all("<F1>", lambda e: notebook.select(start_tab))
        # Dynamically adapt description wrap to available width
        def _adapt_wrap_lea(event=None):
            try:
                lbl_lea_desc.configure(wraplength=max(300, lea_tab.winfo_width() - 40))
            except Exception:
                pass
        def _adapt_wrap_log(event=None):
            try:
                lbl_log_desc.configure(wraplength=max(300, log_tab.winfo_width() - 40))
            except Exception:
                pass
        lea_tab.bind("<Configure>", _adapt_wrap_lea)
        log_tab.bind("<Configure>", _adapt_wrap_log)

        # Log
        frm_log = ttk.LabelFrame(self, text="Protokoll")
        frm_log.pack(fill=tk.BOTH, expand=True, padx=padx, pady=pady)
        self.txt = tk.Text(frm_log, wrap=tk.WORD, state=tk.DISABLED)
        self.txt.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        sb = ttk.Scrollbar(frm_log, orient=tk.VERTICAL, command=self.txt.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt.configure(yscrollcommand=sb.set)

        # Statusbar
        status_frame = ttk.Frame(self)
        status_frame.pack(fill=tk.X, padx=10, pady=(0, 8))
        self.status_var = tk.StringVar(value="Bereit")
        self.status_lbl = ttk.Label(status_frame, textvariable=self.status_var, foreground="#555")
        self.status_lbl.pack(anchor=tk.W)

    def _resolved(self, p: str) -> str:
        if not p:
            return ""
        try:
            return resolve_path(p)
        except Exception:
            return p

    # ---------------- Actions ----------------
    def _pick_lea(self) -> None:
        fn = filedialog.askopenfilename(
            title="LEA-Excel auswählen",
            filetypes=[("Excel", "*.xlsx;*.xls"), ("Alle Dateien", "*.*")],
            initialdir=os.path.dirname(self.var_lea.get() or appdir),
        )
        if fn:
            self.var_lea.set(fn)

    def _pick_logineo(self) -> None:
        fn = filedialog.askopenfilename(
            title="LOGINEO-CSV oder -XLS auswählen",
            filetypes=[
                ("XLS", "*.xls;*.xlsx"),  # Standard zuerst
                ("CSV", "*.csv"),
                ("Alle Dateien", "*.*"),
            ],
            initialdir=os.path.dirname(self.var_logineo.get() or appdir),
        )
        if fn:
            self.var_logineo.set(fn)

    def _open_output(self) -> None:
        path = resolve_path(self.settings.lea_outputpath or "output")
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f"open '{path}'")
            else:
                os.system(f"xdg-open '{path}'")
        except Exception as e:
            messagebox.showerror("Öffnen fehlgeschlagen", str(e))

    def _open_settings(self) -> None:
        SettingsDialog(self, self.settings, on_save=self._apply_and_save_settings)

    def _open_settings_lea(self) -> None:
        SettingsDialog(self, self.settings, on_save=self._apply_and_save_settings, section="lea")

    def _open_settings_logineo(self) -> None:
        SettingsDialog(self, self.settings, on_save=self._apply_and_save_settings, section="logineo")

    def _open_logineo_output(self) -> None:
        path = resolve_path(self.settings.pdf_outputpath or "pdf-files")
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f"open '{path}'")
            else:
                os.system(f"xdg-open '{path}'")
        except Exception as e:
            messagebox.showerror("Öffnen fehlgeschlagen", str(e))

    def _apply_and_save_settings(self, new_settings: Settings) -> None:
        # Update state in app
        self.settings = new_settings
        # Ensure directories exist for updated settings
        self._ensure_output_dirs()
        # Reflect into entry fields
        self.var_lea.set(self._resolved(self.settings.lea_xlsx_file))
        initial_logineo = getattr(self.settings, "logineo_xml_file", "") or self.settings.logineo_csv_file
        self.var_logineo.set(self._resolved(initial_logineo))
        # Persist to config.xml
        try:
            cfg_path = os.path.join(appdir, "config.xml")
            save_settings(cfg_path, self.settings)
            messagebox.showinfo("Einstellungen", "Einstellungen wurden gespeichert.")
        except Exception as e:
            messagebox.showerror("Einstellungen", f"Konnte config.xml nicht speichern.\n\n{e}")

    def _ensure_output_dirs(self) -> None:
        try:
            lea_dir = resolve_path(self.settings.lea_outputpath or "output")
            pdf_dir = resolve_path(self.settings.pdf_outputpath or "pdf-files")
            ensure_dir(lea_dir)
            ensure_dir(pdf_dir)
        except Exception:
            # Do not block startup on directory errors; open buttons will still error if misconfigured
            pass

    def _set_running(self, running: bool) -> None:
        self._running = running
        state = tk.DISABLED if running else tk.NORMAL
        self.btn_run_lea.configure(state=state)
        self.btn_run_pdf.configure(state=state)
        self.status_var.set("Arbeitet…" if running else "Bereit")

    def _configure_fonts(self) -> None:
        # Increase default fonts for better readability
        try:
            for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkFixedFont"):
                f = tkfont.nametofont(name)
                # Prefer Segoe UI on Windows; falls nicht vorhanden, nimmt Tk den nächsten passenden Font
                f.configure(family="Segoe UI", size=11)
        except Exception:
            pass

    def _set_initial_geometry(self) -> None:
        # Compute an initial size responsive to content and screen
        try:
            self.update_idletasks()
            req_w = self.winfo_reqwidth()
            req_h = self.winfo_reqheight()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            # Target between 60% and 90% of screen, but not smaller than requested
            target_w = min(max(req_w, int(sw * 0.6)), int(sw * 0.9))
            target_h = min(max(req_h, int(sh * 0.6)), int(sh * 0.9))
            # Center on screen
            x = (sw - target_w) // 2
            y = max(20, (sh - target_h) // 4)
            self.geometry(f"{target_w}x{target_h}+{x}+{y}")
            # Set a reasonable minimum so things don't collapse
            self.minsize(int(sw * 0.5), int(sh * 0.5))
        except Exception:
            pass

    def _run_convert(self) -> None:
        if self._running:
            return
        xlsx = self.var_lea.get().strip()
        if not xlsx:
            messagebox.showwarning("Eingabe fehlt", "Bitte eine LEA-Excel-Datei auswählen.")
            return
        s = self.settings
        s.lea_xlsx_file = xlsx
        self._launch_thread(self._task_convert, s)

    def _run_pdf(self) -> None:
        if self._running:
            return
        # Einheitliche Pfadlogik über ein gemeinsames Feld
        path = (self.var_logineo.get() or "").strip()
        if not path:
            messagebox.showwarning("Eingabe fehlt", "Bitte eine LOGINEO-CSV- oder XLS-Datei auswählen.")
            return
        ext = os.path.splitext(path)[1].lower()
        s = self.settings
        if ext == ".csv":
            s.logineo_csv_file = path
            s.logineo_xml_file = ""
            self._launch_thread(self._task_pdf_csv, s)
        elif ext in (".xls", ".xlsx"):
            try:
                csv_path = self._convert_xls_to_csv(path, delimiter=s.logineo_csv_delimiter or ",")
            except Exception as e:
                messagebox.showerror("Konvertierung fehlgeschlagen", f"XLS/XLSX konnte nicht gelesen werden.\n\n{e}")
                return
            s.logineo_csv_file = csv_path
            s.logineo_xml_file = ""
            self._launch_thread(self._task_pdf_csv, s)
        else:
            messagebox.showwarning("Falsches Format", "Unterstützt werden .csv oder .xls/.xlsx.")

    def _convert_xls_to_csv(self, xls_path: str, *, delimiter: str = ",") -> str:
        """Konvertiert eine XLS/XLSX nach CSV im tmp-Ordner und liefert den Pfad zurück."""
        df = pd.read_excel(xls_path, dtype=str)
        df.fillna("", inplace=True)
        tmp_dir = resolve_path("tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        base = os.path.splitext(os.path.basename(xls_path))[0]
        csv_path = os.path.join(tmp_dir, f"{base}.csv")
        df.to_csv(csv_path, index=False, encoding="utf-8", sep=delimiter)
        return csv_path

    # ---------------- Background execution ----------------
    def _launch_thread(self, fn, s: Settings) -> None:
        self._set_running(True)
        self._println("Starte…\n")

        t = threading.Thread(target=self._run_captured, args=(fn, s), daemon=True)
        t.start()

    def _run_captured(self, fn, s: Settings) -> None:
        # Redirect stdout/stderr temporarily to GUI
        old_out, old_err = sys.stdout, sys.stderr
        stream = _TextStream(self._log_q)
        sys.stdout = stream
        sys.stderr = stream
        old_env = os.environ.get("NONINTERACTIVE")
        os.environ["NONINTERACTIVE"] = "1"
        try:
            fn(s)
        except Exception:
            traceback.print_exc()
        finally:
            # restore
            if old_env is None:
                os.environ.pop("NONINTERACTIVE", None)
            else:
                os.environ["NONINTERACTIVE"] = old_env
            sys.stdout = old_out
            sys.stderr = old_err
            self._set_running(False)
            self._println("\nFertig.\n")

    def _task_convert(self, s: Settings) -> None:
        LEAConverter(s).convert()

    def _task_pdf_csv(self, s: Settings) -> None:
        PDFGenerator(s).generate()

    def _task_pdf_xml(self, s: Settings) -> None:
        PDFGenerator(s).generate_from_xml()

    # ---------------- Logging ----------------
    def _println(self, text: str) -> None:
        self._log_q.put(text)

    def _drain_log_queue(self) -> None:
        try:
            while True:
                chunk = self._log_q.get_nowait()
                self._append_text(chunk)
        except queue.Empty:
            pass
        self.after(80, self._drain_log_queue)

    def _append_text(self, s: str) -> None:
        self.txt.configure(state=tk.NORMAL)
        self.txt.insert(tk.END, s)
        self.txt.see(tk.END)
        self.txt.configure(state=tk.DISABLED)


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: App, settings: Settings, on_save, section: str | None = None) -> None:
        super().__init__(parent)
        self.title("Einstellungen")
        self.transient(parent)
        self.grab_set()
        self.resizable(True, True)

        self._parent = parent
        self._orig = settings
        self._on_save = on_save
        self._section = (section or "all").lower()

        def yesno_to_bool(v: str) -> bool:
            return (v or "").strip().lower() == "ja"

        # Variables
        self.var_primary = tk.StringVar(value=settings.lea_primary_key or "LEAID")
        self.var_laa_lehramt = tk.BooleanVar(value=yesno_to_bool(settings.lea_gruppe_laa_lehramt))
        self.var_laa_jg = tk.BooleanVar(value=yesno_to_bool(settings.lea_gruppe_laa_lehramt_jg))
        self.var_laa_seminare = tk.BooleanVar(value=yesno_to_bool(settings.lea_gruppe_laa_seminare))
        self.var_lea_out = tk.StringVar(value=settings.lea_outputpath or "output")
        self._lea_format_options = [
            ("csv", "CSV"),
            ("xlsx", "XLSX (nicht empfohlen)"),
        ]
        self._lea_format_label_by_value = {value: label for value, label in self._lea_format_options}
        self._lea_format_value_by_label = {label: value for value, label in self._lea_format_options}
        fmt_value = (settings.lea_output_format or "csv").strip().lower()
        default_label = self._lea_format_label_by_value.get(fmt_value, self._lea_format_label_by_value.get("csv", "CSV"))
        self.var_lea_format = tk.StringVar(value=default_label)

        self.var_csv_delim = tk.StringVar(value=settings.logineo_csv_delimiter or ",")
        self.var_pdf_out = tk.StringVar(value=settings.pdf_outputpath or "pdf-files")
        self.var_logineo_link = tk.StringVar(value=settings.pdf_logineolink)
        self.var_support_name = tk.StringVar(value=settings.pdf_supportname)
        self.var_support_mail = tk.StringVar(value=settings.pdf_supportmail)
        self.var_pdf_einzeln = tk.BooleanVar(value=yesno_to_bool(settings.pdf_einzeln))
        self.var_pdf_lehramt = tk.BooleanVar(value=yesno_to_bool(settings.pdf_lehramt))

        # XML mapping settings are no longer managed via GUI

        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # LEA
        if self._section in ("lea", "all"):
            frm_lea = ttk.LabelFrame(body, text="LEA")
            frm_lea.pack(fill=tk.X, padx=4, pady=6)
            ttk.Label(frm_lea, text="Primärschlüssel:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
            cmb = ttk.Combobox(frm_lea, textvariable=self.var_primary, values=["LEAID", "IdentNr"], state="readonly", width=12)
            cmb.grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)
            ttk.Checkbutton(frm_lea, text="Gruppe LAA_LEHRAMT", variable=self.var_laa_lehramt).grid(row=1, column=0, columnspan=2, sticky=tk.W, padx=4, pady=2)
            ttk.Checkbutton(frm_lea, text="Gruppe LAA_LEHRAMT_JG", variable=self.var_laa_jg).grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=4, pady=2)
            ttk.Checkbutton(frm_lea, text="Seminar-Gruppen", variable=self.var_laa_seminare).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=4, pady=2)
            ttk.Label(frm_lea, text="LEA-Ausgabeordner:").grid(row=4, column=0, sticky=tk.W, padx=4, pady=4)
            ttk.Entry(frm_lea, textvariable=self.var_lea_out, width=50).grid(row=4, column=1, sticky=tk.W, padx=4, pady=4)
            ttk.Button(frm_lea, text="…", width=3, command=self._pick_lea_outdir).grid(row=4, column=2, padx=4, pady=4)
            ttk.Label(frm_lea, text="Ausgabeformat:").grid(row=5, column=0, sticky=tk.W, padx=4, pady=4)
            ttk.Combobox(
                frm_lea,
                textvariable=self.var_lea_format,
                values=[label for _, label in self._lea_format_options],
                state="readonly",
                width=28,
            ).grid(row=5, column=1, sticky=tk.W, padx=4, pady=4)
            ttk.Label(frm_lea, text="Hinweis: Die LEA-Excel-Datei wird im Hauptfenster gewaehlt.", foreground="#555").grid(row=6, column=0, columnspan=3, sticky=tk.W, padx=4, pady=(2, 2))

        # LOGINEO Optionen
        if self._section in ("logineo", "all"):
            frm_log = ttk.LabelFrame(body, text="LOGINEO Optionen")
            frm_log.pack(fill=tk.X, padx=4, pady=6)
            ttk.Label(frm_log, text="CSV-Trennzeichen:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
            ttk.Entry(frm_log, textvariable=self.var_csv_delim, width=8).grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)
            ttk.Label(frm_log, text="Hinweis: LOGINEO CSV/XML-Dateien werden im Hauptfenster gewählt.", foreground="#555").grid(row=1, column=0, columnspan=3, sticky=tk.W, padx=4, pady=(2, 4))

        # PDF & Support
        if self._section in ("logineo", "all"):
            frm_pdf = ttk.LabelFrame(body, text="PDF & Support")
            frm_pdf.pack(fill=tk.X, padx=4, pady=6)
            ttk.Label(frm_pdf, text="PDF-Ausgabeordner:").grid(row=0, column=0, sticky=tk.W, padx=4, pady=4)
            ttk.Entry(frm_pdf, textvariable=self.var_pdf_out, width=50).grid(row=0, column=1, sticky=tk.W, padx=4, pady=4)
            ttk.Button(frm_pdf, text="…", width=3, command=self._pick_pdf_outdir).grid(row=0, column=2, padx=4, pady=4)
            ttk.Label(frm_pdf, text="LOGINEO-Domain:").grid(row=1, column=0, sticky=tk.W, padx=4, pady=4)
            ttk.Entry(frm_pdf, textvariable=self.var_logineo_link, width=50).grid(row=1, column=1, sticky=tk.W, padx=4, pady=4)
            ttk.Label(frm_pdf, text="Support-Name:").grid(row=2, column=0, sticky=tk.W, padx=4, pady=4)
            ttk.Entry(frm_pdf, textvariable=self.var_support_name, width=50).grid(row=2, column=1, sticky=tk.W, padx=4, pady=4)
            ttk.Label(frm_pdf, text="Support-Mail:").grid(row=3, column=0, sticky=tk.W, padx=4, pady=4)
            ttk.Entry(frm_pdf, textvariable=self.var_support_mail, width=50).grid(row=3, column=1, sticky=tk.W, padx=4, pady=4)
            ttk.Checkbutton(frm_pdf, text="Einzel-PDFs", variable=self.var_pdf_einzeln).grid(row=4, column=0, sticky=tk.W, padx=4, pady=2)
            ttk.Checkbutton(frm_pdf, text="PDF pro Lehramt", variable=self.var_pdf_lehramt).grid(row=4, column=1, sticky=tk.W, padx=4, pady=2)
            ttk.Label(frm_pdf, text="Hinweis: Der PDF-Ausgabeordner kann oben gesetzt werden.", foreground="#555").grid(row=5, column=0, columnspan=3, sticky=tk.W, padx=4, pady=(2, 4))

        # XML mapping section removed from GUI

        # Buttons
        frm_btn = ttk.Frame(self)
        frm_btn.pack(fill=tk.X, padx=10, pady=10)
        ttk.Button(frm_btn, text="Abbrechen", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(frm_btn, text="Speichern", command=self._save).pack(side=tk.RIGHT, padx=8)

        self.bind("<Escape>", lambda e: self.destroy())

    def _save(self) -> None:
        def yn(b: bool) -> str:
            return "ja" if b else "nein"
        fmt_label = self.var_lea_format.get()
        lea_output_format = self._lea_format_value_by_label.get(fmt_label, "csv")

        s = Settings(
            # LEA (Pfade bleiben unverändert, nur Optionen übernehmen)
            lea_xlsx_file=self._orig.lea_xlsx_file,
            lea_primary_key=(self.var_primary.get().strip() or "LEAID"),
            lea_gruppe_laa_lehramt=yn(self.var_laa_lehramt.get()),
            lea_gruppe_laa_lehramt_jg=yn(self.var_laa_jg.get()),
            lea_gruppe_laa_seminare=yn(self.var_laa_seminare.get()),
            lea_outputpath=self.var_lea_out.get().strip() or "output",
            lea_output_format=lea_output_format,
            # LOGINEO & PDF
            logineo_csv_file=self._orig.logineo_csv_file,
            logineo_xml_file=self._orig.logineo_xml_file,
            logineo_csv_delimiter=(self.var_csv_delim.get() or ","),
            pdf_outputpath=self.var_pdf_out.get().strip() or "pdf-files",
            pdf_logineolink=self.var_logineo_link.get().strip(),
            pdf_supportname=self.var_support_name.get().strip(),
            pdf_supportmail=self.var_support_mail.get().strip(),
            pdf_einzeln=yn(self.var_pdf_einzeln.get()),
            pdf_lehramt=yn(self.var_pdf_lehramt.get()),
            # Preserve existing XML mapping from original settings
            logineo_xml_user_tag=self._orig.logineo_xml_user_tag,
            logineo_xml_tag_lastname=self._orig.logineo_xml_tag_lastname,
            logineo_xml_tag_firstname=self._orig.logineo_xml_tag_firstname,
            logineo_xml_tag_email=self._orig.logineo_xml_tag_email,
            logineo_xml_tag_password=self._orig.logineo_xml_tag_password,
            logineo_xml_tag_safe_password=self._orig.logineo_xml_tag_safe_password,
            logineo_xml_tag_system=self._orig.logineo_xml_tag_system,
            logineo_xml_tag_group=self._orig.logineo_xml_tag_group,
        )
        try:
            self._on_save(s)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Einstellungen", str(e))

    def _pick_lea_outdir(self) -> None:
        d = filedialog.askdirectory(title="LEA-Ausgabeordner wählen", initialdir=os.path.dirname(self._orig.lea_outputpath or appdir))
        if d:
            self.var_lea_out.set(d)

    def _pick_pdf_outdir(self) -> None:
        d = filedialog.askdirectory(title="PDF-Ausgabeordner wählen", initialdir=os.path.dirname(self._orig.pdf_outputpath or appdir))
        if d:
            self.var_pdf_out.set(d)


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
