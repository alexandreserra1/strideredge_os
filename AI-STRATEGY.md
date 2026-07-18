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
- **[FEITO — pipeline] treinado (Random Forest)** (`analytics/injury_model.py` + `injury_synth.py`).
  O `RiskModel` treina com **class weights** (não SMOTE), avalia por **PR-AUC**, valida **subject-wise**
  (GroupKFold quando há `user_id`, senão StratifiedKFold), e o `predict()` devolve a **MESMA interface**
  do `assess` (drop-in prior→treinado; `form_coach` não muda). Banda vem da probabilidade do RF; peso
  do fator vem de `feature_importances_`; explicação/citação reusa `diagnose`.
  - **Honestidade:** hoje treina em **dados sintéticos** aterrados nas faixas citadas (`injury_synth`).
    O RF reaprende a regra gerada (PR-AUC=1.0 = circular) → **prova o encanamento, não a validade
    preditiva**. Serve pra travar interface/serialização/avaliação antes do dado real.
  - **Próximo — dado real:** trocar o sintético por `injury_dataset.build_dataset` (outcomes dos
    usuários) OU um dataset externo permissivo (ver "Dados externos" abaixo). Faltam ainda: calibração
    Platt/isotonic e o wire do modo `treinado` no `form_coach` (hoje o coach usa o `prior`).

### Taxonomia + coleta (OSTRC) + ponte pro ML — a fundação do outcome

- **[FEITO] `analytics/injury_taxonomy.py`**: vocabulário controlado (região + diagnóstico) das 6
  lesões dominantes de corrida. Guarda 3 mapas citáveis:
  1. **`lesão` (o rótulo `y`)** — sem taxonomia não há classe pra prever.
  2. **`lesão↔fatores biomecânicos`** — QUAIS métricas de `biomechanics.ideal_targets` a literatura
     liga a cada lesão (PFP/ITBS ← `pelvic_drop_deg`+`knee_valgus_deg`; MTSS/fratura ← `cadence_spm`).
     Hoje é referência pra `validate_literature_model`; no modelo treinado vira o PRIOR que regulariza
     com pouco dado. **As 6 lesões têm mapa (`mapped=True`) com fonte citável.** Fascite/Aquiles usam
     fatores PROXY de carga (`cadence_spm`+`vertical_oscillation_pct` / `cadence_spm`+`knee_contact_deg`)
     porque o risco primário delas (dorsiflexão/pronação do pé) **não é medível com o pose COCO-17
     atual** — migra pra fator primário quando o motor subir p/ Halpe26 (ver `docs/adr/0001`). Mapa
     só onde há fonte.
  3. **`fator↔exercício`** (`analytics/exercises.py`, seed) — biblioteca determinística e citada que o
     FormCoach pode usar como fonte de verdade (o LLM personaliza a entrega, não inventa exercício).
- **[FEITO] Coleta**: `injury_reports` (migration 014) + `InjuryService` (`api/injuries.py`, espelha
  `ProfileService`) grava as 4 perguntas OSTRC (0–3) por lesão; severidade 0–100 computada na leitura.
  Endpoints autenticados `POST/GET /api/v1/injuries`.
- **[FEITO] Ponte análise↔lesão (`analytics/injury_dataset.py`)**: lesão é LONGITUDINAL — correlaciona
  com o padrão biomecânico ANTES do onset, não um vídeo isolado. Pré-requisito: `form_analyses.user_id`
  (migration 015, capturado do token no upload, opcional — convidado fica NULL).
  - `build_dataset(window_weeks=8)`: junta lesão × análises do atleta na janela anterior → exemplo
    rotulado `(X=fatores médios, y)`. **A REGIÃO é o `y` primário** (confiável, vem do mapa corporal);
    `diagnosis` é rótulo opcional e mais fino. Filtra `diagnosis IS NOT NULL + valid_diagnosis` (trava
    de integridade no CONSUMIDOR — a API fica permissiva de propósito).
  - `validate_literature_model()`: o que dá pra fazer JÁ com poucos casos — checa se as análises
    anteriores flaguearam os fatores que a taxonomia liga àquela lesão (face-validity do prior contra
    outcome REAL, antes de treinar).
- **[FEITO] Tela "Minhas lesões"** (`frontend`, rota `/lesoes`) — fonte principal do dataset.
  **Reframe importante:** o atleta NÃO auto-diagnostica (não somos médicos + gera rótulo lixo). Marca
  ONDE dói num **mapa muscular anatômico clicável** (`react-body-highlighter`, MIT) → a **região** é o
  `y` estruturado; o diagnóstico virou **texto livre opcional** (sintoma/laudo) — contexto do coach e
  candidato a rótulo via o classificador LLM (abaixo). OSTRC por região; cada região = uma linha
  (append-only). `symptom_text` na migration 016. Migrations rodam no boot da API.

### Classificador LLM texto→diagnóstico (coach-time — refina o rótulo)

- **Objetivo:** o `symptom_text` livre ("dói ao descer escada") → um diagnóstico da taxonomia (`pfp`…).
  Produz o rótulo FINO que refina a região; a região já rotula sozinha, então isto é upgrade, não
  bloqueador.
- **Design (anti-alucinação):** classificação de **conjunto FECHADO com abstenção**, não geração livre.
  A região já é conhecida (mapa) → prior: só os diagnósticos daquela região são candidatos
  (`diagnoses_for_region`). O LLM (`OllamaClient`, mesmo Qwen local) devolve `{diagnosis|null, confiança}`;
  valida contra a taxonomia; se não casar → `null`. Abstenção não polui o dataset (o guardrail de
  `build_dataset` já barra `diagnosis` nulo/inválido).
- **Quando:** coach-time (preguiçoso), não no submit do form (sem latência de LLM no clique). Grava só
  com confiança alta. **Status: desenhado, ainda não implementado.**

### Dados externos + licença (fusão de estudos)

- **Datasets públicos existem e casam com nossas features:** Running Injury Clinic (N=1.798, Nature
  Sci Data 2024) tem rótulo de lesão (pfp/itbs/aquiles/plantar) + OSTRC-style + cadência/queda pélvica/
  flexão de joelho — 4 das nossas 8 features batem direto, 4 são deriváveis. Fukuchi (PMC5426356) é
  CC-BY mas SEM rótulo de lesão (só calibração).
- **Bloqueio:** a licença do Running Injury Clinic é ambígua/NC-ND (não confirmada pra uso comercial).
  Pendência: confirmar no Figshare+, ou achar rotulado+permissivo. Uso não-comercial (portfólio) é ok.
- **Domain shift:** datasets são 3D de laboratório; nós somos 2D de vídeo → treinar a estrutura no
  externo e **recalibrar** no dado dos usuários (prior→treinado, mesma interface).
- **Fusão de estudos honesta:** meta-análise das **estatísticas PUBLICADAS** (odds ratios / médias por
  grupo), não do dado bruto — estatística resumida não tem copyright → **sem problema de licença**. É a
  forma legalmente limpa de "combinar estudos" no modelo.

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
