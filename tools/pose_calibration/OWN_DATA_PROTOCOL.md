# Protocolo de validação com DADO PRÓPRIO

> Fecha o gargalo de licença: em vez de caçar um dataset acadêmico (todos os bons com vídeo são
> "research only", ≠ comercial), a gente coleta uma validação **nossa** — vídeo de celular (o
> caso de uso real) + uma âncora de verdade. **Dono do dado + consentimento nosso → zero licença.**
> O arnês (`calibrate.py`) já consome o resultado; só troca a FONTE da verdade.

## Por que isto (e não mais busca de dataset)

Corrida + vídeo RGB bruto + mocap + licença comercial só existe no **Riglet (CC0, 644×360, já temos)**.
BioCV/OpenCap são research-only (vídeo de pessoa exige consentimento, e consentimento acadêmico não
cobre produto comercial). Coletar o nosso resolve de vez, é barato, e é exatamente o cenário de deploy.

## Captura (mínimo 8–15 corredores)

1. **Vídeo**: celular, **lateral** (câmera perpendicular à direção da corrida), corredor **enquadrado
   e fechado** (corpo inteiro ocupando boa parte do frame — o oposto do overground distante do Riglet
   que deu 27° de MAE). ≥15 s correndo, sem cortes. 30–60 fps.
2. **Consentimento** assinado de cada participante para uso do vídeo em **validação de produto
   comercial** (guardar; é o que destrava o uso comercial que os datasets acadêmicos travam).
3. **Não** reenviar/alterar o vídeo depois — o motor normaliza (assa rotação) sozinho.

## Âncora de verdade (escolha um tier — do melhor ao mais barato)

| Tier | Como | Qualidade | Custo |
|---|---|---|---|
| **A. Mocap** | alugar um lab por uma tarde (marcadores + força) | gold-standard | alto |
| **B. IMU** | um IMU no segmento (coxa/canela) → ângulo de joelho | boa | ~R$200 |
| **C. Anotação manual** | marcar o ângulo interno do joelho em N frames de apoio | fraca (sanity) | zero |

Todos produzem o MESMO CSV de anotação, então o pipeline é o mesmo.

## Do dado ao veredito (pipeline)

1. **Rodar o motor** nos vídeos com o dump por-frame (os dois backends):
   ```
   STRIDE_DUMP_SERIES=<clip>.blazepose33.frames.json stride-vision <clip>.mp4 out.mp4 \
       --view lateral --backend blazepose33 --no-overlay
   STRIDE_DUMP_SERIES=<clip>.yolo17.frames.json      stride-vision <clip>.mp4 out.mp4 \
       --view lateral --backend yolo17      --no-overlay
   ```
2. **Anotar a verdade** num CSV (`clip,frame,joint,angle_deg`), ângulo INTERNO (180°=reto), nos
   frames de apoio. `frame` = índice no vídeo (mesma base do dump). Converter:
   ```
   python tools/pose_calibration/annotations_to_truth.py anotacoes.csv out_dir/
   # -> out_dir/events.json + out_dir/truth.json
   ```
3. **Comparar** (o arnês, com os modos gravados):
   ```
   python tools/pose_calibration/calibrate.py <dumps_dir> \
       --events out_dir/events.json --truth out_dir/truth.json \
       --baseline-mode 2d --candidate-mode world_3d
   ```
   → **MAE/viés real de cada backend vs a nossa verdade**, em vídeo de celular fechado — onde o
   erro deve cair da faixa dos 27° do Riglet e o BlazePose 3D mostra o valor real.

## Honestidade
- Tier C (anotação manual) é âncora FRACA — bom pra sanity, não pra cravar limiar clínico. Pra
  re-derivar limiar 3D de verdade, use A ou B.
- Split por corredor (nunca o mesmo no treino e no teste). 8–15 é piloto de engenharia, não estudo
  clínico — mesma disciplina do `DATASET_SCREENING.md`.
- YOLO17 segue padrão até um relatório com âncora boa (A/B) reproduzido e revisado.
