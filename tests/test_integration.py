"""Testes de integração — executam o marker (modelos, ~90s por paper no M4 Pro).

Gate: SCI_PARSER_SKIP_INTEGRATION=1 desativa (CI/ambientes sem modelos).
"""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = [
    pytest.mark.skipif(
        os.environ.get("SCI_PARSER_SKIP_INTEGRATION") == "1",
        reason="SCI_PARSER_SKIP_INTEGRATION=1",
    ),
]

DATA = Path(__file__).parent / "data"
ATTENTION = DATA / "attention.pdf"


def test_runner_single_pass(tmp_path):
    from sci_parser.runner import MarkerRunner

    document, md_output = MarkerRunner().run(ATTENTION)

    assert "Attention Is All You Need" in md_output.markdown
    # 5 figuras extraídas (números validados nos experimentos)
    assert len(md_output.images) == 5
    # document com páginas e blocos
    assert len(document.pages) == 15


def _args(**kw):
    defaults = dict(
        pdf=ATTENTION, format="md", output=None, dpi=300,
        title=None, keep_latex_equations=False, no_report=False,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def test_pipeline_eq_images(tmp_path):
    """Fluxo completo: mutação de blocos + re-render → refs de imagem nas equações."""
    from sci_parser.pipeline import execute

    out = tmp_path / "out"
    rc = execute(_args(), out)

    assert rc == 0
    md = (out / "attention.md").read_text(encoding="utf-8")

    # 5 equações recortadas e referenciadas
    eq_files = list((out / "eq_images").glob("*.png"))
    assert len(eq_files) == 5
    assert md.count("eq_images/") == 5

    # figuras do marker salvas junto ao markdown
    jpegs = [p for p in out.iterdir() if p.suffix in (".jpeg", ".jpg", ".png")]
    assert len(jpegs) == 5

    # regressão do bug do PoC: nenhuma pipe-table com math sobrou
    pipe_tables_com_math = [
        ln for ln in md.split("\n")
        if ln.strip().startswith("|") and "$" in ln
    ]
    assert pipe_tables_com_math == []

    # report básico
    import json

    report = json.loads((out / "report.json").read_text(encoding="utf-8"))
    assert report["equations"]["found"] == 5
    assert report["pages"] == 15
    assert report["figures"] == 5
    assert report["tables"] == 4  # 4 tabelas reais (TableGroups não contam duplo)


def test_pipeline_keep_latex_equations(tmp_path):
    from sci_parser.pipeline import execute

    out = tmp_path / "out"
    rc = execute(_args(keep_latex_equations=True), out)

    assert rc == 0
    assert not (out / "eq_images").exists()
    md = (out / "attention.md").read_text(encoding="utf-8")
    assert md.count("eq_images/") == 0


def test_pipeline_docx_10_imagens_embutidas(tmp_path):
    """Docx final com as 5 equações + 5 figuras embutidas como mídia."""
    import zipfile

    from sci_parser.pipeline import execute

    out = tmp_path / "out"
    rc = execute(_args(format="docx"), out)

    assert rc == 0
    docx = out / "attention.docx"
    assert docx.exists()
    with zipfile.ZipFile(docx) as zf:
        media = [n for n in zf.namelist() if n.startswith("word/media/")]
    assert len(media) == 10
