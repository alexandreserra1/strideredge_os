# StriderEdge OS

Ecossistema local de biotelemetria e analytics esportivo (corrida / Hyrox): ingere
`.FIT` da Garmin → DuckDB → kernel Rust (Kalman/DTW/FFT) → análises → Coach por LLM local.

## Leia antes de decidir

- **`constitution.md`** — princípios não-negociáveis. É o critério de desempate de TODA
  decisão técnica (Rust só p/ compute pesado, dado validado, conclusão-pronta pro LLM,
  sem overengineering, conexão reutilizável, fontes citáveis, etc.). Respeite-os sempre.
- **`plan.md`** — blueprint de arquitetura e fatias de construção.

## Stack

- **Python** (orquestração, API, LLM, RAG) + **Rust via maturin** (`rust_kernel/`, compute pesado).
- **DuckDB** (`storage/strideredge.db`) — Star Schema; conexão reutilizável em `core/database.py`.
- **LLM local via Ollama**: `qwen2.5:7b-instruct` (coach) + `bge-m3` (embeddings RAG). Sem token.
- **RAG** em `rag/` (base curada em `storage/knowledge.db` + fallback de web em domínios confiáveis).
- **Dashboard** Streamlit em `dashboard/app.py` (Hero + abas).

## Comandos

```bash
source "$HOME/.cargo/env"
ollama serve                                   # precisa estar rodando p/ coach/RAG
.venv/bin/maturin develop                      # recompila o kernel Rust após editar .rs
.venv/bin/python -m rag.knowledge_base         # (re)indexa o corpus RAG
.venv/bin/streamlit run dashboard/app.py       # abre o dashboard (localhost:8501)
```

## Contratos OOP (polimorfismo — trocar implementação sem mexer no resto)

`BaseTelemetryParser`, `BaseLLMClient`, `BaseEmbedder`, `BaseRetriever`, `BaseAnalyzer`
(todos em `core/framework/interfaces.py`).

## Notas

- Sempre rodar `maturin develop` após mudar qualquer `.rs` (senão o Python usa o `.so` antigo).
- Ingestão é idempotente (`garmin_activity_id` UNIQUE); re-ingerir não duplica.
- Degrada gracioso sem GPS/altitude (indoor/Hyrox).
- Projeto também é aprendizado: explicar o "porquê" ao construir.
