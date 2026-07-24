"""Testes herméticos da provisão do runtime BlazePose: contrato de asset, não inferência.

Prova que `provision.py` extrai o runtime de um wheel, fixa SHA-256, escreve um manifest que o
`core.model_assets.BlazePoseAssets` real ACEITA, e falha alto em wheel/SHA errados. Sem baixar nada.
"""

import importlib.util
import io
import json
import os
import zipfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _tool():
    path = _ROOT / "tools" / "blazepose" / "provision.py"
    spec = importlib.util.spec_from_file_location("blazepose_provision", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_wheel(path: Path, runtime_bytes: bytes) -> Path:
    """Wheel-fake com o libmediapipe.dylib no caminho oficial mediapipe/tasks/c/."""
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mediapipe/tasks/c/libmediapipe.dylib", runtime_bytes)
        zf.writestr("mediapipe/__init__.py", "x = 1\n")
    return path


def _blazepose_assets():
    path = _ROOT / "core" / "model_assets.py"
    spec = importlib.util.spec_from_file_location("model_assets", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BlazePoseAssets


def test_provisiona_do_wheel_e_manifest_valida_no_model_assets(tmp_path):
    prov = _tool()
    root = tmp_path / "models"
    root.mkdir(mode=0o700)
    wheel = _fake_wheel(tmp_path / "mp.whl", b"RUNTIME-BYTES")
    task = tmp_path / "pose_landmarker_full.task"
    task.write_bytes(b"TASK-BYTES")

    summary = prov.provision(str(root), str(task), "mediapipe-0.10.35+full", wheel=str(wheel))
    manifest = json.loads(Path(summary["manifest_path"]).read_text())
    assert manifest["backend"] == "blazepose33" and manifest["status"] == "experimental"
    assert manifest["assets"]["runtime"]["sha256"] == summary["runtime_sha256"]

    # o manifest gerado precisa passar no validador REAL de produção.
    BlazePoseAssets = _blazepose_assets()
    env = {"STRIDE_MODEL_ROOT": str(root),
           "STRIDE_BLAZEPOSE_ASSET_MANIFEST": summary["manifest_path"]}
    assets = BlazePoseAssets.from_environment(env)
    assert assets.backend == "blazepose33"
    sub = assets.subprocess_env()
    assert set(sub) == {"STRIDE_MEDIAPIPE_LIB", "STRIDE_BLAZEPOSE_MODEL"}
    assert Path(sub["STRIDE_MEDIAPIPE_LIB"]).is_file()


def test_expected_sha_errado_falha_alto(tmp_path):
    prov = _tool()
    root = tmp_path / "models"
    root.mkdir(mode=0o700)
    wheel = _fake_wheel(tmp_path / "mp.whl", b"RUNTIME-BYTES")
    task = tmp_path / "x.task"
    task.write_bytes(b"TASK")
    with pytest.raises(ValueError, match="não bate"):
        prov.provision(str(root), str(task), "v1", wheel=str(wheel),
                       expected_runtime_sha="0" * 64)


def test_wheel_sem_runtime_falha_alto(tmp_path):
    prov = _tool()
    empty = tmp_path / "empty.whl"
    with zipfile.ZipFile(empty, "w") as zf:
        zf.writestr("mediapipe/__init__.py", "x = 1\n")
    with pytest.raises(ValueError, match="exatamente 1 runtime"):
        prov.extract_runtime_from_wheel(empty, tmp_path)


def test_exige_wheel_ou_runtime_nao_ambos(tmp_path):
    prov = _tool()
    with pytest.raises(ValueError, match="exatamente um"):
        prov.resolve_runtime(None, None, tmp_path)
    with pytest.raises(ValueError, match="exatamente um"):
        prov.resolve_runtime("a.whl", "b.dylib", tmp_path)


def test_destino_existente_nao_sobrescreve(tmp_path):
    prov = _tool()
    root = tmp_path / "models"
    root.mkdir(mode=0o700)
    (root / "blazepose" / "v1").mkdir(parents=True)
    task = tmp_path / "x.task"
    task.write_bytes(b"T")
    runtime = tmp_path / "libmediapipe.dylib"
    runtime.write_bytes(b"R")
    with pytest.raises(ValueError, match="já existe"):
        prov.provision(str(root), str(task), "v1", runtime=str(runtime))
