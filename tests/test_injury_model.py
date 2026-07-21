"""RiskModel (Random Forest) + gerador sintético — prova o pipeline de ML de risco.

Herméticos: sem rede, sem Ollama. Dados sintéticos determinísticos (seed). Validam o FLUXO
(treina → PR-AUC → predict com a mesma interface do prior), não validade preditiva (sintético)."""

import pytest

from analytics.injury_synth import generate, FEATURE_ORDER
from analytics.injury_model import RiskModel
from analytics.injury_risk import assess


def test_synth_gera_rotulado_e_com_todas_as_features():
    data = generate(n=100, seed=1)
    assert len(data) == 100
    assert all(set(e["features"]) == set(FEATURE_ORDER) for e in data)
    labels = {e["label"] for e in data}
    assert labels == {0, 1}                       # tem as duas classes
    assert 0 < sum(e["label"] for e in data) < 100  # positivos raros, não todos


def test_treina_e_reporta_pr_auc_estratificado():
    model = RiskModel()
    report = model.train(generate(n=400, seed=2))
    assert report["validation"] == "stratified"   # sintético não tem atleta
    assert report["pr_auc"] is not None and report["pr_auc"] > 0.5  # aprende o sinal que geramos
    assert report["n"] == 400 and report["positives"] > 0


def test_predict_tem_a_mesma_interface_do_prior():
    """Drop-in: a saída do treinado tem as MESMAS chaves do assess() da literatura."""
    model = RiskModel()
    model.train(generate(n=300, seed=3))
    metrics = {"cadence_spm": 150.0, "pelvic_drop_deg": 18.0, "knee_valgus_deg": 16.0}
    trained = model.predict(metrics)
    prior = assess(metrics)
    assert set(trained) == set(prior)                       # mesmo contrato
    assert set(trained["factors"][0]) == set(prior["factors"][0])
    assert trained["model"] == "treinado"
    assert trained["risk_band"] in ("baixo", "moderado", "elevado", "alto")
    assert all(f["source"] and f["plain"] for f in trained["factors"])  # citado + explicado


def test_forma_ruim_pontua_acima_de_forma_limpa():
    """Known-groups: biomecânica desviada → faixa/prob maior que forma limpa."""
    model = RiskModel()
    model.train(generate(n=400, seed=4))
    limpa = model.predict({"cadence_spm": 180.0, "pelvic_drop_deg": 4.0, "knee_valgus_deg": 3.0})
    ruim = model.predict({"cadence_spm": 150.0, "pelvic_drop_deg": 20.0, "knee_valgus_deg": 18.0})
    assert ruim["score"] > limpa["score"]


def test_cadencia_e_gct_negativamente_correlacionados():
    """Acoplamento MECÂNICO: cadência baixa anda junto com tempo de contato maior (passada longa,
    menos 'mola'). O sintético agora deriva GCT/joelho da cadência, então a correlação é negativa —
    estrutura conjunta realista, não fatores independentes."""
    data = generate(n=1000, seed=11)
    cad = [e["features"]["cadence_spm"] for e in data]
    gct = [e["features"]["ground_contact_ms"] for e in data]
    n = len(data)
    mc, mg = sum(cad) / n, sum(gct) / n
    cov = sum((c - mc) * (g - mg) for c, g in zip(cad, gct))
    vc = sum((c - mc) ** 2 for c in cad) ** 0.5
    vg = sum((g - mg) ** 2 for g in gct) ** 0.5
    corr = cov / (vc * vg)
    assert corr < -0.1                                # negativa (mecânica), não ~0 (independente)
    # lesionado (cadência menor) tem GCT médio maior que saudável — mesmo efeito, agrupado
    gi = [g for g, e in zip(gct, data) if e["label"] == 1]
    gh = [g for g, e in zip(gct, data) if e["label"] == 0]
    assert sum(gi) / len(gi) > sum(gh) / len(gh)


def test_predict_sem_treinar_falha():
    with pytest.raises(RuntimeError):
        RiskModel().predict({"cadence_spm": 150.0})
