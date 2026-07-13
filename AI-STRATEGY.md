# StriderEdge — Estratégia de IA (roteiro AI/data-first)

Como transformar o StriderEdge num app **data & AI-first** de verdade, aproveitando o que já
temos (Qwen local + RAG + DuckDB + biomecânica por vídeo). Baseado em pesquisa de práticas de
produção e nos apps correlatos. Também serve ao objetivo de carreira **SWE GenAI** (RAG avançado,
evals, agentes, fine-tuning, guardrails — tudo transferível).

## Onde estamos (base)
- LLM local (Ollama/Qwen) + embeddings (bge-m3) + **RAG citável** (corpus de ~37 estudos reais).
- Guarda de aterramento (`GroundingGuard`) + eval básico. Coach agêntico **text-to-SQL** (DuckDB).
- **Diferencial que os concorrentes não têm:** biomecânica por VÍDEO (câmera→pose→causa-raiz),
  100% local/privado, ciência **citada e auditável**.

## O que os apps correlatos fazem
- **Runna** (comprada pela Strava): plano ADAPTATIVO (fitness+prova+disponibilidade), empurra
  treino pro relógio, reajusta pace conforme os dados. https://www.runna.com/
- **athletedata.health**: agrega Strava/WHOOP/Oura/Hevy, "lê os números reais em tempo real".
- Padrão comum: agregação de dados + IA que adapta. Nosso edge = vídeo + local + ciência citada.

## Roteiro por fases

### Fase 1 — RAG de nível profissional (rápido, alto valor)
RAG ingênuo (só embeddings, o nosso hoje) acerta ~44% dos fatos; com técnicas avançadas ~63%.
1. **[FEITO] Busca híbrida** — embeddings densos + **BM25** (FTS do DuckDB), fusão base=similaridade
   + bônus de desempate (calibrado no conjunto-ouro; sobe com a escala). `rag/knowledge_base.py`.
2. **[FEITO] Reranking** — LLM local como cross-encoder (`rag/rerank.py`), componível, sempre
   ligado no coach corretivo (DESLIGADO no veredito em streaming, por latência do 1º token).
   **Cacheado** (singleton em `deps.py`) + otimizado p/ latência: modelo pequeno dedicado
   (`qwen2.5:1.5b-instruct`, não o 7B do coach), `num_predict` baixo (resposta é só índices),
   `keep_alive` longo (sem troca de modelo a cada chamada), conexão HTTP persistente
   (`httpx.Client` reusado), payload por candidato menor (160 chars) e `fetch_k` 8→6.
3. **[FEITO] Contextual Retrieval** (Anthropic, set/2024): `rag/contextualize.py` gera 1 frase de
   contexto por chunk (LLM 7B, offline no reindex) e injeta SÓ no índice BM25 (`search_text`) —
   o embedding denso continua do texto puro. Achado empírico: prefixar contexto ANTES de embedar
   dilui termo-âncora do chunk (ex: query usa "quicando", o texto tem "quicar", o contexto
   parafraseia pra "oscilação vertical" — a média do vetor se afasta do termo exato que o denso já
   pegava bem). BM25 não sofre esse efeito (só soma vocabulário ao índice invertido) — é onde o
   contexto realmente ajuda nesse corpus de fatos atômicos curtos (diferente do caso original da
   Anthropic, que quebra documentos longos em pedaços que perdem contexto ao redor).
4. **[FEITO] Eval "estilo RAGAS"**: `analytics/coach_eval.py` monta os 4 nomes canônicos
   (Faithfulness, Answer Relevancy, Context Precision, Context Recall) sem instalar o pacote
   `ragas` (evita dependência pesada + chamada padrão a OpenAI) — reusa `CoachEvaluator`
   (Faithfulness, determinístico) + `LLMJudge` (Answer Relevancy, novo critério `relevancia` na
   rubrica) + `Benchmark.context_precision()` (novo) + `retrieval_report()['hit_rate']` (Context
   Recall). `Benchmark.ragas_report()` monta o boletim combinado.

### Fase 2 — superfície AI-first
5. **Coach agêntico**: unificar text-to-SQL (DuckDB) + RAG + métricas de forma num agente que
   PLANEJA ("o que o atleta precisa?") → consulta dados, recupera ciência, sintetiza (Agentic RAG).
6. **Gerador de plano adaptativo** (plan.md §0.3, estilo Runna) aterrado no ACWR/fitness + ciência.
7. Mais fontes de dado (Strava/Garmin live, HRV/sono) alimentando a mesma análise.

### Fase 3 — especialização de modelo (só quando houver dados)
8. **Fine-tune LoRA** (Qwen 1.5–7B) em 500–2000 pares (métricas→veredito/plano) pra travar
   tom+formato+raciocínio → inferência ~10× mais barata, on-device. RAG segue pros FATOS (híbrido).
9. **Analytics no DuckDB sobre a própria IA**: logar retrievals/vereditos, medir quais estudos são
   usados, lacunas de cobertura, eval ao longo do tempo — "dados sobre a IA".

## Princípio (progressão canônica)
prompt → RAG → fine-tune (só quando necessário). RAG = fatos que mudam (estudos). Fine-tune =
comportamento/tom/formato. O melhor é HÍBRIDO. Fontes: orq.ai, First AI Movers, Anthropic, RAGAS.
