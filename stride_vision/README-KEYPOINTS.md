# Layout de keypoints — COCO-17 (default) vs Halpe26 (experimental)

Todo o pipeline de biomecânica fala em **índices semânticos** (`hip_l`, `knee_r`, `ankle_l`, ...)
via `KeypointLayout` em `src/lib.rs`, não em números mágicos. Trocar o motor de pose é trocar o
layout — nada mais no parsing do tensor, no desenho do esqueleto ou nas métricas muda.

- `COCO17` — **default**. 17 keypoints, YOLO11-pose. **Sem pontos de pé.**
- `HALPE26` — experimental opt-in. 26 keypoints, incluindo hálux, dedinho e calcanhar de ambos os
  pés. Usa um pipeline próprio RTMDet/YOLOX + RTMPose/SimCC; não é compatível com o decoder YOLO.

## Como executar o Halpe26 experimental

O runtime exige dois ONNX oficiais validados: detector de pessoa (saída NMS `[1,N,5]`) e pose
RTMPose (saídas SimCC `[1,26,384]` e `[1,26,512]`). Eles são fornecidos fora do repositório por:

```bash
STRIDE_HALPE_DETECTOR=/caminho/yolox.onnx \
STRIDE_HALPE_POSE=/caminho/rtmpose-halpe26.onnx \
stride-vision video.mp4 overlay.mp4 --backend halpe26
```

O backend valida a ordem Halpe26 contra `HALPE26_NAMES`; o YOLO17 continua default. A licença de
distribuição dos pesos e datasets ainda precisa ser aprovada antes de empacotar os modelos ou
selecionar Halpe26 automaticamente.

## O que isso destrava

Com os índices `heel_*` / `big_toe_*` / `small_toe_*` passando a existir (`layout.has_foot() == true`):

- **Pisada MEDIDA** em vez de inferida. Hoje `foot_strike()` é um *proxy* pela posição
  tornozelo×joelho (a tíbia), porque COCO-17 não tem pé. Com calcanhar + hálux dá pra medir qual
  ponto toca o solo primeiro (retropé/médio/antepé) diretamente.
- **Ângulo de dorsiflexão** do tornozelo no apoio (eixo tíbia vs. eixo do pé calcanhar→hálux) —
  hoje impossível de calcular. Insumo para canelite/tendão de Aquiles/fascite plantar.
- Esqueleto desenhado com os elos do pé (já em `HALPE26_SKELETON`).

Ver `AI-STRATEGY.md` e a memória "Mapa das 6 lesões / proxy até Halpe26" (ADR 0001): plantar e
Aquiles usam fatores *proxy* hoje; a pronação exige justamente estes keypoints de pé.
