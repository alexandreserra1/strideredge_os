# Adaptador de ingestão Riglet → arnês de calibração (design)

> Alimenta `calibrate.py` com **eventos** + **ground-truth** reais (mocap/força) do dataset Riglet
> (figshare 25592865, **CC0** — uso comercial livre). Este doc é o design **antes** de o zip de 30 GB
> terminar; os pontos marcados **[VERIFICAR]** são confirmados contra os arquivos reais no build.

## O que o dataset contém (da descrição oficial)

- **30 participantes**, corrida em **esteira (Treadmill_Run)** e **solo (Overground_Run)**, velocidades
  **Comfortable** e **Fast**, com tênis. Corrida: 2931 ciclos overground + 18945 esteira.
- **63 marcadores** reflexivos (trajetórias 3D) + **GRF 3D e momentos**, gravados **simultaneamente**.
- Formatos: **C3D e CSV**, `Raw` ou `Post_Process`; **vídeo AVI** comprimido.
- Antropometria/demografia nos metadados do C3D/CSV Post_Process + Excel.
- **Inclui um leitor Python oficial** (pasta `Python`) — reusar como referência de parsing.

### Hierarquia de pastas
```
ID/ Session{1,2}/ <Trial>/ <Speed>/ <Data>/ arquivos
  Trial : Overground_Run | Treadmill_Run | Overground_Walk | Treadmill_Walk | Calibration
  Speed : Comfortable | Fast            (corrida)
  Data  : Post_Process (c3d/CSV) | Raw (c3d/CSV) | Video (AVI)
```
Só nos interessa `*_Run` × {Comfortable,Fast} → `Video/*.avi` (entrada de pose) + `Post_Process`
(verdade). Piloto de engenharia: 8–15 IDs, **split por corredor** (nunca o mesmo ID em treino e teste).

## Pipeline do adaptador (`tools/pose_calibration/riglet_adapter.py`, a construir)

Para cada trial de corrida selecionado (`subject = ID_Session_Trial_Speed`):

1. **Pose nos dois backends.** Rodar o motor no AVI com `STRIDE_DUMP_SERIES`, uma vez por backend:
   `yolo17` e `blazepose33` → `<subject>.yolo17.frames.json` / `<subject>.blazepose33.frames.json`
   (o formato por-frame que o `calibrate.py` já consome). **[VERIFICAR]** qual câmera do AVI é a mais
   **sagital/lateral** (pode haver múltiplas vistas); o adaptador recebe a vista por parâmetro.
2. **Verdade dos ângulos (Post_Process).** Ler do CSV Post_Process (evita parser C3D binário; CSV é
   fornecido) as séries **sagitais** de flexão de **joelho** e **quadril** (model outputs tipo
   Plug-in-Gait: `*KneeAngles` eixo X = flexão). **[VERIFICAR]** nomes exatos das colunas + unidade.
   - **Conversão de convenção (crítico):** o nosso `angle_at` devolve o ângulo INTERNO (180° = reto);
     o mocap dá **flexão** (0° = reto). Logo `truth_interno = 180 − flexão`. Sem isso a comparação
     fica invertida.
3. **Eventos de marcha (da GRF).** Contato inicial (IC) e toe-off (TO) pela **força vertical**:
   IC = subida acima do limiar (**[VERIFICAR]** ~20 N), TO = descida abaixo. **[VERIFICAR]** se o C3D
   já traz a seção EVENTS pronta (aí usamos ela direto). Apoio médio = meio entre IC e TO (ou pico de
   flexão de joelho na verdade). Estes são os frames COMUNS onde os dois backends serão medidos.
4. **Alinhar tempo mocap ↔ vídeo.** Mocap/força ~100–200 Hz; AVI ~25–60 fps. **[VERIFICAR]** as duas
   taxas + se há offset de início. Mapear cada evento (em amostra de mocap) → **índice de frame do
   vídeo** por `frame = round(t_evento_s × fps_video)` a partir do mesmo t0 do trial. É o passo mais
   delicado; validar visualmente num trial (overlay no frame do evento) antes de confiar no lote.
5. **Emitir os JSONs do arnês:**
   - `events.json` = `{subject: [frames_de_evento_no_video]}`
   - `truth.json`  = `{subject: {"knee": {frame: interno}, "hip": {frame: interno}}}`
   Depois: `calibrate.py <dumps_dir> --events events.json --truth truth.json` → **MAE/viés real de cada
   backend vs a verdade**, por articulação → responde *quem acerta o joelho*, não quem concorda.

## Convenções e caveats (honestidade)

- **2D vs 3D:** o nosso ângulo é projeção sagital 2D de uma câmera; o mocap é 3D. Só compara honesto
  se a câmera for **realmente lateral** e o corredor se mover no plano — há erro de projeção residual
  (registrar como limite, não varrer pra baixo).
- **Sagital only:** comparar apenas flexão/extensão (o que a nossa vista lateral mede). Nada de valgo
  aqui (é plano frontal, outra câmera/outro trial).
- **Piloto de engenharia, não validação clínica** (ADR 0002): 8–15 corredores medem erro real e viés,
  mas não autorizam "diagnóstico clínico". Split por corredor.
- **Sem inventar:** onde a coluna/limiar/sincronia não bater com o real, o adaptador **falha alto**
  (não chuta) — mesma disciplina do `tools/halpe26`.

## Dependências
- Ler **CSV** Post_Process = sem dependência nova (parsing direto). Se só houver C3D → usar o leitor
  oficial da pasta `Python` do dataset, ou `ezc3d` (avaliar no build).
- Nenhum peso/vídeo do dataset entra no Git (é ground-truth externo; fica em `~/strideredge_datasets/`).

## Ordem de execução (quando o zip terminar)
1. Descompactar; inspecionar 1 ID de corrida → confirmar os **[VERIFICAR]** (colunas, taxas, câmera,
   seção EVENTS, limiar de força).
2. Escrever `riglet_adapter.py` contra a estrutura real + teste hermético (com um mini-fixture CSV/dump).
3. Rodar 8–15 IDs → `calibrate.py --events --truth` → relatório de erro vs verdade.
4. Só ENTÃO discutir offset/limiar por backend (passo 5 do plano).

**Fontes:** dataset Riglet (figshare 25592865, CC0) · descritor *Scientific Data* s41597-024-03420-y.
