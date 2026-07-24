# Procedência dos assets Halpe26

**Estado:** `experimental-not-for-production`  
**Última verificação técnica:** 22 jul. 2026  
**Decisão de licença:** **PENDENTE — não distribuir, não embutir no app e não tornar o backend padrão.**

Este registro separa deliberadamente (1) código de inferência, (2) pesos/ONNX e (3) dados de
treino. Uma licença Apache-2.0 para o código **não** é, por si só, uma aprovação para redistribuir
pesos nem uma confirmação sobre os datasets. Isto é um registro técnico de diligência, não um
parecer jurídico.

## Artefatos observados

Os hashes abaixo são dos arquivos ONNX extraídos e usados no spike local. Eles permitem detectar
troca acidental de modelo; não constituem checksum publicado pelo fornecedor.

| Papel | Nome do arquivo | Origem de download | SHA-256 local | Tamanho local | Estado de distribuição |
| --- | --- | --- | --- | ---: | --- |
| Detector de pessoa | `yolox_m_8xb8-300e_humanart-c2c7a14a.onnx` | [zip ONNX do OpenMMLab](https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/yolox_m_8xb8-300e_humanart-c2c7a14a.zip) | `3dea6513388889f0fff4b77bf7a26013600321b9eb9ceb0e9a400a82572f5f23` | 97 MB | PENDENTE |
| Pose 26 pontos | `rtmpose-m_simcc-body7_pt-body7-halpe26_700e-256x192-4d3e73dd_20230605.onnx` | [zip ONNX do OpenMMLab](https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/onnx_sdk/rtmpose-m_simcc-body7_pt-body7-halpe26_700e-256x192-4d3e73dd_20230605.zip) | `26f3a19e61304a600dfb82d1001d41d24343b89fc70a33ffc84657e0b0bf2ecf` | 53 MB | PENDENTE |

O checkpoint PyTorch de referência, quando necessário para reproduzir conversão, é
[`rtmpose-m_simcc-body7_pt-body7-halpe26_700e-256x192-4d3e73dd_20230605.pth`](https://download.openmmlab.com/mmpose/v1/projects/rtmposev1/rtmpose-m_simcc-body7_pt-body7-halpe26_700e-256x192-4d3e73dd_20230605.pth).
Nenhum SHA-256 publicado para esses downloads foi localizado nesta auditoria; portanto o checksum
do `.pth` também permanece pendente.

## Evidências de origem e escopo

| Componente | Fato verificável | Fonte primária | Leitura de licença/risco |
| --- | --- | --- | --- |
| MMPose / implementação RTMPose | O repositório oficial publica o código sob Apache-2.0 e documenta o checkpoint `...body7...halpe26...pth`. | [MMPose LICENSE/repositório](https://github.com/open-mmlab/mmpose) · [guia oficial de inferência](https://github.com/open-mmlab/mmpose/blob/main/docs/en/user_guides/inference.md) | **Código:** Apache-2.0 confirmado. **Pesos:** a página de download não fornece nesta auditoria uma licença de pesos separada, checksum publicado ou autorização expressa de redistribuição. PENDENTE. |
| Detector YOLOX-M | O pacote ONNX oficial vem do domínio `download.openmmlab.com`; a documentação oficial do `rtmlib` o lista como detector de pessoa treinado em HumanArt+COCO. | [rtmlib — model zoo](https://github.com/Tau-J/rtmlib) | Origem técnica confirmada; direito de redistribuir o ONNX e diligência sobre HumanArt+COCO ainda PENDENTES. |
| Pose RTMPose-M / Halpe26 | A documentação oficial de MMPose expõe o alias `body26` e a família RTMPose/26 keypoints; o download exato usado pelo spike traz `body7_pt_body7_halpe26` no nome. | [MMPose — model alias](https://github.com/open-mmlab/mmpose/blob/main/docs/en/user_guides/inference.md) | A diferença entre o alias atual (`body8`) e o nome do checkpoint histórico (`body7`) exige manter o identificador exato e não inferir equivalência com versões futuras. Licença de pesos/datasets: PENDENTE. |
| Especificação Halpe | O repositório dos autores documenta os 26 keypoints corporais, incluindo hálux, dedinho e calcanhar. | [Halpe-FullBody](https://github.com/Fang-Haoshu/Halpe-FullBody) | A página aponta downloads de anotações e imagens provenientes de HICO-DET/COCO, mas não apresenta nesta auditoria uma licença única e inequívoca para a cadeia do peso. PENDENTE. |
| Código dos projetos MMPose | Um mantenedor do MMPose informou que RTMPose e YOLOX-Pose nos projetos MMPose são Apache-2.0 e permitem uso comercial. | [issue oficial #2393](https://github.com/open-mmlab/mmpose/issues/2393) | É evidência útil **somente para implementação de código**; não a usar como autorização automática para pesos ou dados de treino. |

## Limites conhecidos

- Os dois ONNX foram recuperados de URLs de entrega do OpenMMLab e extraídos localmente pelo
  runtime de referência; o repositório StriderEdge não os versiona nem deve passar a versioná-los
  antes da aprovação.
- O rótulo `body7_pt_body7_halpe26` sugere pré-treino e fine-tuning, mas esta auditoria **não
  confirmou** o inventário completo de datasets por trás dele. Não substituir esse inventário por
  uma suposição baseada no nome do arquivo.
- HumanArt, COCO, Halpe e eventuais datasets adicionais podem ter termos distintos. A análise deve
  cobrir uso, derivados/weights, redistribuição, atribuição/NOTICE e qualquer restrição comercial.
- A medição de qualidade ou FPS não altera esse estado jurídico.

## Checklist obrigatório para promoção

- [ ] Guardar URL final, data de download, tamanho e SHA-256 de cada arquivo entregue (zip **e**
      ONNX extraído) em um manifest versionado.
- [ ] Localizar termos oficiais explícitos para **os pesos** de detector e pose, incluindo uso em
      produto e redistribuição do arquivo ONNX.
- [ ] Obter do fornecedor, ou documentar em fonte oficial, o inventário de datasets de treino de
      cada checkpoint e seus termos aplicáveis.
- [ ] Revisar compatibilidade de cada termo com o modelo de distribuição planejado (local,
      download pelo usuário, binário/instalador ou SaaS), com responsável jurídico/comercial.
- [ ] Registrar atribuições, NOTICE e obrigações de licença que devem acompanhar a distribuição.
- [ ] Confirmar que a conversão para ONNX não muda obrigações e que o hash do ONNX corresponde ao
      artefato aprovado.
- [ ] Implementar no código o resolvedor estrito de assets (ID + versão + SHA) antes de qualquer
      auto-download ou seleção por API.
- [ ] Manter YOLO17 como padrão e Halpe26 opt-in até aprovação documental, validação operacional e
      validação clínica separadas.

## Regra operacional atual

É permitido usar estes arquivos apenas como **spike local controlado**, com paths explícitos
`STRIDE_HALPE_DETECTOR` e `STRIDE_HALPE_POSE`, para validação técnica. É proibido por esta decisão
de engenharia: copiá-los para o Git, incluí-los no instalador, hospedá-los para download, ou
habilitar Halpe26 automaticamente para usuários.
