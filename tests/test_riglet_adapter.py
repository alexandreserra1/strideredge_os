"""Adaptador Riglet (tools/pose_calibration/riglet_adapter) — parser + eventos + verdade.

Hermético: um mini-CSV Post_Process sintético (mesma estrutura do real). Prova meta/eventos/ângulos,
a conversão INTERNO = 180−flexão, e o mapeamento evento→frame de vídeo (t×50)."""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "riglet_adapter",
    Path(__file__).resolve().parent.parent / "tools" / "pose_calibration" / "riglet_adapter.py")
ra = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ra)

# mini-CSV com a estrutura real: meta / blank / eventos / blank / rótulos / unidades / X,Y,Z / dados
_CSV = """FrameNumber,3
FirstFrame,100
PointFrequency,100
AnalogFrequency,1000

Right_Foot_Strike,1.00,1.50
Right_Foot_Off,1.20

Time,RKneeAngles,,,RHipAngles,,,LKneeAngles,,,LHipAngles,,,
s,deg,deg,deg,deg,deg,deg,deg,deg,deg,deg,deg,deg
,X,Y,Z,X,Y,Z,X,Y,Z,X,Y,Z
1.00,10.0,0,0,30.0,0,0,11.0,0,0,31.0,0,0
1.10,40.0,0,0,35.0,0,0,41.0,0,0,36.0,0,0
1.50,12.0,0,0,32.0,0,0,13.0,0,0,33.0,0,0
"""


def _fixture(tmp_path):
    p = tmp_path / "Run_Comfortable1.csv"
    p.write_text(_CSV)
    return str(p)


def test_parse_meta_eventos_e_angulos(tmp_path):
    p = ra.parse_post_process_csv(_fixture(tmp_path))
    assert p["meta"]["PointFrequency"] == "100"
    assert p["events"]["Right_Foot_Strike"] == [1.0, 1.5]
    assert p["times"] == [1.0, 1.1, 1.5]
    assert p["flex"][("r", "knee")] == [10.0, 40.0, 12.0]          # flexão bruta (X)


def test_interno_e_180_menos_flexao(tmp_path):
    p = ra.parse_post_process_csv(_fixture(tmp_path))
    assert ra.truth_interior(p, "r", "knee", 1.00) == 170.0        # 180-10 (contato: quase reto)
    assert ra.truth_interior(p, "r", "knee", 1.10) == 140.0        # 180-40 (apoio: flexionado)
    assert ra.truth_interior(p, "l", "hip", 1.50) == 147.0         # 180-33


def test_evento_mapeia_para_frame_de_video(tmp_path):
    frames, truth = ra.condition_events_truth([_fixture(tmp_path)], "r", event="strike", fps=50.0)
    assert frames == [50, 75]                                      # round(1.0*50), round(1.5*50)
    assert truth["knee"] == {50: 170.0, 75: 168.0}                 # verdade no MESMO frame do evento


def test_apoio_medio_usa_strike_e_off(tmp_path):
    # strike 1.00 + off 1.20 -> apoio médio 1.10 -> frame round(1.10*50)=55, joelho interno 140
    frames, truth = ra.condition_events_truth([_fixture(tmp_path)], "r", event="midstance", fps=50.0)
    assert frames == [55] and truth["knee"] == {55: 140.0}


def test_check_sync_casa_apoios_da_pose_com_strikes(tmp_path):
    # dump sintético: tornozelo em mínimo (y alto) exatamente nos frames de strike -> lag ~0
    frames = [50, 75]
    dump = {"frames": []}
    for i in range(40, 90):
        y = 100.0 if i in frames else 10.0
        dump["frames"].append({"i": i, "present": True, "kp": {"ankle_r": [0.0, y, 0.9]}})
    (tmp_path / "d.json").write_text(__import__("json").dumps(dump))
    sync = ra.check_sync(str(tmp_path / "d.json"), frames, "r")
    assert sync["ok"] and sync["matched_frac"] == 1.0 and sync["median_lag_frames"] == 0
