"""Recorte das regiões de equação do PDF original em alta resolução."""

from pathlib import Path

import pymupdf

from sci_parser.equations import EqSpec

# Margem de segurança (pontos PDF) para não cortar frações/delimitadores
# (valor validado nos experimentos com attention.pdf)
DEFAULT_MARGIN = 3.0


def crop_equations(
    pdf_path: Path,
    eqs: list[EqSpec],
    out_dir: Path,
    dpi: int = 300,
    margin: float = DEFAULT_MARGIN,
) -> list[EqSpec]:
    """Renderiza cada bbox de equação em PNG e marca `eq.image`.

    O bbox vem em pontos PDF do layout model do marker (mesmo espaço de
    coordenadas do PyMuPDF — verificado: page polygon 612x792).
    `eq.image` recebe o caminho relativo ao diretório do markdown.
    """
    eq_dir = out_dir / "eq_images"
    eq_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    try:
        for n, eq in enumerate(eqs, 1):
            x0, y0, x1, y1 = eq.bbox
            rect = pymupdf.Rect(x0 - margin, y0 - margin, x1 + margin, y1 + margin)
            pix = doc[eq.page_id].get_pixmap(clip=rect, dpi=dpi)
            fname = f"eq_p{eq.page_id + 1}_{n:02d}.png"
            pix.save(eq_dir / fname)
            eq.image = f"eq_images/{fname}"
    finally:
        doc.close()
    return eqs
