"""Integração do PIPELINE do coach — trava o contrato ponta a ponta, em memória, com LLM FAKE.

Exercita o fluxo INTEIRO que roda quando um vídeo vira plano corretivo, sem Ollama/RAG/Rust:

    metrics dict → biomechanics.diagnose → injury_risk.assess → training_plan.build_plan
                 → FormCoach.plan

Não é teste de unidade de cada peça (isso já existe em test_biomechanics/test_injury_risk/
test_training_plan/test_form_coach). Aqui garantimos que as PEÇAS SE ENCAIXAM: o que uma produz
é o que a próxima consome, e a saída final tem a forma que o frontend/coach espera. Determinístico:
mesmas entradas → mesma saída, sem rede.
"""

from analytics.biomechanics import ideal_targets, diagnose
from analytics.injury_risk import assess
from analytics.training_plan import build_plan
from analytics.form_coach import FormCoach


class _FakeLLM:
    """LLM falso determinístico: uma recomendação citada por linha, no formato que o coach parseia."""

    def __init__(self, reply="- Aumente sua cadencia contando os passos e usando um metronomo "
                             "1x na semana numa corrida leve (Fonte: PMC12440572)"):
        self.reply = reply

    def chat(self, system_prompt, user_prompt):
        return self.reply


class _FakeKB:
    """RAG falso: devolve uma evidência curada citada (sem busca real)."""

    def retrieve(self, query, k=3, domains=None):
        return [{"text": "aumentar a cadencia reduz o impacto por passada", "origin": "curado",
                 "source": "PMC12440572"}]


# Captura BOA (lateral, confiável) com desvios REAIS: cadência baixa + oscilação vertical alta.
_METRICS_DESVIO = {
    "cadence_spm": 150.0, "vertical_oscillation_pct": 10.0, "ground_contact_ms": 210.0,
    "knee_contact_deg": 150.0, "trunk_lean_deg": 8.0, "asymmetry_pct": 4.0, "reliable": True,
}


def _coach():
    return FormCoach(llm=_FakeLLM(), knowledge=_FakeKB())


def test_estagios_intermediarios_se_encaixam():
    """diagnose → assess → build_plan: a saída de um alimenta o próximo sem remendo."""
    targets = ideal_targets()
    devs = diagnose(_METRICS_DESVIO, targets)
    metricas = {d["metric"] for d in devs}
    assert "cadence_spm" in metricas and "vertical_oscillation_pct" in metricas

    risk = assess(_METRICS_DESVIO)
    assert risk["risk_band"] in ("baixo", "moderado", "elevado", "alto")
    assert risk["score"] > 0.0                                    # há desvio ⇒ risco > 0
    assert risk["factors"], "assess deve devolver os fatores que puxaram o risco"
    # by_injury é decomposto por diagnóstico, ranqueado
    assert risk["by_injury"] and all("dx" in i for i in risk["by_injury"])

    plan = build_plan(risk["factors"], weeks=6)
    assert plan["duration_weeks"] == 6
    assert len(plan["weeks"]) == 6
    # cada semana tem sessões e cada sessão traz o COMO fazer (plano explicativo, não só nome)
    semanas_com_sessao = [w for w in plan["weeks"] if w["sessions"]]
    assert semanas_com_sessao, "com desvio de cadência tem que haver sessão prescrita"
    for w in semanas_com_sessao:
        for s in w["sessions"]:
            assert s["source"] and "how" in s


def test_plan_devolve_contrato_completo_com_desvio():
    """FormCoach.plan() — a saída final que o /coach entrega: verdict, actions(fonte),
    deviations(how_to_measure), risk(faixa + by_injury), uncertain_metrics."""
    out = _coach().plan(_METRICS_DESVIO)

    assert not out.get("unreliable")
    assert isinstance(out["verdict"], str) and out["verdict"]
    assert out["actions"], "LLM gerou exercício ⇒ actions não vazio"
    assert out["citations"] and "PMC12440572" in out["citations"]

    # deviations determinísticos, com o COMO MEDIR pronto (o atleta confere sozinho)
    assert any(d["metric"] == "cadence_spm" and d["side"] == "baixo" for d in out["deviations"])
    assert all("how_to_measure" in d for d in out["deviations"])

    # risco: faixa relativa + decomposição por lesão
    assert out["risk"]["risk_band"] in ("baixo", "moderado", "elevado", "alto")
    assert out["risk"]["by_injury"]
    assert out["injury_profile"] == out["risk"]["by_injury"]

    # uncertain_metrics sempre presente como lista (aqui vazio: captura boa)
    assert out["uncertain_metrics"] == []


def test_captura_ruim_pede_refilmagem_nao_diagnostica():
    """reliable=false NÃO diagnostica nem tranquiliza; pede refilmagem e ecoa o motivo do motor."""
    ruim = {"cadence_spm": 150.0, "reliable": False,
            "quality_note": "Angulo parece nao ser lateral — filme de LADO."}
    out = _coach().plan(ruim)
    assert out["unreliable"] is True
    assert out["deviations"] == [] and out["actions"] == []
    assert "refa" in out["verdict"].lower() or "refilm" in out["verdict"].lower()
    assert "lado" in out["verdict"].lower()                       # ecoou o motivo do motor
    assert "otima" not in out["verdict"].lower()


def test_metrica_implausivel_vira_uncertain_e_verdict_nao_diz_tudo_ideal():
    """Oscilação vertical 22% é fisiologicamente impossível (artefato de captura): é nulificada
    pelo saneamento, vira uncertain_metrics e — como não sobrou desvio — o verdict NÃO pode
    afirmar 'está tudo ideal' (seria enganoso num app de lesão)."""
    metrics = {
        "cadence_spm": 180.0,                    # dentro da faixa (sem desvio)
        "vertical_oscillation_pct": 22.0,        # > 20 (limite plausível) ⇒ nulificada
        "reliable": True,
    }
    out = _coach().plan(metrics)
    assert out["deviations"] == []               # nada avaliável ficou fora da faixa
    nomes = {u["metric"] for u in out["uncertain_metrics"]}
    assert "vertical_oscillation_pct" in nomes
    low = out["verdict"].lower()
    assert "tudo ideal" not in low and "está ótima" not in low
    # cada uncertain traz o shape que o frontend consome no selo "medição incerta"
    for u in out["uncertain_metrics"]:
        assert set(u) >= {"metric", "label", "reason"}
