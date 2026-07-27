#!/usr/bin/env python3
"""Provisiona o runtime BlazePose (MediaPipe) como asset FIXADO, sem depender de pip em produção.

O portão do ADR 0002 exige "runtime empacotado sem depender de uma instalação Python". O binário
`libmediapipe.{dylib,so}` só é distribuído dentro do wheel oficial do MediaPipe — então a gente
o extrai UMA vez, computa o SHA-256, e o copia pra raiz privada de modelos junto do
`pose_landmarker_full.task`. O wheel vira PROCEDÊNCIA (registro de origem), não dependência de
execução: o servidor rodando só faz `dlopen` no binário fixado, sem mediapipe instalado.

Esta ferramenta NÃO baixa nem instala nada — opera em caminhos que o operador já obteve das fontes
oficiais (mesma disciplina de `tools/halpe26/export.py`). O manifest resultante é exatamente o que
`core.model_assets.BlazePoseAssets.from_environment` valida (schema_version=1, backend blazepose33,
status experimental, assets.runtime + assets.pose_landmarker com SHA-256).
"""

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Optional

# nome do binário do runtime dentro do wheel do MediaPipe (por plataforma).
RUNTIME_NAMES = {"dylib": "libmediapipe.dylib", "so": "libmediapipe.so"}
# caminho do runtime dentro do wheel oficial (mediapipe/tasks/c/).
WHEEL_RUNTIME_DIR = "mediapipe/tasks/c/"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_runtime_from_wheel(wheel: Path, dest_dir: Path) -> Path:
    """Extrai o `libmediapipe.{dylib,so}` de um wheel oficial do MediaPipe. Falha alto se o wheel
    trouxer zero ou mais de um candidato — não se adivinha binário num app de lesão."""
    with zipfile.ZipFile(wheel) as zf:
        members = [n for n in zf.namelist()
                   if n.startswith(WHEEL_RUNTIME_DIR)
                   and Path(n).name in RUNTIME_NAMES.values()]
        if len(members) != 1:
            raise ValueError(
                f"wheel deve conter exatamente 1 runtime em {WHEEL_RUNTIME_DIR}; achei {members}")
        member = members[0]
        dest = dest_dir / Path(member).name
        with zf.open(member) as src, dest.open("wb") as out:
            shutil.copyfileobj(src, out)
    dest.chmod(0o755)
    return dest


def resolve_runtime(wheel: Optional[str], runtime: Optional[str], work_dir: Path) -> Path:
    if bool(wheel) == bool(runtime):
        raise ValueError("informe exatamente um de --wheel ou --runtime")
    if wheel:
        return extract_runtime_from_wheel(Path(wheel), work_dir)
    src = Path(runtime)
    if src.suffix.lstrip(".") not in RUNTIME_NAMES:
        raise ValueError("--runtime deve ser um .dylib ou .so")
    return src


def build_manifest(model_version: str, runtime_rel: str, runtime_sha: str,
                   task_rel: str, task_sha: str) -> dict:
    """Manifest no formato que BlazePoseAssets valida (schema_version=1, status experimental)."""
    return {
        "schema_version": 1,
        "backend": "blazepose33",
        "model_version": model_version,
        "status": "experimental",
        "assets": {
            "runtime": {"file": runtime_rel, "sha256": runtime_sha},
            "pose_landmarker": {"file": task_rel, "sha256": task_sha},
        },
    }


def _verify_expected(label: str, got: str, expected: Optional[str]) -> None:
    if expected and got.lower() != expected.lower():
        raise ValueError(f"SHA-256 do {label} não bate: esperado {expected}, obtido {got}")


def provision(out_root: str, task: str, model_version: str,
              wheel: Optional[str] = None, runtime: Optional[str] = None,
              expected_runtime_sha: Optional[str] = None,
              expected_task_sha: Optional[str] = None) -> dict:
    """Copia runtime + .task pra <out_root>/blazepose/<model_version>/ e escreve manifest.json.
    Retorna um resumo com os SHA-256 fixados. Não sobrescreve destino já existente (append-only)."""
    root = Path(out_root)
    if not root.is_absolute():
        raise ValueError("out_root deve ser caminho absoluto (raiz privada de modelos)")
    stage = root / "blazepose" / model_version
    if stage.exists():
        raise ValueError(f"destino já existe: {stage} — não sobrescrevo asset fixado")
    stage.mkdir(parents=True)

    runtime_src = resolve_runtime(wheel, runtime, stage)
    runtime_dest = stage / runtime_src.name
    if runtime_src.resolve() != runtime_dest.resolve():
        shutil.copyfile(runtime_src, runtime_dest)
        runtime_dest.chmod(0o755)
    runtime_sha = sha256_file(runtime_dest)
    _verify_expected("runtime", runtime_sha, expected_runtime_sha)

    task_src = Path(task)
    if task_src.suffix != ".task":
        raise ValueError("--task deve ser um bundle .task")
    task_dest = stage / task_src.name
    shutil.copyfile(task_src, task_dest)
    task_sha = sha256_file(task_dest)
    _verify_expected("pose_landmarker", task_sha, expected_task_sha)

    runtime_rel = str(runtime_dest.relative_to(root))
    task_rel = str(task_dest.relative_to(root))
    manifest = build_manifest(model_version, runtime_rel, runtime_sha, task_rel, task_sha)
    manifest_path = stage / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return {
        "manifest_path": str(manifest_path),
        "runtime_sha256": runtime_sha,
        "task_sha256": task_sha,
        "model_root": str(root),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Fixa o runtime BlazePose como asset (sem pip em prod)")
    ap.add_argument("--out-root", required=True, help="raiz privada de modelos (STRIDE_MODEL_ROOT)")
    ap.add_argument("--task", required=True, help="pose_landmarker_full.task oficial")
    ap.add_argument("--model-version", required=True, help="ex.: mediapipe-0.10.35+full")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--wheel", help="wheel oficial do MediaPipe (extrai o libmediapipe)")
    src.add_argument("--runtime", help="libmediapipe.{dylib,so} já extraído")
    ap.add_argument("--expected-runtime-sha", help="SHA-256 conhecido-bom do runtime (trava)")
    ap.add_argument("--expected-task-sha", help="SHA-256 conhecido-bom do .task (trava)")
    a = ap.parse_args(argv)
    try:
        summary = provision(a.out_root, a.task, a.model_version, a.wheel, a.runtime,
                            a.expected_runtime_sha, a.expected_task_sha)
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2))
    print("\naponte a API para:", file=sys.stderr)
    print(f"  STRIDE_MODEL_ROOT={summary['model_root']}", file=sys.stderr)
    print(f"  STRIDE_BLAZEPOSE_ASSET_MANIFEST={summary['manifest_path']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
