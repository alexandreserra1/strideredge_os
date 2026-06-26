"""Testes dos guarda-corpos do agente text-to-SQL — sem LLM, sem banco.

is_safe e _extract_sql não usam o LLM, então passamos llm=None.
"""

from analytics.sql_agent import SqlAgent

agent = SqlAgent(llm=None)


def test_allows_select():
    assert agent.is_safe("SELECT avg(heart_rate) FROM fact_telemetry")


def test_allows_cte():
    assert agent.is_safe("WITH x AS (SELECT 1 AS a) SELECT a FROM x")


def test_blocks_delete():
    assert not agent.is_safe("DELETE FROM dim_activities")


def test_blocks_drop():
    assert not agent.is_safe("DROP TABLE fact_telemetry")


def test_blocks_multiple_statements():
    assert not agent.is_safe("SELECT 1; DROP TABLE x")


def test_blocks_update_disguised():
    assert not agent.is_safe("UPDATE dim_users SET name = 'x'")


def test_extract_sql_strips_markdown_fence():
    raw = "Claro! Aqui:\n```sql\nSELECT * FROM dim_users\n```"
    assert agent._extract_sql(raw) == "SELECT * FROM dim_users"


def test_extract_sql_from_prose():
    raw = "A query é: SELECT count(*) FROM fact_telemetry;"
    assert agent._extract_sql(raw) == "SELECT count(*) FROM fact_telemetry"
