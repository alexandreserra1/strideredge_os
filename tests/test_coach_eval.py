"""Testes das métricas de eval anti-alucinação (determinísticas, sem LLM).

As métricas medem se o veredito é FIEL ao que demos: números e citações no
veredito têm que aparecer no prompt (dados + evidências).
"""

import httpx
import pytest

from analytics.coach_eval import CoachEvaluator, LLMJudge

ev = CoachEvaluator(coach=None)  # as métricas não usam o coach


def _ollama_up() -> bool:
    try:
        httpx.get("http://localhost:11434/api/version", timeout=2.0)
        return True
    except Exception:
        return False


def test_numeric_fidelity_perfect():
    assert ev.numeric_fidelity("cadência 162 e FC 154", "162 spm ... 154 bpm") == 1.0


def test_numeric_fidelity_flags_invented_number():
    # 200 não está no prompt -> 1 de 2 suportado
    assert ev.numeric_fidelity("162 e 200", "só 162 aqui") == 0.5


def test_numeric_fidelity_no_numbers_is_one():
    assert ev.numeric_fidelity("texto sem números", "qualquer") == 1.0


def test_citation_validity_valid():
    assert ev.citation_validity("ver PMC12440572", "evidência PMC12440572") == 1.0


def test_citation_validity_flags_fake_source():
    assert ev.citation_validity("ver PMC99999", "evidência PMC12440572") == 0.0


def test_citation_validity_no_citation_is_one():
    assert ev.citation_validity("sem citação", "x") == 1.0


def test_extrapolation_terms_flags_unmeasured_cause():
    # citar causa nao medida (desidratacao) = extrapolacao; falar de fadiga (medida) = ok
    assert "desidrat" in ev.extrapolation_terms("a FC subiu, pode ser desidratacao")
    assert ev.extrapolation_terms("a FC subiu no fim, sinal de fadiga") == []


class _FakeJudgeLLM:
    def __init__(self, reply):
        self.reply = reply

    def chat(self, system_prompt, user_prompt):
        return self.reply


def test_llm_judge_parseia_campo_relevancia():
    judge = LLMJudge(_FakeJudgeLLM(
        '{"acionabilidade": 0.5, "aterramento": 0.5, "relevancia": 0.5, "justificativa": "x"}'))
    assert judge.judge("fatos", "veredito")["relevancia"] == 0.5


def test_llm_judge_json_invalido_inclui_relevancia_none():
    judge = LLMJudge(_FakeJudgeLLM("isso nao e json"))
    r = judge.judge("fatos", "veredito")
    assert r["relevancia"] is None
    assert r["acionabilidade"] is None


@pytest.mark.skipif(not _ollama_up(), reason="Ollama não está rodando")
def test_real_coach_grounding_gate():
    """Portão de ATERRAMENTO (gated por Ollama, temp 0 p/ estabilidade): o veredito real
    nao pode inventar numeros nem extrapolar causas nao medidas. Garante que o coach
    'sai do jeito certo' — concreto E aterrado.
    """
    from api.deps import build_coach
    from core.database import get_connection

    aid = str(get_connection().execute(
        "SELECT activity_id FROM dim_activities WHERE activity_name = 'Corrida Floripa'"
    ).fetchone()[0])
    coach = build_coach(temperature=0)              # deterministico
    r = CoachEvaluator(coach).evaluate(aid)
    assert isinstance(r["verdict"], str) and r["verdict"]
    # Garantias DETERMINISTICAS que o prompt controla de fato:
    assert r["citation_validity"] == 1.0                          # nenhuma fonte inventada
    assert CoachEvaluator.extrapolation_terms(r["verdict"]) == []  # nenhuma causa nao medida
    # Fidelidade numerica: piso tolerante (LLM oscila em dado sintetico); a medicao fina e o benchmark.
    assert r["numeric_fidelity"] >= 0.6
