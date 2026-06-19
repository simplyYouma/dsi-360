"""Génération du rapport d'analyse en PDF (fpdf2, pur Python — aucune dépendance système)."""

from typing import Any

from fpdf import FPDF

_ENCRE = (24, 26, 29)  # noir de marque
_GRIS = (120, 128, 140)
_VERT = (31, 157, 85)
_TRAIT = (224, 226, 230)


def _entete(pdf: FPDF, periode: str, genere_le: str) -> None:
    pdf.set_fill_color(*_ENCRE)
    pdf.rect(0, 0, 210, 28, "F")
    pdf.set_xy(14, 7)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 9, "DSI 360 - Rapport d'analyse")
    pdf.set_xy(14, 17)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(200, 205, 212)
    pdf.cell(0, 6, f"Periode : {periode}   -   Genere le {genere_le}")
    pdf.set_text_color(*_ENCRE)
    pdf.set_y(36)


def _titre_section(pdf: FPDF, texte: str) -> None:
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*_ENCRE)
    pdf.cell(0, 8, texte, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*_TRAIT)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(2)


def _kpis(pdf: FPDF, kpis: dict[str, Any]) -> None:
    cartes = [
        ("Activites ouvertes", str(kpis["ouvertes"])),
        ("Respect du SLA", f"{kpis['respect_sla']} %"),
        ("Delai moyen resolution", f"{kpis['mttr_jours']} j"),
        ("Echeances depassees", str(kpis["en_retard"])),
    ]
    largeur = 44
    x0 = 14
    y0 = pdf.get_y()
    for i, (libelle, valeur) in enumerate(cartes):
        x = x0 + i * (largeur + 2)
        pdf.set_fill_color(246, 247, 249)
        pdf.rect(x, y0, largeur, 22, "F")
        pdf.set_xy(x + 3, y0 + 4)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(*_ENCRE)
        pdf.cell(largeur - 6, 8, valeur)
        pdf.set_xy(x + 3, y0 + 14)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*_GRIS)
        pdf.cell(largeur - 6, 5, libelle)
    pdf.set_y(y0 + 22)


def _tableau(pdf: FPDF, entetes: list[tuple[str, float]], lignes: list[list[str]]) -> None:
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*_GRIS)
    for libelle, largeur in entetes:
        pdf.cell(largeur, 7, libelle, border="B")
    pdf.ln(7)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_ENCRE)
    for ligne in lignes:
        if pdf.get_y() > 270:
            pdf.add_page()
        for (_, largeur), valeur in zip(entetes, ligne, strict=False):
            pdf.cell(largeur, 6, valeur, border="B")
        pdf.ln(6)


def construire_rapport(data: dict[str, Any]) -> bytes:
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_left_margin(14)
    pdf.set_right_margin(14)
    _entete(pdf, data["periode"], data["genere_le"])

    _kpis(pdf, data["kpis"])

    _titre_section(pdf, "Respect du SLA par priorite")
    _tableau(
        pdf,
        [("Priorite", 30), ("Dans les delais", 40), ("Total", 30), ("Taux", 30)],
        [
            [p["priorite"], str(p["dans_delai"]), str(p["total"]), f"{p['taux']} %"]
            for p in data["sla_par_priorite"]
        ]
        or [["-", "-", "-", "-"]],
    )

    _titre_section(pdf, "Repartition par module")
    _tableau(
        pdf,
        [("Module", 120), ("Activites ouvertes", 60)],
        [[m["module"], str(m["valeur"])] for m in data["par_module"]] or [["-", "-"]],
    )

    _titre_section(pdf, "Charge et performance des gestionnaires")
    _tableau(
        pdf,
        [("Gestionnaire", 70), ("Traites", 25), ("En charge", 30), ("MTTR (j)", 28), ("Taux", 25)],
        [
            [
                g["gestionnaire"],
                str(g["volume"]),
                str(g["charge"]),
                "-" if g["mttr_jours"] is None else str(g["mttr_jours"]),
                f"{g['taux']} %",
            ]
            for g in data["gestionnaires"]
        ]
        or [["-", "-", "-", "-", "-"]],
    )

    pdf.set_y(285)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(*_GRIS)
    pdf.cell(0, 5, "AFG Bank - DSI 360 - Document interne, confidentiel.")

    return bytes(pdf.output())
