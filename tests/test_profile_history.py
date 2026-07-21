"""EPIC B — perfil estendido (campos de plano/tênis) + histórico de lesão sensibilizando o risco.
Hermético: usa o DB de teste do conftest."""

import uuid

from api.profile import ProfileService, _FIELDS
from analytics.injury_dataset import injury_history
from analytics.injury_risk import assess
from api.injuries import InjuryService
from core.database import get_connection


def test_perfil_grava_e_le_campos_novos():
    svc = ProfileService()
    uid = str(uuid.uuid4())
    try:
        data = {"height_cm": 178.0, "weight_kg": 90.0, "years_running": 3.0, "goal": "correr sem dor",
                "goal_timeframe_weeks": 8, "weekly_volume_km": 40.0, "days_per_week": 4,
                "current_shoe": "Nike Pegasus", "footstrike_pref": "antepe"}
        out = svc.upsert(uid, data)
        assert set(out) == set(_FIELDS)                       # todos os campos conhecidos
        got = svc.get(uid)
        assert got["goal_timeframe_weeks"] == 8 and got["current_shoe"] == "Nike Pegasus"
        assert got["weekly_volume_km"] == 40.0 and got["footstrike_pref"] == "antepe"
    finally:
        get_connection().execute("DELETE FROM athlete_profile WHERE user_id = ?", [uid])


def test_injury_history_traz_fatores_da_lesao_reportada():
    uid = str(uuid.uuid4())
    con = get_connection()
    try:
        InjuryService().log(uid, {"region": "joelho_frente", "diagnosis": "pfp",
                                  "onset_date": "2026-06-01", "q_pain": 2})
        hist = injury_history(uid)
        assert "pfp" in hist["diagnoses"] and "joelho_frente" in hist["regions"]
        # PFP liga a queda pélvica + valgo → viram fatores sensibilizados
        assert "pelvic_drop_deg" in hist["factors"] and "knee_valgus_deg" in hist["factors"]
    finally:
        con.execute("DELETE FROM injury_reports WHERE user_id = ?", [uid])


def test_historico_sensibiliza_o_risco():
    """Lesão prévia (preditor #1) eleva o risco nos fatores ligados a ela."""
    m = {"cadence_spm": 150.0, "pelvic_drop_deg": 16.0, "knee_valgus_deg": 14.0}
    sem = assess(m)
    com = assess(m, history={"factors": ["pelvic_drop_deg", "knee_valgus_deg"]})
    assert com["score"] > sem["score"]                       # histórico pesa mais
    sens = [f["metric"] for f in com["factors"] if f.get("sensitized")]
    assert "pelvic_drop_deg" in sens and "knee_valgus_deg" in sens
    assert not any(f.get("sensitized") for f in sem["factors"])  # sem histórico, nada sensibilizado


def test_injury_history_vazio_sem_usuario():
    assert injury_history("")["factors"] == []
