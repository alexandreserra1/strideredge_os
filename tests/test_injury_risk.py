"""Modelo de risco de lesão — validação known-groups (sem verdade-base de lesão, o que dá pra
checar é a ordenação: pior biomecânica → risco maior) + as garantias de honestidade."""

from analytics.injury_risk import assess


# forma limpa (tudo dentro do ideal) vs desviada (cadência baixa + oscilação alta)
_LIMPA = {"cadence_spm": 180.0, "vertical_oscillation_pct": 6.0, "asymmetry_pct": 4.0,
          "knee_contact_deg": 150.0, "trunk_lean_deg": 8.0, "ground_contact_ms": 220.0}
_DESVIADA = {**_LIMPA, "cadence_spm": 150.0, "vertical_oscillation_pct": 18.0}
_FRONTAL_RUIM = {"pelvic_drop_deg": 20.0, "knee_valgus_deg": 22.0}


def test_forma_limpa_e_risco_baixo():
    r = assess(_LIMPA)
    assert r["risk_band"] == "baixo" and r["score"] == 0.0 and r["factors"] == []


def test_pior_biomecanica_aumenta_o_risco():
    """Known-groups: mais/piores desvios → score e faixa maiores (ordenação, não %)."""
    limpa = assess(_LIMPA)
    desviada = assess(_DESVIADA)
    assert desviada["score"] > limpa["score"]
    assert desviada["risk_band"] != "baixo"


def test_fatores_ordenados_por_contribuicao_com_fonte():
    r = assess(_DESVIADA)
    contribs = [f["contribution"] for f in r["factors"]]
    assert contribs == sorted(contribs, reverse=True)          # do maior contribuinte pro menor
    assert all(f["source"] and f["plain"] for f in r["factors"])  # cada fator citado + explicado


def test_sinais_frontais_pesam_forte():
    """Queda pélvica + valgo (peso 3) fora do ideal → risco elevado/alto."""
    r = assess(_FRONTAL_RUIM)
    assert r["risk_band"] in ("elevado", "alto")
    metrics_flagged = {f["metric"] for f in r["factors"]}
    assert "pelvic_drop_deg" in metrics_flagged and "knee_valgus_deg" in metrics_flagged


def test_honestidade_faixa_relativa_nao_probabilidade():
    """Guarda de honestidade: é FAIXA relativa + caveat explícito, nunca 'X% de chance'."""
    r = assess(_DESVIADA)
    assert r["risk_band"] in ("baixo", "moderado", "elevado", "alto")
    assert r["model"] == "literatura"
    assert "não é diagnóstico" in r["caveat"].lower() or "relativo" in r["caveat"].lower()
    assert "%" not in str(r["risk_band"])   # a faixa não é porcentagem
