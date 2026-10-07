"""Integração com o marker 2.0 em passada única de inferência.

O `PdfConverter.build_document()` executa todo o pipeline (layout, OCR,
equações, tabelas) e retorna o `Document` com todos os blocos — permitindo
mutar os blocos de equação ANTES do render markdown (ver equations.py).
"""

from pathlib import Path

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.renderers.markdown import MarkdownOutput, MarkdownRenderer
from marker.schema.document import Document


class MarkerRunner:
    """Carrega os modelos lazy e converte PDF → (Document, MarkdownOutput)."""

    def __init__(self) -> None:
        self._converter: PdfConverter | None = None

    def _ensure_models(self) -> PdfConverter:
        if self._converter is None:
            self._converter = PdfConverter(artifact_dict=create_model_dict())
        return self._converter

    def build(self, pdf_path: Path) -> Document:
        """Executa o pipeline do marker e retorna o Document (blocos mutáveis)."""
        converter = self._ensure_models()
        return converter.build_document(str(pdf_path))

    def run(self, pdf_path: Path) -> tuple[Document, MarkdownOutput]:
        document = self.build(pdf_path)
        md_output = MarkdownRenderer()(document)
        return document, md_output
