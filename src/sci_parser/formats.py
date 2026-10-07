"""Conversão do markdown final para os formatos de destino via pandoc.

Flags validadas nos experimentos:
- html: --embed-resources --standalone (arquivo único com data URIs)
- epub/docx: --metadata title= obrigatório (epub falha sem título)
- recursos: cwd no diretório do markdown resolve refs relativas
- txt: pré-processamos refs de imagem (alt text) antes do pandoc -t plain
"""

import re
import subprocess
from pathlib import Path

import pymupdf

IMG_REF_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


def extract_title(pdf_path: Path, override: str | None = None) -> str:
    """Título: --title > metadata do PDF > stem do arquivo."""
    if override:
        return override
    doc = pymupdf.open(pdf_path)
    try:
        title = (doc.metadata or {}).get("title", "").strip()
    finally:
        doc.close()
    return title or pdf_path.stem


def _to_plain_text(md: str) -> str:
    """Markdown → texto puro: eq images viram o LaTeX do alt; figuras sem alt somem."""

    def repl(match: re.Match) -> str:
        alt, _src = match.group(1), match.group(2)
        return alt if alt.strip() else ""

    return IMG_REF_RE.sub(repl, md)


def convert(md_path: Path, fmt: str, title: str, out_dir: Path) -> Path | None:
    """Converte o markdown para `fmt`. Retorna o arquivo final (None para md)."""
    stem = md_path.stem
    if fmt == "md":
        return None

    if fmt == "txt":
        plain_md = _to_plain_text(md_path.read_text())
        plain_path = out_dir / f"{stem}.plain.md"
        plain_path.write_text(plain_md)
        cmd = ["pandoc", plain_path.name, "-f", "markdown", "-t", "plain",
               "-o", f"{stem}.txt"]
    else:
        cmd = ["pandoc", md_path.name, "-t", fmt, "-o", f"{stem}.{fmt}",
               "--metadata", f"title={title}"]
        if fmt == "html":
            cmd += ["--embed-resources", "--standalone"]

    subprocess.run(cmd, check=True, cwd=out_dir, capture_output=True)
    out = out_dir / f"{stem}.{fmt}"
    if not out.exists():
        raise RuntimeError(f"pandoc não gerou {out}")
    return out
