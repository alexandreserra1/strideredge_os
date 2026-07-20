"""Verificação LONGITUDINAL do modelo de risco: um atleta desenvolve PFP ao longo de 8 semanas
com a forma degradando (queda pélvica + valgo pioram). Confere se o modelo FAZ SENTIDO:
  - o risco SOBE conforme a biomecânica piora (progressão monotônica, pelos fatores certos);
  - o padrão PRÉ-lesão bate com a lesão real (face-validity via validate_literature_model).
Hermético: usa o DB de teste do conftest."""

import json
import uuid
from datetime import date, timedelta

from analytics.injury_risk import assess
from analytics.injury_dataset import validate_literature_model
from api.injuries import InjuryService
from core.database import get_connection


def _ingest_degrading_athlete(uid: str) -> list:
    """8 semanas de análises com queda pélvica/valgo piorando + cadência caindo. Devolve os scores."""
    con = get_connection()
    start = date(2026, 5, 1)
    scores = []
    for wk in range(8):
        metrics = {
            "cadence_spm": round(174 - wk * 2.5, 1),      # 174 -> 156
            "pelvic_drop_deg": round(5 + wk * 1.7, 1),    # 5 -> 17 (fator de PFP)
            "knee_valgus_deg": round(4 + wk * 1.5, 1),    # 4 -> 15 (fator de PFP)
            "knee_contact_deg": 170.0, "vertical_oscillation_pct": 7.0,
            "ground_contact_ms": 240.0, "trunk_lean_deg": 8.0, "reliable": True,
        }
        con.execute("INSERT INTO form_analyses (analysis_id, status, metrics, user_id, created_at) "
                    "VALUES (?, 'done', ?, ?, ?)",
                    [str(uuid.uuid4()), json.dumps(metrics), uid, start + timedelta(weeks=wk)])
        scores.append(assess(metrics)["score"])
    return scores


def test_risco_sobe_conforme_a_forma_degrada():
    uid = str(uuid.uuid4())
    try:
        scores = _ingest_degrading_athlete(uid)
        # monotônico não-decrescente, e o fim MUITO acima do início
        assert scores == sorted(scores), f"risco não subiu monotônico: {scores}"
        assert scores[-1] > scores[0] and scores[0] == 0.0 and scores[-1] > 4.0
        # a banda final é 'alto' (forma bem degradada)
        final = assess({"cadence_spm": 156.5, "pelvic_drop_deg": 16.9, "knee_valgus_deg": 14.5})
        assert final["risk_band"] == "alto"
    finally:
        get_connection().execute("DELETE FROM form_analyses WHERE user_id = ?", [uid])


def test_padrao_pre_lesao_bate_com_a_lesao_reportada():
    """Face-validity: reporta PFP; a validação confirma que o pré-onset flagou os fatores de PFP."""
    uid = str(uuid.uuid4())
    con = get_connection()
    try:
        _ingest_degrading_athlete(uid)
        onset = date(2026, 5, 1) + timedelta(weeks=8)
        InjuryService().log(uid, {"region": "joelho_frente", "diagnosis": "pfp", "side": "direito",
                                  "onset_date": str(onset), "q_pain": 3})
        val = validate_literature_model()
        case = next(c for c in val["cases"] if c["diagnosis"] == "pfp")
        # os fatores de PFP (queda pélvica + valgo) foram flagueados ANTES do onset
        assert "pelvic_drop_deg" in case["flagged_before"]
        assert "knee_valgus_deg" in case["flagged_before"]
        assert case["hit_rate"] and case["hit_rate"] > 0.5
    finally:
        con.execute("DELETE FROM form_analyses WHERE user_id = ?", [uid])
        con.execute("DELETE FROM injury_reports WHERE user_id = ?", [uid])
