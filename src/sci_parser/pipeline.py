"""Orquestração do pipeline sci-parser.

Fluxo (ver PLAN.md):
  marker build_document → find_equations → crop 300dpi → mutate <img>
  → re-render markdown → salvar md + figuras → formato (pandoc) → report
"""

import json
import sys
from argparse import Namespace
from pathlib import Path

from sci_parser.cropper import crop_equations
from sci_parser.equations import EqSpec, find_equations, mutate_blocks
from sci_parser.formats import convert, extract_title
from sci_parser.runner import MarkerRunner

from marker.schema import BlockTypes


def _save_markdown_assets(out_dir: Path, stem: str, markdown: str, images: dict) -> Path:
    """Salva o markdown final e as figuras extraídas pelo marker."""
    for img_name, img in images.items():
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out_dir / img_name)
    md_path = out_dir / f"{stem}.md"
    md_path.write_text(markdown)
    return md_path


def _count_blocks(document, types) -> int:
    """Conta blocos (inclusive aninhados) dos tipos dados, deduplicados por id.

    Um Table aparece tanto como child da página quanto dentro do TableGroup
    que o agrupa — sem deduplicação, cada tabela real conta 2-3x.
    """
    seen: set[str] = set()
    n = 0

    def walk(block):
        nonlocal n
        bid = str(block.id)
        if bid in seen:
            return
        seen.add(bid)
        if block.block_type in types:
            n += 1
        for child_id in block.structure or []:
            walk(document.get_block(child_id))

    for page in document.pages:
        for bid in page.children:
            walk(document.get_block(bid))
    return n


def execute(args: Namespace, out_dir: Path) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.pdf.stem

    print(f"[1/4] parseando {args.pdf.name} com marker (modelos na primeira execução)...",
          file=sys.stderr)
    runner = MarkerRunner()
    document = runner.build(args.pdf)

    if args.keep_latex_equations:
        eqs: list[EqSpec] = []
        print("[2/4] --keep-latex-equations: equações mantidas como LaTeX nativo",
              file=sys.stderr)
    else:
        eqs = find_equations(document)
        print(f"[2/4] {len(eqs)} equações detectadas; recortando a {args.dpi} DPI...",
              file=sys.stderr)
        crop_equations(args.pdf, eqs, out_dir, dpi=args.dpi)
        mutate_blocks(eqs)

    print("[3/4] renderizando markdown...", file=sys.stderr)
    from marker.renderers.markdown import MarkdownRenderer

    md_output = MarkdownRenderer()(document)
    md_path = _save_markdown_assets(out_dir, stem, md_output.markdown, md_output.images)

    final_path = md_path
    if args.format != "md":
        title = extract_title(args.pdf, args.title)
        final_path = convert(md_path, args.format, title, out_dir)
        print(f"[4/4] {args.format}: {final_path}", file=sys.stderr)
    else:
        print(f"[4/4] markdown: {md_path}", file=sys.stderr)

    if not args.no_report:
        report = {
            "pdf": str(args.pdf),
            "format": args.format,
            "pages": len(document.pages),
            "equations": {"found": len(eqs), "cropped": len(eqs)},
            "figures": len(md_output.images),
            "tables": _count_blocks(document, (BlockTypes.Table,)),
            "output": {
                "markdown": str(md_path),
                "final": str(final_path),
                "dir": str(out_dir),
            },
        }
        (out_dir / "report.json").write_text(json.dumps(report, indent=2))

    return 0
