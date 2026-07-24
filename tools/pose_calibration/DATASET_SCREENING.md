# Triagem de datasets para calibração de pose

> Estado em 23 jul. 2026. Esta é uma triagem de **validação**, não uma licença para redistribuir
> vídeos, treinar um modelo novo ou fazer alegação clínica. Cada download aceito deve registrar URL,
> licença, data, SHA-256 e o subconjunto de trials usado; vídeos externos nunca entram no Git.

## Critérios de aceite

Um dataset só pode entrar no gate de promoção do backend se tiver todos os itens:

1. corrida (não caminhada, high knees ou outro proxy);
2. vídeo RGB bruto que possa passar pelos backends do StriderEdge;
3. verdade sincronizada: mocap para ângulos e, quando avaliarmos eventos/GCT, força ou eventos
   anotados;
4. relação frame/tempo e orientação de câmera documentadas;
5. licença e consentimento compatíveis com o uso comercial de **validação interna**. Publicar ou
   redistribuir os vídeos exige uma análise separada.

## Fontes avaliadas

| Fonte | Dados úteis | Situação de licença/acesso | Decisão |
| --- | --- | --- | --- |
| **Riglet et al.** — Figshare 25592865 | 30 participantes, corrida overground/treadmill, AVI, marcadores 3D, força e eventos | **CC0**, download de 28,29 GB | **Aceito para piloto**. É a única fonte permissiva confirmada; a resolução overground de 644×366 limita a validação absoluta. |
| **Zenodo 19720803** | A descrição pública declara corrida, dois smartphones a 30 fps e mocap OptiTrack 120 Hz | **CC BY 4.0** no registro, mas a cópia inspecionada ficou parcial/corrompida e não comprovou vídeo RGB de corrida utilizável | **Rejeitado por enquanto**. Não concluir “não há corrida”: a fonte oficial diz que há. Reavaliar somente com manifesto íntegro + um trial RGB que passe no motor. |
| **BioCV / University of Bath** | 15 participantes; 10 corridas por participante; 9 câmeras RGB 1920×1280/200 fps, mocap 200 Hz, placas 1000 Hz, eventos por frame | Acesso restrito; exige aceite de termos e proíbe compartilhar os dados fora do dataset | **Não usar sem autorização escrita** compatível com SaaS. É o melhor candidato técnico, mas não é automaticamente uma licença comercial permissiva. |

## Ordem de execução

1. Reproduzir o piloto Riglet com `--baseline-mode 2d --candidate-mode world_3d`, por corredor e
   evento de apoio anotado. O JSON deve guardar os modos, MAE, viés, limites de concordância e
   número de frames válidos.
2. Manter YOLO17 como padrão enquanto esse relatório não estiver reproduzido e revisado.
3. Para Zenodo, inspecionar primeiro o manifesto de um download íntegro; não fazer inferência sobre
   arquivos parcialmente extraídos.
4. Só solicitar BioCV depois de confirmar por escrito que a licença permite validação interna de um
   produto comercial. O aceite é uma decisão do titular do produto, não automática.

## Referências

- Riglet et al., [Figshare dataset (CC0)](https://springernature.figshare.com/articles/dataset/3D_motion_analysis_dataset_of_healthy_young_adult_volunteers_walking_and_running_on_overground_and_treadmill/25592865).
- Guo et al., [Zenodo 19720803 (CC BY 4.0)](https://zenodo.org/records/19720803).
- Evans et al., [BioCV dataset — University of Bath](https://researchdata.bath.ac.uk/1258/).
