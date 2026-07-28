"""Retrospecto da lesão: cruza o diagnóstico com os fatores biomecânicos das análises ANTES do
onset (face-validity da literatura contra outcome real). Hermético — banco temporário do conftest."""

import json
import uuid
from datetime import date, timedelta

from analytics.injury_dataset import injury_retrospective
from api.injuries import InjuryService
from core.database import get_connection


def _analise(con, uid, weeks_before, onset, metrics):
    con.execute(
        "INSERT INTO form_analyses (analysis_id, status, metrics, user_id, created_at) "
        "VALUES (?,?,?,?,?)",
        [str(uuid.uuid4()), "done", json.dumps(metrics), uid, onset - timedelta(weeks=weeks_before)])


def test_cruza_fator_presente_antes_do_onset():
    con = get_connection()
    uid = "retro_" + str(uuid.uuid4())
    onset = date(2026, 7, 1)
    # PFP; análises antes com queda pélvica ALTA (fator ligado a PFP) e valgo normal
    _analise(con, uid, 5, onset, {"pelvic_drop_deg": 15.0, "knee_valgus_deg": 6.0, "reliable": True})
    _analise(con, uid, 3, onset, {"pelvic_drop_deg": 14.0, "knee_valgus_deg": 5.0, "reliable": True})
    try:
        out = injury_retrospective(uid, "pfp", onset)
        assert out["status"] == "ok" and out["analyses_before"] == 2 and out["source"] == "PMC6829001"
        by = {s["metric"]: s for s in out["signals"]}
        assert by["pelvic_drop_deg"]["present"] is True     # 14.5 média > 10 -> sinal PRESENTE
        assert by["knee_valgus_deg"]["present"] is False    # ~5.5 dentro do ideal -> ausente
        assert "não prova que causou" in out["caveat"]      # honesto: associação, não causa
    finally:
        con.execute("DELETE FROM form_analyses WHERE user_id = ?", [uid])


def test_sem_analises_no_periodo_degrada_gracioso():
    out = injury_retrospective("retro_sem_hist_" + str(uuid.uuid4()), "pfp", date(2026, 7, 1))
    assert out["status"] == "no_history" and out["signals"] == [] and "Filme" in out["caveat"]


def test_diagnostico_sem_mapa_nao_inventa_sinal():
    out = injury_retrospective("x", "diagnostico_inexistente", date(2026, 7, 1))
    assert out["status"] == "unmapped" and out["signals"] == []


def test_service_exige_dono_diagnostico_e_data():
    svc = InjuryService()
    con = get_connection()
    uid = "retro_svc_" + str(uuid.uuid4())
    # lesão SEM diagnóstico -> status próprio (não cruza)
    rid = con.execute(
        "INSERT INTO injury_reports (id, user_id, region, onset_date) VALUES (?,?,?,?) RETURNING id",
        [str(uuid.uuid4()), uid, "joelho_frente", date(2026, 7, 1)]).fetchone()[0]
    try:
        assert svc.retrospective(str(rid), uid)["status"] == "no_diagnosis"
        # outro atleta não enxerga a lesão (ownership)
        assert svc.retrospective(str(rid), "outro_" + str(uuid.uuid4())) is None
    finally:
        con.execute("DELETE FROM injury_reports WHERE user_id = ?", [uid])
