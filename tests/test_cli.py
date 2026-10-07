"""Testes do CLI: contract de argumentos, validações e checks de ambiente."""

import pytest

from sci_parser.cli import (
    FORMATS,
    build_parser,
    check_environment,
    resolve_output_dir,
    validate_args,
)


def _parse(pdf, kw):
    argv = [str(pdf)]
    if kw.get("format"):
        argv += ["--format", kw["format"]]
    if kw.get("output"):
        argv += ["-o", str(kw["output"])]
    if kw.get("dpi"):
        argv += ["--dpi", str(kw["dpi"])]
    if kw.get("title"):
        argv += ["--title", kw["title"]]
    if kw.get("keep_latex_equations"):
        argv += ["--keep-latex-equations"]
    if kw.get("no_report"):
        argv += ["--no-report"]
    return build_parser().parse_args(argv)


class TestParser:
    def test_format_default_md(self, tmp_path):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        args = _parse(pdf, {})
        assert args.format == "md"

    @pytest.mark.parametrize("fmt", FORMATS)
    def test_formats_validos(self, tmp_path, fmt):
        pdf = tmp_path / "paper.pdf"
        args = _parse(pdf, {"format": fmt})
        assert args.format == fmt

    def test_format_invalido_rejeitado(self, tmp_path, capsys):
        pdf = tmp_path / "paper.pdf"
        with pytest.raises(SystemExit):
            build_parser().parse_args([str(pdf), "--format", "rtf"])

    def test_dpi_default_300(self, tmp_path):
        args = _parse(tmp_path / "p.pdf", {})
        assert args.dpi == 300


class TestValidateArgs:
    def test_pdf_inexistente(self, tmp_path):
        args = _parse(tmp_path / "nope.pdf", {})
        with pytest.raises(SystemExit, match="não encontrado"):
            validate_args(args)

    def test_arquivo_nao_pdf(self, tmp_path):
        f = tmp_path / "paper.txt"
        f.write_text("x")
        args = _parse(f, {})
        with pytest.raises(SystemExit, match="não é um PDF"):
            validate_args(args)

    def test_pdf_valido_passa(self, tmp_path):
        f = tmp_path / "paper.pdf"
        f.write_bytes(b"%PDF-1.4")
        validate_args(_parse(f, {}))


class TestOutputDir:
    def test_default_e_cwd_stem_parsed(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pdf = tmp_path / "paper.pdf"
        out = resolve_output_dir(_parse(pdf, {}))
        assert out == tmp_path / "paper_parsed"

    def test_output_custom(self, tmp_path):
        pdf = tmp_path / "paper.pdf"
        custom = tmp_path / "saida"
        out = resolve_output_dir(_parse(pdf, {"output": custom}))
        assert out == custom

    def test_dir_existente_nao_vazio_erro(self, tmp_path):
        pdf = tmp_path / "paper.pdf"
        out = tmp_path / "saida"
        out.mkdir()
        (out / "lixo.txt").write_text("x")
        with pytest.raises(SystemExit, match="não está vazio"):
            resolve_output_dir(_parse(pdf, {"output": out}))

    def test_dir_existente_vazio_ok(self, tmp_path):
        pdf = tmp_path / "paper.pdf"
        out = tmp_path / "saida"
        out.mkdir()
        assert resolve_output_dir(_parse(pdf, {"output": out})) == out


class TestCheckEnvironment:
    def test_sem_pandoc_erro(self, monkeypatch):
        monkeypatch.setattr(
            "shutil.which", lambda name: "/bin/llama-server" if name == "llama-server" else None
        )
        with pytest.raises(SystemExit, match="pandoc"):
            check_environment()

    def test_sem_llama_server_erro(self, monkeypatch):
        monkeypatch.setattr(
            "shutil.which", lambda name: "/opt/homebrew/bin/pandoc" if name == "pandoc" else None
        )
        with pytest.raises(SystemExit, match="llama-server"):
            check_environment()

    def test_sem_nada_erro_lista_todos(self, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda name: None)
        with pytest.raises(SystemExit) as exc:
            check_environment()
        assert "pandoc" in str(exc.value) and "llama-server" in str(exc.value)
