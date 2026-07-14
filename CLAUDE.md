# StriderEdge OS

**IA de visão computacional para prevenção de lesão na corrida.** O atleta filma a própria
corrida → motor de pose em Rust (`stride_vision`) extrai a biomecânica → o Coach por LLM local
(RAG citável) traduz os desvios num plano corretivo com exercícios e fontes científicas.
Autossuficiente: só precisa de uma câmera, 100% no aparelho, sem depender de API de terceiros.

> **Pivot (jul/2026):** o app deixou de ser um ecossistema de biotelemetria `.FIT` (Garmin/Strava)
> e passou a focar SÓ na análise de forma por vídeo. Toda a stack `.FIT` (ingestão, DuckDB star
> schema, kernel Rust Kalman/DTW/FFT, coach de treino, dashboards) foi removida — recuperável na
> tag git `archive/fit-full-app`. Docs de fases antigas (app/device-spec) podem citar features que
> não existem mais.

## Leia antes de decidir

- **`constitution.md`** — princípios não-negociáveis (critério de desempate de TODA decisão:
  Rust só p/ compute pesado, dado validado, conclusão-pronta pro LLM, sem overengineering, fontes
  citáveis — é app de risco de lesão, etc.). Respeite sempre.
- **`plan.md`** — blueprint de arquitetura.
- **`AI-STRATEGY.md`** — roteiro de IA/ML (RAG avançado, evals, roteiro de visão/risco de lesão).
- **`frontend-spec.md`** — spec do frontend web. Ler ao trabalhar na UI.

## Stack

- **Python** (orquestração, API, LLM, RAG) — build Python puro (setuptools; sem PyO3/maturin).
- **Rust `stride_vision/`** — motor de pose (YOLO11-pose via ONNX) + biomecânica, crate STANDALONE
  rodado por subprocesso. Buildado pelo próprio cargo (`cargo build --release`), NÃO por maturin.
- **DuckDB** (`storage/strideredge.db`) — auth, análises de forma, perfil; conexão reutilizável em
  `core/database.py`. Base RAG num `.db` separado (`storage/knowledge.db`).
- **LLM local via Ollama**: `qwen2.5:7b-instruct` (coach/geração) + `qwen2.5:1.5b-instruct`
  (reranking) + `bge-m3` (embeddings RAG). Sem token.
- **RAG** em `rag/` (busca híbrida densa+BM25, reranking, contextual retrieval, grounding).
- **Frontend** React em `frontend/apps/web` (Vite). O produto = login → análise de forma.

## Comandos

```bash
ollama serve                                       # precisa estar rodando p/ coach/RAG
cargo build --release --manifest-path stride_vision/Cargo.toml   # (re)compila o motor de visão
.venv/bin/python -m rag.knowledge_base             # (re)indexa o corpus RAG
.venv/bin/uvicorn api.main:app --port 8000         # sobe a API
.venv/bin/pytest tests/ -q -k "not e2e"            # suíte hermética
cd frontend/apps/web && npm run dev                # sobe o frontend (localhost:5173)
```

## Contratos OOP (polimorfismo — trocar implementação sem mexer no resto)

`BaseLLMClient`, `BaseEmbedder`, `BaseRetriever`, `BaseGuard` (em `core/framework/interfaces.py`).

## Notas

- **App de prevenção de lesão:** conselho corretivo tem que ser correto e aterrado. Grounding
  anti-alucinação (`analytics/grounding.py`) + fontes citáveis (PMC/DOI/PubMed). Testar o pipeline
  vídeo→IA de ponta a ponta, não só os números.
- Processamento pesado (transcode + pose + métricas) roda em BACKGROUND pela fila de jobs
  (`core/jobs.py`): o upload responde `processing` na hora, o usuário fecha a página e volta depois.
- Degrada gracioso: captura ruim (ângulo não-lateral, fora do quadro) → `reliable=false`, o coach
  avisa pra refilmar em vez de opinar em cima de dado ruim.
- Projeto também é aprendizado: explicar o "porquê" ao construir.
