"""InjuryService — log/list de lesão + severidade OSTRC + validação da taxonomia (usa o DB de teste)."""

import uuid

import pytest

from api.injuries import InjuryService, InjuryError
from core.database import get_connection

svc = InjuryService()


def _uid():
    return str(uuid.uuid4())


def test_severidade_ostrc_monotonica():
    assert InjuryService.severity({}) == 0
    assert InjuryService.severity({"q_participation": 3, "q_volume": 3,
                                   "q_performance": 3, "q_pain": 3}) == 100
    leve = InjuryService.severity({"q_pain": 1})
    forte = InjuryService.severity({"q_pain": 3, "q_participation": 2})
    assert 0 < leve < forte < 100


def test_log_e_list_por_usuario():
    uid = _uid()
    try:
        out = svc.log(uid, {"diagnosis": "pfp", "side": "direito", "onset_date": "2026-06-01",
                            "q_pain": 2, "q_participation": 1})
        assert out["diagnosis"] == "pfp" and out["region"] == "joelho_frente"  # herdou a região
        assert out["side"] == "direito" and out["severity"] > 0
        lst = svc.list(uid)
        assert len(lst) == 1 and lst[0]["id"] == out["id"]
        # outro usuário não vê
        assert svc.list(_uid()) == []
    finally:
        get_connection().execute("DELETE FROM injury_reports WHERE user_id = ?", [uid])


def test_log_por_regiao_com_texto_livre_sem_diagnostico():
    """Reframe: o atleta marca a região (mapa corporal) + texto livre; NÃO auto-diagnostica.
    diagnosis fica NULL (candidato a rótulo via LLM em coach-time); region é o y confiável."""
    uid = _uid()
    try:
        out = svc.log(uid, {"region": "canela", "side": "esquerdo", "onset_date": "2026-07-01",
                            "q_pain": 3, "symptom_text": "arde na canela ao correr"})
        assert out["region"] == "canela" and out["diagnosis"] is None
        assert out["symptom_text"] == "arde na canela ao correr" and out["severity"] > 0
    finally:
        get_connection().execute("DELETE FROM injury_reports WHERE user_id = ?", [uid])


def test_diagnostico_invalido_recusado():
    with pytest.raises(InjuryError):
        svc.log(_uid(), {"diagnosis": "inexistente"})
    with pytest.raises(InjuryError):
        svc.log(_uid(), {"region": "cabeca"})


def test_lesao_nao_mapeada_ainda_pode_ser_logada():
    """Plantar/aquiles (mapa pendente) entram no log normalmente."""
    uid = _uid()
    try:
        out = svc.log(uid, {"diagnosis": "plantar", "q_pain": 3})
        assert out["diagnosis"] == "plantar" and out["region"] == "pe"
    finally:
        get_connection().execute("DELETE FROM injury_reports WHERE user_id = ?", [uid])
