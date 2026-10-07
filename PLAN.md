# Plan: sci-parser — CLI marker + eq-images

**Goal:** CLI production-grade (`sci-parser paper.pdf`) que converte PDFs científicos para markdown (default) ou docx/html/epub/txt via `--format`, com equações preservadas como imagens 300 DPI (fidelidade pixel-perfect) e figuras/tabelas nativas do marker 2.0.

**Approach:** Uma única passada de inferência do marker (Python API: `PdfConverter.build_document()` + `MarkdownRenderer`), com mutação dos blocos `Equation` para tags `<img>` **antes** do render — o markdownify posiciona as refs `![alt](src)` automaticamente na posição exata de leitura (elimina a cirurgia de markdown do PoC). Crops das equações via PyMuPDF. Conversão final via pandoc com flags específicas por formato (validadas nos experimentos). Relatório de validação com contagens por página.

---

## Decisões de design verificadas (fonte dos requisitos abaixo)

1. **API do marker 2.0** (lida em `.venv-marker/.../marker/`):
   - `PdfConverter(artifact_dict=create_model_dict(), config={...})` — construtor com `renderer=None` → default `MarkdownRenderer`; `processor_list=None` → defaults
   - `converter.build_document(pdf_path)` → `Document` completo (blocos + bboxes) **antes** do render; `converter(fpath)` = `build_document` + render
   - `MarkdownRenderer()(document)` → `MarkdownOutput(markdown=..., images=..., metadata=...)`
   - Bloco: `block.page_id` (0-based, alinha com `pymupdf.doc[page_id]`), `block.polygon.bbox` (pontos PDF), `block.html` (Equation carrega o LaTeX best-effort), `block.structure` (BlockIds filhos), `BlockTypes.Equation`
   - `metadata["page_stats"]` tem `block_counts` por página (fonte do relatório)
2. **Markdownify** (o conversor html→md do marker) **não sobrescreve** `convert_img`; o default do markdownify emite `![alt](src)`. Logo: mutar `equation_block.html = '<img src="..." alt="...">'` antes do render → ref de imagem na posição correta automaticamente
3. **Pandoc** (validado nos experimentos): html exige `--embed-resources --standalone`; epub/docx exigem `--metadata title=` (epub **falha** sem título); imagens resolvem por cwd do arquivo md ou `--resource-path`; md do marker usa math `$...$` (compatível com o reader default)
4. **Dependências externas**: `pandoc` (brew) e `llama-server` (brew llama.cpp — o marker 2.0 o exige para equações; spawn/killed automático pelo marker). Primeira execução baixa modelos Surya (~2GB, cache)
5. **Números esperados** no fixture `attention.pdf`: 5 equações, 5 figuras, 4 tabelas

---

## Critical Files

- `pyproject.toml`: projeto uv, deps `marker-pdf==2.0.0` + `pymupdf`, console script `sci-parser`, pytest
- `src/sci_parser/cli.py`: argparse (contract completo), checks de ambiente, orquestração
- `src/sci_parser/runner.py`: `MarkerRunner` — `create_model_dict` + `build_document` (passada única)
- `src/sci_parser/equations.py`: walk recursivo do Document → `EqSpec(page_id, bbox, alt, block)`; sanitização do alt; mutação `block.html` → `<img>`
- `src/sci_parser/cropper.py`: PyMuPDF `get_pixmap(clip=Rect, dpi)` com margem 3pt; nome determinístico `eq_images/eq_p{page+1}_{n:02d}.png`
- `src/sci_parser/formats.py`: pandoc por formato + pré-processamento txt (refs de imagem → alt text)
- `src/sci_parser/report.py`: `report.json` com contagens e paths
- `tests/data/attention.pdf`: fixture (copiar de `/tmp/sci-test/pdfs/attention.pdf`)
- `poc/`: mantido como referência (não faz parte do pacote)

---

## Tasks

### Task 1: Scaffold do projeto
- [x] `git init` (se necessário), `.gitignore` com `.venv*`, `__pycache__`, `dist`, `_parsed/`
- [x] `pyproject.toml`: `[project]` name `sci-parser`, requires-python `>=3.11,<3.12`, deps `marker-pdf==2.0.0`, `pymupdf>=1.28`; `[project.scripts] sci-parser = "sci_parser.cli:main"`; `[dependency-groups] dev = ["pytest"]`; build backend hatchling
- [x] `uv sync --python 3.11` → valida resolução de deps (não usar o `.venv-marker` existente; venv nova `.venv`)
- [x] Estrutura vazia `src/sci_parser/__init__.py` com `__version__ = "0.1.0"`
- [x] Copiar `tests/data/attention.pdf` (de `/tmp/sci-test/pdfs/attention.pdf`)
- [x] Commit: `chore: scaffold do projeto com uv e estrutura src`

### Task 2: CLI skeleton + checks de ambiente
- [x] `src/sci_parser/cli.py`: argparse com contract exato:
  - positional `pdf` (valida existência + sufixo `.pdf`)
  - `--format {md,docx,txt,html,epub}` default `md`
  - `-o/--output` default `<cwd>/<stem>_parsed`; **erro se dir existe e não-vazio** (mensagem com dica de `-o`)
  - `--dpi` (default 300), `--title` (default: metadata do PDF ou stem), `--keep-latex-equations` (desativa eq-images), `--no-report`
- [x] Checks de ambiente (função `check_environment()`): `shutil.which("pandoc")` e `shutil.which("llama-server")` → erro claro com comando de instalação (`brew install pandoc llama.cpp`)
- [x] `tests/test_cli.py`: argparse aceita formats válidos, rejeita inválido; output dir existente não-vazio → erro; checks de ambiente com PATH sem pandoc → erro (monkeypatch `shutil.which`)
- [x] Commit: `feat(cli): skeleton com contract de formatos e checks de ambiente`

### Task 3: MarkerRunner (passada única)
- [x] `src/sci_parser/runner.py`: classe `MarkerRunner` com `run(pdf_path) -> tuple[Document, MarkdownOutput]`:
  ```python
  models = create_model_dict()
  converter = PdfConverter(artifact_dict=models)   # defaults: mode fast em MPS/CPU
  document = converter.build_document(str(pdf_path))
  md_output = MarkdownRenderer()(document)
  ```
- [x] Manter referência do `document` viva (returned tuple) — os blocos mutados no Task 5 precisam do mesmo objeto
- [x] `tests/test_integration.py` (gated por `os.environ.get("SCI_PARSER_SKIP_INTEGRATION")`): `MarkerRunner().run(attention.pdf)` retorna markdown contendo "Attention Is All You Need" e `md_output.images` com 5 entradas; dura ~90s
- [x] Commit: `feat(runner): integracao marker 2.0 em passada unica via python api`

### Task 4: Descoberta de equações
- [x] `src/sci_parser/equations.py`: função `find_equations(document) -> list[EqSpec]` — walk recursivo: para cada `page` em `document.pages`, para cada block id em `page.children`, `document.get_block(id)`, recursão via `block.structure`; coletar `block.block_type == BlockTypes.Equation` com `block.html` não-nulo
- [x] `EqSpec` (dataclass): `page_id: int`, `bbox: tuple[float, float, float, float]` (de `block.polygon.bbox`), `alt: str` (html do bloco → strip tags, colapsar whitespace, remover `[` `]`, limitar 200 chars), `block` (referência para mutação)
- [x] Ordenar por `(page_id, bbox[1])` (ordem de leitura)
- [x] `tests/test_equations.py`: walk com fake duck-typed (objetos simples com `block_type`, `polygon.bbox`, `structure`, `children`) — 3 páginas, equação aninhada em grupo, uma com `html=None` (ignorada), uma em página posterior; alt sanitizado corretamente
- [x] Commit: `feat(equations): descoberta recursiva de blocos equation com alt text sanitizado`

### Task 5: Cropper + mutação de blocos
- [x] `src/sci_parser/cropper.py`: `crop_equations(pdf_path, eqs, out_dir, dpi=300, margin=3.0)` — para cada `EqSpec`: `pymupdf.Rect(bbox[0]-margin, ...)` + `doc[page_id].get_pixmap(clip=rect, dpi=dpi)` → salvar em `out_dir/eq_images/eq_p{page_id+1}_{n:02d}.png`; retornar lista de `(EqSpec, filename)`
- [x] Em `equations.py`: `mutate_blocks(eqs_with_files, keep_latex=False)` — para cada `(eq, fname)`: `eq.block.html = f'<img src="eq_images/{fname}" alt="{eq.alt}">'`
- [x] Fluxo no `cli.py` (ainda sem formatos): runner → find_equations → crop → mutate → **re-render** `MarkdownRenderer()(document)` → salvar `<stem>.md` + `md_output.images` (figuras, via `marker.output.save_output` ou loop manual `img.save(out_dir / name)`)
- [x] `tests/test_cropper.py`: PDF sintético gerado com pymupdf (uma página, texto + retângulo desenhado); recorte de bbox conhecido → assert dimensões do PNG ≈ `(w - 2*margin) * dpi/72`
- [x] `tests/test_integration.py`: com attention.pdf → 5 eqs descobertas, 5 PNGs em `eq_images/`, markdown final contém 5 refs `![...](eq_images/...)` e **zero** pipe-tables com `$` (regressão do bug do PoC); com `--keep-latex-equations` → 0 refs de eq_images
- [x] Commit: `feat(equations): crops 300dpi via pymupdf e mutacao de blocos para img`

### Task 6: Formatos de saída (pandoc)
- [x] `src/sci_parser/formats.py`: `convert(md_path, out_dir, fmt, title, pdf_path)`:
  - `md`: no-op (já salvo)
  - `html`: `pandoc <md> -t html -o <stem>.html --embed-resources --standalone --metadata title=<title>` com `cwd=out_dir` (resolve refs relativas — aprendido no PoC)
  - `docx`: `pandoc <md> -t docx -o <stem>.docx --metadata title=<title> --resource-path <out_dir>`
  - `epub`: idem docx com `-t epub` (title obrigatório)
  - `txt`: **pré-processar** md (regex `!\[([^\]]*)\]\(([^)]+)\)` → alt text para eqs com alt, remover linhas de figuras sem alt) → `pandoc -f markdown -t plain -o <stem>.txt`
- [x] Extrair `title` default: `pymupdf.open(pdf).metadata.get("title")` ou stem
- [x] `tests/test_formats.py`: md fixture pequeno (heading + tabela + `![eq](img.png)` + imagem real 1x1 px) em tmp_path; converter nos 4 formatos; asserts: html contém `data:image` (2 embutidas), docx/epub existem e não-vazios (epub: `unzip -p` confirma title no OPF), txt contém o alt text da equação e não contém `![`
- [x] `tests/test_integration.py`: attention.pdf com `--format docx` → docx gerado com 10 imagens embutidas (`unzip -l` conta `word/media`)
- [x] Commit: `feat(formats): conversao pandoc para docx/html/epub/txt com preprocessing`

### Task 7: Relatório de validação
- [x] `src/sci_parser/report.py`: `build_report(document, eqs, figs, out_dir, fmt) -> dict` com: `pages`, `equations: {found, cropped}`, `figures` (len `md_output.images`), `tables` (contagem de `BlockTypes.Table*` no walk), `output: {format, paths}`; escrever `report.json`
- [x] `tests/test_report.py`: fake document → report correto; arquivo escrito com JSON válido
- [x] Commit: `feat(report): relatorio de validacao com contagens por tipo de bloco`

### Task 8: End-to-end + docs
- [x] `cli.py` final: sequência check_environment → MarkerRunner → (find/crop/mutate | skip) → re-render → save → formats → report; saídas de progresso em stderr (pandoc silencioso), resumo final com paths
- [x] Teste manual completo: `uv run sci-parser tests/data/attention.pdf --format html` → abrir HTML e revisar: 5 equações como imagem, 5 figuras, 4 tabelas, math inline residual (limitação conhecida — documentar no README)
- [x] `README.md`: instalação (brew pandoc/llama.cpp, `uv sync`), primeiro run baixa modelos, uso, formatos, limitações conhecidas (math inline degradado; equações são imagens → não pesquisáveis, alt text carrega LaTeX best-effort), arquitetura
- [x] `tests/test_integration.py`: rodada final completa nos 5 formatos (parametrizada), asserts consolidados
- [x] Commit: `docs(readme): uso, instalacao e limitacoes conhecidas`
- [x] Commit final: `chore: release v0.1.0`

---

## Verificação por task (comandos)

- Tasks 1–2, 4, 6–7: `uv run pytest -x -q` (rápido, sem modelos)
- Tasks 3, 5, 8: `uv run pytest -x -q tests/test_integration.py` (baixa modelos na 1ª vez; ~2–4 min por paper no M4 Pro)
- Smoke manual: `uv run sci-parser tests/data/attention.pdf` → `<stem>.md` + `eq_images/` + figuras + `report.json`

## Fora de escopo (v1)

- Validação por text-layer diff (frases perdidas) — evolução futura do `report.py`
- `--mode` passthrough do marker (balanced/fast) e `--use-llm`
- Crops de tabelas como imagem (mesma mecânica de eq, extensível depois)
- Cache/resume por página
