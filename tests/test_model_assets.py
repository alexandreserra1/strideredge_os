"""Contrato de segurança do registro de assets do motor de pose (BlazePose)."""

import hashlib
import json
import os

import pytest

from core.model_assets import AssetValidationError, BlazePoseAssets


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _blazepose_environment(tmp_path, *, runtime=b"runtime", model=b"task", **changes):
    root = tmp_path / "models"
    root.mkdir(mode=0o700, parents=True)
    (root / "libmediapipe.dylib").write_bytes(runtime)
    (root / "pose_landmarker_full.task").write_bytes(model)
    manifest = {
        "schema_version": 1,
        "backend": "blazepose33",
        "status": "experimental",
        "model_version": "pose-landmarker-full-2026.07",
        "assets": {
            "runtime": {"file": "libmediapipe.dylib", "sha256": _hash(runtime)},
            "pose_landmarker": {"file": "pose_landmarker_full.task", "sha256": _hash(model)},
        },
    }
    for key, value in changes.items():
        manifest[key] = value
    manifest_path = root / "blazepose-assets.json"
    manifest_path.write_text(json.dumps(manifest))
    return {
        "STRIDE_MODEL_ROOT": str(root),
        "STRIDE_BLAZEPOSE_ASSET_MANIFEST": str(manifest_path),
    }, manifest_path


def test_valida_runtime_e_bundle_task_versionados(tmp_path):
    env, manifest_path = _blazepose_environment(tmp_path)

    assets = BlazePoseAssets.from_environment(env)

    assert assets.backend == "blazepose33"
    assert assets.version == "pose-landmarker-full-2026.07"
    assert assets.manifest_path == manifest_path
    assert assets.subprocess_env() == {
        "STRIDE_MEDIAPIPE_LIB": str(tmp_path / "models" / "libmediapipe.dylib"),
        "STRIDE_BLAZEPOSE_MODEL": str(tmp_path / "models" / "pose_landmarker_full.task"),
    }


def test_recusa_hash_ou_extensao_incorretos(tmp_path):
    env, manifest_path = _blazepose_environment(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["assets"]["runtime"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssetValidationError, match="SHA-256 divergente"):
        BlazePoseAssets.from_environment(env)

    env, manifest_path = _blazepose_environment(tmp_path / "second")
    manifest = json.loads(manifest_path.read_text())
    manifest["assets"]["pose_landmarker"]["file"] = "pose.onnx"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssetValidationError, match=".task"):
        BlazePoseAssets.from_environment(env)


def test_recusa_configuracao_ausente_ou_caminho_relativo(tmp_path):
    with pytest.raises(AssetValidationError, match="STRIDE_MODEL_ROOT"):
        BlazePoseAssets.from_environment({})
    env, _ = _blazepose_environment(tmp_path)
    env["STRIDE_BLAZEPOSE_ASSET_MANIFEST"] = "blazepose-assets.json"
    with pytest.raises(AssetValidationError, match="caminho absoluto"):
        BlazePoseAssets.from_environment(env)


def test_recusa_manifest_fora_da_raiz_e_travessia_de_asset(tmp_path):
    env, manifest_path = _blazepose_environment(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes(manifest_path.read_bytes())
    env["STRIDE_BLAZEPOSE_ASSET_MANIFEST"] = str(outside)
    with pytest.raises(AssetValidationError, match="dentro de STRIDE_MODEL_ROOT"):
        BlazePoseAssets.from_environment(env)

    env, manifest_path = _blazepose_environment(tmp_path / "second")
    manifest = json.loads(manifest_path.read_text())
    manifest["assets"]["pose_landmarker"]["file"] = "../pose_landmarker_full.task"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssetValidationError, match="inseguro"):
        BlazePoseAssets.from_environment(env)


def test_recusa_asset_ausente(tmp_path):
    env, _ = _blazepose_environment(tmp_path)
    os.unlink(tmp_path / "models" / "pose_landmarker_full.task")
    with pytest.raises(AssetValidationError, match="arquivo existente"):
        BlazePoseAssets.from_environment(env)


def test_recusa_schema_backend_status_e_symlink(tmp_path):
    env, manifest_path = _blazepose_environment(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["backend"] = "yolo17"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssetValidationError, match="não pertence"):
        BlazePoseAssets.from_environment(env)

    env, manifest_path = _blazepose_environment(tmp_path / "second")
    manifest = json.loads(manifest_path.read_text())
    manifest["status"] = "approved"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssetValidationError, match="status experimental"):
        BlazePoseAssets.from_environment(env)

    env, _ = _blazepose_environment(tmp_path / "third")
    root = tmp_path / "third" / "models"
    os.unlink(root / "pose_landmarker_full.task")
    os.symlink(root / "libmediapipe.dylib", root / "pose_landmarker_full.task")
    with pytest.raises(AssetValidationError, match="sem symlink"):
        BlazePoseAssets.from_environment(env)
