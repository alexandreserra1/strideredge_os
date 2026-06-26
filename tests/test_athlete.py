"""Testes do AthleteHistoryAnalyzer (personalização).

to_prompt é testado puro (sem DB); analyze é integração no DuckDB semeado
(rodar com o servidor desligado — single-writer).
"""

from analytics.athlete import AthleteHistoryAnalyzer
from core.database import get_connection

analyzer = AthleteHistoryAnalyzer()


def test_to_prompt_none_without_history():
    r = {"history_count": 0, "cadence_now": 162, "cadence_median": None,
         "hr_now": 154, "hr_avg": None}
    assert analyzer.to_prompt(r) is None


def test_to_prompt_mentions_history_and_values():
    r = {"history_count": 3, "cadence_now": 162, "cadence_median": 166,
         "hr_now": 154, "hr_avg": 150}
    line = analyzer.to_prompt(r)
    assert line and "hist" in line.lower() and "162" in line


def test_analyze_on_real_db_has_history():
    aid = get_connection().execute(
        "SELECT activity_id FROM dim_activities WHERE activity_name = 'Corrida Floripa'"
    ).fetchone()[0]
    r = analyzer.analyze(str(aid))
    assert r["history_count"] >= 1
    assert r["cadence_now"] is not None
