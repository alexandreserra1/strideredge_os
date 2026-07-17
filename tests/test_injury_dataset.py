"""Ponte lesão↔análise (injury_dataset) — com form_analyses + injury_reports sintéticos no DB de teste."""

import json
import uuid

from core.database import get_connection
from analytics.injury_dataset import build_dataset, validate_literature_model


def _seed_analysis(con, user_id, created_date, metrics):
    con.execute(
        "INSERT INTO form_analyses (analysis_id, status, metrics, created_at, view, user_id) "
        "VALUES (?, 'done', ?, ?, 'frontal', ?)",
        [str(uuid.uuid4()), json.dumps(metrics), created_date, user_id])


def _seed_injury(con, user_id, dx, onset):
    con.execute(
        "INSERT INTO injury_reports (id, user_id, diagnosis, region, onset_date, q_pain) "
        "VALUES (?, ?, ?, ?, ?, 3)",
        [str(uuid.uuid4()), user_id, dx, "joelho_frente", onset])


def test_build_dataset_liga_lesao_a_analise_na_janela():
    con = get_connection()
    uid = str(uuid.uuid4())
    try:
        # análise 2 semanas antes da lesão, com queda pélvica + valgo altos
        _seed_analysis(con, uid, "2026-06-17", {"pelvic_drop_deg": 20.0, "knee_valgus_deg": 18.0})
        _seed_injury(con, uid, "pfp", "2026-07-01")
        ds = [e for e in build_dataset(window_weeks=8) if e["user_id"] == uid]
        assert len(ds) == 1
        ex = ds[0]
        assert ex["label_dx"] == "pfp" and ex["n_analyses"] == 1
        assert ex["features"]["pelvic_drop_deg"] == 20.0     # feature agregada da janela
    finally:
        con.execute("DELETE FROM form_analyses WHERE user_id = ?", [uid])
        con.execute("DELETE FROM injury_reports WHERE user_id = ?", [uid])


def test_analise_fora_da_janela_nao_entra():
    con = get_connection()
    uid = str(uuid.uuid4())
    try:
        _seed_analysis(con, uid, "2026-01-01", {"pelvic_drop_deg": 20.0})  # 6 meses antes
        _seed_injury(con, uid, "pfp", "2026-07-01")
        ds = [e for e in build_dataset(window_weeks=8) if e["user_id"] == uid]
        assert ds == []   # nenhuma análise na janela -> sem exemplo
    finally:
        con.execute("DELETE FROM form_analyses WHERE user_id = ?", [uid])
        con.execute("DELETE FROM injury_reports WHERE user_id = ?", [uid])


def test_validate_face_validity_do_modelo_da_literatura():
    """PFP liga a queda pélvica + valgo + joelho no apoio. Se a análise anterior flagueou 2 dos 3,
    o hit_rate é ~0.67 — a validação honesta do prior contra outcome real."""
    con = get_connection()
    uid = str(uuid.uuid4())
    try:
        # queda pélvica 20 (>10) e valgo 18 (>10) flagueiam; joelho no apoio normal (não flagueia)
        _seed_analysis(con, uid, "2026-06-20",
                       {"pelvic_drop_deg": 20.0, "knee_valgus_deg": 18.0, "knee_contact_deg": 150.0})
        _seed_injury(con, uid, "pfp", "2026-07-01")
        rep = validate_literature_model(window_weeks=8)
        case = next(c for c in rep["cases"] if c["diagnosis"] == "pfp")
        assert set(case["flagged_before"]) == {"pelvic_drop_deg", "knee_valgus_deg"}
        assert abs(case["hit_rate"] - 2 / 3) < 0.01
    finally:
        con.execute("DELETE FROM form_analyses WHERE user_id = ?", [uid])
        con.execute("DELETE FROM injury_reports WHERE user_id = ?", [uid])
