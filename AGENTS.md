# AGENTS.md

Instruções para agents de código trabalhando neste repositório.

## O que é este projeto

CLI que converte PDFs científicos para markdown/docx/html/epub/txt. Stack:
**marker 2.0** (layout, OCR, figuras, tabelas) + **PyMuPDF** (recortes de equação
em 300 DPI) + **pandoc** (conversão de formato). Diferencial: equações display
viram imagens pixel-perfect com LaTeX best-effort no alt text, em vez de
conversão LaTeX não-confiável.

## Setup e comandos

```bash
# dependências externas (obrigatórias, checadas pelo CLI no startup)
brew install pandoc llama.cpp

uv sync                                                    # ambiente (Python 3.11 pinned)
uv run sci-parser paper.pdf --format docx                  # uso
uv run pytest                                              # unit tests (rápido, sem modelos)
uv run pytest tests/test_integration.py                    # integração (~30s, precisa modelos)
SCI_PARSER_SKIP_INTEGRATION=1 uv run pytest                # CI sem modelos
```

Primeira execução do marker baixa ~2GB de modelos (cache global em `~/.cache`).
O marker 2.0 faz spawn/kill do `llama-server` automaticamente (log "Force-killed
llamacpp" é normal).

## Arquitetura (pipeline em `src/sci_parser/pipeline.py`)

```
marker build_document()          # passada ÚNICA de inferência
  → find_equations()             # walk recursivo dos blocos Equation
  → crop_equations()             # PyMuPDF: bbox + margem 3pt, 300 DPI
  → mutate_blocks()              # block.html = '<img src=... alt=LaTeX>'
  → MarkdownRenderer()(document) # re-render: markdownify posiciona ![alt](src) sozinho
  → convert()                    # pandoc → docx/html/epub/txt
  → report.json                  # contagens de validação
```

**Decisão central (não "otimizar" sem entender):** a substituição das equações
acontece por mutação de `block.html` ANTES do render markdown — não por regex
sobre o markdown final. O PoC original fazia cirurgia de markdown e era frágil
(pipe-tables com `$`, caso especial hardcoded). Ver `poc/` no histórico do repo.

## Fatos de API verificados (não redescobrir)

- `PdfConverter(artifact_dict=create_model_dict()).build_document(pdf)` retorna
  o `Document` mutável ANTES do render — é isso que permite uma só passada
- `block.page_id` é **0-based** e alinha direto com `pymupdf.doc[page_id]`
- `block.polygon.bbox` está em **pontos PDF** (page polygon 612×792) — mesmo
  espaço de coordenadas do `pymupdf.Rect`
- O `Markdownify` do marker **não** sobrescreve `convert_img`; o default do
  markdownify emite `![alt](src)` — é por isso que a mutação de `<img>` funciona
- Bloco `Equation` carrega o LaTeX best-effort no campo `html`

## Gotchas

1. **Tabelas duplicadas na estrutura do marker**: cada Table aparece como child
   da página E dentro do TableGroup que o agrupa. Ao contar blocos, dedupe por
   `block.id` (ver `_count_blocks` no pipeline)
2. **epub exige `--metadata title=`** — pandoc falha sem título (o extrator usa
   metadata do PDF com fallback pro stem)
3. **pandoc resolve refs de imagem por cwd** — rodar com `cwd=out_dir` (flags já
   corretas em `formats.py`)
4. **txt**: pré-processamos `![alt](src)` → alt text antes do `pandoc -t plain`,
   senão as equações somem do output texto
5. **Fixture de regressão**: `tests/data/attention.pdf` → 5 equações, 5 figuras,
   4 tabelas, 15 páginas. Se essas contagens mudarem, ou o marker mudou de
   comportamento (verificar bump de versão — está pinned `marker-pdf==2.0.0`)
   ou o pipeline quebrou

## Regras de contribuição

- **Nunca commite direto em main** — crie worktree + branch (`feature/...` ou
  `fix/...`). Merges em main são feitos pelo humano
- **TDD**: mudanças de comportamento começam no teste. Unit tests usam fakes
  duck-typed (ver `test_equations.py`) — nunca dependam dos modelos do marker
- Testes de integração sempre gated por `SCI_PARSER_SKIP_INTEGRATION`
- Commits em português, formato `feat(module):`, `fix(module):`, `chore:`, `docs:`
- Código e comentários em PT-BR; identificadores em inglês

## Fora de escopo (candidatos a v2 — ver PLAN.md)

- Validação por text-layer diff (frases perdidas pelo OCR)
- Crops de tabelas com math como imagem (mesma mecânica das equações)
- Cache/resume por página (rasterização em PNG)
- `--mode` passthrough do marker (balanced/fast) e `--use-llm`

## Limitações conhecidas (documentadas no README — não são bugs)

- Math inline degradado pelo OCR do marker (`d_k` vira `dk`)
- Equações como imagem não são pesquisáveis (alt text carrega o LaTeX)
