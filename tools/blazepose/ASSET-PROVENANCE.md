# Procedência dos assets BlazePose (runtime MediaPipe + Pose Landmarker)

**Estado:** `experimental` — candidato do ADR 0002, ainda não é o default até o portão fechar.
**Última verificação técnica:** 24 jul. 2026
**Decisão de licença:** código do MediaPipe é **Apache-2.0** (permite uso comercial). Pesos do
`.task` e o binário do runtime seguem a mesma licença do projeto; este é um registro técnico de
diligência, não um parecer jurídico.

## Por que este toolkit existe

O binário `libmediapipe.{dylib,so}` só é distribuído **dentro do wheel oficial do MediaPipe**. O
portão do ADR 0002 exige "runtime empacotado sem depender de uma instalação Python". Solução: extrair
o binário do wheel **uma vez** (`provision.py`), fixar o SHA-256, e copiá-lo pra raiz privada de
modelos. O wheel vira **procedência**, não dependência de execução — o servidor rodando só faz
`dlopen` no binário fixado. Nenhum destes arquivos entra no Git.

## Artefatos fixados (spike local — macOS arm64)

Os SHA-256 abaixo são dos arquivos usados no spike local; permitem detectar troca acidental de
binário. Não são checksum publicado pelo fornecedor.

| Papel | Arquivo | Origem | SHA-256 local | Tamanho |
| --- | --- | --- | --- | ---: |
| Runtime MediaPipe | `libmediapipe.dylib` | wheel `mediapipe==0.10.35` (`mediapipe/tasks/c/`) | `f183acadefa74df7d9651beb3ff8339320c544020920e8d9038637f50bfdd453` | 50,7 MB |
| Pose Landmarker | `pose_landmarker_full.task` | [Google MediaPipe model card (Pose Landmarker, Full)](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) | `4eaa5eb7a98365221087693fcc286334cf0858e2eb6e15b506aa4a7ecdcec4ad` | 9,4 MB |

> **Plataforma:** o `libmediapipe.dylib` acima é **macOS arm64**. Para Linux, extrair o `.so` do
> wheel `manylinux` correspondente (mesma versão `0.10.35`) e re-fixar o SHA — o binário é
> **por-plataforma**, então cada alvo de deploy tem seu próprio manifest.

## Evidências de origem e escopo

| Componente | Fato verificável | Fonte | Leitura de licença/risco |
| --- | --- | --- | --- |
| MediaPipe (código/runtime) | O repositório oficial publica sob Apache-2.0. | [google-ai-edge/mediapipe LICENSE](https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE) | **Código/runtime:** Apache-2.0 confirmado; permite uso comercial e redistribuição com NOTICE. |
| Pose Landmarker (`.task`) | O bundle GHUM/BlazePose é publicado pela Google na model card oficial, sob os termos do MediaPipe. | [model card oficial](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker) | Distribuição sob Apache-2.0 do projeto; sem checksum publicado localizado nesta auditoria. |
| BlazePose GHUM | 33 landmarks (incl. pés) + world-3D em metros; usado pela nossa validação Riglet (world-3D = 23,7° MAE no joelho). | [paper BlazePose GHUM Holistic](https://arxiv.org/abs/2206.11678) | Evidência técnica da capacidade 3D; não é alegação clínica. |

## Limites conhecidos

- O `libmediapipe.dylib` é **macOS arm64**; um deploy Linux exige extrair o `.so` do wheel
  `manylinux` e gerar um manifest próprio (o binário é por-plataforma).
- Nenhum SHA-256 publicado pelo fornecedor foi localizado; os hashes acima são locais (anti-troca),
  não checksum oficial.
- O StriderEdge **não versiona** estes binários; `provision.py` os fixa fora do repo.
- Status `experimental`: o backend só vira default quando o portão do ADR 0002 fechar (shadow +
  E2E/benchmark em CI + avaliação pareada estável). Ver `docs/adr/0002`.
