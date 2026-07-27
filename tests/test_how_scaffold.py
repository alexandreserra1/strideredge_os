"""Trava o scaffold determinístico do COMO (medir a métrica + executar o exercício).

Objetivo: o "como fazer/medir" é FATO do código, não pode depender do LLM lembrar. Estes testes
garantem que a cobertura é completa (toda métrica com faixa tem 'como medir'; todo exercício tem
'como fazer') e que esse dado FLUI pro desvio (coach) e pra sessão do plano de treino."""

from analytics.biomechanics import MEASURE_HOWTO, diagnose, ideal_targets
from analytics.exercises import EXERCISES, for_factors
from analytics.training_plan import build_plan


def test_todo_exercicio_tem_como_fazer_nao_vazio():
    for e in EXERCISES:
        assert e.get("how", "").strip(), f"exercício {e['id']} sem 'how' (como fazer)"


def test_toda_metrica_com_faixa_tem_como_medir():
    # cada métrica diagnosticável precisa ensinar o atleta a conferir sozinho
    for key in ideal_targets().keys():
        assert MEASURE_HOWTO.get(key, "").strip(), f"métrica {key} sem MEASURE_HOWTO"


def test_diagnose_anexa_how_to_measure_no_desvio():
    # cadência baixa -> desvio; deve trazer o método de medição pronto
    targets = ideal_targets()
    devs = diagnose({"cadence_spm": 150.0}, targets)
    cad = next(d for d in devs if d["metric"] == "cadence_spm")
    assert "20 segundos" in cad["how_to_measure"]  # o método concreto (contar em 20s x6)


def test_sessoes_do_plano_carregam_o_como_fazer():
    # plano a partir de um fator real -> toda sessão traz o 'how' do exercício
    plan = build_plan([{"metric": "cadence_spm", "label": "cadência"}], weeks=6)
    sessions = [s for w in plan["weeks"] for s in w["sessions"]]
    assert sessions, "plano sem sessões"
    assert all(s.get("how", "").strip() for s in sessions), "sessão sem 'como fazer'"


def test_for_factors_traz_exercicio_com_how_citado():
    exs = for_factors(["pelvic_drop_deg"])
    assert exs and all(e.get("how") and e.get("source") for e in exs)
