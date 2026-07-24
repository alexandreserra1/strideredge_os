# Spike Halpe26 / RTMPose

Este diretório é a etapa de prova: não altera o upload, a API nem o backend YOLO17 ativo. O
artefato de produção, se aprovado, será ONNX rodando no Rust; MMPose e MMDeploy entram somente
para preparar e testar esse artefato.

## Fluxo

1. Preencha `manifest.json` com o SHA-256 e confirme as licenças dos pesos/datasets.
2. Converta a saída de uma amostra do MMPose para o JSON normalizado de `validate.py` e rode:

   ```bash
   .venv/bin/python tools/halpe26/validate.py amostra.json --strict-feet
   ```

   Para gerar a amostra com os ONNX oficiais, `run_reference.py` usa o detector YOLOX e o
   RTMPose Halpe26 via `rtmlib` + ONNX Runtime. No Mac, `--device mps` pede Core ML e o runtime
   pode cair para CPU se alguma operação não for compatível:

   ```bash
   /tmp/strideredge-halpe26/bin/python tools/halpe26/run_reference.py frame.jpg \
     --output halpe26.json --device mps
   ```

3. Amostre um vídeo inteiro com o Halpe26. O runner só considera a sequência confiável se 80% dos
   frames amostrados mantiverem os seis pontos de pé; ele não persiste frames do atleta:

   ```bash
   /tmp/strideredge-halpe26/bin/python tools/halpe26/run_video_reference.py corrida.mp4 \
     --output halpe26.json --device mps
   ```

4. Meça YOLO17 e Halpe26 nos mesmos vídeos e compare:

   ```bash
   # YOLO17, sem desenho/encode: mesma medição do runner Halpe26
   cd stride_vision && target/release/stride-vision corrida.mp4 \
     --benchmark --output /tmp/yolo17.json

   # Halpe26: use --sample-fps igual ao FPS do vídeo para sample_stride=1
   /tmp/strideredge-halpe26/bin/python tools/halpe26/run_video_reference.py corrida.mp4 \
     --output /tmp/halpe26.json --device mps --sample-fps 30

   .venv/bin/python tools/halpe26/benchmark.py yolo17.json halpe26.json
   ```

5. Gere o comando de exportação sem executar downloads implícitos:

   ```bash
   .venv/bin/python tools/halpe26/export.py \
     --mmdeploy-root /caminho/mmdeploy --deploy-config /caminho/deploy.py \
     --model-config /caminho/model.py --checkpoint /caminho/body26.pth \
     --output-dir /tmp/halpe26
   ```

`benchmark.py` é o comparador reprodutível de **shadow evaluation**. Ele exige exatamente um par
por vídeo, os mesmos vídeos, contagem de frames, amostragem e estágio de medição (por exemplo,
`decode+pose_inference` nos dois lados), pelo menos a mesma confiabilidade, cobertura de pé no
candidato e pelo menos 75% do FPS agregado do baseline. Quando ambos os relatórios fornecem taxa
de detecção, uma regressão também reprova o gate; quando não fornecem, o relatório marca a métrica
como não comparável em vez de inventar um resultado. Use `--min-foot-coverage 0.80` se o gate da
rodada exigir 80% dos frames com os seis pontos.

`eligible_for_shadow_evaluation=true` (e o nome compatível `eligible_for_rust_adapter`) é uma
decisão operacional: permite a próxima rodada de avaliação, **não** declara melhor precisão
anatômica nem vencedor clínico. A revisão humana do overlay continua obrigatória.

## Backend Rust experimental

O backend foi implementado como `RtmPose26Backend`: RTMDet/YOLOX com NMS + recorte top-down +
decoder SimCC do RTMPose. Ele é **opt-in** e o YOLO17 permanece default. Não passe um ONNX RTMPose
para `STRIDE_MODEL`; informe os dois assets explicitamente:

```bash
cd stride_vision
STRIDE_HALPE_DETECTOR=/caminho/yolox.onnx \
STRIDE_HALPE_POSE=/caminho/rtmpose-halpe26.onnx \
target/release/stride-vision corrida.mp4 overlay.mp4 --backend halpe26
```

No macOS, o crate pede CoreML e cai para CPU quando o provider não está disponível. Os pesos não
entram no repositório e o backend não pode virar padrão enquanto `manifest.json` mantiver a licença
de distribuição dos pesos/datasets como pendente.
