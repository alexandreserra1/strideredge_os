# StriderEdge — Estratégia de IA (roteiro AI-first)

> ⚠️ **Pós-pivot (jul/2026):** o app é 100% **visão computacional pra prevenção de lesão**. O
> text-to-SQL e o coach de treino (`.FIT`) saíram; o RAG e os evals **ficam** (aterram o plano
> corretivo do vídeo). O roteiro AI/ML abaixo vale, reorientado pro eixo VÍDEO: pose melhor
> (RTMPose → pisada/pronação reais), **modelo de risco de lesão** (biomecânica → score, aterrado
> na literatura), forma ao longo do tempo (deriva = fadiga/risco), evals RAGAS de tudo isso.

Como aprofundar a IA do StriderEdge, aproveitando o que já temos (Qwen local + RAG citável +
biomecânica por vídeo). Serve ao objetivo de carreira **SWE GenAI** (RAG avançado, evals,
guardrails, visão computacional, ML clássico — tudo transferível).

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
2. **[REMOVIDO — decisão de eval] Reranking** — tínhamos um reranker por LLM local (cross-encoder).
   Medido no golden set (`analytics/rag_eval`, hit@1/hit@2), ele **degradava** a recuperação num
   corpus curado onde a busca híbrida já é forte: base 10/10 no top-2 → com o rerank 1.5b caía a
   7/10; o 7b ficava neutro (8/10 no hit@1 mas 9/10 no top-2) e custava a latência. Também testamos
   reranquear pelo `search_text` (texto+contexto) — não ajudou. **Conclusão eval-driven:** o
   reranker não pagava o próprio custo aqui; removido (`rag/rerank.py` deletado). A lição vale mais
   que a peça: técnica avançada só entra se o eval provar ganho — e num corpus pequeno/curado a
   fusão densa+BM25 já basta. (Reintroduzir faz sentido quando o corpus escalar pra centenas+ de
   fontes, onde reranking rende de verdade.)
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

### Modelo de RISCO de lesão (pós-pivot — o eixo do produto)

- **[FEITO] v1 — score transparente aterrado na literatura** (`analytics/injury_risk.py`). SEM
  outcomes de lesão rotulados, NÃO dá pra treinar um classificador honesto (RF/XGBoost precisam de
  `y` real). O que dá: regressão logística / score aditivo cujos PESOS vêm da força de associação
  publicada de cada fator biomecânico com lesão (cada peso citando a fonte via `biomechanics`). Reusa
  `diagnose` (severidade do desvio) × peso de risco → **FAIXA relativa** (baixo/moderado/elevado/alto)
  + os fatores que a puxaram + caveat. **NUNCA "X% de chance"** (score de log-odds não calibrado não
  promete probabilidade). Alimenta a GenAI: a saída estruturada + o LLM redige/amarra ao corretivo.
- **Próximo — treinado (quando houver dados)**: logar biomecânica por análise + lesão auto-reportada
  ao longo do tempo → dataset rotulado. Aí **random forest / XGBoost** (padrão pra tabular de lesão),
  feito certinho: class weights (não SMOTE, que distorce calibração), **PR-AUC/recall** (não acurácia
  — lesão é rara), calibração Platt/isotonic, validação **subject-wise** (vídeos do mesmo atleta em
  folds ≠ = leakage). Mesma interface: o modelo da literatura é o `prior`; o treinado é o upgrade.

### Fase 2 — superfície AI-first (roteiro amplo — reavaliar pós-pivot)
5. **Coach agêntico**: unificar RAG + métricas de forma + risco num agente que PLANEJA.
6. Comparar forma AO LONGO DO TEMPO (deriva = fadiga/risco) → janela temporal do risco.
7. Mais fatores frontais (RTMPose/Halpe26 → pronação real) alimentando o mesmo modelo de risco.

### Fase 3 — especialização de modelo (só quando houver dados)
8. **Fine-tune LoRA** (Qwen 1.5–7B) em 500–2000 pares (métricas→veredito/plano) pra travar
   tom+formato+raciocínio → inferência ~10× mais barata, on-device. RAG segue pros FATOS (híbrido).
9. **Analytics no DuckDB sobre a própria IA**: logar retrievals/vereditos, medir quais estudos são
   usados, lacunas de cobertura, eval ao longo do tempo — "dados sobre a IA".

## Princípio (progressão canônica)
prompt → RAG → fine-tune (só quando necessário). RAG = fatos que mudam (estudos). Fine-tune =
comportamento/tom/formato. O melhor é HÍBRIDO. Fontes: orq.ai, First AI Movers, Anthropic, RAGAS.
