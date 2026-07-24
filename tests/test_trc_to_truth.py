"""Adaptador .trc (verdade 3D triangulada, ex.: Pose2Sim) → JSONs do arnês. Hermético."""

import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "trc", Path(__file__).resolve().parent.parent / "tools" / "pose_calibration" / "trc_to_truth.py")
trc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(trc)

# .trc mínimo: RHip/RKnee/RAnkle. Frame0 = perna reta (180°); Frame1 = 90° com z (fora do plano).
_TRC = "\n".join([
    "PathFileType\t4\t(X/Y/Z)\ttest.trc",
    "DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\tOrigDataRate\tOrigDataStartFrame\tOrigNumFrames",
    "30\t30\t2\t3\tm\t30\t1\t2",
    "Frame#\tTime\tRHip\t\t\tRKnee\t\t\tRAnkle\t\t\t",
    "\t\tX1\tY1\tZ1\tX2\tY2\tZ2\tX3\tY3\tZ3",
    "1\t0.000\t0\t1\t0\t0\t0\t0\t0\t-1\t0",
    "2\t0.033\t0\t1\t0\t0\t0\t0\t0\t0\t1",
])


def _write(tmp_path):
    p = tmp_path / "t.trc"
    p.write_text(_TRC)
    return str(p)


def test_parse_trc_acha_marcadores_e_taxa(tmp_path):
    d = trc.parse_trc(_write(tmp_path))
    assert d["rate"] == 30.0 and len(d["rows"]) == 2
    assert d["marker_col"] == {"RHip": 2, "RKnee": 5, "RAnkle": 8}   # cada marcador spanning 3 cols


def test_angulo_interno_3d_do_trc(tmp_path):
    d = trc.parse_trc(_write(tmp_path))
    knee = trc.truth_from_trc(d, "knee", "r")
    assert knee == {0: 180.0, 1: 90.0}                              # reto -> 180; z fora do plano -> 90


def test_convert_escreve_events_e_truth(tmp_path):
    summ = trc.convert(_write(tmp_path), "corredor01", str(tmp_path / "out"))
    assert summ["clip"] == "corredor01" and summ["rate"] == 30.0
    truth = json.loads((tmp_path / "out" / "truth.json").read_text())
    assert truth["corredor01"]["knee"]["0"] == 180.0
    events = json.loads((tmp_path / "out" / "events.json").read_text())
    assert events["corredor01"] == [0, 1]


def test_trc_sem_cabecalho_falha_alto(tmp_path):
    p = tmp_path / "ruim.trc"
    p.write_text("lixo\nsem frame header\n")
    with pytest.raises(ValueError, match="Frame#"):
        trc.parse_trc(str(p))
