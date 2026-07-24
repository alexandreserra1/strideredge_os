# Adaptador de ingestão Riglet → arnês de calibração (design — CONFIRMADO contra os arquivos)

> Alimenta `calibrate.py` com **eventos** + **ground-truth** reais (mocap/força) do dataset Riglet
> (figshare 25592865, **CC0** — uso comercial livre). O zip de 30,38 GB baixou e o **MD5 confere**
> (`59da4a9b…`); os pontos abaixo foram **confirmados inspecionando os arquivos reais** (não o paper).

## Estrutura real (confirmada)

```
Data_Run_Walk/<ID>/Session{1,2}/<Trial>/<Speed>/<Data>/arquivos
  Trial : Overground_Run | Treadmill_Run | Overground_Walk | ... | Calibration
  Speed : Run_Comfortable | Run_Fast
  Data  : Post_Process (.c3d + .csv) | Raw | Video (.avi)
```
- **30 IDs** (ex.: `AJ026`). Cada condição de corrida tem **~10 trials** (`Run_Comfortable1..10`).
- **Vídeo: SÓ overground** (não há AVI de esteira). `Video/Run_Comfortable.avi` — **mpeg4, 644×366,
  50 fps**, cobrindo os vários passes da condição (≈99 s: passes de corrida + volta andando).
- **Mocap 100 Hz** (`PointFrequency`), **força 1000 Hz** (`AnalogFrequency`).
- **Eventos JÁ ANOTADOS** no topo do CSV, em **tempo absoluto** (mesma base do vídeo):
  `Right_Foot_Strike,9.81,10.52,11.22` / `Right_Foot_Off` / `Left_Foot_Strike` / `Left_Foot_Off`.
- **CSV Post_Process traz ÂNGULOS prontos + centros articulares** (cada rótulo ocupa 3 colunas X,Y,Z):
  `LKneeAngles`/`RKneeAngles`/`LHipAngles`/`RHipAngles` (**X = flexão sagital**), e
  `LHJC/RHJC/LKJC/RKJC/LAJC/RAJC` (**joint centers 3D**), + GRF/momentos/potências/todos os marcadores.
- Leitor oficial `Data_Run_Walk/Python Code/…py` usa **btk** (C3D). Nós usamos o **CSV** → **sem
  dependência nova** (btk é chato de instalar; o CSV tem tudo).

## Pipeline do adaptador (`tools/pose_calibration/riglet_adapter.py`, a construir)

Por trial de corrida (`subject = ID_SessionN_Speed_k`):

1. **Pose nos 2 backends** no AVI (`STRIDE_DUMP_SERIES`, `--view lateral`): `yolo17` e `blazepose33`
   → `<subject>.<backend>.frames.json`. O AVI é longo (vários passes); só usamos os frames de evento.
2. **Verdade dos ângulos (CSV, apples-to-apples):** computar o **ângulo INTERNO** de joelho/quadril
   dos **joint centers** com a MESMA fórmula do nosso `joint_angle` (joelho = HJC-KJC-AJC; quadril =
   ombro/tronco-HJC-KJC), **projetado no plano sagital** (eixo ântero-posterior + vertical). Isso casa
   exatamente com o que a pose 2D mede. Cross-check: `RKneeAngles` X (flexão) ⇒ interno = 180−flexão.
3. **Eventos → frame do vídeo.** Os tempos do CSV são absolutos: `video_frame = round(t_evento × 50)`.
   Usar `Foot_Strike` (contato inicial) e `Foot_Off` (toe-off); apoio médio = meio do apoio (IC→TO) ou
   pico de flexão de joelho na verdade. São os frames COMUNS onde os dois backends são medidos.
4. **Emitir p/ o arnês:** `events.json = {subject: [frames]}` e
   `truth.json = {subject: {"knee": {frame: interno}, "hip": {frame: interno}}}` →
   `calibrate.py <dumps> --events events.json --truth truth.json` → **MAE/viés real por backend vs a
   verdade** → responde *quem acerta o joelho*.

## [VERIFICAR ainda — no build, contra 1 trial]
- **Sincronia t0 vídeo↔mocap:** confirmar que `t_evento × 50` cai no frame onde o pé realmente toca
  (overlay num foot-strike). Se houver offset de início, medir e aplicar. **É o passo mais delicado.**
- **Eixo sagital:** qual eixo do lab é ântero-posterior (pra projetar) — do cabeçalho/reader.
- **Layout do CSV:** cabeçalho multi-linha + rótulo = 3 colunas (`,,,`) → mapa rótulo→índice; a coluna
  `Time` e a `FirstFrame` alinham o índice de amostra do mocap.
- **Vista do AVI:** confirmar que a câmera overground é ~lateral no trecho do pass (é onde medimos).

## Honestidade (mantida)
- **2D-vs-3D:** projetamos o mocap no sagital pra casar com a nossa vista; erro de projeção residual é
  LIMITE declarado, não varrido. Só flexão/extensão (sagital) — nada de valgo aqui.
- **Piloto de engenharia** (8–15 IDs, **split por corredor**), não validação clínica (ADR 0002).
- **Falha-alto:** coluna/sincronia/eixo que não bater com o real → erro explícito, sem chutar.
- Dataset (30 GB) **fora do Git**, em `~/strideredge_datasets/`.

## Ordem de build (agora que o zip está aqui e verificado)
1. Escrever `riglet_adapter.py` (parser CSV puro: header, eventos, ângulos/JC; + runner dos 2 backends
   no AVI) + teste hermético com mini-fixture CSV.
2. Validar sincronia num trial (overlay no foot-strike).
3. Rodar 8–15 IDs → `calibrate.py --events --truth` → relatório de erro vs verdade.
4. Só ENTÃO discutir offset/limiar por backend (passo 5 do plano).

**Fontes:** dataset Riglet (figshare 25592865, CC0) · descritor *Scientific Data* s41597-024-03420-y.
