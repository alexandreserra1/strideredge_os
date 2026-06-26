"""analytics/sql_agent.py — coach agentico text-to-SQL (tool-use sobre o DuckDB).

Ensina function-calling de forma segura: o LLM PROPOE uma query; o CODIGO valida e
executa (read-only). O LLM nunca toca o banco direto — guarda-corpos no codigo.

Fluxo: pergunta + schema -> LLM gera SELECT -> validacao (so SELECT, sem ';',
sem palavras mutantes, com LIMIT) -> executa -> LLM resume o resultado em PT.
"""

import re

from core.database import get_connection
from core.framework.interfaces import BaseLLMClient

# Palavras que NUNCA podem aparecer (mutacao/efeitos colaterais).
_FORBIDDEN = ["insert", "update", "delete", "drop", "alter", "create",
              "attach", "copy", "pragma", "replace", "truncate"]


class SqlAgent:
    """Responde perguntas em linguagem natural consultando o DuckDB via LLM."""

    SYSTEM_SQL = (
        "Voce traduz a pergunta do atleta em UMA query SQL para DuckDB. "
        "Responda APENAS com a query SELECT, sem explicacao e sem ponto e virgula. "
        "Use somente as tabelas e colunas do schema fornecido."
    )
    SYSTEM_ANSWER = (
        "Voce e um treinador. Responda a pergunta do atleta em portugues, direto, "
        "usando SOMENTE os resultados da consulta fornecidos. Nao invente numeros."
    )

    def __init__(self, llm: BaseLLMClient, row_limit: int = 200):
        self.llm = llm
        self.row_limit = row_limit

    def schema(self) -> str:
        """Schema real do banco (introspecção) — fica sempre em sincronia."""
        con = get_connection()
        rows = con.execute(
            """SELECT table_name, column_name, data_type
               FROM information_schema.columns
               WHERE table_schema = 'main'
               ORDER BY table_name, ordinal_position"""
        ).fetchall()
        tabelas = {}
        for t, c, dt in rows:
            tabelas.setdefault(t, []).append(f"{c} {dt}")
        return "\n".join(f"{t}({', '.join(cols)})" for t, cols in tabelas.items())

    @staticmethod
    def _extract_sql(text: str) -> str:
        """Tira cercas markdown e pega da 1a SELECT/WITH em diante."""
        fence = re.search(r"```(?:sql)?\s*(.+?)```", text, re.DOTALL | re.IGNORECASE)
        if fence:
            text = fence.group(1)
        m = re.search(r"\b(select|with)\b", text, re.IGNORECASE)
        sql = text[m.start():] if m else text
        return sql.strip().rstrip(";").strip()

    def is_safe(self, sql: str) -> bool:
        """So permite UMA query de leitura (SELECT/CTE). Sem isso, nao executa."""
        low = sql.strip().lower()
        if ";" in low:                       # bloqueia multiplas instrucoes
            return False
        if not (low.startswith("select") or low.startswith("with")):
            return False
        return not any(re.search(rf"\b{kw}\b", low) for kw in _FORBIDDEN)

    def _run_sql(self, sql: str) -> list:
        if " limit " not in sql.lower():
            sql = f"{sql}\nLIMIT {self.row_limit}"
        con = get_connection()
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def answer(self, question: str, max_retries: int = 1) -> dict:
        """Gera SQL, valida, executa (com retry agêntico) e resume."""
        schema = self.schema()
        base = (f"Schema:\n{schema}\n\n"
                "Obs: ha um unico atleta no banco; NAO filtre por user_id.\n\n"
                f"Pergunta: {question}")
        sql = self._extract_sql(self.llm.chat(self.SYSTEM_SQL, base))

        rows, last_err = None, None
        for attempt in range(max_retries + 1):
            if not self.is_safe(sql):
                return {"sql": sql, "rows": [], "answer": "Não gerei uma consulta segura para isso."}
            try:
                rows = self._run_sql(sql)
                break
            except Exception as e:
                last_err = str(e).splitlines()[0]
                if attempt == max_retries:
                    return {"sql": sql, "rows": [], "answer": f"A consulta falhou: {last_err}"}
                # retry agentico: mostra o erro pro LLM corrigir a query
                fix = (f"Schema:\n{schema}\n\nA query abaixo deu erro:\n{sql}\n"
                       f"Erro: {last_err}\nCorrija. Responda so com a query SELECT.")
                sql = self._extract_sql(self.llm.chat(self.SYSTEM_SQL, fix))

        resposta = self.llm.chat(
            self.SYSTEM_ANSWER,
            f"Pergunta: {question}\nResultado da consulta (JSON): {rows}",
        )
        return {"sql": sql, "rows": rows, "answer": resposta}


if __name__ == "__main__":
    from analytics.coach import OllamaClient
    agent = SqlAgent(llm=OllamaClient())
    for q in ["qual o meu pace medio nas corridas (tipo RUN)?",
              "quantos treinos de cada tipo eu tenho?"]:
        print(f"\n=== {q} ===")
        r = agent.answer(q)
        print("SQL:", r["sql"])
        print("Resposta:", r["answer"])
