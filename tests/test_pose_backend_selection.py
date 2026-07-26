"""Seleção server-side de backend de pose e proveniência por análise."""

import pytest

from api.form import (BackendConfigurationError, FormService, PoseBackendSnapshot,
                      VIDEOS_DIR)
from core.database import get_connection
from core.jobs import JobQueue


class NoRunQueue(JobQueue):
    """Captura o job sem executar Rust/ffmpeg."""

    def __init__(self):
        self.calls = []

    def start(self):
        pass

    def enqueue(self, fn, *args, **kwargs):
        self.calls.append((fn, args, kwargs))
        return True


class FixedResolver:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.requested = []

    def resolve(self, backend):
        self.requested.append(backend)
        return self.snapshot


def _blazepose_snapshot(tmp_path) -> PoseBackendSnapshot:
    runtime = tmp_path / "libmediapipe.dylib"
    model = tmp_path / "pose_landmarker_full.task"
    runtime.write_bytes(b"runtime")
    model.write_bytes(b"task")
    return PoseBackendSnapshot(
        requested="blazepose33", effective="blazepose33", model_version="pose-landmarker-full",
        model_assets={"runtime": "a" * 64, "pose_landmarker": "b" * 64},
        subprocess_env={
            "STRIDE_MEDIAPIPE_LIB": str(runtime),
            "STRIDE_BLAZEPOSE_MODEL": str(model),
        },
    )


def test_backend_fora_da_allowlist_nao_chega_ao_registro():
    with pytest.raises(BackendConfigurationError):
        FormService(queue=NoRunQueue(), backend="../../modelo-do-cliente")


def test_resolver_nao_pode_injetar_env_do_subprocesso(tmp_path):
    snapshot = _blazepose_snapshot(tmp_path)
    unsafe = PoseBackendSnapshot(
        requested=snapshot.requested, effective=snapshot.effective,
        model_version=snapshot.model_version, model_assets=snapshot.model_assets,
        subprocess_env={**snapshot.subprocess_env, "LD_PRELOAD": "/tmp/evil.dylib"},
    )
    svc = FormService(queue=NoRunQueue(), backend="blazepose33", backend_resolver=FixedResolver(unsafe))
    with pytest.raises(BackendConfigurationError):
        svc.create(b"video", "run.mp4")


def test_snapshot_blazepose_aprovado_chega_ao_job(tmp_path):
    queue = NoRunQueue()
    svc = FormService(queue=queue, backend="blazepose33",
                      backend_resolver=FixedResolver(_blazepose_snapshot(tmp_path)))
    out = svc.create(b"video", "run.mp4")
    try:
        assert queue.calls[0][1][4].effective == "blazepose33"
        assert svc.get(out["analysis_id"])["backend"]["assets"] == {
            "runtime": "a" * 64, "pose_landmarker": "b" * 64,
        }
    finally:
        get_connection().execute("DELETE FROM form_analyses WHERE analysis_id = ?", [out["analysis_id"]])
        FormService._discard_dir(VIDEOS_DIR / out["analysis_id"])
