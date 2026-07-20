"""Filtro de qualidade — nenhum dado ruidoso treina o modelo (§7: dado validado)."""

from analytics.injury_quality import clean, sanitize_metrics, PLAUSIBLE


def test_clipa_valor_impossivel_pro_limite():
    # queda pélvica negativa (ruído de cauda) e cadência absurda → clipadas
    data = [{"features": {"pelvic_drop_deg": -3.0, "cadence_spm": 500.0,
                          "knee_valgus_deg": 5.0}, "label": 1}]
    out, report = clean(data)
    f = out[0]["features"]
    assert f["pelvic_drop_deg"] == PLAUSIBLE["pelvic_drop_deg"][0]   # 0.0
    assert f["cadence_spm"] == PLAUSIBLE["cadence_spm"][1]           # 230.0
    assert report["clipped_values"] == 2


def test_descarta_linha_quase_vazia():
    data = [{"features": {"cadence_spm": 180.0}, "label": 0},          # só 1 feature → fora
            {"features": {"cadence_spm": 180.0, "pelvic_drop_deg": 3.0,
                          "knee_valgus_deg": 4.0}, "label": 0}]        # 3 → ok
    out, report = clean(data)
    assert report["n_out"] == 1 and report["dropped_sparse"] == 1


def test_descarta_duplicata_exata():
    row = {"features": {"cadence_spm": 180.0, "pelvic_drop_deg": 3.0, "knee_valgus_deg": 4.0}, "label": 1}
    out, report = clean([row, dict(row)])
    assert report["n_out"] == 1 and report["dropped_duplicates"] == 1


def test_sanitize_nulifica_metrica_impossivel_do_motor():
    # gct 2490ms (bug do motor em vídeo ruim) → NULL, não vira desvio falso
    m = {"cadence_spm": 160.0, "ground_contact_ms": 2490.7, "trunk_lean_deg": 5.0}
    clean_m, nulled = sanitize_metrics(m)
    assert clean_m["ground_contact_ms"] is None and nulled == ["ground_contact_ms"]
    assert clean_m["cadence_spm"] == 160.0                 # o plausível fica


def test_sanitize_nao_mexe_em_metrica_plausivel():
    m = {"cadence_spm": 175.0, "pelvic_drop_deg": 8.0, "ground_contact_ms": 250.0}
    clean_m, nulled = sanitize_metrics(m)
    assert nulled == [] and clean_m == m


def test_dado_limpo_passa_intacto():
    data = [{"features": {"cadence_spm": 180.0, "pelvic_drop_deg": 3.0, "knee_valgus_deg": 4.0}, "label": 0}]
    out, report = clean(data)
    assert report["n_out"] == 1 and report["clipped_values"] == 0
    assert out[0]["features"] == data[0]["features"]
