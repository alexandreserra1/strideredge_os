"""Ingestão sintética 'como se fosse usuário' → pipeline REAL fim-a-fim (seed → dataset → RF).

Hermético: usa o DB de teste do conftest. Prova que os dados sintéticos parametrizados pela
literatura fluem pelas MESMAS tabelas (form_analyses + injury_reports) e treinam o modelo."""

from analytics.injury_seed import seed, clear_synthetic, SYNTHETIC_PREFIX
from analytics.injury_dataset import build_training_set
from analytics.injury_model import RiskModel
from core.database import get_connection


def test_seed_popula_as_tabelas_reais_e_limpa():
    con = get_connection()
    counts = seed(con, n=120, seed_val=1)
    assert counts["injured"] > 0 and counts["healthy"] > 0
    # caiu nas tabelas de verdade, marcado como sintético
    inj = con.execute("SELECT count(*) FROM injury_reports WHERE user_id LIKE ?",
                      [SYNTHETIC_PREFIX + "%"]).fetchone()[0]
    ana = con.execute("SELECT count(*) FROM form_analyses WHERE user_id LIKE ?",
                      [SYNTHETIC_PREFIX + "%"]).fetchone()[0]
    assert inj == counts["injured"] and ana == 120
    clear_synthetic(con)
    assert con.execute("SELECT count(*) FROM injury_reports WHERE user_id LIKE ?",
                       [SYNTHETIC_PREFIX + "%"]).fetchone()[0] == 0


def test_build_training_set_tem_positivos_e_negativos():
    con = get_connection()
    seed(con, n=200, seed_val=2)
    try:
        ds = build_training_set()
        labels = [e["label"] for e in ds]
        assert 1 in labels and 0 in labels          # as duas classes vêm do pipeline real
        assert all(e["user_id"].startswith(SYNTHETIC_PREFIX) for e in ds)
    finally:
        clear_synthetic(con)


def test_treina_pelo_pipeline_real_com_validacao_subject_wise():
    con = get_connection()
    seed(con, n=300, seed_val=3)
    try:
        ds = build_training_set()
        report = RiskModel().train(ds)
        assert report["validation"] == "subject-wise"   # há user_id → GroupKFold
        assert report["pr_auc"] is not None
        assert report["positives"] > 0 and report["n"] == len(ds)
    finally:
        clear_synthetic(con)
