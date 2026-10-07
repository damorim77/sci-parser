"""Testes da descoberta de equações com fakes duck-typed do Document do marker."""

from types import SimpleNamespace

from marker.schema import BlockTypes

from sci_parser.equations import EqSpec, find_equations, mutate_blocks, sanitize_alt


def _block(block_type, page_id=0, bbox=(0, 0, 100, 50), html="<math>x</math>",
           block_id=None, nested=None):
    """Bloco fake; `nested` são blocos filhos (expostos via structure)."""
    children = list(nested or [])
    return SimpleNamespace(
        block_type=block_type,
        page_id=page_id,
        polygon=SimpleNamespace(bbox=list(bbox)),
        html=html,
        structure=[c.block_id for c in children],
        block_id=block_id,
        _children=children,
    )


def _document(blocks_by_page):
    """blocks_by_page: lista de páginas, cada uma lista de blocos top-level."""
    all_blocks = {}

    def register(block):
        all_blocks[block.block_id] = block
        for child in block._children:
            register(child)

    for blocks in blocks_by_page:
        for b in blocks:
            register(b)

    pages = [SimpleNamespace(children=[b.block_id for b in blocks])
             for blocks in blocks_by_page]
    return SimpleNamespace(pages=pages, get_block=all_blocks.__getitem__)


class TestFindEquations:
    def test_coleta_equacoes_em_ordem_de_leitura(self):
        eq_p0 = _block(BlockTypes.Equation, 0, (0, 100, 100, 150),
                       html="<p>sin(x)</p>", block_id="eq0")
        eq_p1 = _block(BlockTypes.Equation, 1, (0, 200, 100, 250),
                       html="<p>cos(x)</p>", block_id="eq1")
        txt = _block(BlockTypes.Text, 0, (0, 0, 100, 50), block_id="t0")
        doc = _document([[txt, eq_p0], [eq_p1]])

        eqs = find_equations(doc)

        assert [e.alt for e in eqs] == ["sin(x)", "cos(x)"]
        assert eqs[0].page_id == 0
        assert eqs[0].bbox == (0, 100, 100, 150)

    def test_equacao_aninhada_em_grupo(self):
        nested_eq = _block(BlockTypes.Equation, 0, (10, 20, 30, 40),
                           html="<math>E=mc^2</math>", block_id="nested")
        group = _block(BlockTypes.FigureGroup, 0, html=None,
                       block_id="g0", nested=[nested_eq])
        doc = _document([[group]])

        eqs = find_equations(doc)
        assert len(eqs) == 1
        assert eqs[0].alt == "E=mc^2"

    def test_equacao_sem_html_ignorada(self):
        no_html = _block(BlockTypes.Equation, 0, html=None, block_id="e0")
        doc = _document([[no_html]])

        assert find_equations(doc) == []

    def test_ordenacao_por_pagina_e_y(self):
        # mesma página, y invertido na ordem de inserção
        eq_low = _block(BlockTypes.Equation, 0, (0, 10, 100, 60), block_id="a")
        eq_high = _block(BlockTypes.Equation, 0, (0, 100, 100, 150), block_id="b")
        doc = _document([[eq_high, eq_low]])

        eqs = find_equations(doc)
        assert [e.block for e in eqs] == [eq_low, eq_high]


class TestSanitizeAlt:
    def test_strip_de_tags_e_whitespace(self):
        assert sanitize_alt("<p><math>x^2</math></p>") == "x^2"

    def test_remove_colchetes_e_aspas(self):
        assert sanitize_alt("<p>a[b]c</p>") == "a(b)c"
        assert sanitize_alt('<p>say "hi"</p>') == "say 'hi'"

    def test_limita_tamanho(self):
        assert len(sanitize_alt("<p>" + "x" * 500 + "</p>")) == 200


class TestMutateBlocks:
    def test_substitui_html_do_bloco(self):
        block = _block(BlockTypes.Equation, 0, html="<p>old</p>")
        eq = EqSpec(page_id=0, bbox=(0, 0, 1, 1), alt="LaTeX alt",
                    block=block, image="eq_images/eq_p1_01.png")

        mutate_blocks([eq])

        assert block.html == '<img src="eq_images/eq_p1_01.png" alt="LaTeX alt">'

    def test_sem_image_nao_muta(self):
        block = _block(BlockTypes.Equation, 0, html="<p>keep</p>")
        eq = EqSpec(page_id=0, bbox=(0, 0, 1, 1), alt="x", block=block)

        mutate_blocks([eq])
        assert block.html == "<p>keep</p>"
