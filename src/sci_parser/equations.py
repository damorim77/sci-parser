"""Descoberta de blocos de equação no Document do marker e mutação para <img>.

O marker renderiza display equations como LaTeX em pipe tables ou texto
quebrado (converção não confiável). Em vez de cirurgia no markdown (PoC),
mutamos `equation_block.html` para uma tag `<img>` ANTES do render: o
markdownify do marker converte `<img>` em `![alt](src)` na posição exata
de leitura, automaticamente.
"""

import re
from dataclasses import dataclass, field

from marker.schema import BlockTypes
from marker.schema.document import Document


@dataclass
class EqSpec:
    """Uma equação display detectada no documento."""

    page_id: int
    bbox: tuple[float, float, float, float]
    alt: str
    block: object = field(repr=False, default=None)
    image: str | None = None  # preenchido pelo cropper


_TAG_RE = re.compile(r"<[^>]+>")


def sanitize_alt(html: str, max_len: int = 200) -> str:
    """Html do bloco → alt text: strip de tags, whitespace colapsado, sem [ ]."""
    text = _TAG_RE.sub(" ", html)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.replace("[", "(").replace("]", ")")
    text = text.replace('"', "'")
    return text[:max_len]


def _walk_structure(doc, block_ids):
    for bid in block_ids:
        block = doc.get_block(bid)
        yield block
        if block.structure:
            yield from _walk_structure(doc, block.structure)


def _walk_blocks(document: Document):
    """Itera todos os blocos recursivamente (estrutura em ordem de leitura)."""
    for page in document.pages:
        yield from _walk_structure(document, page.children)


def find_equations(document: Document) -> list[EqSpec]:
    """Equações display com html do VLM, em ordem de leitura."""
    eqs = [
        EqSpec(
            page_id=block.page_id,
            bbox=tuple(block.polygon.bbox),
            alt=sanitize_alt(block.html),
            block=block,
        )
        for block in _walk_blocks(document)
        if block.block_type == BlockTypes.Equation and block.html
    ]
    eqs.sort(key=lambda e: (e.page_id, e.bbox[1]))
    return eqs


def mutate_blocks(eqs: list[EqSpec]) -> None:
    """Substitui o html de cada bloco Equation por uma tag <img>.

    Deve ser chamado ANTES do render markdown. `eq.image` deve conter o
    nome do arquivo relativo ao diretório do markdown (ex: eq_images/eq_p4_01.png).
    """
    for eq in eqs:
        if not eq.image:
            continue
        eq.block.html = f'<img src="{eq.image}" alt="{eq.alt}">'
