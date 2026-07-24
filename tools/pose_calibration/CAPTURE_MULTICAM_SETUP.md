# Setup de captura multi-celular (RÉGUA interna, não o produto)

> **Isto NÃO é o produto.** O produto é UM vídeo de celular → o app acha os pontos → insights. Este
> setup é a nossa **régua interna**: filmamos alguns corredores com 2–3 celulares UMA vez pra medir
> quão preciso o nosso pipeline single-cam é (contra a verdade 3D triangulada). Depois, jogamos as
> câmeras extras fora e enviamos o produto single-cam. Multi-cam = medir; single-cam = vender.

## 1. Câmeras (mínimo 2, ideal 3)

- **2 câmeras** já triangulam (estéreo). **3** dão robustez (perna de trás oclui na corrida) e melhor 3D.
- **Uma delas é a "câmera do produto"**: lateral, enquadramento FECHADO (corpo inteiro ocupando o
  frame) — é a vista que o app usaria, e a que vamos validar.
- As outras em **ângulos diferentes** (~45° e ~frontal), com **base larga** entre elas (câmeras muito
  próximas trianguam mal a profundidade). Todas em **tripé estável**, ~altura do quadril, **todas
  vendo o corredor ao mesmo tempo** no trecho medido.

## 2. Gravação (igual em todos os celulares)

- **Mesmo FPS**, alto: **60 fps** (corrida é rápida; ajuda a sincronia e pega o apoio curto).
- Resolução igual, **foco e exposição TRAVADOS** (auto-foco estraga a triangulação).
- **Esteira é o ideal**: corredor parado no volume → todas as câmeras têm vista longa e estável.
  Sem esteira: passes de corrida atravessando o volume comum às câmeras.

## 3. Calibração (o passo que o Pose2Sim faz)

- **Intrínseca** (lente de cada câmera): filmar um **tabuleiro de xadrez/charuco** movendo na frente
  de cada celular por ~20s.
- **Extrínseca** (posição relativa): mostrar o **mesmo** tabuleiro **visível em TODAS as câmeras ao
  mesmo tempo** por alguns segundos (define a geometria entre elas). Pose2Sim tem esse passo pronto.

## 4. Sincronia (celular não tem clock comum)

- No começo de cada tomada, um **evento visível a todas as câmeras**: uma **palma forte** ou um
  **pulo** — dá um pico nítido pra alinhar os frames em pós.
- Pose2Sim tem um utilitário de **sincronização** (cruza a oscilação vertical de um keypoint entre
  as câmeras) que refina o alinhamento.

## 5. Corredores

- **8–15 pessoas**, 2–3 passes cada, variando ritmo. **Consentimento** assinado (uso em validação de
  produto comercial). Split por corredor no relatório.

## 6. Pipeline (verdade → veredito)

```
2–3 celulares (calibrados, sincronizados)
   └─► Pose2Sim (BSD): pose 2D por vista → TRIANGULA → joints 3D → arquivo .trc   ← a NOSSA verdade
        └─► tools/pose_calibration/trc_to_truth.py  → truth.json + events.json     ← já codado
   câmera-do-produto (single-cam)
   └─► stride-vision --backend blazepose33 --no-overlay  (STRIDE_DUMP_SERIES)      → dump por-frame
        └─► calibrate.py <dumps> --events events.json --truth truth.json           → MAE/viés real
```
Como a triangulação vem dos MESMOS vídeos, os frames alinham direto (sem sincronia externa no arnês).

## 7. Futuro: peitoral (IMU) — melhor ainda, e serve de âncora

Um **peitoral com IMU** (tipo Stryd/Garmin RD Pod) mede cadência, tempo de contato e oscilação
vertical DIRETO do corpo — mais preciso que vídeo pros números de TEMPO. No roteiro ele entra duplo:
(a) **fusão de sensores** no produto (vídeo = forma/ângulos; IMU = timing/carga), e (b) **âncora de
verdade** pra validar as métricas de tempo do vídeo (GCT/cadência do vídeo vs IMU) — barato e nosso.
Não substitui a triangulação pros ÂNGULOS (IMU não dá ângulo articular sagital direto), mas fecha o
timing. É Fase futura; a triangulação multi-cam resolve os ângulos agora.
