"""Contrato de segurança para o registro de ONNX experimentais."""

import hashlib
import json
import os

import pytest

from core.model_assets import AssetValidationError, BlazePoseAssets, Halpe26Assets


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _environment(tmp_path, *, detector=b"detector", pose=b"pose", **changes):
    root = tmp_path / "models"
    root.mkdir(mode=0o700, parents=True)
    (root / "detector.onnx").write_bytes(detector)
    (root / "pose.onnx").write_bytes(pose)
    manifest = {
        "schema_version": 1,
        "backend": "halpe26",
        "status": "experimental",
        "model_version": "rtmpose-m-halpe26-2026.07.22",
        "assets": {
            "detector": {"file": "detector.onnx", "sha256": _hash(detector)},
            "pose": {"file": "pose.onnx", "sha256": _hash(pose)},
        },
    }
    for key, value in changes.items():
        if key == "manifest":
            manifest = value
        else:
            manifest[key] = value
    manifest_path = root / "halpe26-assets.json"
    manifest_path.write_text(json.dumps(manifest))
    return {
        "STRIDE_MODEL_ROOT": str(root),
        "STRIDE_HALPE_ASSET_MANIFEST": str(manifest_path),
    }, manifest_path


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


def test_valida_assets_versionados_e_expoe_ambiente_do_subprocesso(tmp_path):
    env, manifest_path = _environment(tmp_path)

    assets = Halpe26Assets.from_environment(env)

    assert assets.backend == "halpe26"
    assert assets.version == "rtmpose-m-halpe26-2026.07.22"
    assert assets.manifest_path == manifest_path
    assert assets.subprocess_env() == {
        "STRIDE_HALPE_DETECTOR": str(tmp_path / "models" / "detector.onnx"),
        "STRIDE_HALPE_POSE": str(tmp_path / "models" / "pose.onnx"),
    }
    assert len(assets.manifest_sha256) == 64


def test_recusa_configuracao_ausente_ou_caminho_relativo(tmp_path):
    with pytest.raises(AssetValidationError, match="STRIDE_MODEL_ROOT"):
        Halpe26Assets.from_environment({})
    env, _ = _environment(tmp_path)
    env["STRIDE_HALPE_ASSET_MANIFEST"] = "halpe26-assets.json"
    with pytest.raises(AssetValidationError, match="caminho absoluto"):
        Halpe26Assets.from_environment(env)


def test_recusa_manifest_fora_da_raiz_e_travessia_de_asset(tmp_path):
    env, manifest_path = _environment(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_bytes(manifest_path.read_bytes())
    env["STRIDE_HALPE_ASSET_MANIFEST"] = str(outside)
    with pytest.raises(AssetValidationError, match="dentro de STRIDE_MODEL_ROOT"):
        Halpe26Assets.from_environment(env)

    env, manifest_path = _environment(tmp_path / "second")
    manifest = json.loads(manifest_path.read_text())
    manifest["assets"]["pose"]["file"] = "../pose.onnx"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssetValidationError, match="inseguro"):
        Halpe26Assets.from_environment(env)


def test_recusa_asset_ausente_ou_hash_divergente(tmp_path):
    env, manifest_path = _environment(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["assets"]["pose"]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssetValidationError, match="SHA-256 divergente"):
        Halpe26Assets.from_environment(env)

    env, _ = _environment(tmp_path / "second")
    os.unlink(tmp_path / "second" / "models" / "pose.onnx")
    with pytest.raises(AssetValidationError, match="arquivo existente"):
        Halpe26Assets.from_environment(env)


def test_recusa_schema_backend_status_e_symlink(tmp_path):
    env, manifest_path = _environment(tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["backend"] = "yolo17"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssetValidationError, match="não pertence"):
        Halpe26Assets.from_environment(env)

    env, manifest_path = _environment(tmp_path / "second")
    manifest = json.loads(manifest_path.read_text())
    manifest["status"] = "approved"
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(AssetValidationError, match="status experimental"):
        Halpe26Assets.from_environment(env)

    env, _ = _environment(tmp_path / "third")
    root = tmp_path / "third" / "models"
    os.unlink(root / "pose.onnx")
    os.symlink(root / "detector.onnx", root / "pose.onnx")
    with pytest.raises(AssetValidationError, match="sem symlink"):
        Halpe26Assets.from_environment(env)


def test_blazepose_valida_runtime_e_bundle_task_versionados(tmp_path):
    env, manifest_path = _blazepose_environment(tmp_path)

    assets = BlazePoseAssets.from_environment(env)

    assert assets.backend == "blazepose33"
    assert assets.version == "pose-landmarker-full-2026.07"
    assert assets.manifest_path == manifest_path
    assert assets.subprocess_env() == {
        "STRIDE_MEDIAPIPE_LIB": str(tmp_path / "models" / "libmediapipe.dylib"),
        "STRIDE_BLAZEPOSE_MODEL": str(tmp_path / "models" / "pose_landmarker_full.task"),
    }


def test_blazepose_recusa_hash_ou_extensao_incorretos(tmp_path):
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
