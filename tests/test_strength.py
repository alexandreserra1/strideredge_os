"""Séries de força: mapa de músculos + resumo + endpoint (gracioso quando vazio)."""

from fastapi.testclient import TestClient

from analytics.strength import StrengthSets
from api.main import app
from core.database import get_connection

client = TestClient(app)
AID = "55555555-5555-5555-5555-555555555555"


def test_summary_agrupa_musculos_por_series():
    con = get_connection()
    for i, (ex, reps) in enumerate([("bench_press", 10), ("bench_press", 8),
                                    ("squat", 12), ("exercicio_novo", 5)]):
        con.execute("INSERT OR REPLACE INTO fact_strength_sets VALUES (?, ?, ?, ?, NULL, 60.0, NULL)",
                    [AID, i, ex, reps])
    try:
        out = StrengthSets().summary(AID)
        assert len(out["sets"]) == 4
        top = out["muscles"][0]
        assert top["muscle"] in ("peito", "tríceps", "ombro") and top["sets"] == 2
        assert {"muscle": "outros", "sets": 1} in out["muscles"]   # degrada gracioso
    finally:
        con.execute("DELETE FROM fact_strength_sets WHERE activity_id = ?", [AID])


def test_endpoint_vazio_gracioso():
    r = client.get(f"/api/v1/activities/{AID}/sets")
    assert r.status_code == 200
    assert r.json()["sets"] == [] and r.json()["muscles"] == []
