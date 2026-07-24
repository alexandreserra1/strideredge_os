# ADR 0002 — BlazePose GHUM Full é o candidato permissivo para substituir o pose proprietário

- **Status:** rollout controlado (jul/2026). BlazePose é o padrão de seleção do servidor;
  ângulos produtivos permanecem em `image_2d` e a validação clínica continua aberta.
- **Escopo:** escolha de asset e trilha de integração para um SaaS proprietário, não validação clínica.

## Contexto

O produto deve poder ser comercializado sem licença paga de modelo. O YOLO11 usado hoje tem
licenciamento AGPL ou Enterprise pela Ultralytics; logo, não é uma base aceitável para distribuir
um SaaS proprietário sem adquirir a licença comercial. O experimento Halpe26 melhora pontos de pé,
mas a licença e a cadeia de dados dos pesos ONNX atuais ainda não estão comprovadas.

O **Pose Landmarker Full / BlazePose GHUM** da MediaPipe é um candidato diferente: a documentação
oficial descreve um bundle de detector + landmarker, 33 landmarks e uso on-device de fitness. O
model card declara Apache License 2.0. O pacote inclui tornozelo, calcanhar e `foot_index` de ambos
os pés (27–32), enquanto COCO-17 termina no tornozelo.

## Evidência do spike e da ponte nativa

O bundle oficial Full, baixado somente para teste, teve SHA-256
`4eaa5eb7a98365221087693fcc286334cf0858e2eb6e15b506aa4a7ecdcec4ad`.

No MacBook Pro M1 Pro, processando todos os quadros, em CPU/XNNPACK:

| Vídeo | Quadros | Corpo detectado | Dois pés utilizáveis* | Throughput |
|---|---:|---:|---:|---:|
| `laisa_correndo.mp4` | 955 | 100% | 100% | 54,5 FPS |
| `video_corrida_23.mp4` | 693 | 100% | 100% | 58,6 FPS |

\* Tornozelo, calcanhar e `foot_index` dos dois lados com `visibility` e `presence` >= 0,35.

O adaptador nativo foi então medido no mesmo `laisa_correndo.mp4`, com decode + inferência, sem
Python no caminho: **1.005 frames, 100% de detecção e 59,7 FPS**, contra **53,2 FPS** do YOLO11
atual (+12,2%). A análise completa do BlazePose retornou `reliable=true`, cadência de 165,9 spm e
comprimento de perna de 170,6 px. Isto é evidência de integração, cobertura e throughput; não é
uma afirmação de erro angular, diagnóstico ou validade clínica.

## Decisão

1. Adotar o BlazePose Full como **candidato permissivo**. Os assets futuros só podem vir da URL
   oficial, com versão e SHA-256 pinados num manifesto; o binário não entra no Git.
2. Não introduzir `mediapipe` Python no caminho de produção. O motor continua Rust e mantém o
   contrato `PoseBackend`. `build.rs` compila uma ponte C++ mínima que carrega a C API oficial de
   Tasks do MediaPipe, abre o bundle `.task` em modo vídeo e devolve os 33 landmarks normalizados.
   Rust converte para pixels e aplica `min(visibility, presence)` antes de qualquer métrica.
3. BlazePose Full é o backend principal de novas análises. YOLO17 fica temporariamente apenas como
   **shadow opt-in** do mesmo vídeo (`STRIDE_POSE_SHADOW_BACKEND=yolo17`), para medir divergências
   pareadas sem alterar a resposta ao atleta. Não há fallback silencioso: se os assets do Blaze não
   estiverem instalados e validados, a criação falha como indisponibilidade do serviço. Halpe26
   continua experimental e bloqueado de produto.
4. O novo conjunto permite medir o **segmento** calcanhar→ponta do pé em vista lateral. Ele não
   autoriza chamar isso de pronação clínica: não há hálux/dedo menor e a avaliação de eversão do
   retropé exige captura/validação apropriadas.
5. Ângulos de joelho/quadril expostos pelo produto usam sempre os landmarks **`image_2d`**, tanto
   para YOLO quanto para BlazePose. Os world landmarks do BlazePose são preservados somente no dump
   diagnóstico opt-in: o piloto Riglet reproduzível favoreceu 2D para joelho e quadril, e não é
   aceitável alternar a geometria conforme o backend sem revalidar limiares e risco.
6. Para o BlazePose, GCT, voo e o frame de apoio usam o ponto mais baixo entre calcanhar e
   `foot_index` quando ambos passam a confiança; a resposta registra cobertura e fallback para
   tornozelo. Isso é melhoria de observação do contato, não medição de pronação ou dorsiflexão.

## Portão para promoção a padrão

- o runtime oficial para macOS/Linux é empacotado e testado sem depender de uma instalação Python;
- asset, licença Apache-2.0, URL, versão, hash e avisos de terceiros estão registrados;
- teste E2E e benchmark comparável passam em CI, incluindo vídeo ruim e ausência de pessoa;
- avaliação pareada contra referência/ground truth demonstra que as métricas expostas são estáveis;
- textos do produto não fazem diagnóstico e conservam os guardrails de captura e de risco.

## Consequências

Não há taxa de licença por cliente ou por inferência para esse candidato; Apache-2.0 ainda exige
preservar licença/NOTICE e atribuições aplicáveis. O `.task` contém `pose_detector.tflite` e
`pose_landmarks_detector.tflite`, não um ONNX que possa ser aberto diretamente pelo `ort` atual;
por isso a ponte usa o runtime Tasks, que já coordena detector, crop e tracking. Na máquina de
desenvolvimento ela carregou o runtime distribuído pelo pacote oficial MediaPipe; a distribuição
do produto deve piná-lo em manifesto, incluí-lo por plataforma e manter os notices — nunca buscar
pesos ou bibliotecas em tempo de execução.

Durante a transição, a evolução pessoal do atleta só compara análises confiáveis com a mesma
vista, backend, versão do modelo e geometria angular. A troca YOLO→Blaze cria uma nova linha de
base; nunca é apresentada como melhora ou piora biomecânica.

## Fontes primárias

- [MediaPipe Pose Landmarker — modelos, 33 landmarks e uso on-device](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker)
- [Model Card BlazePose GHUM 3D — licença Apache-2.0](https://storage.googleapis.com/mediapipe-assets/Model%20Card%20BlazePose%20GHUM%203D.pdf)
- [Licença da Ultralytics — AGPL-3.0 ou Enterprise](https://www.ultralytics.com/license)
