# tools/blazepose — provisão do runtime BlazePose (sem pip em produção)

Fecha o item do portão do ADR 0002: **"runtime empacotado sem depender de uma instalação Python"**.
O binário `libmediapipe.{dylib,so}` só vem dentro do wheel oficial do MediaPipe — a gente o extrai
UMA vez, fixa o SHA-256, e o servidor rodando só faz `dlopen`. Nenhum binário entra no Git.

## Provisão (uma vez por plataforma de deploy)

```bash
# 1. Obtenha das fontes oficiais (fora do repo):
#    - o wheel oficial do MediaPipe da plataforma alvo (ex.: mediapipe-0.10.35-...-macosx_arm64.whl)
#    - pose_landmarker_full.task da model card oficial da Google

# 2. Extraia o runtime + fixe os SHAs na raiz privada de modelos:
.venv/bin/python tools/blazepose/provision.py \
  --out-root /opt/strideredge/models \
  --wheel   ./mediapipe-0.10.35-cp39-cp39-macosx_11_0_arm64.whl \
  --task    ./pose_landmarker_full.task \
  --model-version mediapipe-0.10.35+full \
  --expected-runtime-sha f183acadefa74df7d9651beb3ff8339320c544020920e8d9038637f50bfdd453 \
  --expected-task-sha    4eaa5eb7a98365221087693fcc286334cf0858e2eb6e15b506aa4a7ecdcec4ad
```

Isso escreve `/opt/strideredge/models/blazepose/<versão>/manifest.json` + os dois assets.
(Se já tiver o `.dylib`/`.so` extraído, use `--runtime <caminho>` no lugar de `--wheel`.)

## Aponte a API para o manifest

```bash
export STRIDE_MODEL_ROOT=/opt/strideredge/models
export STRIDE_BLAZEPOSE_ASSET_MANIFEST=/opt/strideredge/models/blazepose/<versão>/manifest.json
export STRIDE_POSE_BACKEND=blazepose33
```

`core.model_assets.BlazePoseAssets` valida o manifest (schema/backend/status/SHA) e emite
`STRIDE_MEDIAPIPE_LIB` + `STRIDE_BLAZEPOSE_MODEL` pro subprocesso Rust. Se o SHA não bater ou o
arquivo sumir, a criação da análise **falha explícito** em vez de rodar peso trocado.

## Por plataforma

O binário do runtime é **por-plataforma** (macOS arm64 ≠ Linux x86_64). Rode o `provision.py` uma
vez em cada alvo, com o wheel correspondente da **mesma versão** do MediaPipe, e cada um gera seu
manifest. Ver `ASSET-PROVENANCE.md` p/ origem, licença Apache-2.0 e SHAs verificados.
