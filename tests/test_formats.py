"""Testes dos formatos de saída (pandoc) com markdown sintético rápido."""

import zipfile

import pytest

from sci_parser.formats import _to_plain_text, convert, extract_title

MD_FIXTURE = """# Meu Paper

Parágrafo com **negrito** e uma tabela:

| A | B |
|---|---|
| 1 | 2 |

![eq: x^2 + y^2](eq_images/eq_p1_01.png)

![](_page_2_Diagram_0.jpeg)

Fim.
"""


@pytest.fixture
def md_dir(tmp_path):
    # imagem 1x1 px real (pandoc embute)
    from PIL import Image

    eq_dir = tmp_path / "eq_images"
    eq_dir.mkdir()
    Image.new("RGB", (1, 1)).save(eq_dir / "eq_p1_01.png")
    Image.new("RGB", (1, 1)).save(tmp_path / "_page_2_Diagram_0.jpeg")
    (tmp_path / "paper.md").write_text(MD_FIXTURE)
    return tmp_path


class TestConvert:
    @pytest.mark.parametrize("fmt", ["html", "docx", "epub", "txt"])
    def test_gera_arquivo(self, md_dir, fmt):
        out = convert(md_dir / "paper.md", fmt, "Título Teste", md_dir)
        assert out is not None and out.exists() and out.stat().st_size > 0

    def test_html_embutido_e_selfcontained(self, md_dir):
        out = convert(md_dir / "paper.md", "html", "Título Teste", md_dir)
        html = out.read_text()
        assert html.count("data:image") == 2  # eq + figura embutidas
        assert "<html" in html and "Título Teste" in html

    def test_docx_e_zip_valido(self, md_dir):
        out = convert(md_dir / "paper.md", "docx", "Título Teste", md_dir)
        with zipfile.ZipFile(out) as zf:
            assert "word/document.xml" in zf.namelist()
            media = [n for n in zf.namelist() if n.startswith("word/media/")]
            assert len(media) == 2

    def test_epub_tem_titulo(self, md_dir):
        out = convert(md_dir / "paper.md", "epub", "Título Teste", md_dir)
        with zipfile.ZipFile(out) as zf:
            opf = [n for n in zf.namelist() if n.endswith(".opf")]
            assert opf, "epub sem OPF"
            content = zf.read(opf[0]).decode()
            assert "Título Teste" in content

    def test_md_e_noop(self, md_dir):
        assert convert(md_dir / "paper.md", "md", "x", md_dir) is None

    def test_txt_contem_alt_de_equacao_e_sem_refs(self, md_dir):
        out = convert(md_dir / "paper.md", "txt", "T", md_dir)
        txt = out.read_text()
        assert "eq: x^2 + y^2" in txt
        assert "![" not in txt
        assert "_page_2_Diagram" not in txt


class TestToPlainText:
    def test_eq_vira_alt_figura_sem_alt_some(self):
        out = _to_plain_text(MD_FIXTURE)
        assert "eq: x^2 + y^2" in out
        assert "![" not in out


class TestExtractTitle:
    def test_override_tem_prioridade(self, tmp_path):
        pdf = tmp_path / "f.pdf"
        pdf.write_bytes(b"")
        assert extract_title(pdf, "Escolhido") == "Escolhido"

    def test_fallback_para_stem_sem_metadata(self, tmp_path):
        import pymupdf

        doc = pymupdf.open()
        doc.new_page()
        p = tmp_path / "meu_paper.pdf"
        doc.save(p)
        doc.close()
        assert extract_title(p) == "meu_paper"

    def test_usa_metadata_do_pdf(self, tmp_path):
        import pymupdf

        doc = pymupdf.open()
        doc.new_page()
        doc.set_metadata({"title": "Attention Is All You Need"})
        p = tmp_path / "qualquer.pdf"
        doc.save(p)
        doc.close()
        assert extract_title(p) == "Attention Is All You Need"
