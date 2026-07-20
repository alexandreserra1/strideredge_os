"""Classificador texto→diagnóstico — conjunto fechado + abstenção (hermético, LLM mockado)."""

import uuid

from analytics.injury_classifier import DiagnosisClassifier
from api.injuries import InjuryService
from core.database import get_connection


class _FakeLLM:
    """LLM falso: devolve a resposta programada (sem Ollama)."""
    def __init__(self, reply: str):
        self.reply = reply
    def chat(self, system_prompt: str, user_prompt: str) -> str:
        return self.reply


def test_casa_diagnostico_com_confianca_alta():
    clf = DiagnosisClassifier(_FakeLLM('{"diagnosis": "pfp", "confidence": "alta"}'))
    out = clf.classify("dói na frente do joelho ao descer escada", region="joelho_frente")
    assert out["diagnosis"] == "pfp"


def test_confianca_baixa_abstem():
    clf = DiagnosisClassifier(_FakeLLM('{"diagnosis": "pfp", "confidence": "baixa"}'))
    assert clf.classify("dói algo no joelho", region="joelho_frente")["diagnosis"] is None


def test_id_fora_da_regiao_e_rejeitado():
    """Alucinação/erro: LLM devolve um dx que não pertence à região → vira null."""
    clf = DiagnosisClassifier(_FakeLLM('{"diagnosis": "mtss", "confidence": "alta"}'))
    assert clf.classify("dói no joelho", region="joelho_frente")["diagnosis"] is None


def test_id_inventado_e_rejeitado():
    clf = DiagnosisClassifier(_FakeLLM('{"diagnosis": "inexistente", "confidence": "alta"}'))
    assert clf.classify("dói", region="joelho_frente")["diagnosis"] is None


def test_texto_vazio_nao_chama_llm():
    clf = DiagnosisClassifier(_FakeLLM('{"diagnosis": "pfp", "confidence": "alta"}'))
    assert clf.classify("", region="joelho_frente")["diagnosis"] is None


def test_classify_persiste_no_service():
    svc = InjuryService()
    uid = str(uuid.uuid4())
    try:
        rep = svc.log(uid, {"region": "canela", "onset_date": "2026-07-01",
                            "symptom_text": "arde na canela ao correr", "q_pain": 2})
        assert rep["diagnosis"] is None                       # sem diagnóstico ainda
        clf = DiagnosisClassifier(_FakeLLM('{"diagnosis": "mtss", "confidence": "alta"}'))
        out = svc.classify(rep["id"], clf)
        assert out["diagnosis"] == "mtss"                     # canela → mtss é candidato válido
    finally:
        get_connection().execute("DELETE FROM injury_reports WHERE user_id = ?", [uid])
