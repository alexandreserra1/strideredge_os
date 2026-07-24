"""Seleção server-side e proveniência dos assets de pose.

Este módulo decide qual backend pode executar uma análise. Nenhum dado do request escolhe paths,
assets ou variáveis do subprocesso; `FormService` só recebe um snapshot já validado.
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Protocol


class BackendConfigurationError(RuntimeError):
    """O backend escolhido pelo operador não está pronto para receber análises."""


@dataclass(frozen=True)
class PoseBackendSnapshot:
    """Identidade imutável do motor de uma análise, sem paths expostos ao banco/API."""

    requested: str
    effective: str
    model_version: Optional[str]
    model_assets: Mapping[str, Optional[str]]
    subprocess_env: Mapping[str, str]


class PoseBackendResolver(Protocol):
    """Costura mínima para o futuro registry: `resolve(backend)` -> snapshot executável."""

    def resolve(self, backend: str) -> PoseBackendSnapshot:
        ...


class ServerPoseBackendResolver:
    """Resolve somente assets configurados no host; nenhum request participa desta decisão."""

    def __init__(self, yolo_model: Path):
        self.yolo_model = yolo_model

    @staticmethod
    def _sha256(path: Path) -> Optional[str]:
        """Hash de um asset existente; ausência mantém o comportamento legado (job falha honesto)."""
        if not path.is_file():
            return None
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def resolve(self, backend: str) -> PoseBackendSnapshot:
        if backend == "yolo17":
            return PoseBackendSnapshot(
                requested=backend, effective="yolo17", model_version="yolo11n-pose",
                model_assets={"yolo11n-pose.onnx": self._sha256(self.yolo_model)},
                subprocess_env={"STRIDE_MODEL": str(self.yolo_model)},
            )
        if backend == "halpe26":
            try:
                from core.model_assets import Halpe26Assets
                assets = Halpe26Assets.from_environment()
            except (ImportError, ValueError, OSError) as exc:
                raise BackendConfigurationError("Assets Halpe26 indisponíveis no servidor.") from exc
            if not assets.detector_path.is_file() or not assets.pose_path.is_file():
                raise BackendConfigurationError("Assets Halpe26 indisponíveis no servidor.")
            return PoseBackendSnapshot(
                requested=backend, effective=assets.backend, model_version=assets.version,
                model_assets={
                    "detector": assets.detector_sha256,
                    "pose": assets.pose_sha256,
                },
                subprocess_env=assets.subprocess_env(),
            )
        if backend == "blazepose33":
            try:
                from core.model_assets import BlazePoseAssets
                assets = BlazePoseAssets.from_environment()
            except (ImportError, ValueError, OSError) as exc:
                raise BackendConfigurationError("Assets BlazePose indisponíveis no servidor.") from exc
            if not assets.runtime_path.is_file() or not assets.model_path.is_file():
                raise BackendConfigurationError("Assets BlazePose indisponíveis no servidor.")
            return PoseBackendSnapshot(
                requested=backend, effective=assets.backend, model_version=assets.version,
                model_assets={
                    "runtime": assets.runtime_sha256,
                    "pose_landmarker": assets.model_sha256,
                },
                subprocess_env=assets.subprocess_env(),
            )
        raise BackendConfigurationError("Backend de pose não permitido.")
