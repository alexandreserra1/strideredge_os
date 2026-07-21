# Layout de keypoints — COCO-17 (ativo) vs Halpe26 (bloqueado por asset)

Todo o pipeline de biomecânica fala em **índices semânticos** (`hip_l`, `knee_r`, `ankle_l`, ...)
via `KeypointLayout` em `src/lib.rs`, não em números mágicos. Trocar o motor de pose é trocar o
layout — nada mais no parsing do tensor, no desenho do esqueleto ou nas métricas muda.

- `COCO17` — **default e único ativo hoje**. 17 keypoints, YOLO11-pose. **Sem pontos de pé.**
- `HALPE26` — layout-alvo já definido no código, porém **bloqueado**: falta o modelo ONNX.

## O que falta para ativar o Halpe26

1. **Baixar o modelo ONNX Halpe26.** Um estimador de pose treinado no dataset Halpe (26 kp),
   exportado para ONNX com a **mesma convenção de saída YOLO-pose** que o código já consome:
   tensor `[1, 5 + 3*K, N]` = 4 box (cx,cy,w,h) + 1 conf + `(x,y,conf)` por keypoint.
   - Para K=26 => **83 canais** (COCO-17 usava 56). O `infer()` já deriva isso de `layout.count`.
   - Fonte típica: exportar YOL11x-pose/AlphaPose-Halpe26 para ONNX, ou um `yolo11-pose` treinado
     em Halpe26. Colocar em `models/` e apontar via `STRIDE_MODEL=...`.
   - **Validar a ordem dos keypoints** do modelo baixado contra `HALPE26_NAMES` (índices 17–25:
     cabeca, pescoco, quadril_c, hallux_e/d, dedinho_e/d, calcanhar_e/d). Se o export usar outra
     ordem, ajustar os índices semânticos em `HALPE26`.
2. **Plugar o layout:** trocar `PoseEngine::new(model)` por `PoseEngine::with_layout(model, &HALPE26)`
   (ou expor uma flag `--layout halpe26` no `main`). O default segue COCO-17.

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
