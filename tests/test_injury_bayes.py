"""BayesianRiskModel — prior informativo que atualiza online (#4-B).

Herméticos: sem rede/Ollama. Provam (1) com N=0 é IDÊNTICO ao prior da literatura (não regride),
(2) outcomes reais movem os pesos na direção certa, (3) a interface é drop-in do `assess`."""

from analytics.injury_bayes import BayesianRiskModel
from analytics.injury_risk import assess, RISK_WEIGHT

_RUIM = {"cadence_spm": 150.0, "vertical_oscillation_pct": 16.0, "reliable": True}


def test_sem_dado_e_identico_ao_prior_da_literatura():
    """N=0: médias posteriores = RISK_WEIGHT → score/faixa idênticos ao assess. Não regride."""
    m = BayesianRiskModel()
    b = m.predict(_RUIM)
    p = assess(_RUIM)
    assert b["score"] == p["score"] and b["risk_band"] == p["risk_band"]
    assert [f["metric"] for f in b["factors"]] == [f["metric"] for f in p["factors"]]
    assert b["model"] == "prior-bayes" and b["uncertainty"]["n_real_updates"] == 0


def test_interface_drop_in_do_assess():
    """Mesmas chaves do prior (+ uncertainty aditivo) — o coach não muda ao trocar."""
    b = BayesianRiskModel().predict(_RUIM)
    assert set(assess(_RUIM)).issubset(set(b))
    assert "by_injury" in b and "uncertainty" in b


def test_outcome_lesionado_sobe_o_peso_do_fator_causante():
    """Vários casos de cadência baixa → LESÃO devem AUMENTAR o peso posterior de cadence_spm
    (a evidência real reforça o fator), subindo o score de uma captura com cadência baixa."""
    metrics = {"cadence_spm": 150.0, "reliable": True}
    base = BayesianRiskModel().predict(metrics)["score"]
    trained = BayesianRiskModel()
    trained.partial_fit([{"features": {"cadence_spm": 148.0}, "label": 1} for _ in range(40)])
    subiu = trained.predict(metrics)["score"]
    assert trained._m["cadence_spm"] > RISK_WEIGHT["cadence_spm"]   # crença reforçada
    assert subiu > base                                            # score reflete


def test_outcome_sem_lesao_derruba_o_peso():
    """Muitos casos com cadência baixa SEM lesão → o peso de cadence_spm CAI (deixa de discriminar)."""
    trained = BayesianRiskModel()
    trained.partial_fit([{"features": {"cadence_spm": 150.0}, "label": 0} for _ in range(60)])
    assert trained._m["cadence_spm"] < RISK_WEIGHT["cadence_spm"]


def test_incerteza_cai_com_mais_dado_real():
    """Honestidade: mais outcomes reais apertam a precisão → score_std menor."""
    metrics = {"cadence_spm": 150.0, "reliable": True}
    m = BayesianRiskModel()
    antes = m.predict(metrics)["uncertainty"]["score_std"]
    m.partial_fit([{"features": {"cadence_spm": 150.0}, "label": 1} for _ in range(30)])
    depois = m.predict(metrics)["uncertainty"]["score_std"]
    assert depois < antes and m.predict(metrics)["uncertainty"]["n_real_updates"] == 30


def test_peso_tem_piso_zero_nao_vira_protetor():
    """Num app de lesão, um fator de risco não pode virar protetor (peso<0) por ruído."""
    trained = BayesianRiskModel()
    trained.partial_fit([{"features": {"vertical_oscillation_pct": 16.0}, "label": 0}
                         for _ in range(200)])
    assert all(f["weight"] >= 0.0 for f in trained.predict(_RUIM)["factors"])
