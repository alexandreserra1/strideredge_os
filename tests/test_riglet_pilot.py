"""Seleção/extracão seletiva do piloto Riglet, sem o dataset real de 30 GB."""

import importlib.util
import zipfile
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "run_riglet_pilot",
    Path(__file__).resolve().parent.parent / "tools" / "pose_calibration" / "run_riglet_pilot.py")
pilot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pilot)


def _write_subject(archive, subject, *, complete=True):
    base = f"Data_Run_Walk/{subject}/Session1/Overground_Run/Run_Comfortable/"
    archive.writestr(base + "Video/Run_Comfortable.avi", b"avi")
    if complete:
        archive.writestr(base + "Post_Process/Run_Comfortable1.csv", b"csv-1")
        archive.writestr(base + "Post_Process/Run_Comfortable2.csv", b"csv-2")


def test_seleciona_apenas_corredores_com_avi_e_csv(tmp_path):
    path = tmp_path / "riglet.zip"
    with zipfile.ZipFile(path, "w") as archive:
        _write_subject(archive, "Z99")
        _write_subject(archive, "A01")
        _write_subject(archive, "BROKEN", complete=False)
    assert pilot.available_subjects(path, "Session1") == ["A01", "Z99"]


def test_extrai_so_avi_e_csvs_da_condicao_escolhida(tmp_path):
    path = tmp_path / "riglet.zip"
    with zipfile.ZipFile(path, "w") as archive:
        _write_subject(archive, "A01")
        archive.writestr("Data_Run_Walk/A01/Session1/Overground_Walk/Walk/Video/Walk.avi", b"ignore")
    avi, csvs = pilot.extract_subject(path, "A01", "Session1", tmp_path / "out")
    assert avi.read_bytes() == b"avi"
    assert [path.read_bytes() for path in csvs] == [b"csv-1", b"csv-2"]
    assert not (tmp_path / "out" / "Data_Run_Walk" / "A01" / "Session1" /
                "Overground_Walk").exists()


def test_recusa_zip_slip_antes_de_escrever_fora_do_destino(tmp_path):
    path = tmp_path / "riglet-malicioso.zip"
    with zipfile.ZipFile(path, "w") as archive:
        _write_subject(archive, "A01")
        archive.writestr("Data_Run_Walk/A01/Session1/Overground_Run/Run_Comfortable/../evil.csv", b"evil")
    with zipfile.ZipFile(path) as archive:
        with pytest.raises(ValueError, match="inseguro"):
            pilot._extract_member_safely(
                archive,
                "Data_Run_Walk/A01/Session1/Overground_Run/Run_Comfortable/../../../../../../evil.csv",
                tmp_path / "out",
            )
    assert not (tmp_path / "evil.csv").exists()
