"""Registro verificável de assets para backends de visão experimentais.

O binário Rust recebe caminhos por ambiente, mas não deve confiar em qualquer caminho
que o processo herdou. Este módulo é a fronteira Python: somente um manifest versionado
e checado por SHA-256 pode produzir as variáveis que serão passadas ao subprocesso.

Não faz download nem converte modelos. A integração de jobs deve chamar
``Halpe26Assets.from_environment().subprocess_env()`` antes de iniciar o backend
experimental ``halpe26``.
"""

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_ASSETS = ("detector", "pose")


class AssetValidationError(ValueError):
    """Configuração ou arquivo de modelo não é seguro/reproduzível para uso."""


@dataclass(frozen=True)
class Halpe26Assets:
    """Assets Halpe26 aprovados para uma execução, com a procedência preservada."""

    backend: str
    version: str
    manifest_path: Path
    manifest_sha256: str
    detector_path: Path
    detector_sha256: str
    pose_path: Path
    pose_sha256: str

    @classmethod
    def from_environment(cls, environ: Optional[Mapping[str, str]] = None) -> "Halpe26Assets":
        """Valida o manifest configurado explicitamente no ambiente.

        Requer ``STRIDE_MODEL_ROOT`` e ``STRIDE_HALPE_ASSET_MANIFEST``. Ambos devem ser
        caminhos absolutos; o manifest e seus ONNX ficam *dentro* da raiz, sem symlinks.
        Isso impede path traversal e evita que o servidor execute pesos trocados em cache.
        """
        env = os.environ if environ is None else environ
        root = _configured_directory(env.get("STRIDE_MODEL_ROOT"), "STRIDE_MODEL_ROOT")
        manifest_path = _configured_file(
            env.get("STRIDE_HALPE_ASSET_MANIFEST"), "STRIDE_HALPE_ASSET_MANIFEST", root
        )
        manifest_bytes = _read_file(manifest_path, "manifest")
        try:
            manifest = json.loads(manifest_bytes)
        except (TypeError, json.JSONDecodeError) as exc:
            raise AssetValidationError("manifest Halpe26 não contém JSON válido") from exc
        if not isinstance(manifest, dict):
            raise AssetValidationError("manifest Halpe26 deve ser um objeto JSON")

        if manifest.get("schema_version") != 1:
            raise AssetValidationError("manifest Halpe26 exige schema_version=1")
        if manifest.get("backend") != "halpe26":
            raise AssetValidationError("manifest não pertence ao backend halpe26")
        version = manifest.get("model_version")
        if not isinstance(version, str) or not version.strip():
            raise AssetValidationError("manifest Halpe26 exige model_version não vazio")
        if manifest.get("status") != "experimental":
            raise AssetValidationError("manifest Halpe26 deve declarar status experimental")

        assets = manifest.get("assets")
        if not isinstance(assets, dict):
            raise AssetValidationError("manifest Halpe26 exige o objeto assets")
        checked = {}
        for name in _REQUIRED_ASSETS:
            descriptor = assets.get(name)
            if not isinstance(descriptor, dict):
                raise AssetValidationError("manifest Halpe26 exige assets.%s" % name)
            checked[name] = _validate_asset(root, name, descriptor, {".onnx"})

        return cls(
            backend="halpe26",
            version=version.strip(),
            manifest_path=manifest_path,
            manifest_sha256=_sha256_bytes(manifest_bytes),
            detector_path=checked["detector"][0],
            detector_sha256=checked["detector"][1],
            pose_path=checked["pose"][0],
            pose_sha256=checked["pose"][1],
        )

    def subprocess_env(self) -> dict:
        """As únicas variáveis de assets que o executor Rust precisa receber."""
        return {
            "STRIDE_HALPE_DETECTOR": str(self.detector_path),
            "STRIDE_HALPE_POSE": str(self.pose_path),
        }


@dataclass(frozen=True)
class BlazePoseAssets:
    """Runtime MediaPipe e bundle Pose Landmarker aprovados para uma execução nativa."""

    backend: str
    version: str
    manifest_path: Path
    manifest_sha256: str
    runtime_path: Path
    runtime_sha256: str
    model_path: Path
    model_sha256: str

    @classmethod
    def from_environment(cls, environ: Optional[Mapping[str, str]] = None) -> "BlazePoseAssets":
        """Valida um manifesto privado com o runtime e o `.task` oficiais.

        O binário Rust nunca recebe um caminho vindo de request. Ambos os arquivos precisam estar
        na raiz privada de modelos, sem symlink, e bater o SHA-256 declarado pelo operador.
        """
        env = os.environ if environ is None else environ
        root = _configured_directory(env.get("STRIDE_MODEL_ROOT"), "STRIDE_MODEL_ROOT")
        manifest_path = _configured_file(
            env.get("STRIDE_BLAZEPOSE_ASSET_MANIFEST"), "STRIDE_BLAZEPOSE_ASSET_MANIFEST", root
        )
        manifest_bytes = _read_file(manifest_path, "manifest")
        try:
            manifest = json.loads(manifest_bytes)
        except (TypeError, json.JSONDecodeError) as exc:
            raise AssetValidationError("manifest BlazePose não contém JSON válido") from exc
        if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
            raise AssetValidationError("manifest BlazePose exige schema_version=1")
        if manifest.get("backend") != "blazepose33":
            raise AssetValidationError("manifest não pertence ao backend blazepose33")
        version = manifest.get("model_version")
        if not isinstance(version, str) or not version.strip():
            raise AssetValidationError("manifest BlazePose exige model_version não vazio")
        if manifest.get("status") != "experimental":
            raise AssetValidationError("manifest BlazePose deve declarar status experimental")
        assets = manifest.get("assets")
        if not isinstance(assets, dict):
            raise AssetValidationError("manifest BlazePose exige o objeto assets")
        runtime = _validate_asset(root, "runtime", assets.get("runtime"), {".dylib", ".so", ".dll"})
        model = _validate_asset(root, "pose_landmarker", assets.get("pose_landmarker"), {".task"})
        return cls(
            backend="blazepose33", version=version.strip(), manifest_path=manifest_path,
            manifest_sha256=_sha256_bytes(manifest_bytes), runtime_path=runtime[0],
            runtime_sha256=runtime[1], model_path=model[0], model_sha256=model[1],
        )

    def subprocess_env(self) -> dict:
        return {
            "STRIDE_MEDIAPIPE_LIB": str(self.runtime_path),
            "STRIDE_BLAZEPOSE_MODEL": str(self.model_path),
        }


def _configured_directory(value: Optional[str], variable: str) -> Path:
    if not value:
        raise AssetValidationError("%s é obrigatório para os assets de pose" % variable)
    path = Path(value)
    if not path.is_absolute():
        raise AssetValidationError("%s deve ser um caminho absoluto" % variable)
    if path.is_symlink() or not path.is_dir():
        raise AssetValidationError("%s deve ser um diretório existente, sem symlink" % variable)
    _require_private_directory(path, variable)
    return path.resolve()


def _configured_file(value: Optional[str], variable: str, root: Path) -> Path:
    if not value:
        raise AssetValidationError("%s é obrigatório para o manifesto de assets" % variable)
    path = Path(value)
    if not path.is_absolute():
        raise AssetValidationError("%s deve ser um caminho absoluto" % variable)
    return _safe_file(path, root, variable)


def _validate_asset(root: Path, name: str, descriptor: object, suffixes: set) -> tuple:
    if not isinstance(descriptor, dict):
        raise AssetValidationError("manifest exige assets.%s" % name)
    filename = descriptor.get("file")
    expected_hash = descriptor.get("sha256")
    if not isinstance(filename, str) or not filename:
        raise AssetValidationError("assets.%s.file deve ser um caminho relativo" % name)
    relative = Path(filename)
    if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
        raise AssetValidationError("assets.%s.file contém caminho inseguro" % name)
    if relative.suffix.lower() not in suffixes:
        allowed = " ou ".join(sorted(suffixes))
        raise AssetValidationError("assets.%s.file deve apontar para %s" % (name, allowed))
    if not isinstance(expected_hash, str) or not _SHA256.fullmatch(expected_hash):
        raise AssetValidationError("assets.%s.sha256 deve ter 64 hexadecimais minúsculos" % name)

    path = _safe_file(root / relative, root, "assets.%s.file" % name)
    actual_hash = _sha256_file(path)
    if actual_hash != expected_hash:
        raise AssetValidationError("SHA-256 divergente para assets.%s" % name)
    return path, actual_hash


def _safe_file(path: Path, root: Path, label: str) -> Path:
    if path.is_symlink() or not path.is_file():
        raise AssetValidationError("%s deve ser um arquivo existente, regular e sem symlink" % label)
    resolved = path.resolve()
    if not _is_within(resolved, root):
        raise AssetValidationError("%s deve ficar dentro de STRIDE_MODEL_ROOT" % label)
    return resolved


def _require_private_directory(path: Path, variable: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o022:
        raise AssetValidationError("%s não pode permitir escrita por grupo ou outros" % variable)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _read_file(path: Path, label: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise AssetValidationError("não foi possível ler %s" % label) from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise AssetValidationError("não foi possível calcular SHA-256 do asset") from exc
    return digest.hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
