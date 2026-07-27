"""Garantia determinística: a ação de cadência SEMPRE contém o método de contagem
(conte ... 20 segundos ... multiplique por 6), venha o LLM como vier — sem depender do humor
do qwen 7b. Testa o pós-processamento _ensure_measure_method do FormCoach com um LLM FAKE."""

from analytics.form_coach import FormCoach
from analytics.biomechanics import MEASURE_HOWTO


class _FakeLLM:
    def __init__(self, reply):
        self.reply = reply

    def chat(self, system_prompt, user_prompt):
        return self.reply


class _FakeKB:
    def retrieve(self, query, k=3, domains=None):
        return [{"text": "aumentar cadencia reduz impacto", "source": "PMC12440572",
                 "origin": "curado"}]


# boa captura, um desvio real: cadência baixa
_LOW_CADENCE = {
    "cadence_spm": 150.0, "ground_contact_ms": 200.0, "vertical_oscillation_pct": 6.0,
    "knee_contact_deg": 150.0, "trunk_lean_deg": 8.0, "asymmetry_pct": 4.0, "reliable": True,
}

# âncoras do método de contar cadência (texto pronto em MEASURE_HOWTO["cadence_spm"])
_METHOD = ("20 segundos", "multiplique")


def _cadence_action(actions):
    return next((a for a in actions if "cadenc" in a.lower()), None)


def test_llm_sem_metodo_recebe_o_metodo_anexado():
    """(a) LLM manda a ação de cadência SEM o método -> a saída final CONTÉM o método."""
    llm = _FakeLLM(reply="- Aumente sua cadencia para perto de 170 passos por minuto "
                         "(Fonte: PMC12440572)")
    out = FormCoach(llm=llm, knowledge=_FakeKB()).plan(_LOW_CADENCE)
    acao = _cadence_action(out["actions"])
    assert acao is not None
    low = acao.lower()
    assert all(a in low for a in _METHOD)           # método de contagem presente
    assert MEASURE_HOWTO["cadence_spm"].split(":", 1)[1].strip()[:20].lower() in low


def test_llm_com_metodo_nao_duplica():
    """(b) LLM já traz o método (paráfrase) -> não duplica a contagem."""
    llm = _FakeLLM(reply="- Aumente sua cadencia: conte quantas vezes um pe toca o chao em 20 "
                         "segundos e multiplique por 6; se der menos de 170 use um metronomo "
                         "(Fonte: PMC12440572)")
    out = FormCoach(llm=llm, knowledge=_FakeKB()).plan(_LOW_CADENCE)
    acao = _cadence_action(out["actions"]).lower()
    assert acao.count("20 segundos") == 1
    assert acao.count("multiplique") == 1


def test_fonte_citada_continua_presente():
    """(c) o pós-processamento não derruba a fonte citada."""
    llm = _FakeLLM(reply="- Aumente sua cadencia para 170 (Fonte: PMC12440572)")
    out = FormCoach(llm=llm, knowledge=_FakeKB()).plan(_LOW_CADENCE)
    assert "PMC12440572" in out["citations"]


def test_metrica_sem_how_to_measure_nao_e_alterada():
    """(d) uma ação cujo desvio não tem how_to_measure não é tocada. Forçamos um desvio de
    métrica sem MEASURE_HOWTO (knee_valgus_deg não entra em captura lateral); usamos aqui o
    caminho direto do helper pra garantir invariância."""
    devs = [{"metric": "sem_metodo", "label": "metrica x", "how_to_measure": ""}]
    original = ["- Faca a acao da metrica x do jeito Y"]
    assert FormCoach._ensure_measure_method(original, devs) == original
