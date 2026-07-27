"""Testes herméticos do IC bootstrap: determinismo + detecção honesta de (não-)significância."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "bootstrap_ci",
    Path(__file__).resolve().parent.parent / "tools" / "pose_calibration" / "bootstrap_ci.py")
boot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(boot)


def test_ci_e_deterministico_e_contem_a_media():
    xs = [10.0, 12.0, 14.0, 16.0, 18.0]
    a = boot.bootstrap_ci(xs, seed=1)
    b = boot.bootstrap_ci(xs, seed=1)
    assert a == b                                   # mesma seed -> mesmo resultado
    assert a["ci_low"] <= a["mean"] <= a["ci_high"]
    assert a["mean"] == 14.0 and a["n"] == 5


def test_diferenca_pareada_clara_e_significativa():
    # b é sempre ~5° menor que a, por corredor -> a-b > 0 estável, IC não cruza zero.
    a = [30.0, 28.0, 26.0, 24.0, 22.0]
    b = [25.0, 23.0, 21.0, 19.0, 17.0]
    r = boot.paired_diff_ci(a, b, seed=1)
    assert r["significant"] is True and r["ci_low"] > 0


def test_diferenca_ruidosa_nao_e_significativa():
    # sinal pequeno afogado em ruído -> IC cruza zero -> não-significativo (a honestidade do gate).
    a = [26.0, 18.0, 34.0, 20.0, 30.0]
    b = [25.0, 19.0, 33.0, 21.0, 29.0]
    r = boot.paired_diff_ci(a, b, seed=1)
    assert r["significant"] is False and r["ci_low"] < 0 < r["ci_high"]


def test_analyze_le_report_e_pareia(tmp_path):
    report = tmp_path / "r.json"
    report.write_text('{"rows":['
                      '{"s":"A","yolo_2d":{"mae":30},"blaze_3d":{"mae":25}},'
                      '{"s":"B","yolo_2d":{"mae":28},"blaze_3d":{"mae":23}}]}')
    out = boot.analyze(str(report), backends=["yolo_2d", "blaze_3d"])
    assert out["n_rows"] == 2
    assert out["per_backend"]["blaze_3d"]["mean"] == 24.0
    assert "yolo_2d_minus_blaze_3d" in out["paired"]
