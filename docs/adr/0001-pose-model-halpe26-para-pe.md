# ADR 0001 — Fascite plantar e Aquiles exigem upgrade do modelo de pose (COCO-17 → Halpe26)

- **Status:** aceito (jul/2026)
- **Contexto do achado:** entrevista de design da tela "Minhas lesões" (log OSTRC → dataset de risco).

## Contexto

O produto é monitoramento e predição de lesão de corrida. A taxonomia (`analytics/injury_taxonomy.py`)
cobre as 6 lesões dominantes, mas 2 delas — **fascite plantar** e **tendinopatia do Aquiles** —
estavam `mapped=False` (sem `factors` nem `source`). Investigamos o porquê e a causa NÃO era só
lacuna de corpus RAG.

Os fatores de risco **primários** dessas duas lesões, segundo a literatura, são **dorsiflexão de
tornozelo reduzida** e **pronação/eversão do retropé**. Ambos exigem o *segmento do pé*
(calcanhar → dedos, em relação à canela) para serem medidos.

O motor de pose atual (`stride_vision`) é **YOLO11n-pose com os 17 keypoints do COCO**
(`stride_vision/src/lib.rs`), cujo último ponto da cadeia inferior é o **tornozelo** (índices 15/16).
**Não há keypoints de pé.** Logo, pronação e dorsiflexão são **fisicamente não-medíveis** com o
modelo atual — não é uma métrica que se adiciona em `biomechanics.py`, é uma limitação do conjunto
de keypoints.

## Decisão

1. **Fechar o mapa das 6 agora com fatores PROXY citáveis** (feito nesta rodada). A literatura também
   liga essas lesões a proxies de **carga** que já medimos:
   - `plantar` → `["cadence_spm", "vertical_oscillation_pct"]`, fonte **PMC11878588** (coorte
     prospectiva 4HAIE, 1 ano) — maior taxa de carga vertical associada à fascite.
   - `achilles` → `["cadence_spm", "knee_contact_deg"]`, fonte **PMC9845578** (revisão sistemática,
     2023) — flexão de joelho alterada e cadência como modulador de carga do tendão.

   As 6 ficam `mapped=True`, sem alucinar: todo fator apontado tem suporte real na fonte. Isso
   destrava o log e o dataset supervisionado das 6 desde já.

2. **Comprometer o upgrade do modelo de pose (COCO-17 → Halpe26/RTMPose) como fatia vertical
   própria.** Halpe26 adiciona hálux, dedo menor e calcanhar por pé → habilita pronação e
   dorsiflexão REAIS. Já antecipado em `AI-STRATEGY.md:99`. Quando cair, os `factors` de
   `plantar`/`achilles` migram de proxy → primário (mesma interface, só troca o conteúdo do mapa).

## Alternativas consideradas

- **Manter `mapped=False` até a pronação existir.** Rejeitada: deixa 2 das 6 lesões sem cobertura
  de risco num app cujo propósito é predizer lesão — buraco de produto. Os proxies de carga têm
  fonte real; segurar tudo seria honestidade mal-calibrada (jogar fora sinal citável válido).
- **Preencher `source` com uma PMC de dorsiflexão/pronação sem adicioná-la ao corpus.** Rejeitada:
  citar fonte que não está no corpus RAG é exatamente a alucinação que o grounding
  (`constitution.md` §13-14) existe para impedir.
- **Aproximar pronação/dorsiflexão só com o tornozelo (COCO-17).** Rejeitada: sem o segmento do pé,
  o número seria chutado — viola "dado validado, nunca chutado" (§7).

## Consequências

- **Positivas:** as 6 lesões cobertas por mapa citável hoje; caminho de fortalecimento claro e sem
  refatoração (só troca de conteúdo do mapa quando Halpe26 chegar); a razão da limitação fica
  registrada (é keypoint-set, não corpus).
- **Custo/risco:** o upgrade Halpe26 repercute no motor Rust inteiro — ONNX novo, decodificação de
  26 keypoints (os arrays fixos `[…; 17]`, esqueleto e desenho mudam), métricas novas, revalidação.
  Difícil de reverter → por isso este ADR.
- **Sinalização honesta:** enquanto for proxy, a força do mapa de `plantar`/`achilles` é menor que a
  dos joelhos (PFP/ITBS → queda pélvica). Comentário em `injury_taxonomy.py` marca isso e aponta
  para este ADR.
