"""Conversor de anotações de dado próprio → JSONs do arnês. Hermético."""

import importlib.util
import json
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "ann", Path(__file__).resolve().parent.parent / "tools" / "pose_calibration" / "annotations_to_truth.py")
ann = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ann)

_CSV = "clip,frame,joint,angle_deg\nc01,142,knee,141.0\nc01,318,knee,138.5\nc01,142,hip,150.0\nc02,96,knee,160.0\n"


def _write(tmp_path, text):
    p = tmp_path / "ann.csv"
    p.write_text(text)
    return str(p)


def test_converte_para_events_e_truth(tmp_path):
    rows = ann.load_annotations(_write(tmp_path, _CSV))
    events, truth = ann.to_events_and_truth(rows)
    assert events == {"c01": [142, 318], "c02": [96]}                 # frames únicos, ordenados
    assert truth["c01"]["knee"] == {142: 141.0, 318: 138.5}
    assert truth["c01"]["hip"] == {142: 150.0}                        # joelho e quadril separados
    assert truth["c02"]["knee"] == {96: 160.0}


def test_escreve_os_dois_jsons(tmp_path):
    summ = ann.convert(_write(tmp_path, _CSV), str(tmp_path / "out"))
    assert summ["clips"] == 2 and summ["annotations"] == 4
    assert json.loads(Path(summ["truth_json"]).read_text())["c01"]["knee"]["142"] == 141.0


def test_falha_alto_em_joint_invalido_ou_linha_ruim(tmp_path):
    with pytest.raises(ValueError, match="joint inválido"):
        ann.load_annotations(_write(tmp_path, "clip,frame,joint,angle_deg\nc,1,ombro,90\n"))
    with pytest.raises(ValueError):
        ann.load_annotations(_write(tmp_path, "clip,frame,joint,angle_deg\nc,xx,knee,90\n"))
    with pytest.raises(ValueError, match="sem anotações"):
        ann.load_annotations(_write(tmp_path, "clip,frame,joint,angle_deg\n"))
