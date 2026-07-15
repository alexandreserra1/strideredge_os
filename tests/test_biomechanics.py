"""Testa os alvos personalizados + diagnóstico de gap (aritmética pura, sem LLM)."""

from analytics.biomechanics import ideal_targets, diagnose


def test_cadencia_alvo_escala_com_altura():
    base = ideal_targets()
    assert base["cadence_spm"]["lo"] == 170.0
    alto = ideal_targets({"height_cm": 185})   # +10cm -> piso ~3 spm menor
    assert alto["cadence_spm"]["lo"] < base["cadence_spm"]["lo"]
    assert abs(alto["cadence_spm"]["lo"] - 167.0) < 0.1


def test_diagnose_ordena_por_severidade_e_ignora_dentro_da_faixa():
    t = ideal_targets()
    metrics = {
        "cadence_spm": 150,               # bem abaixo do piso (170) -> desvio grande
        "vertical_oscillation_pct": 9,    # pouco acima de 8 -> desvio pequeno
        "asymmetry_pct": 5,               # dentro (<10) -> ignorado
        "trunk_lean_deg": 8,              # dentro (5-14) -> ignorado
    }
    devs = diagnose(metrics, t)
    metricas = [d["metric"] for d in devs]
    assert "asymmetry_pct" not in metricas and "trunk_lean_deg" not in metricas
    assert devs[0]["metric"] == "cadence_spm"     # pior desvio primeiro
    assert devs[0]["side"] == "baixo"
    assert all("source" in d and "query" in d for d in devs)


def test_forma_perfeita_sem_desvios():
    t = ideal_targets()
    metrics = {"cadence_spm": 180, "ground_contact_ms": 230, "vertical_oscillation_pct": 6,
               "knee_contact_deg": 160, "trunk_lean_deg": 8, "asymmetry_pct": 4}
    assert diagnose(metrics, t) == []


def test_cadencia_alta_nao_e_desvio_higher_better():
    """Regressao (domínio): cadencia e higher_better — passar do topo (207 > 190) NAO e falha
    a corrigir, cadencia alta protege contra impacto. So cadencia BAIXA (< piso) vira desvio.
    Antes o topo era tratado como teto rigido e o coach mandava 'reduza a cadencia' — conselho
    invertido num app de prevencao de lesao."""
    t = ideal_targets()
    assert [d for d in diagnose({"cadence_spm": 207}, t) if d["metric"] == "cadence_spm"] == []
    baixo = diagnose({"cadence_spm": 150}, t)
    assert baixo[0]["metric"] == "cadence_spm" and baixo[0]["side"] == "baixo"


def test_oscilacao_alta_e_desvio_lower_better():
    """oscilacao vertical e lower_better: passar do teto (21 > 8) e desvio; ficar abaixo, nao."""
    t = ideal_targets()
    alto = diagnose({"vertical_oscillation_pct": 21}, t)
    assert alto and alto[0]["side"] == "alto"
    assert diagnose({"vertical_oscillation_pct": 5}, t) == []


def test_metrica_range_busca_por_DIRECAO():
    """Regressao (direcao): inclinacao de tronco e `range` (erra pros dois lados). A busca
    corretiva TEM que diferir por lado — ereto demais pede 'inclinar pra frente', inclinado
    demais pede 'reduzir sobrecarga lombar'. Reusar a mesma busca inverteria o conselho."""
    t = ideal_targets()
    ereto = diagnose({"trunk_lean_deg": 2}, t)[0]      # < 5 -> baixo
    curvado = diagnose({"trunk_lean_deg": 20}, t)[0]   # > 14 -> alto
    assert ereto["side"] == "baixo" and curvado["side"] == "alto"
    assert ereto["query"] != curvado["query"]          # direcoes -> buscas diferentes
    assert ereto["plain"] and curvado["plain"]         # ambos com explicacao (nao vazio)


def test_metricas_frontais_pelvic_drop_e_valgo():
    """Plano frontal: queda pélvica e valgo altos viram desvio (lower_better) com fonte + plain."""
    t = ideal_targets()
    devs = {d["metric"]: d for d in diagnose({"pelvic_drop_deg": 16, "knee_valgus_deg": 18}, t)}
    assert devs["pelvic_drop_deg"]["side"] == "alto"
    assert devs["pelvic_drop_deg"]["source"] == "PMC6829001"
    assert devs["pelvic_drop_deg"]["plain"] and devs["knee_valgus_deg"]["plain"]
    # dentro da faixa (≤10°) não vira desvio
    assert diagnose({"pelvic_drop_deg": 5, "knee_valgus_deg": 4}, t) == []
