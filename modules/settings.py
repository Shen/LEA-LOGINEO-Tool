from dataclasses import dataclass
import xml.etree.ElementTree as ET
from typing import Optional


@dataclass
class Settings:
    # LEA -> LOGINEO Konverter
    lea_xlsx_file: str
    lea_primary_key: str               # "LEAID" oder "IdentNr"
    lea_gruppe_laa_lehramt: str        # "ja"/"nein"
    lea_gruppe_laa_lehramt_jg: str     # "ja"/"nein"
    lea_gruppe_laa_seminare: str       # "ja"/"nein"
    # Ausgabeordner für LEA-Konverter
    lea_outputpath: str

    # LOGINEO PDF-Generator
    logineo_csv_file: str
    logineo_xml_file: str
    # Optionales XML-Mapping (Tag-Namen); leer => Heuristik
    logineo_xml_user_tag: str = ""
    logineo_xml_tag_lastname: str = ""
    logineo_xml_tag_firstname: str = ""
    logineo_xml_tag_email: str = ""
    logineo_xml_tag_password: str = ""
    logineo_xml_tag_safe_password: str = ""
    logineo_xml_tag_system: str = ""
    logineo_xml_tag_group: str = ""
    # CSV/PDF-Optionen mit sinnvollen Defaults (entsprechen load_settings)
    logineo_csv_delimiter: str = ","
    pdf_outputpath: str = "pdf-files"
    pdf_logineolink: str = ""
    pdf_supportname: str = ""
    pdf_supportmail: str = ""
    pdf_einzeln: str = "ja"          # "ja"/"nein"
    pdf_lehramt: str = "nein"         # "ja"/"nein"
    lea_output_format: str = "csv"


def _get_text(root: ET.Element, tag: str, default: str = "") -> str:
    el = root.find(tag)
    return el.text.strip() if el is not None and el.text is not None else default


def _warn_invalid(raw: str, varname: str, default: str) -> None:
    # Gewünschte Formulierung:
    # "Ungültiger Wert für X in der config.xml, nutze für Variable Z Standardwert Y"
    print(f"Ungültiger Wert {raw!r} für Variable {varname!r} in der config.xml. Nutze Standardwert {default!r}")


def _norm_yes_no(value: str, *, varname: str, default_yes: bool) -> str:
    """
    Normalisiert eine Ja/Nein-Option:
    - akzeptiert nur 'ja' oder 'nein' (case-insensitiv)
    - alles andere -> Default (ja, wenn default_yes=True; sonst nein) + Warnhinweis
    - Leerer Wert -> Default (ohne Warnhinweis)
    """
    v_raw = value or ""
    v = v_raw.strip().lower()
    if v == "":
        return "ja" if default_yes else "nein"
    if v in ("ja", "nein"):
        return v
    default_str = "ja" if default_yes else "nein"
    _warn_invalid(v_raw, varname, default_str)
    return default_str


def _norm_primary_key(value: str) -> str:
    """
    Normalisiert den Primary Key:
    - akzeptiert 'leaid' oder 'identnr' (case-insensitiv)
    - alles andere -> 'LEAID' + Warnhinweis (nur wenn nicht leer)
    - Leerer Wert -> 'LEAID' (ohne Warnhinweis)
    """
    v_raw = value or ""
    v = v_raw.strip().lower()
    if v == "":
        return "LEAID"
    if v == "leaid":
        return "LEAID"
    if v == "identnr":
        return "IdentNr"
    _warn_invalid(v_raw, "lea_primary_key", "LEAID")
    return "LEAID"


def _norm_output_format(value: str) -> str:
    """
    Normalisiert das Ausgabeformat für die LEA-Konvertierung.
    Erlaubt: 'csv' (Standard) oder 'xlsx'.
    """
    v_raw = value or ""
    v = v_raw.strip().lower()
    if v == "":
        return "csv"
    if v in ("csv", "xlsx"):
        return v
    _warn_invalid(v_raw, "lea_output_format", "csv")
    return "csv"


def load_settings(config_path: str) -> Settings:
    with open(config_path, "r", encoding="utf-8") as f:
        xml_text = f.read()
    # Parse XML using ElementTree (keine bs4-Abhängigkeit)
    root = ET.fromstring(xml_text)

    # Rohwerte auslesen
    lea_xlsx_file          = _get_text(root, "lea_xlsx_file")
    lea_primary_key_raw    = _get_text(root, "lea_primary_key", "LEAID")
    laa_lehramt_raw        = _get_text(root, "lea_gruppe_laa_lehramt", "ja")
    laa_jg_raw             = _get_text(root, "lea_gruppe_laa_lehramt_jg", "ja")
    laa_seminare_raw       = _get_text(root, "lea_gruppe_laa_seminare", "ja")
    lea_outputpath         = _get_text(root, "lea_outputpath", "output")
    lea_output_format_raw  = _get_text(root, "lea_output_format", "csv")

    logineo_csv_file       = _get_text(root, "logineo_csv_file")
    logineo_xml_file       = _get_text(root, "logineo_xml_file", "")
    logineo_csv_delimiter  = _get_text(root, "logineo_csv_delimiter", ",")
    # XML-Tag-Mapping (optional)
    logineo_xml_user_tag         = _get_text(root, "logineo_xml_user_tag")
    logineo_xml_tag_lastname     = _get_text(root, "logineo_xml_tag_lastname")
    logineo_xml_tag_firstname    = _get_text(root, "logineo_xml_tag_firstname")
    logineo_xml_tag_email        = _get_text(root, "logineo_xml_tag_email")
    logineo_xml_tag_password     = _get_text(root, "logineo_xml_tag_password")
    logineo_xml_tag_safe_password= _get_text(root, "logineo_xml_tag_safe_password")
    logineo_xml_tag_system       = _get_text(root, "logineo_xml_tag_system")
    logineo_xml_tag_group        = _get_text(root, "logineo_xml_tag_group")
    pdf_outputpath         = _get_text(root, "pdf_outputpath", "pdf-files")
    pdf_logineolink        = _get_text(root, "pdf_logineolink")
    pdf_supportname        = _get_text(root, "pdf_supportname")
    pdf_supportmail        = _get_text(root, "pdf_supportmail")
    pdf_einzeln_raw        = _get_text(root, "pdf_einzeln", "ja")
    pdf_lehramt_raw        = _get_text(root, "pdf_lehramt", "nein")

    # Normalisieren mit Warnhinweisen wo nötig
    lea_primary_key            = _norm_primary_key(lea_primary_key_raw)
    lea_gruppe_laa_lehramt     = _norm_yes_no(laa_lehramt_raw,      varname="lea_gruppe_laa_lehramt",    default_yes=True)
    lea_gruppe_laa_lehramt_jg  = _norm_yes_no(laa_jg_raw,           varname="lea_gruppe_laa_lehramt_jg", default_yes=True)
    lea_gruppe_laa_seminare    = _norm_yes_no(laa_seminare_raw,     varname="lea_gruppe_laa_seminare",   default_yes=True)
    lea_output_format          = _norm_output_format(lea_output_format_raw)

    # (Optional) Auch PDF-Flags robust normalisieren + warnen
    pdf_einzeln                = _norm_yes_no(pdf_einzeln_raw,      varname="pdf_einzeln",               default_yes=True)
    pdf_lehramt                = _norm_yes_no(pdf_lehramt_raw,      varname="pdf_lehramt",               default_yes=False)

    return Settings(
        # LEA
        lea_xlsx_file=lea_xlsx_file,
        lea_primary_key=lea_primary_key,
        lea_gruppe_laa_lehramt=lea_gruppe_laa_lehramt,
        lea_gruppe_laa_lehramt_jg=lea_gruppe_laa_lehramt_jg,
        lea_gruppe_laa_seminare=lea_gruppe_laa_seminare,
        lea_outputpath=lea_outputpath,
        lea_output_format=lea_output_format,
        # PDF
        logineo_csv_file=logineo_csv_file,
        logineo_xml_file=(logineo_xml_file or ""),
        logineo_csv_delimiter=logineo_csv_delimiter,
        pdf_outputpath=pdf_outputpath,
        pdf_logineolink=pdf_logineolink,
        pdf_supportname=pdf_supportname,
        pdf_supportmail=pdf_supportmail,
        pdf_einzeln=pdf_einzeln,
        pdf_lehramt=pdf_lehramt,
        # XML Tag-Mapping
        logineo_xml_user_tag=logineo_xml_user_tag,
        logineo_xml_tag_lastname=logineo_xml_tag_lastname,
        logineo_xml_tag_firstname=logineo_xml_tag_firstname,
        logineo_xml_tag_email=logineo_xml_tag_email,
        logineo_xml_tag_password=logineo_xml_tag_password,
        logineo_xml_tag_safe_password=logineo_xml_tag_safe_password,
        logineo_xml_tag_system=logineo_xml_tag_system,
        logineo_xml_tag_group=logineo_xml_tag_group,
    )


def save_settings(config_path: str, s: Settings) -> None:
    """Persistiert die Einstellungen zur vorhandenen config.xml.

    - Erhält vorhandene Kommentare und Reihenfolge, sofern die Tags existieren.
    - Legt fehlende Tags bei Bedarf neu an.
    """
    try:
        tree = ET.parse(config_path)
        root = tree.getroot()
    except Exception:
        # Falls die Datei fehlt/kaputt ist, neu aufbauen
        root = ET.Element("config")
        tree = ET.ElementTree(root)

    def set_text(tag: str, value: Optional[str]) -> None:
        el = root.find(tag)
        if el is None:
            el = ET.SubElement(root, tag)
        el.text = (value or "")

    # LEA
    set_text("lea_xlsx_file", s.lea_xlsx_file)
    set_text("lea_primary_key", s.lea_primary_key)
    set_text("lea_gruppe_laa_lehramt", s.lea_gruppe_laa_lehramt)
    set_text("lea_gruppe_laa_lehramt_jg", s.lea_gruppe_laa_lehramt_jg)
    set_text("lea_gruppe_laa_seminare", s.lea_gruppe_laa_seminare)
    set_text("lea_outputpath", s.lea_outputpath)
    set_text("lea_output_format", s.lea_output_format)

    # LOGINEO / PDF
    set_text("logineo_csv_file", s.logineo_csv_file)
    set_text("logineo_xml_file", s.logineo_xml_file)
    set_text("logineo_csv_delimiter", s.logineo_csv_delimiter)
    set_text("pdf_outputpath", s.pdf_outputpath)
    set_text("pdf_logineolink", s.pdf_logineolink)
    set_text("pdf_supportname", s.pdf_supportname)
    set_text("pdf_supportmail", s.pdf_supportmail)
    set_text("pdf_einzeln", s.pdf_einzeln)
    set_text("pdf_lehramt", s.pdf_lehramt)

    # XML-Mapping (optional)
    set_text("logineo_xml_user_tag", s.logineo_xml_user_tag)
    set_text("logineo_xml_tag_lastname", s.logineo_xml_tag_lastname)
    set_text("logineo_xml_tag_firstname", s.logineo_xml_tag_firstname)
    set_text("logineo_xml_tag_email", s.logineo_xml_tag_email)
    set_text("logineo_xml_tag_password", s.logineo_xml_tag_password)
    set_text("logineo_xml_tag_safe_password", s.logineo_xml_tag_safe_password)
    set_text("logineo_xml_tag_system", s.logineo_xml_tag_system)
    set_text("logineo_xml_tag_group", s.logineo_xml_tag_group)

    tree.write(config_path, encoding="utf-8", xml_declaration=False)
