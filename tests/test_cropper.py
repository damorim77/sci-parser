"""Testes do cropper com PDF sintético gerado por PyMuPDF."""

import pymupdf
import pytest

from sci_parser.cropper import crop_equations
from sci_parser.equations import EqSpec


@pytest.fixture
def synthetic_pdf(tmp_path):
    """PDF com um retângulo desenhado em posição conhecida (100,100)-(200,150)."""
    doc = pymupdf.open()
    page = doc.new_page()  # 612x792 pt
    page.draw_rect(pymupdf.Rect(100, 100, 200, 150), color=(0, 0, 0))
    path = tmp_path / "synthetic.pdf"
    doc.save(path)
    doc.close()
    return path


def _eq(bbox):
    return EqSpec(page_id=0, bbox=bbox, alt="alt", block=object())


class TestCropEquations:
    def test_dimensoes_conferem_dpi_e_margem(self, synthetic_pdf, tmp_path):
        eq = _eq((100, 100, 200, 150))
        crop_equations(synthetic_pdf, [eq], tmp_path, dpi=300, margin=3.0)

        img = pymupdf.Pixmap(tmp_path / "eq_images" / "eq_p1_01.png")
        # bbox 100x50 pt + margem 2*3pt em cada eixo, a 300/72 px/pt
        expected_w = (100 + 6) * 300 / 72  # 441.7
        expected_h = (50 + 6) * 300 / 72  # 233.3
        assert abs(img.width - expected_w) <= 2
        assert abs(img.height - expected_h) <= 2

    def test_marca_image_com_caminho_relativo(self, synthetic_pdf, tmp_path):
        eq = _eq((100, 100, 200, 150))
        crop_equations(synthetic_pdf, [eq], tmp_path, dpi=150)

        assert eq.image == "eq_images/eq_p1_01.png"
        assert (tmp_path / "eq_images" / "eq_p1_01.png").exists()

    def test_numeracao_global_e_pagina_1_indexed(self, tmp_path):
        doc = pymupdf.open()
        doc.new_page()
        doc.new_page()
        doc[1].draw_rect(pymupdf.Rect(10, 10, 60, 60), color=(0, 0, 0))
        path = tmp_path / "two.pdf"
        doc.save(path)
        doc.close()

        e1 = _eq((0, 0, 30, 30))
        e1.page_id = 0
        e2 = _eq((10, 10, 60, 60))
        e2.page_id = 1

        crop_equations(path, [e1, e2], tmp_path, dpi=72, margin=0)

        assert e1.image == "eq_images/eq_p1_01.png"
        assert e2.image == "eq_images/eq_p2_02.png"

    def test_bbox_limite_nao_explode_fora_da_pagina(self, synthetic_pdf, tmp_path):
        # bbox colado no canto: margem extrapola, PyMuPDF recorta no page box
        eq = _eq((0, 0, 50, 50))
        crop_equations(synthetic_pdf, [eq], tmp_path, dpi=72, margin=3.0)

        assert (tmp_path / "eq_images" / "eq_p1_01.png").exists()
