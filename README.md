# StriderEdge OS

[![CI](https://github.com/alexandreserra1/strideredge_os/actions/workflows/ci.yml/badge.svg)](https://github.com/alexandreserra1/strideredge_os/actions/workflows/ci.yml)

Ecossistema local de **biotelemetria e analytics esportivo** para corrida, HYROX e CrossFit.
Ingere arquivos `.FIT` da Garmin, processa com um kernel numérico em **Rust**, persiste num
**DuckDB**, e entrega insights por um **coach de IA local** (Ollama/Qwen) com RAG citável.

> Visão de produto: um wearable de IA para atletas (inspirado no Amazfit Helio). Hoje roda
> com `.FIT`; o dispositivo próprio é a Fase 3. Ver [`plan.md`](plan.md) e [`constitution.md`](constitution.md).

## Arquitetura

```
Dashboard (Streamlit, cliente HTTP)
   │  REST + gzip
   ▼
API (FastAPI, controllers finos) ──► Serviços OOP: ActivityService · Coach · SqlAgent · TrainingLoad
   ▼
Domínio: analyzers (BaseAnalyzer) · kernel Rust (Kalman/DTW/FFT) · RAG (bge-m3 + DuckDB VSS)
   ▼
Dados: DuckDB (conexão reutilizável)        Ingestão: sync Garmin (.FIT) → idempotente
```

**O que faz:** suavização de GPS (Kalman), ponto de quebra mecânica, eficiência por terreno,
zonas de FC, semáforo de cadência, carga/ACWR (com portão de confiança), coach LLM aterrado
em literatura científica (com fallback de web), personalização por histórico, e text-to-SQL agêntico.

## Stack

Python · **Rust** (PyO3/maturin: kernel de compute) · **DuckDB** · **Ollama** (Qwen 7B + bge-m3) ·
FastAPI · Streamlit · structlog. Sem custo de token (LLM local).

## Como rodar

Pré-requisitos: Python 3.9+, [Rust](https://rustup.rs), [Ollama](https://ollama.com).

```bash
# 1. ambiente + build do kernel Rust
python -m venv .venv && source .venv/bin/activate
pip install ".[dev,dashboard,sync]"
maturin develop

# 2. modelos locais (uma vez)
ollama pull qwen2.5:7b-instruct
ollama pull bge-m3
ollama serve &                                  # deixa rodando

# 3. ingestão automática da Garmin (cria .env a partir do .env.example)
cp .env.example .env                             # preencha GARMIN_EMAIL / GARMIN_PASSWORD
python -m ingestion.garmin_sync 30               # últimos 30 dias
python -m rag.knowledge_base                      # indexa o corpus de ciência do esporte

# 4. subir a API e o dashboard (2 processos)
uvicorn api.main:app                              # http://localhost:8000
streamlit run dashboard/app.py                    # http://localhost:8501
```

## Testes

```bash
pytest -q          # 61 testes (unit + RAG eval + contrato + segurança); E2E/Ollama pulam sem servidor
```

Suíte **hermética** (banco temporário semeado) — roda em qualquer máquina e no CI, sem dados pessoais.
Os testes E2E (cliente HTTP) rodam com a API/Ollama no ar: `pytest tests/test_e2e.py`.

## Documentação

- [`constitution.md`](constitution.md) — princípios não-negociáveis (critério de desempate).
- [`plan.md`](plan.md) — arquitetura, visão de produto e roadmap.
- [`frontend-spec.md`](frontend-spec.md) — spec do frontend web + identidade (mascote StrideFox).
- [`app-spec.md`](app-spec.md) — spec do app mobile (Fase C: insights + voz em tempo real, BLE).
- [`device-spec.md`](device-spec.md) — spec do wearable próprio (Fase 3: firmware, IMU, BLE).
- [`CLAUDE.md`](CLAUDE.md) — contexto pro Claude Code.
