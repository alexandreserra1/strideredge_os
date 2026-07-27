# Verdade 3D AUTOSSUFICIENTE — o playbook do open-source, replicado

> Sem depender de terceiros, sem e-mail, sem licença de dataset. É EXATAMENTE como os projetos de
> biomecânica markerless do GitHub (Pose2Sim, OpenCap) geram a própria verdade: **múltiplas câmeras
> baratas + triangulação**. O dado é nosso, a licença é nossa, e é o nosso caso de uso (celular).

## A ideia (por que funciona)

Uma câmera só dá ângulo 2D projetado (erra fora do plano). **N câmeras calibradas** olhando a mesma
cena, com pose 2D em cada vista, **triangulam** os joints em 3D — precisão de referência **sem
mocap**. Esse 3D triangulado é a VERDADE contra a qual validamos a nossa pose de **UMA** câmera.

```
2–4 celulares (calibrados) ─► pose 2D por vista ─► TRIANGULAÇÃO (Pose2Sim) ─► joints 3D (.trc)
                                                                                    │  = a nossa VERDADE
1 câmera (a que o produto usa) ─► BlazePose/YOLO ─► ângulo single-cam ───────────► compara no arnês
```

## Ferramentas (forkáveis, verificadas)

| Ferramenta | Licença | Papel |
|---|---|---|
| **Pose2Sim** | **BSD-3-Clause** ✅ (comercial OK) | calibração multi-câmera + triangulação → `.trc` 3D. **É a que usamos.** |
| FreeMocap | AGPL-3.0 ⚠️ | mesma ideia com webcams, MAS copyleft (igual ao problema do YOLO) — evitar no produto. |
| OpenCap | código Apache, **dado research-only** | referência de método; não usar o dado deles. |

## Pipeline (o que já está codado vs. o que falta)

1. **Captura**: 2–4 celulares, um deles é a "câmera do produto" (lateral, fechada). Calibração de
   câmera (tabuleiro de xadrez — o Pose2Sim tem o passo). Corredor ≥15s.
2. **Triangular a verdade** (Pose2Sim, BSD): pose 2D nas N vistas → 3D dos joints → **`.trc`**.
   *(fork/uso do Pose2Sim — passo externo, mas open-source e nosso)*
3. **`.trc` → arnês**: ✅ **CODADO** — `trc_to_truth.py` computa o ângulo interno 3D de joelho/
   quadril do `.trc` e escreve `truth.json`/`events.json`. Como a triangulação vem dos MESMOS
   vídeos, o frame do `.trc` **alinha direto** com o dump do motor (sem sincronia externa).
4. **Nossa pose single-cam**: rodar BlazePose/YOLO na câmera-do-produto com `STRIDE_DUMP_SERIES`.
5. **Comparar**: `calibrate.py <dumps> --events events.json --truth truth.json` → **MAE/viés da
   nossa pose single-cam vs a nossa verdade 3D triangulada**, em vídeo de celular fechado.

## Trilha alternativa (âncora manual, sem multi-câmera)
Se não der pra montar 2–4 câmeras, a anotação manual entra por `annotations_to_truth.py`
(CSV → arnês). É âncora FRACA (sanity), não pra limiar clínico. Ver `OWN_DATA_PROTOCOL.md`.

## Honestidade
- Triangulação multi-câmera é referência FORTE (é o que OpenCap/Pose2Sim usam pra publicar), mas
  não é mocap de marcador — registrar como "referência triangulada", não "gold-standard clínico".
- Split por corredor; 8–15 é piloto de engenharia. YOLO17 padrão até um relatório reproduzido.
- Nenhum vídeo/dado de terceiros entra no Git; a nossa captura fica fora do repo.
