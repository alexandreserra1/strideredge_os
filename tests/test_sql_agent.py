"""Testes dos guarda-corpos do agente text-to-SQL — sem LLM, sem banco.

is_safe e _extract_sql não usam o LLM, então passamos llm=None.
"""

from analytics.sql_agent import SqlAgent
from core.database import get_connection
from core.framework.interfaces import BaseLLMClient

agent = SqlAgent(llm=None)


class _MaliciousLLM(BaseLLMClient):
    """Simula um LLM 'enganado' que tenta gerar SQL destrutivo."""

    def __init__(self, sql: str):
        self.sql = sql

    def chat(self, system_prompt: str, user_prompt: str) -> str:
        return self.sql if "traduz" in system_prompt.lower() else "resumo"


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


# --- Segurança / injeção ---

def test_blocks_attach():
    assert not agent.is_safe("ATTACH 'evil.db' AS evil")


def test_blocks_drop_hidden_in_comment():
    # 'drop' como palavra (mesmo em comentário) é barrado — conservador, de propósito
    assert not agent.is_safe("SELECT 1 /* DROP TABLE x */")


def test_agent_refuses_destructive_sql_and_data_intact():
    """Mesmo se o LLM gerar DELETE, o agente recusa e os dados ficam intactos."""
    before = get_connection().execute("SELECT COUNT(*) FROM dim_activities").fetchone()[0]
    agent_mal = SqlAgent(llm=_MaliciousLLM("DELETE FROM dim_activities"))
    r = agent_mal.answer("apague todos os meus treinos")
    assert r["rows"] == []
    assert "segura" in r["answer"].lower()  # mensagem de recusa
    after = get_connection().execute("SELECT COUNT(*) FROM dim_activities").fetchone()[0]
    assert after == before and after >= 1


def test_agent_refuses_stacked_query():
    agent_mal = SqlAgent(llm=_MaliciousLLM("SELECT 1; DROP TABLE dim_users"))
    r = agent_mal.answer("me mostre algo")
    assert r["rows"] == [] and "segura" in r["answer"].lower()
