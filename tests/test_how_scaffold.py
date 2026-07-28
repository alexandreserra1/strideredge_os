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
    exercicios = [ex for ph in plan["phases"] for ex in ph["exercises"]]
    assert exercicios, "plano sem exercícios"
    assert all(ex.get("how", "").strip() for ex in exercicios), "exercício sem 'como fazer'"


def test_for_factors_traz_exercicio_com_how_citado():
    exs = for_factors(["pelvic_drop_deg"])
    assert exs and all(e.get("how") and e.get("source") for e in exs)


def test_metrica_implausivel_vira_incerta_e_verdict_nao_diz_tudo_ideal():
    """video_23: oscilação 21.9% (implausível, >20) deve ser ANULADA e sinalizada — o coach NÃO
    pode dizer 'está tudo ideal' quando não conseguiu avaliar uma métrica (perigoso num app de lesão)."""
    from analytics.form_coach import FormCoach

    class _FakeLLM:
        def chat(self, system, prompt): return "- ok (Fonte: PMC1)"

    coach = FormCoach(llm=_FakeLLM(), knowledge=None)
    # métricas plausíveis EXCETO oscilação (21.9 > teto plausível 20) — as demais dentro do ideal
    metrics = {"cadence_spm": 175.0, "vertical_oscillation_pct": 21.9, "trunk_lean_deg": 8.0,
               "reliable": True}
    out = coach.plan(metrics)
    uncertain = {u["metric"] for u in out.get("uncertain_metrics", [])}
    assert "vertical_oscillation_pct" in uncertain, "oscilação implausível deveria virar incerta"
    assert "ideais" not in out["verdict"] or "não consegui" in out["verdict"].lower() \
        or "avaliar" in out["verdict"].lower(), "verdict não pode afirmar 'tudo ideal' com métrica não avaliada"
