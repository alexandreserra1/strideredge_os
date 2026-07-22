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


def _find(by_injury, dx):
    return next(i for i in by_injury if i["dx"] == dx)


def test_by_injury_ranqueia_e_cita_fonte():
    """Perfil por-lesão: lesões avaliáveis ordenadas por contribuição desc, cada uma com fonte."""
    r = assess(_DESVIADA)
    avaliaveis = [i for i in r["by_injury"] if i["evaluable"]]
    scores = [i["score"] for i in avaliaveis]
    assert scores == sorted(scores, reverse=True)
    assert all(i["source"] for i in r["by_injury"])
    # cadência baixa + oscilação alta → stress_fx (cadence+oscilacao) no topo dos avaliáveis
    assert avaliaveis[0]["dx"] in ("stress_fx", "mtss", "plantar")


def test_lateral_deixa_lesao_frontal_nao_avaliavel_nunca_baixo():
    """Honestidade: captura lateral não mede pelvic_drop/valgus → itbs 'não avaliável', não baixo."""
    r = assess(_DESVIADA)   # sem fatores frontais
    itbs = _find(r["by_injury"], "itbs")   # factors = pelvic_drop + knee_valgus (ambos frontais)
    assert itbs["evaluable"] is False
    assert "frente" in itbs["reason"]
    assert "band" not in itbs and "score" not in itbs


def test_todos_factors_none_sai_nao_avaliavel():
    r = assess({})   # nada medido
    assert all(i["evaluable"] is False for i in r["by_injury"])
    assert all("band" not in i for i in r["by_injury"])


def test_partial_quando_so_alguns_factors_medidos():
    """pfp pede pelvic_drop+valgus (frontais) + knee_contact (lateral). No lateral, knee_contact
    medido → parcial (não pode ser 'não avaliável', mas avisa que está incompleto)."""
    r = assess({**_LIMPA, "knee_contact_deg": 178.0})   # knee_contact desviado, frontais None
    pfp = _find(r["by_injury"], "pfp")
    assert pfp["evaluable"] is True and pfp["partial"] is True


def test_perfis_diferentes_para_metricas_diferentes():
    """Dois atletas diferentes → topos de lesão diferentes."""
    a = assess(_DESVIADA)                       # cadência baixa + oscilação
    b = assess({**_LIMPA, **_FRONTAL_RUIM})     # frontal ruim (pelvic drop + valgus)
    top_a = next(i["dx"] for i in a["by_injury"] if i["evaluable"] and i["score"] > 0)
    top_b = next(i["dx"] for i in b["by_injury"] if i["evaluable"] and i["score"] > 0)
    assert top_a != top_b
    assert top_b in ("pfp", "itbs")             # frontal ruim → joelho


def test_honestidade_faixa_relativa_nao_probabilidade():
    """Guarda de honestidade: é FAIXA relativa + caveat explícito, nunca 'X% de chance'."""
    r = assess(_DESVIADA)
    assert r["risk_band"] in ("baixo", "moderado", "elevado", "alto")
    assert r["model"] == "literatura"
    assert "não é diagnóstico" in r["caveat"].lower() or "relativo" in r["caveat"].lower()
    assert "%" not in str(r["risk_band"])   # a faixa não é porcentagem
