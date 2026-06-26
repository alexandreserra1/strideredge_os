"""analytics/training_load.py — carga de treino (TRIMP) e ACWR.

Trilha 1: transforma treinos soltos em metricas de carga e risco de lesao.
Tudo em SQL (DuckDB) + Python — sem Rust, sem LLM.

Estrategia de performance (pedido do usuario):
- A varredura pesada da fact_telemetry (milhoes de linhas) acontece UMA vez por
  treino, em refresh_summary_cache(), com WHERE filtrando ANTES de agregar.
- As consultas de carga/ACWR leem so cache_workout_summary + dim_activities
  (1 linha por treino) — nunca reescaneiam a telemetria crua.

Conceitos:
- CARGA (TRIMP) = duracao_min x FC_media. Proxy do "peso" da sessao.
- ACWR = carga aguda (media 7 dias) / cronica (media 28 dias).
  0.8-1.3 = zona segura; >1.5 = risco de lesao; <0.8 = destreino.
"""

from core.database import get_connection


def refresh_summary_cache() -> int:
    """(Re)calcula os agregados por treino e grava em cache_workout_summary.

    Esta e a UNICA funcao que varre a fact_telemetry. O WHERE filtra nulos ANTES
    do GROUP BY. Roda na ingestao (ou sob demanda). Retorna o nº de treinos.
    """
    con = get_connection()  # read-write: vamos escrever no cache
    # Reconstroi do zero: evita ORFAOS (atividades ja deletadas) inflarem o cache
    # e distorcerem agregados/historico. O cache reflete so a telemetria atual.
    con.execute("DELETE FROM cache_workout_summary")
    con.execute(
        """
        INSERT INTO cache_workout_summary
            (activity_id, avg_hr, max_hr, avg_cadence)
        SELECT
            activity_id,
            AVG(heart_rate),
            MAX(heart_rate),
            AVG(cadence)
        FROM fact_telemetry
        WHERE heart_rate IS NOT NULL   -- filtra ANTES de agregar
        GROUP BY activity_id
        """
    )
    count = con.execute("SELECT COUNT(*) FROM cache_workout_summary").fetchone()[0]
    return count


def session_loads() -> list[dict]:
    """Carga (TRIMP) de cada atividade — lendo so tabelas pequenas.

    Join entre dim_activities (duracao) e cache_workout_summary (FC media). Ambas
    tem 1 linha por treino, entao o join e trivial — a telemetria crua nao e tocada.
    """
    con = get_connection()
    rows = con.execute(
        """
        SELECT
            a.activity_name,
            a.primary_type,
            CAST(a.start_time AS DATE)              AS day,
            a.total_duration_seconds / 60.0         AS duration_min,
            c.avg_hr,
            (a.total_duration_seconds / 60.0) * COALESCE(c.avg_hr, 0) AS trimp_load
        FROM dim_activities a
        LEFT JOIN cache_workout_summary c ON c.activity_id = a.activity_id
        WHERE a.total_duration_seconds IS NOT NULL
        ORDER BY a.start_time
        """
    ).fetchall()
    cols = ["activity_name", "primary_type", "day", "duration_min", "avg_hr", "trimp_load"]
    return [dict(zip(cols, r)) for r in rows]


def acwr_timeline() -> list[dict]:
    """Linha do tempo de carga diaria + ACWR (razao aguda/cronica).

    Window function ensinada (= pandas df.rolling('7d').sum()):
      SUM(load) OVER (ORDER BY day RANGE BETWEEN INTERVAL 6 DAY PRECEDING AND CURRENT ROW)
      -> para cada dia, soma a carga dos ultimos 7 dias (a "janela desliza").

    ACWR = (soma 7d / 7) / (soma 28d / 28). Dias sem treino contam como carga 0,
    por isso dividimos pelo nº de dias da janela, nao pela contagem de treinos.
    """
    con = get_connection()
    rows = con.execute(
        """
        WITH session AS (                  -- carga de cada treino (so tabelas pequenas)
            SELECT
                CAST(a.start_time AS DATE) AS day,
                (a.total_duration_seconds / 60.0) * COALESCE(c.avg_hr, 0) AS load
            FROM dim_activities a
            LEFT JOIN cache_workout_summary c ON c.activity_id = a.activity_id
            WHERE a.total_duration_seconds IS NOT NULL
        ),
        daily AS (                         -- soma por dia (varios treinos no mesmo dia)
            SELECT day, SUM(load) AS daily_load
            FROM session GROUP BY day
        )
        SELECT
            day,
            daily_load,
            -- janela de 7 dias / 7 = carga AGUDA media diaria
            SUM(daily_load) OVER (
                ORDER BY day RANGE BETWEEN INTERVAL 6 DAY PRECEDING AND CURRENT ROW
            ) / 7.0 AS acute,
            -- janela de 28 dias / 28 = carga CRONICA media diaria
            SUM(daily_load) OVER (
                ORDER BY day RANGE BETWEEN INTERVAL 27 DAY PRECEDING AND CURRENT ROW
            ) / 28.0 AS chronic
        FROM daily
        ORDER BY day
        """
    ).fetchall()

    result = []
    for day, daily_load, acute, chronic in rows:
        # ACWR so faz sentido com cronica > 0 (evita divisao por zero).
        acwr = (acute / chronic) if chronic and chronic > 0 else None
        result.append({
            "day": day,
            "daily_load": daily_load,
            "acute_7d": acute,
            "chronic_28d": chronic,
            "acwr": acwr,
        })
    return result


def _acwr_zone(acwr) -> str:
    """Traduz o ACWR em zona de risco (linguagem de Coach)."""
    if acwr is None:
        return "sem dados"
    if acwr < 0.8:
        return "destreino"
    if acwr <= 1.3:
        return "zona segura"
    if acwr <= 1.5:
        return "atencao"
    return "RISCO DE LESAO"


if __name__ == "__main__":
    n = refresh_summary_cache()
    print(f"cache atualizado: {n} treinos\n")
    print("=== Carga por treino (TRIMP) ===")
    for s in session_loads():
        print(
            f"{s['day']}  {s['primary_type']:8} {s['activity_name'][:16]:16} "
            f"dur={s['duration_min']:5.0f}min  fc={(s['avg_hr'] or 0):3.0f}  "
            f"carga={s['trimp_load']:7.0f}"
        )
    print("\n=== Linha do tempo ACWR ===")
    for r in acwr_timeline():
        acwr_str = f"{r['acwr']:.2f}" if r["acwr"] is not None else "  - "
        print(
            f"{r['day']}  carga_dia={r['daily_load']:7.0f}  "
            f"aguda={r['acute_7d']:6.0f}  cronica={r['chronic_28d']:6.0f}  "
            f"ACWR={acwr_str}  [{_acwr_zone(r['acwr'])}]"
        )
