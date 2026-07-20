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
    seed(con, n=MIN_REAL_CASES * 4, seed_val=2, prefix="realuser-")  # simula usuários reais
    try:
        out = current_assessor()(_METRICS)
        assert out["model"] == "treinado"          # virou pro RF
        assert out["risk_band"] in ("baixo", "moderado", "elevado", "alto")
        assert all(f["source"] for f in out["factors"])  # segue citado
    finally:
        con.execute("DELETE FROM injury_reports WHERE user_id LIKE 'realuser-%'")
        con.execute("DELETE FROM form_analyses WHERE user_id LIKE 'realuser-%'")
