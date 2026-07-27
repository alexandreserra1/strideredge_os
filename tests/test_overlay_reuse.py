"""Overlay reusa as poses da passada de métricas (sem re-inferir) — contrato da cmd do motor.

Os fakes de test_form.py sobrescrevem `_run_engine`, então NÃO exercitam a construção da cmd real.
Este teste mira o `_run_engine_impl` de produção com `subprocess.run` e `_normalize` mockados: prova
que a passada de métricas pede `--emit-poses` e que o overlay pede `--overlay-from` (e, nesse caso,
NÃO tenta ler um metrics.json que o overlay-from não escreve)."""

import json
import types

from api.form_processing import FormProcessingMixin
from api.pose_backends import PoseBackendSnapshot


class _Svc(FormProcessingMixin):
    """Instância mínima só com o necessário p/ `_run_engine_impl` (sem tocar Rust/ffmpeg)."""
    binary = "/bin/stride-vision"
    _ENV = {"PATH": "/usr/bin"}


def _snapshot():
    return PoseBackendSnapshot(requested="blazepose33", effective="blazepose33",
                              model_version="v1", model_assets={}, subprocess_env={})


def _patch_run(svc, captured, tmp_path, monkeypatch, write_metrics=True):
    monkeypatch.setattr(svc, "_normalize", lambda original: original)  # sem ffmpeg
    def fake_run(cmd, **kwargs):
        captured.append(cmd)
        if write_metrics:
            (tmp_path / "overlay.metrics.json").write_text(json.dumps({"reliable": True}))
        return types.SimpleNamespace(returncode=0, stderr="", stdout="")
    import api.form_processing as fp
    monkeypatch.setattr(fp.subprocess, "run", fake_run)


def test_metricas_pedem_emit_poses(tmp_path, monkeypatch):
    svc = _Svc()
    captured = []
    _patch_run(svc, captured, tmp_path, monkeypatch)
    poses = tmp_path / "poses.json"
    out = svc._run_engine_impl(tmp_path / "in.mp4", tmp_path / "overlay.mp4", "lateral",
                               _snapshot(), draw_overlay=False, poses_path=poses)
    cmd = captured[0]
    assert "--no-overlay" in cmd and "--emit-poses" in cmd
    assert cmd[cmd.index("--emit-poses") + 1] == str(poses)
    assert out == {"reliable": True}


def test_overlay_reusa_poses_e_nao_le_metricas(tmp_path, monkeypatch):
    svc = _Svc()
    captured = []
    # write_metrics=False: se o impl tentasse ler metrics.json no overlay-from, quebraria.
    _patch_run(svc, captured, tmp_path, monkeypatch, write_metrics=False)
    poses = tmp_path / "poses.json"
    poses.write_text("{}")
    out = svc._run_engine_impl(tmp_path / "in.mp4", tmp_path / "overlay.mp4", "lateral",
                               _snapshot(), draw_overlay=True, overlay_from=poses)
    cmd = captured[0]
    assert "--overlay-from" in cmd and cmd[cmd.index("--overlay-from") + 1] == str(poses)
    assert "--no-overlay" not in cmd            # overlay-from desenha; não é passada só-métricas
    assert out == {}                            # overlay-from não produz métricas
