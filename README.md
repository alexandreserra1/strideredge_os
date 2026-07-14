# StriderEdge OS

[![CI](https://github.com/alexandreserra1/strideredge_os/actions/workflows/ci.yml/badge.svg)](https://github.com/alexandreserra1/strideredge_os/actions/workflows/ci.yml)

**IA de visão computacional para prevenção de lesão na corrida.** O atleta filma a própria
corrida com o celular; um motor de pose em **Rust** (`stride_vision`) extrai a biomecânica
(cadência, pisada, ângulos, tempo de contato/voo, assimetria); e um **coach de IA local**
(Ollama/Qwen) com **RAG citável** traduz os desvios num plano corretivo com exercícios e fontes
científicas. Autossuficiente: só precisa de uma câmera, 100% no aparelho.

> **Pivot (jul/2026):** o projeto começou como ecossistema de biotelemetria `.FIT` (Garmin/Strava)
> e focou-se só na análise de forma por vídeo — o diferencial que os concorrentes não têm. A stack
> `.FIT` (ingestão, DuckDB star schema, kernel Rust numérico, coach de treino, dashboards) foi
> removida; recuperável na tag git `archive/fit-full-app`.

## Arquitetura

```
Frontend web (React/Vite)  ──REST──►  API (FastAPI, controllers finos)
                                          │
   upload de vídeo ──► fila de jobs (core/jobs.py) ──► worker:
       ffmpeg (transcode) → stride_vision (pose YOLO11 via ONNX) → métricas (JSON)
                                          │
   plano corretivo ◄── FormCoach ◄── RAG híbrido (denso+BM25 + reranking + grounding)
                                          │
   Dados: DuckDB (auth, análises, perfil) · base RAG num .db separado (bge-m3)
```

**O que faz:** pose estimation por vídeo → biomecânica (cadência via FFT, contato/voo, ângulos
articulares no apoio, inclinação de tronco, assimetria, pisada) com guarda de confiabilidade;
diagnóstico determinístico (medido × ideal personalizado); plano corretivo com exercícios citados
(RAG híbrido + reranking + grounding anti-alucinação, fontes PMC/DOI/PubMed).

## Stack

Python · **Rust** (`stride_vision`, motor de pose standalone via ONNX) · **DuckDB** ·
**Ollama** (Qwen 7B + 1.5B rerank + bge-m3) · FastAPI · React/Vite · structlog. Sem custo de token.

## Como rodar

Pré-requisitos: Python 3.9+, [Rust](https://rustup.rs), [Ollama](https://ollama.com), Node, ffmpeg.

```bash
# 1. ambiente Python
python -m venv .venv && source .venv/bin/activate
pip install ".[dev]"

# 2. motor de visão (Rust standalone) + modelos locais
cargo build --release --manifest-path stride_vision/Cargo.toml
ollama pull qwen2.5:7b-instruct && ollama pull qwen2.5:1.5b-instruct && ollama pull bge-m3
ollama serve &                                    # deixa rodando
python -m rag.knowledge_base                       # indexa o corpus de ciência do esporte

# 3. subir API + frontend
uvicorn api.main:app --port 8000                   # http://localhost:8000
cd frontend/apps/web && npm install && npm run dev # http://localhost:5173
```

## Testes

```bash
pytest -q -k "not e2e"   # suíte hermética (unit + RAG eval + segurança); Ollama pula sem servidor
```

Suíte **hermética** (banco temporário) — roda em qualquer máquina e no CI, sem dados pessoais.

## Documentação

- [`CLAUDE.md`](CLAUDE.md) — contexto e comandos (o mais atualizado).
- [`constitution.md`](constitution.md) — princípios não-negociáveis (critério de desempate).
- [`plan.md`](plan.md) — arquitetura e roadmap.
- [`AI-STRATEGY.md`](AI-STRATEGY.md) — roteiro de IA/ML (RAG avançado, evals, visão/risco de lesão).
- [`frontend-spec.md`](frontend-spec.md) — spec do frontend web.
