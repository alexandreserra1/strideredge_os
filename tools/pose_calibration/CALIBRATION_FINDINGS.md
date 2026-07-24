# Achados da calibração de ângulos (YOLO × BlazePose vs mocap)

> Registro honesto do que a calibração respondeu — e do que NÃO respondeu. Insumo pro ADR 0002
> (promoção do BlazePose). Metodologia em `RIGLET_ADAPTER_DESIGN.md`; ferramentas em `calibrate.py`
> + `riglet_adapter.py`.

## Piloto Riglet (CC0) — n=12 corredores, apoio médio, perna visível, lado casado por menor erro

| | YOLO | BlazePose |
|---|---|---|
| MAE médio do joelho (vs mocap) | **26,2°** | **28,6°** |
| Mediana | 25,4° | 28,7° |
| Corredores em que ficou mais perto | **6/12** | **6/12** |

## Conclusões

1. **Empate técnico — inconclusivo pra escolha de backend.** 6-6, diferença de 2,4° **dentro do
   ruído**. O palpite do n=1 ("BlazePose erra mais o joelho") **NÃO se sustentou** no n=12. Bom que
   não agimos no n=1 — é exatamente por isso que se roda piloto.

2. **O erro é grande demais pra validar QUALQUER um dos dois.** ~27° de MAE, sendo que a flexão de
   joelho na corrida varia ~5-45° — o erro é da ordem do sinal. Causa: **vídeo overground do Riglet
   é grosso** (644×366, figura pequena atravessando o quadro) + erro de projeção 2D↔3D. O casamento
   "melhor caso" de lado já minimiza e ainda dá 27°.

3. **Sinal pro produto (não pro backend):** ângulo de joelho medido de vídeo ruim/distante é ±27° de
   lixo. Reforça o **gate de confiabilidade** (recusar captura ruim) — é a coisa certa num app de lesão.

## Decisão

- **Não promover o BlazePose a padrão** ainda (ADR 0002) — não por ser pior, mas porque **nada está
  validado** a esse nível de erro. YOLO segue como transição; BlazePose como candidato.
- **Riglet cumpriu o papel de provar o PIPELINE** (adaptador + arnês + sincronia validada, lag 0),
  mas não tem resolução pra decidir entre os backends.

## Próximo passo (o que decide de verdade)

**Validar no dataset Zenodo** (21 participantes, **vídeo de celular 30 fps** sincronizado com
OptiTrack 120 Hz, CC BY 4.0) — é o **nosso caso de uso real** (câmera de celular, lateral, mais
fechada) e melhor resolução → o MAE deve cair pra uma faixa onde dá pra **discriminar** os backends.
O adaptador já existe; só precisa de um ingestor pro formato do Zenodo (marker labels + sync).

## Atualização — world landmarks 3D do BlazePose (n=12)

A ponte C++ descartava o `pose_world_landmarks` (3D métrico) do BlazePose; ligá-lo e medir o ângulo
em 3D (`angle_at_3d`, imune à projeção 2D) **mudou o veredito**:

| Backend | MAE médio do joelho |
|---|---|
| YOLO 2D | 26,2° |
| BlazePose 2D | 28,6° (perdia pro YOLO) |
| **BlazePose 3D (world)** | **23,7°** (ganha) — melhor que YOLO em **9/12**, melhor que o próprio 2D em 9/12 |

**Conclusões:** (1) o BlazePose se sobressai por uma capacidade REAL (3D que o YOLO não tem), não por
tuning; (2) inverte o empate anterior a favor do BlazePose; (3) MAS 23,7° ainda é grande — o gargalo
restante é a RESOLUÇÃO do vídeo overground (644×366). O erro absoluto deve cair no Zenodo (vídeo de
celular, fechado) = nosso caso de uso. **Próximo passo pra produção:** ligar o ângulo 3D no pipeline
de métricas (`analyze_form`) pro BlazePose — hoje é só o experimento de calibração.
