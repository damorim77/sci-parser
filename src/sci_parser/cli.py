"""CLI entry point e orquestração do pipeline sci-parser."""

import shutil
import sys
from argparse import ArgumentParser, Namespace
from pathlib import Path

from sci_parser import __version__

FORMATS = ("md", "docx", "txt", "html", "epub")

MISSING_TOOLS = {
    "pandoc": "brew install pandoc",
    "llama-server": "brew install llama.cpp",
}


def build_parser() -> ArgumentParser:
    parser = ArgumentParser(
        prog="sci-parser",
        description=(
            "Parse scientific PDFs to markdown (default), docx, txt, html or epub. "
            "Equations are preserved as high-DPI images; figures and tables are "
            "extracted natively by marker."
        ),
    )
    parser.add_argument("pdf", type=Path, help="caminho do PDF de entrada")
    parser.add_argument(
        "--format",
        choices=FORMATS,
        default="md",
        help="formato de saída (default: md)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help=(
            "diretório de saída (default: <cwd>/<stem>_parsed; "
            "erro se existir e não estiver vazio)"
        ),
    )
    parser.add_argument(
        "--dpi", type=int, default=300, help="DPI dos recortes de equação (default: 300)"
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="título do documento para epub/docx/html (default: metadata do PDF ou stem)",
    )
    parser.add_argument(
        "--keep-latex-equations",
        action="store_true",
        help="desativa eq-images; mantém o LaTeX nativo do marker nas equações",
    )
    parser.add_argument(
        "--no-report", action="store_true", help="não escrever report.json"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def check_environment() -> None:
    """Valida binários externos obrigatórios (pandoc, llama-server)."""
    missing = [tool for tool in MISSING_TOOLS if shutil.which(tool) is None]
    if missing:
        lines = ["dependências externas ausentes:"]
        for tool in missing:
            lines.append(f"  - {tool}: instale com `{MISSING_TOOLS[tool]}`")
        raise SystemExit("\n".join(lines))


def validate_args(args: Namespace) -> None:
    pdf: Path = args.pdf
    if not pdf.exists():
        raise SystemExit(f"erro: PDF não encontrado: {pdf}")
    if pdf.suffix.lower() != ".pdf":
        raise SystemExit(f"erro: arquivo de entrada não é um PDF: {pdf}")


def resolve_output_dir(args: Namespace) -> Path:
    out: Path = args.output if args.output is not None else Path.cwd() / f"{args.pdf.stem}_parsed"
    if out.exists() and any(out.iterdir()):
        raise SystemExit(
            f"erro: diretório de saída existe e não está vazio: {out}\n"
            f"      use -o para escolher outro diretório"
        )
    return out


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    check_environment()
    validate_args(args)
    out_dir = resolve_output_dir(args)

    from sci_parser.pipeline import execute

    return execute(args, out_dir)


if __name__ == "__main__":
    sys.exit(main())
