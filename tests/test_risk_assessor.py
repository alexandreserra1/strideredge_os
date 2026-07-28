"""Seletor de risco: prior da literatura por default, TREINADO quando há dado real suficiente.
Honestidade: dados sintéticos (synthetic-…) NÃO ativam o treinado."""

from analytics.risk_assessor import current_assessor, MIN_REAL_CASES
from analytics.injury_seed import seed, clear_synthetic
from core.database import get_connection

_METRICS = {"cadence_spm": 150.0, "pelvic_drop_deg": 18.0, "knee_valgus_deg": 16.0}


def test_sem_dado_real_usa_o_prior():
    con = get_connection()
    clear_synthetic(con)
    assessor = current_assessor()
    assert assessor(_METRICS)["model"] == "literatura"


def test_dado_sintetico_nao_ativa_o_treinado():
    """Semear sintético NÃO deve virar o coach pro treinado (é andaime, não usuário real)."""
    con = get_connection()
    seed(con, n=300, seed_val=1)   # prefixo 'synthetic-' → excluído da decisão
    try:
        assert current_assessor()(_METRICS)["model"] == "literatura"
    finally:
        clear_synthetic(con)


def test_dado_real_suficiente_ativa_o_treinado():
    con = get_connection()
    clear_synthetic(con)
    seed(con, n=MIN_REAL_CASES * 4, seed_val=2, prefix="realuser-", training_approved=True)
    try:
        out = current_assessor()(_METRICS)
        assert out["model"] == "treinado"          # virou pro RF
        assert out["risk_band"] in ("baixo", "moderado", "elevado", "alto")
        assert all(f["source"] for f in out["factors"])  # segue citado
    finally:
        con.execute("DELETE FROM injury_reports WHERE user_id LIKE 'realuser-%'")
        con.execute("DELETE FROM form_analyses WHERE user_id LIKE 'realuser-%'")


def _reset_cache():
    from analytics import risk_assessor as ra
    ra._cache.update({"model": None, "n": None, "bayes": None, "bayes_n": None, "report": None})


def test_risk_regime_reporta_prior_sem_dado_real():
    from analytics.risk_assessor import risk_regime
    con = get_connection(); clear_synthetic(con); _reset_cache()
    r = risk_regime()
    assert r["regime"] == "prior" and r["real_cases"] == 0 and r["real_positives"] == 0


def test_risk_regime_treinado_expõe_o_boletim():
    """Com dado real suficiente, o regime vira 'trained' e traz o boletim (PR-AUC + validação) —
    transparência do ciclo que se auto-fecha."""
    from analytics.risk_assessor import risk_regime, MIN_REAL_CASES as MC
    con = get_connection(); clear_synthetic(con); _reset_cache()
    seed(con, n=MC * 4, seed_val=7, prefix="realuser-", training_approved=True)
    try:
        r = risk_regime()
        assert r["regime"] == "trained" and r["real_cases"] >= MC
        assert r["model_report"] and "pr_auc" in r["model_report"] and "validation" in r["model_report"]
    finally:
        con.execute("DELETE FROM injury_reports WHERE user_id LIKE 'realuser-%'")
        con.execute("DELETE FROM form_analyses WHERE user_id LIKE 'realuser-%'")
        _reset_cache()
