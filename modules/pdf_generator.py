from __future__ import annotations

import csv
import os
import time
from datetime import datetime
from typing import Dict, List, Tuple, Callable
import xml.etree.ElementTree as ET

from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .io_utils import resolve_path, ensure_dir, pause
from .settings import Settings
from xml.sax.saxutils import escape as xml_escape


def _register_unicode_font() -> str:
    candidates = [
        os.path.join(os.environ.get("WINDIR", r"C:\\Windows"), "Fonts", "arial.ttf"),
        os.path.join(os.environ.get("WINDIR", r"C:\\Windows"), "Fonts", "Calibri.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    font_name = "AppUnicode"
    for path in candidates:
        try:
            if path and os.path.isfile(path):
                pdfmetrics.registerFont(TTFont(font_name, path))
                return font_name
        except Exception:
            continue
    return "Helvetica"


def _make_styles(font_name: str):
    styles = getSampleStyleSheet()
    for key in ("Normal", "BodyText", "Title", "Heading1", "Heading2", "Heading3"):
        if key in styles.byName:
            styles.byName[key].fontName = font_name
    if "Justify" not in styles.byName:
        styles.add(ParagraphStyle(name="Justify", alignment=TA_JUSTIFY, fontName=font_name))
    return styles


class PDFGenerator:
    def __init__(self, settings: Settings) -> None:
        self.s = settings
        self.output_dir = resolve_path(self.s.pdf_outputpath)
        ensure_dir(self.output_dir)
        self.tmp_dir = resolve_path("tmp")
        ensure_dir(self.tmp_dir)

        self._font_name = _register_unicode_font()
        self.styles = _make_styles(self._font_name)

    # ---------------- Public API ----------------
    def generate(self) -> None:
        csv_path = resolve_path(self.s.logineo_csv_file)
        if not os.path.isfile(csv_path):
            print("FEHLER!")
            print(f"Die CSV-Datei ({csv_path}) wurde nicht gefunden.")
            pause()
            raise FileNotFoundError(csv_path)

        print("")
        print("Das Tool generiert nun PDF-Dateien aus Ihrer LOGINEO-CSV.")
        pause("Bitte drücken Sie eine beliebige Taste, um den Prozess zu starten.")
        print("\nHier eine Übersicht der importierten Nutzer:\n")

        usertable: Dict[str, Dict[str, List[str]]] = self._read_csv_to_usertable(csv_path)

        do_individual = self._truthy(self.s.pdf_einzeln)
        do_grouped = self._truthy(self.s.pdf_lehramt)
        if not do_individual and not do_grouped:
            do_individual = True

        exported_any = False
        msgs: List[str] = []

        if do_individual and self._export_individual(usertable):
            exported_any = True
            msgs.append("Einzel-PDFs")

        if do_grouped and self._export_grouped(usertable):
            exported_any = True
            msgs.append("Sammel-PDFs pro Lehramt/Typ")

        if exported_any:
            print("")
            print("================================================================================")
            print("Erfolg: PDF-Dateien erzeugt:", " und ".join(msgs))
            print(f"Ergebnisse wurden im Output-Ordner abgelegt: '{self.output_dir}'.")
            print("================================================================================")
            print("")
            pause("Drücken Sie eine beliebige Taste, um den Prozess zu beenden.")
        else:
            print("\nIhre Datei enthält keine Nutzer, für die ein Kennwort generiert wurde. Es wurde keine PDF-Datei erzeugt.")
            pause()
            raise SystemExit(1)

    def generate_from_xml(self, xml_path: str | None = None) -> None:
        src = xml_path or getattr(self.s, 'logineo_xml_file', '') or ''
        src = src.strip()
        if not src:
            raise ValueError("Kein XML-Pfad angegeben.")
        xml_abs = resolve_path(src)
        if not os.path.isfile(xml_abs):
            print("FEHLER!")
            print(f"Die XML-Datei ({xml_abs}) wurde nicht gefunden.")
            pause()
            raise FileNotFoundError(xml_abs)

        print("")
        print("Das Tool generiert nun PDF-Dateien aus Ihrer LOGINEO-XML.")
        pause("Bitte drücken Sie eine beliebige Taste, um den Prozess zu starten.")
        print("\nHier eine Übersicht der importierten Nutzer (aus XML):\n")

        usertable = self._read_xml_to_usertable(xml_abs)

        do_individual = self._truthy(self.s.pdf_einzeln)
        do_grouped = self._truthy(self.s.pdf_lehramt)
        if not do_individual and not do_grouped:
            do_individual = True

        exported_any = False
        msgs: List[str] = []
        if do_individual and self._export_individual(usertable):
            exported_any = True
            msgs.append("Einzel-PDFs")
        if do_grouped and self._export_grouped(usertable):
            exported_any = True
            msgs.append("Sammel-PDFs pro Lehramt/Typ")

        if exported_any:
            print("")
            print("================================================================================")
            print("Erfolg: PDF-Dateien erzeugt:", " und ".join(msgs))
            print(f"Ergebnisse wurden im Output-Ordner abgelegt: '{self.output_dir}'.")
            print("================================================================================")
            print("")
            pause("Drücken Sie eine beliebige Taste, um den Prozess zu beenden.")
        else:
            print("\nIhre Datei enthält keine Nutzer, für die ein Kennwort generiert wurde. Es wurde keine PDF-Datei erzeugt.")
            pause()
            raise SystemExit(1)

    # ---------------- CSV -> usertable ----------------
    def _read_csv_to_usertable(self, csv_path: str) -> Dict[str, Dict[str, List[str]]]:
        usertable: Dict[str, Dict[str, List[str]]] = {}
        delimiter = (self.s.logineo_csv_delimiter or ",")

        with open(csv_path, encoding="utf-8", newline="") as csvfile:
            reader = csv.reader(csvfile, delimiter=delimiter)
            header_index: Dict[str, int] | None = None
            counter = 0

            for i, row in enumerate(reader):
                if i == 0:
                    header_index = {name: idx for idx, name in enumerate(row)}
                    continue

                def has_field(field: str) -> bool:
                    return header_index is not None and field in header_index

                def get_field(field: str) -> str:
                    return row[header_index[field]] if has_field(field) else ""

                if has_field("Kennwort") and get_field("Kennwort") == "":
                    continue

                user_key = f"user{counter}"
                user = {
                    "Nachname": [],
                    "Vorname": [],
                    "E-Mail": [],
                    "Seminar": [],
                    "Gruppe": [],
                    "Kennwort": [],
                    "Datensafe-Kennwort": [],
                    "Typ": [],
                }

                if has_field("Nachname"):
                    user["Nachname"].append(get_field("Nachname"))
                if has_field("Vorname"):
                    user["Vorname"].append(get_field("Vorname"))
                if has_field("Kennwort"):
                    user["Kennwort"].append(get_field("Kennwort"))
                if has_field("Datensafe-Kennwort"):
                    user["Datensafe-Kennwort"].append(get_field("Datensafe-Kennwort"))
                if has_field("System"):
                    user["Typ"].append(get_field("System"))

                for element in row:
                    if not isinstance(element, str):
                        continue
                    val = element.strip()
                    if "@" in val:
                        user["E-Mail"].append(val)
                    if val.startswith("Seminar_"):
                        user["Seminar"].append(val)
                    if val.startswith("LAA_"):
                        user["Gruppe"].append(val)

                if not user["Typ"]:
                    user["Typ"].append("SAB")

                usertable[user_key] = user
                counter += 1

        return usertable

    # ---------------- Einzel-PDFs ----------------
    def _export_individual(self, usertable: Dict[str, Dict[str, List[str]]]) -> bool:
        any_export = False
        for u in usertable.values():
            seminar = self._first(u.get("Seminar"), default="Seminar_UNBEKANNT")
            typ = self._first(u.get("Typ"), default="SAB")
            lastname = self._first(u.get("Nachname"), default="Nachname")
            firstname = self._first(u.get("Vorname"), default="Vorname")

            sub_dir = os.path.join(self.output_dir, seminar, typ)
            ensure_dir(sub_dir)

            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            filename = f"{typ}_{lastname}, {firstname}_{timestamp}.pdf"
            output_filepath = os.path.join(sub_dir, filename)
            print("Es wird erstellt: " + output_filepath)

            story = self._build_user_story(u)
            doc = self._make_doc(output_filepath)

            # Footer: leave fields empty if missing; avoid placeholders
            disp_seminar = self._first(u.get("Seminar"))
            disp_typ = self._first(u.get("Typ"))
            disp_lastname = self._first(u.get("Nachname"))
            disp_firstname = self._first(u.get("Vorname"))
            name_bits = [p for p in (disp_lastname, disp_firstname) if p]
            name_part = ", ".join(name_bits) if name_bits else ""
            parts = [disp_seminar, disp_typ, name_part]
            footer_text = " - ".join([p for p in parts if p])
            page_fn = self._make_page_decorator(None, default_footer_text=footer_text)
            doc.build(story, onFirstPage=page_fn, onLaterPages=page_fn)
            any_export = True
            time.sleep(0.02)

        return any_export

    # ---------------- Sammel-PDFs ----------------
    def _export_grouped(self, usertable: Dict[str, Dict[str, List[str]]]) -> bool:
        groups: Dict[Tuple[str, str], List[Dict[str, List[str]]]] = {}
        for _, u in usertable.items():
            typ = self._first(u.get("Typ"), default="SAB")
            lehramt = self._lehramt_from_seminar(self._first(u.get("Seminar")))
            key = (typ, lehramt)
            groups.setdefault(key, []).append(u)

        if not groups:
            return False

        for (typ, lehramt), users in groups.items():
            seminar_label = f"Seminar_{lehramt}" if lehramt else "Seminar_UNBEKANNT"
            sub_dir = os.path.join(self.output_dir, seminar_label, typ)
            ensure_dir(sub_dir)

            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            filename = f"SAMMEL_{typ}_{lehramt or 'UNBEKANNT'}_{timestamp}.pdf"
            output_filepath = os.path.join(sub_dir, filename)
            print("Es wird erstellt: " + output_filepath)

            story: List = []
            footer_map: List[str] = []
            for idx, u in enumerate(users):
                # Footer fields: empty if not present
                disp_seminar = f"Seminar_{lehramt}" if lehramt else ""
                disp_typ = self._first(u.get("Typ")) or typ
                disp_lastname = self._first(u.get("Nachname"))
                disp_firstname = self._first(u.get("Vorname"))
                name_bits = [p for p in (disp_lastname, disp_firstname) if p]
                name_part = ", ".join(name_bits) if name_bits else ""
                parts = [disp_seminar, disp_typ, name_part]
                footer_map.append(" - ".join([p for p in parts if p]))
                story.extend(self._build_user_story(u))
                if idx < (len(users) - 1):
                    story.append(PageBreak())

            # Default footer for pages without map entry
            default_parts = [f"Seminar_{lehramt}" if lehramt else "", typ, "Sammel"]
            default_footer = " - ".join([p for p in default_parts if p])

            doc = self._make_doc(output_filepath)
            page_fn = self._make_page_decorator(footer_map, default_footer_text=default_footer)
            doc.build(story, onFirstPage=page_fn, onLaterPages=page_fn)
            time.sleep(0.05)

        return True

    # ---------------- Bausteine ----------------
    def _build_user_story(self, u: Dict[str, List[str]]) -> List:
        styles = self.styles
        if "Justify" not in styles.byName:
            styles.add(ParagraphStyle(name="Justify", alignment=TA_JUSTIFY, fontName=styles["Normal"].fontName))

        story: List = []

        # Logo
        logineologo = resolve_path("assets/LOGINEO-NRW.png")
        im = Image(logineologo, 477, 105)
        im._restrictSize(4 * cm, 8 * cm)
        story.append(im)

        # Anrede & Name
        firstname = xml_escape(self._first(u.get("Vorname")))
        lastname = xml_escape(self._first(u.get("Nachname")))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"<font size=12>Sehr geehrte/r {firstname} {lastname},</font>", styles["Justify"]))
        story.append(Spacer(1, 12))

        # Einleitung
        story.append(Paragraph(
            "<font size=12>Mit diesem Schreiben erhalten Sie Informationen zum Anmeldeprozess "
            "in der ZfsL-Basis-IT-Infrastruktur, die vom Nordrhein-Westfälischen Ministerium für Schule und Bildung "
            "für Lehramtsanwärter und Seminarausbilder kostenlos zur Verfügung gestellt wird.</font>",
            styles["Normal"]
        ))
        story.append(Spacer(1, 12))

        # URL
        story.append(Paragraph(
            "<font size=12>Für den Zugang zu unserer Plattform müssen Sie zunächst im oberen Feld Ihres Browsers die folgende URL eingeben:</font>",
            styles["Normal"]
        ))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"<font size=14>https://{xml_escape(self.s.pdf_logineolink)}</font>", styles["Normal"]))
        story.append(Spacer(1, 24))

        # Hinweise
        story.append(Paragraph("<font size=12>Bitte beachten Sie folgende Hinweise:</font>", styles["Heading1"]))
        story.append(Paragraph(
            "<font size=12>Der Zugriff erfolgt grundsätzlich nur mit zugewiesenen persönlichen Login-Daten einschließlich des Passwortes. "
            "Jede Person ist verantwortlich für alle Aktionen, die mit ihren Zugangsdaten ausgeführt werden. Gehen Sie deshalb sorgfältig mit "
            "Ihrer Zugangserkennung und Ihrem Passwort um.</font>",
            styles["Normal"]
        ))
        story.append(Spacer(1, 6))

        typ = self._first(u.get("Typ"), default="SAB")
        if typ != "LAA":
            story.append(Paragraph(
                "<font size=12>Nach Ihrer Erstanmeldung müssen sowohl das Zugangspasswort als auch das Passwort für den Bereich Safe geändert werden.</font>",
                styles["Normal"]
            ))
        else:
            story.append(Paragraph(
                "<font size=12>Nach Ihrer Erstanmeldung muss das Zugangspasswort geändert werden.</font>",
                styles["Normal"]
            ))

        story.append(Spacer(1, 6))
        story.append(Paragraph("<font size=12>Die Nutzung der Plattform ist ausschließlich für dienstliche Zwecke gestattet.</font>", styles["Normal"]))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            "<font size=12>Für die Nutzung der Basis-IT-Infrastruktur gelten die Nutzungsbedingungen, denen Sie direkt nach Ihrer Erstanmeldung "
            "mit den hier mitgeteilten Zugangsdaten zustimmen müssen. Diese Nutzungsbedingungen sind später im Bereich 'Mein Konto' einsehbar.</font>",
            styles["Normal"]
        ))
        story.append(Spacer(1, 24))

        # Zugangsdaten
        story.append(Paragraph("<font size=12>Ihre Zugangsdaten zur ZfsL-LOGINEO NRW-Plattform finden Sie im Folgenden:</font>", styles["Heading1"]))
        story.append(Paragraph("<font size=14>Benutzername / E-Mail-Adresse:</font>", styles["Normal"]))
        story.append(Spacer(1, 12))

        # E-Mails
        emails = u.get("E-Mail", [])
        for mail in emails:
            if not isinstance(mail, str):
                continue
            mail_clean = xml_escape(mail.replace('"', "").strip())
            if not mail_clean:
                continue
            story.append(Paragraph(f'<font size=14>{mail_clean}</font>', styles["Heading1"]))

        # Login-Kennwort
        password = xml_escape(self._first(u.get("Kennwort")))
        story.append(Paragraph("<font size=14>Login-Kennwort:</font>", styles["Normal"]))
        story.append(Spacer(1, 12))
        story.append(Paragraph(f"<font size=14>{password}</font>", styles["Heading1"]))

        # Safe-Kennwort (nur SAB)
        if typ != "LAA" and u.get("Datensafe-Kennwort"):
            safe_pw = xml_escape(self._first(u.get("Datensafe-Kennwort")))
            story.append(Paragraph("<font size=14>Safe-Kennwort:</font>", styles["Normal"]))
            story.append(Spacer(1, 12))
            story.append(Paragraph(f"<font size=14>{safe_pw}</font>", styles["Heading1"]))

        story.append(Spacer(1, 12))
        story.append(Paragraph(
            "<font size=12>Tipps und Hinweise für sichere Kennwörter sowie Anleitungen, kleine Einführungsvideos und Hilfestellungen für den Umgang mit LOGINEO NRW "
            "finden Sie im Netzwerk von LOGINEO NRW.</font>",
            styles["Normal"]
        ))
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"<font size=12>Bei Problemen mit Ihren Zugangsdaten wenden Sie sich bitte an Ihre:n LOGINEO-NRW-Administrator:in "
            f"{xml_escape(self.s.pdf_supportname)} ({xml_escape(self.s.pdf_supportmail)}).</font>",
            styles["Normal"]
        ))

        return story

    def _make_doc(self, output_filepath: str) -> SimpleDocTemplate:
        return SimpleDocTemplate(
            output_filepath,
            pagesize=A4,
            rightMargin=52,
            leftMargin=52,
            topMargin=18,
            bottomMargin=18,
        )

    def _make_page_decorator(self, footer_map: List[str] | None, default_footer_text: str) -> Callable:
        styles = self.styles
        footer_style = styles["Normal"]

        def draw(canvas, doc):
            canvas.saveState()
            page_num = canvas.getPageNumber()
            footer_text = default_footer_text
            if footer_map:
                idx = page_num - 1
                if 0 <= idx < len(footer_map):
                    footer_text = footer_map[idx]
            if footer_text:
                para = Paragraph(footer_text, footer_style)
                w, h = para.wrap(doc.width, doc.bottomMargin)
                para.drawOn(canvas, doc.leftMargin, h)
            canvas.restoreState()

        return draw

    # ---------------- Hilfsfunktionen ----------------
    @staticmethod
    def _truthy(value: str | None) -> bool:
        if value is None:
            return False
        return str(value).strip().lower() in {"ja", "true", "1", "yes", "y"}

    @staticmethod
    def _first(lst: List[str] | None, default: str = "") -> str:
        if not lst:
            return default
        return (lst[0] or default)

    @staticmethod
    def _lehramt_from_seminar(seminar_value: str) -> str:
        if not seminar_value:
            return ""
        if seminar_value.startswith("Seminar_"):
            return seminar_value[len("Seminar_"):]
        return seminar_value

    def _read_xml_to_usertable(self, xml_path: str) -> Dict[str, Dict[str, List[str]]]:
        def norm(s: str) -> str:
            return s.strip() if isinstance(s, str) else ""

        tree = ET.parse(xml_path)
        root = tree.getroot()

        candidates: List[ET.Element] = []
        for tag in ("user", "account", "person", "record", "row", "eintrag", "datensatz"):
            candidates.extend(root.findall(f".//{tag}"))
        if not candidates:
            candidates = list(root)
        if not candidates:
            candidates = [root]

        usertable: Dict[str, Dict[str, List[str]]] = {}
        counter = 0
        for node in candidates:
            leaves: List[Tuple[str, str]] = []
            for el in node.iter():
                if list(el):
                    continue
                tag = (el.tag or "").lower()
                text = norm(el.text or "")
                if not text:
                    continue
                leaves.append((tag, text))

            user: Dict[str, List[str]] = {
                "Nachname": [],
                "Vorname": [],
                "E-Mail": [],
                "Seminar": [],
                "Gruppe": [],
                "Kennwort": [],
                "Datensafe-Kennwort": [],
                "Typ": [],
            }

            for tag, text in leaves:
                low = tag.lower()
                if any(k in low for k in ("nachname", "lastname", "surname")):
                    user["Nachname"].append(text)
                    continue
                if any(k in low for k in ("vorname", "firstname", "givenname", "given_name")):
                    user["Vorname"].append(text)
                    continue
                if "@" in text:
                    user["E-Mail"].append(text)
                if ("kennwort" in low) or ("password" in low):
                    if ("datensafe" in low) or ("safe" in low):
                        user["Datensafe-Kennwort"].append(text)
                    else:
                        user["Kennwort"].append(text)
                if ("system" in low) or ("typ" in low) or ("type" in low):
                    user["Typ"].append(text)
                if text.startswith("Seminar_"):
                    user["Seminar"].append(text)
                if text.startswith("LAA_"):
                    user["Gruppe"].append(text)

            if not user["Typ"]:
                user["Typ"].append("LAA" if user["Gruppe"] else "SAB")

            usertable[f'user{counter}'] = user
            counter += 1

        return usertable








