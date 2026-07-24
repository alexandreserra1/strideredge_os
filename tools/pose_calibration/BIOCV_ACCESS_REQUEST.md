# BioCV — pedido de acesso (rascunho pronto pra enviar)

> O BioCV (Univ. Bath, 15 participantes, 9 câmeras 1920×1280@200fps, mocap + força, **inclui
> corrida**) é tecnicamente o dataset ideal. MAS: os DADOS são **"All Rights Reserved"**, acesso por
> pedido a `research-data@bath.ac.uk` + aceite de termos éticos, e **redistribuição proibida**. A
> licença fala em "biomechanics and machine vision **research**" — não diz *comercial*. Por isso
> **a decisão é do dono do produto, não minha**: enviar este e-mail é aceitar/consultar os termos.
> **Não enviei nada; deixo pronto pra você.**

## Ponto crítico a resolver ANTES de usar
Se o uso é validação de um **produto comercial** (SaaS), e a licença é "research" + all-rights-reserved,
**pergunte explicitamente** se o uso comercial-interno de validação é permitido. Se a resposta for
não, o BioCV está fora (e o caminho é dado próprio — ver `OWN_DATA_PROTOCOL.md`).

## Rascunho do e-mail

**Para:** research-data@bath.ac.uk
**Assunto:** Access request — BioCV markerless validation dataset (Evans et al., 10.1038/s41597-024-04077-3)

> Dear Research Data Team,
>
> I would like to request access to the BioCV dataset ("Synchronised Video, Motion Capture and Force
> Plate Dataset for Validating Markerless Human Movement Analysis", Evans et al., 2024,
> doi:10.1038/s41597-024-04077-3), specifically the **running** trials with the synchronised RGB
> video and marker-based motion capture.
>
> **Intended use (please advise on compatibility):** I am developing a running-injury-prevention
> application that estimates lower-limb joint angles from a single consumer camera. I would use the
> dataset **internally**, to validate the angular accuracy of our pose pipeline against the
> marker-based ground truth. I would **not** redistribute the data, publish the videos, or use them
> for any purpose that could identify, demean or harm participants; results reported would be
> aggregate accuracy metrics only.
>
> Because the eventual product is **commercial**, could you please confirm whether such **internal,
> non-redistributed validation for a commercial product** is permitted under the dataset licence, or
> whether it is restricted to non-commercial research? I want to respect the participants' consent and
> your terms precisely before downloading anything.
>
> I acknowledge the ethical commitments regarding participant consent and agree to abide by the
> dataset terms if access is granted.
>
> Thank you,
> [SEU NOME / INSTITUIÇÃO / CONTATO]

## Depois (se autorizado + comercial OK)
O adaptador de ingestão é análogo ao do Riglet (`riglet_adapter.py`): vídeo → dump dos 2 backends;
c3d/força → verdade + eventos → `calibrate.py --events --truth`. Eu construo quando o acesso vier.
