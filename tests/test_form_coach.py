"""Testa o FormCoach (algoritmo corretivo) com fakes — sem Ollama nem RAG real."""

from analytics.form_coach import FormCoach


class _FakeLLM:
    """LLM falso: devolve um exercício citado, no formato que o coach espera."""

    def __init__(self, reply="- Faca drills de cadencia (Fonte: PMC12440572)"):
        self.reply = reply

    def chat(self, system_prompt, user_prompt):
        return self.reply

    def chat_stream(self, system_prompt, user_prompt):
        yield self.reply


class _FakeKB:
    def retrieve(self, query, k=3):
        return [{"text": "aumentar cadencia reduz impacto", "source": "PMC12440572",
                 "origin": "curado"}]


# métricas de uma boa captura (lateral, confiável) com UM desvio real: cadência baixa
_RELIABLE_LOW_CADENCE = {
    "cadence_spm": 150.0, "ground_contact_ms": 200.0, "vertical_oscillation_pct": 6.0,
    "knee_contact_deg": 150.0, "trunk_lean_deg": 8.0, "asymmetry_pct": 4.0, "reliable": True,
}


def test_captura_nao_confiavel_nao_diagnostica_pede_refilmagem():
    """Guarda de lesao: reliable=false -> NAO diagnostica nem tranquiliza; pede refilmagem
    e ecoa o motivo do motor. Nao pode dizer 'sua forma esta otima' em cima de dado ruim."""
    metrics = {"cadence_spm": 205.0, "asymmetry_pct": 6.6, "reliable": False,
               "quality_note": "Angulo parece nao ser lateral — filme de LADO."}
    out = FormCoach(llm=_FakeLLM(), knowledge=_FakeKB()).plan(metrics)
    assert out.get("unreliable") is True
    assert out["deviations"] == [] and out["actions"] == []
    assert "refa" in out["verdict"].lower() or "refilm" in out["verdict"].lower()
    assert "lado" in out["verdict"].lower()                      # ecoa o motivo do motor
    assert "otima" not in out["verdict"].lower() and "ideais" not in out["verdict"].lower()


def test_captura_confiavel_com_desvio_gera_plano():
    out = FormCoach(llm=_FakeLLM(), knowledge=_FakeKB()).plan(_RELIABLE_LOW_CADENCE)
    assert not out.get("unreliable")
    assert any(d["metric"] == "cadence_spm" and d["side"] == "baixo" for d in out["deviations"])
    assert out["actions"]                                        # LLM gerou exercicio
    assert "PMC12440572" in out["citations"]


def test_captura_confiavel_sem_desvio_elogia():
    perfeita = {**_RELIABLE_LOW_CADENCE, "cadence_spm": 180.0}   # tudo na faixa
    out = FormCoach(llm=_FakeLLM(), knowledge=_FakeKB()).plan(perfeita)
    assert out["deviations"] == [] and not out.get("unreliable")
    assert "ideais" in out["verdict"].lower()
