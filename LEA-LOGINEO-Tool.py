#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import traceback

from modules.io_utils import appdir, print_header, ask_menu, pause
from modules.settings import load_settings
from modules.converter import LEAConverter
from modules.pdf_generator import PDFGenerator

DEBUG = False

def run_cli() -> None:
    """Behält die bisherige Konsolen-Variante bei (für Power-User)."""
    print_header()

    try:
        settings = load_settings(os.path.join(appdir, "config.xml"))
    except Exception as e:
        print("FEHLER!")
        print("Die config.xml konnte nicht gelesen werden.")
        print("Bitte stellen Sie sicher, dass sich die Programmdatei")
        print("(LEA-LOGINEO-Tool.exe) und die config.xml im selben Ordner befinden.")
        print(f"Pfad gesucht: {os.path.join(appdir, 'config.xml')}")
        if DEBUG:
            traceback.print_exc()
        else:
            print(f"Details: {e}")
        pause("\nDrücken Sie eine beliebige Taste, um das Programm zu beenden.")
        sys.exit(1)

    print("")
    print("###################################################################################")
    print("# Inoffizielles LAA-LEA-Export zu LOGINEO NRW-Import-Tool für ZfsL-Instanzen      #")
    print("# VERSION: 3.0                                                                    #")
    print("# Dieses Tool erstellt aus einem unveränderten LAA-LEA-.xlsx-Export               #")
    print("# eine Exceldatei (.xlsx), für den LOGINEO NRW-LAA-Nutzerdatenimport.             #")
    print("#                                                                                 #")
    print("# Es werden automatische Gruppen erzeugt: LAA, LAA_Lehramt (z. B. LAA_GyGe)       #")
    print("# und Seminarzugehörigkeiten                                                      #")
    print("# Fehlerhafte Zeilen der Datei oder Zeilen, die keine Ident-Nr. enthalten,        #")
    print("# werden in einer gesonderten Excel-Datei ausgegeben.                             #")
    print("#                                                                                 #")
    print("# Das Script generiert zudem aus dem LOGINEO NRW Export PDF-Dateien mit den       #")
    print("# Nutzerdaten.                                                                    #")
    print("###################################################################################")
    print("")
    print("")
    print("Wenn Sie sicher sind, dass Ihre Einstellungen in der config.xml korrekt sind,")
    print("drücken Sie eine beliebige Taste, um fortzufahren.")
    input("Andernfalls brechen Sie den Prozess mit [STRG + C] ab.")

    print("\nWählen Sie Ihr Vorhaben:")
    print("1: LEA-Export (.xlsx) für LOGINEO-Import vorbereiten")
    print("2: PDF-Dateien aus LOGINEO-Import-Ergebnis (.csv) erstellen")

    choice = ask_menu("\nGeben Sie '1' oder '2' ein und drücken anschließend die Eingabetaste: ", {1, 2})

    if choice == 1:
        try:
            LEAConverter(settings).convert()
        except KeyboardInterrupt:
            print("\nVorgang abgebrochen.")
            sys.exit(1)
        except Exception as e:
            print("\nFEHLER bei der Verarbeitung des LEA-Exports.")
            if DEBUG:
                traceback.print_exc()
            else:
                print(f"Details: {e}")
            pause("\nDrücken Sie eine beliebige Taste, um das Programm zu beenden.")
            sys.exit(1)

    elif choice == 2:
        print("")
        print("###################################################################################")
        print("# Inoffizieller LOGINEO NRW PDF-Generator für ZfsL                                #")
        print("# Dieses Tool erstellt PDF-Dateien mit den                                        #")
        print("# LOGINEO NRW-Nutzerdaten aus einer CSV-Datei, die nach dem Datenimport durch     #")
        print("# LOGINEO NRW generiert wurde.                                                    #")
        print("#                                                                                 #")
        print("# WICHTIG FÜR DIE FUKTIONALITÄT DIESES SCRIPTS:                                   #")
        print("# Es müssen für die Personen folgende Gruppen angelegt                            #")
        print("# und in der .csv-Datei bei den einzelnen Personen aufgeführt sein:               #")
        print("# Seminar_LEHRAMT (z. B. Seminar_G)                                               #")
        print("# SAB_LEHRAMT (z.B. SAB_GyGe) / LAA_LEHRAMT (z.B. LAA_BK) zugeordnet wurden)      #")
        print("# und bei LAA: LAA_JAHRGANG (z.B. LAA_BK_2022-05)                                 #")
        print("###################################################################################")
        print("")
        print("")
        print("Wenn Sie sicher sind, dass Ihre Einstellungen in der config.xml korrekt sind,")
        print("drücken Sie beliebige Taste, um fortzufahren.")
        input("Andernfalls brechen Sie den Prozess mit [STRG + C] ab.")
        try:
            pdfgen = PDFGenerator(settings)
            xml_path = getattr(settings, 'logineo_xml_file', '').strip() if hasattr(settings, 'logineo_xml_file') else ''
            if xml_path:
                pdfgen.generate_from_xml()
            else:
                pdfgen.generate()
        except KeyboardInterrupt:
            print("\nVorgang abgebrochen.")
            sys.exit(1)
        except Exception as e:
            print("\nFEHLER beim PDF-Export.")
            if DEBUG:
                traceback.print_exc()
            else:
                print(f"Details: {e}")
            pause("\nDrücken Sie eine beliebige Taste, um das Programm zu beenden.")
            sys.exit(1)


def main() -> None:
    """Startet standardmäßig die GUI. Mit --cli lässt sich die
    bisherige Konsolen-Variante erzwingen.
    """
    if any(arg in ("--cli", "-c") for arg in sys.argv[1:]):
        run_cli()
        return
    # GUI starten
    from modules.gui import main as gui_main
    gui_main()

if __name__ == "__main__":
    main()
