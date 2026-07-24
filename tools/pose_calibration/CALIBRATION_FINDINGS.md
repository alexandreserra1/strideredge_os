# Achados da calibração de ângulos (YOLO × BlazePose vs mocap)

> Registro auditável para o ADR 0002 (promoção do BlazePose). É um **piloto de engenharia**, não
> validação clínica. Ferramentas: `calibrate.py`, `riglet_adapter.py` e `run_riglet_pilot.py`.

## Reprodução Riglet — 24 jul. 2026

O piloto usou corrida overground confortável da Session1, com os eventos anotados do Riglet como
frames comuns e os ângulos do mocap como verdade. O relatório foi gerado com:

- YOLO17: `2d`;
- BlazePose33: `2d` (a mesma geometria que o produto expõe);
- perna por corredor escolhida pela **confiança combinada** de joelho+tornozelo dos dois backends,
  nunca pelo menor erro contra o mocap;
- SHA-256 do ZIP: `4a9c0a8ac31d69303577616ee98946a882635932a8cc8af9b0ffd7886f4b6fa8`.

Foram aceitos 12 corredores: `AJ026`, `BD004`, `BL025`, `CF027`, `CL007`, `DA013`, `GQ016`,
`HN021`, `HS018`, `JS009`, `LA014` e `LD002`. `DC005` e `GF022` foram excluídos porque só 50% dos
foot strikes casaram com os apoios detectados (gate mínimo: 60%). Os JSONs de entrada e o
`report.json` ficam em `/tmp/strideredge-riglet-pilot-20260723-native/` e não entram no Git.

| Articulação | YOLO 2D — MAE vs mocap | BlazePose 2D — MAE vs mocap | Melhor em corredores |
| --- | ---: | ---: | --- |
| Joelho | 25,1° | **21,9°** | BlazePose |
| Quadril | 22,8° | **19,7°** | BlazePose |

Os backends também divergem entre si: MAE pareado de 15,8° no joelho e 16,3° no quadril. Os valores
são médias dos MAEs por corredor nos mesmos frames de evento, não uma comparação agregada de fases
diferentes.

## Interpretação e decisão

1. O antigo valor ad-hoc de **23,7° no joelho do BlazePose não se confirmou** na máquina auditável.
   O comparativo reproduzível no espaço de produto é 21,9° (BlazePose 2D).
2. O 2D do BlazePose foi menor que o YOLO 2D nas duas articulações deste piloto. Por isso o motor
   passou a registrar e usar `image_2d` explicitamente; world-3D fica disponível apenas para
   diagnóstico, sem trocar limiares clínicos por backend.
3. Os erros absolutos continuam grandes para orientar uma alegação clínica de ângulo articular. A baixa
   resolução e o enquadramento do Riglet são limitações plausíveis, mas não justificam corrigir o
   número por suposição.
4. **BlazePose33 permanece candidato experimental** até empacotamento do runtime por plataforma,
   shadow mode e validação numa segunda base. O resultado autoriza a geometria 2D uniforme, não um
   offset fixo nem alegação clínica.

## Segunda reprodução — 24 jul. 2026 (agora COM o world-3D)

A primeira rodada só mediu 2D. Esta re-rodou os 12 corredores medindo também o **world_3d** do
BlazePose (os 33 landmarks 3D que antes eram descartados), pelo mesmo arnês auditável
(`error_vs_truth(mode=...)`). Subconjunto de corredores levemente diferente (inclui `DC005`/`GF022`,
que a 1ª rodada excluiu pelo gate de 60%). Joelho, MAE médio vs mocap:

| Backend / modo | MAE joelho (média) | (mediana) |
| --- | ---: | ---: |
| YOLO 2D | 26,2° | 25,4° |
| BlazePose 2D | 28,6° | 28,7° |
| **BlazePose world-3D** | **23,7°** | **23,1°** |

Offset mediano **3D − 2D = −7,1°**: o 3D lê o joelho ~7° MAIS flexionado que a projeção 2D nos
eventos — coerente com o 2D sub-medir flexão fora do plano sagital.

### Honestidade (o que NÃO bate entre as duas rodadas)
O **2D do BlazePose divergiu** (21,9° na 1ª rodada vs 28,6° nesta) — ou seja, o ranking ABSOLUTO é
**sensível ao subconjunto de corredores** (12 é piloto pequeno). O que é **robusto nas duas**: (a) os
erros são grandes (~22–29°) por causa do enquadramento distante e baixa-res do Riglet — não do
pipeline; (b) o BlazePose no seu melhor modo bate o YOLO no joelho. O world-3D ser o menor aqui é
promissor, **não** cravado — não vira offset clínico fixo nem troca de default sozinho. Produção
segue `image_2d`; 3D é diagnóstico. `report.json` desta rodada em `/tmp/riglet_final/`.

## Próximo passo (sem multi-câmera — com o que já temos)

1. **Riglet já é a validação** que temos: dado CC0 baixado, vídeo+mocap, 12 corredores. Não precisa
   de mais captura pra decidir geometria — precisa de mais corredores/base pra cravar absoluto.
2. **Vídeos de celular próprios** (caso de uso real, enquadramento fechado): sem mocap, mas dá pra
   ancorar por **anotação manual** (`annotations_to_truth.py`, tier C) — sanity, não limiar clínico.
   É o único jeito autossuficiente de medir NA nossa moldura sem montar multi-câmera.
3. Multi-câmera/triangulação (`CAPTURE_MULTICAM_SETUP.md`) fica como opção FUTURA quando der — não
   é pré-requisito pra seguir.
