"""analytics/run_analysis.py — inteligencia de UMA corrida (profundidade por treino).

Foco: o que aconteceu DENTRO de um treino. Comeca pelo ponto de quebra mecanica
(plan.md 6.1): o instante em que a fadiga aparece — FC sobe acima da linha de base
enquanto a cadencia cai abaixo dela.

Decisao de design: limiares PERSONALIZADOS (linha de base do proprio treino), nao
numeros fixos. 165 bpm e fadiga pra um, aquecimento pra outro.

SQL ensinado:
- Janela por LINHAS: ROWS BETWEEN 30 PRECEDING AND CURRENT ROW  (= df.rolling(30))
  suaviza ruido olhando as ultimas ~30 leituras (~30s).
- Janela VAZIA: AVG(x) OVER ()  -> media da corrida inteira = linha de base,
  calculada SEM join e sem segundo scan.
"""

from typing import Optional

from core.database import get_connection
from core.framework.interfaces import BaseAnalyzer

# Limiares de referencia CITADOS da literatura. Servem para o codigo entregar a
# COMPARACAO pronta (deterministica) ao LLM, em vez de deixar ele recalcular e errar.
CADENCE_PROTECTIVE_MIN = 166   # abaixo: risco tibial 6-7x maior
CADENCE_PROTECTIVE_GOOD = 178  # >= : faixa mais protetora
CADENCE_REF_SOURCE = "Revisao sistematica de cadencia e prevencao de lesao (PMC12440572)"
DECOUPLING_SOURCE = "Revisao sobre deriva cardiaca / decoupling aerobico (PMC12271085)"


def metabolic_efficiency(speed_ms: float, heart_rate: float) -> float:
    """Eficiencia metabolica = velocidade por batimento (x100 p/ escala).

    DEFINICAO UNICA da metrica, reusada por durabilidade (abaixo) e por RunningFitness.
    O EfficiencyAnalyzer calcula a MESMA conta em SQL (por terreno) — mesma formula.
    """
    return speed_ms / heart_rate * 100


def breaking_point(activity_id: str, cadence_drop: float = 0.05) -> dict:
    """Acha o 1o instante de fadiga mecanica de uma corrida.

    Fadiga = cadencia media movel cai >cadence_drop (5%) abaixo da base do treino
    E ao mesmo tempo a FC media movel esta acima da base. Retorna o evento ou None.
    """
    con = get_connection()
    row = con.execute(
        """
        WITH rolling AS (
            SELECT
                timestamp,
                -- medias moveis de ~30s (janela por LINHAS) suavizam o ruido
                AVG(heart_rate) OVER w AS roll_hr,
                AVG(cadence)    OVER w AS roll_cad,
                -- linha de base = media da corrida inteira (janela VAZIA, sem join)
                AVG(heart_rate) OVER () AS base_hr,
                AVG(cadence)    OVER () AS base_cad
            FROM fact_telemetry
            WHERE activity_id = ?
              AND heart_rate IS NOT NULL
              AND cadence IS NOT NULL
              AND cadence > 0                 -- ignora paradas/aquecimento (cad 0)
            WINDOW w AS (ORDER BY timestamp ROWS BETWEEN 30 PRECEDING AND CURRENT ROW)
        )
        SELECT timestamp, roll_hr, roll_cad, base_hr, base_cad
        FROM rolling
        WHERE roll_cad < base_cad * (1 - ?)   -- cadencia caiu abaixo da base
          AND roll_hr  > base_hr              -- e FC esta elevada (decoupling)
        ORDER BY timestamp
        LIMIT 1                                -- o PRIMEIRO instante de quebra
        """,
        [activity_id, cadence_drop],
    ).fetchone()

    if row is None:
        return {"activity_id": activity_id, "breaking_point": None}

    ts, roll_hr, roll_cad, base_hr, base_cad = row
    return {
        "activity_id": activity_id,
        "breaking_point": ts,
        "hr_at_break": round(roll_hr, 0),
        "cadence_at_break": round(roll_cad, 0),
        "baseline_hr": round(base_hr, 0),
        "baseline_cadence": round(base_cad, 0),
        "cadence_drop_pct": round(100 * (1 - roll_cad / base_cad), 1),
    }


def efficiency_by_terrain(activity_id: str, grade_threshold: float = 0.01) -> dict:
    """Eficiencia metabolica (velocidade/FC x 100) segmentada por terreno.

    Eficiencia = velocidade(m/s) / FC * 100 — quanto de velocidade por batimento.
    Terreno vem do GRADE = Δaltitude / Δdistancia (ambos reais, via LAG).

    SQL ensinado — LAG(coluna, 10) OVER (ORDER BY timestamp):
      pega o valor de 10 leituras atras (= df.shift(10)). Usamos em altitude E
      distancia para medir subida e avanco nos ultimos ~10s. Grade exato, sem
      derivar de velocidade.
    """
    con = get_connection()
    rows = con.execute(
        """
        WITH pts AS (
            SELECT
                (speed_ms / heart_rate) * 100 AS efficiency,  -- = metabolic_efficiency() em SQL
                altitude   - LAG(altitude, 10)   OVER (ORDER BY timestamp) AS alt_delta,
                distance_m - LAG(distance_m, 10) OVER (ORDER BY timestamp) AS dist_delta
            FROM fact_telemetry
            WHERE activity_id = ?
              AND heart_rate > 0 AND speed_ms > 0   -- ignora paradas
            -- NAO exigimos altitude: a eficiencia nao precisa dela. Sem altitude
            -- (ex: esteira indoor), o CASE classifica tudo como 'plano'.
        )
        SELECT
            CASE
                WHEN alt_delta IS NULL OR dist_delta <= 0 THEN 'plano'
                WHEN alt_delta / dist_delta >  ? THEN 'subida'
                WHEN alt_delta / dist_delta < -? THEN 'descida'
                ELSE 'plano'
            END AS terreno,
            COUNT(*)        AS segundos,
            AVG(efficiency) AS efic_media
        FROM pts
        GROUP BY terreno
        """,
        [activity_id, grade_threshold, grade_threshold],
    ).fetchall()

    by_terrain = {t: {"segundos": n, "eficiencia": round(e, 2)} for t, n, e in rows}

    # Queda de eficiencia plano -> subida (indicador-chave para provas hibridas).
    drop = None
    if "plano" in by_terrain and "subida" in by_terrain:
        flat = by_terrain["plano"]["eficiencia"]
        up = by_terrain["subida"]["eficiencia"]
        drop = round(100 * (1 - up / flat), 1)

    return {"activity_id": activity_id, "by_terrain": by_terrain, "uphill_efficiency_drop_pct": drop}


def aerobic_decoupling(activity_id: str, min_points: int = 60) -> dict:
    """Durabilidade aerobica: a MESMA eficiencia (velocidade/FC) na 1a vs 2a metade da
    corrida. Desacoplamento >10% = 'racha' sob fadiga (deriva cardiaca). So onde ha
    velocidade continua (corrida/esteira) — força/HIIT sem speed caem fora sozinhos.

    SQL ensinado — NTILE(2) OVER (ORDER BY timestamp): divide as leituras em 2 baldes
    iguais por tempo (1a/2a metade), sem achar o ponto medio na mao.
    """
    con = get_connection()
    rows = con.execute(
        """
        WITH pts AS (
            SELECT speed_ms, heart_rate, NTILE(2) OVER (ORDER BY timestamp) AS half
            FROM fact_telemetry
            WHERE activity_id = ? AND heart_rate > 0 AND speed_ms > 0
        )
        SELECT half, AVG(speed_ms), AVG(heart_rate), COUNT(*)
        FROM pts GROUP BY half ORDER BY half
        """,
        [activity_id],
    ).fetchall()
    if len(rows) < 2 or sum(r[3] for r in rows) < min_points:
        return {"applicable": False}

    (_, sp1, hr1, _), (_, sp2, hr2, _) = rows
    eff1, eff2 = metabolic_efficiency(sp1, hr1), metabolic_efficiency(sp2, hr2)
    pct = round((eff1 - eff2) / eff1 * 100, 1)
    label = "durabilidade alta" if pct <= 5 else "durabilidade boa" if pct <= 10 else "racha sob fadiga"
    return {
        "applicable": True, "decoupling_pct": pct, "label": label,
        "eff_first": round(eff1, 2), "eff_second": round(eff2, 2),
        "hr_first": round(hr1), "hr_second": round(hr2),
    }


class BreakingPointAnalyzer(BaseAnalyzer):
    """Ponto de quebra mecanica (§6.1) como analyzer polimorfico."""

    label = "Ponto de quebra"

    def analyze(self, activity_id: str) -> dict:
        return breaking_point(activity_id)

    def to_prompt(self, result: dict) -> Optional[str]:
        bp = result
        if bp["breaking_point"]:
            return (
                f"Ponto de quebra: cadencia caiu {bp['cadence_drop_pct']}% "
                f"(de {bp['baseline_cadence']:.0f} para {bp['cadence_at_break']:.0f}) "
                f"com a FC subindo para {bp['hr_at_break']:.0f}."
            )
        return "Sem ponto de quebra: cadencia estavel o treino todo."


class EfficiencyAnalyzer(BaseAnalyzer):
    """Eficiencia metabolica por terreno (§6.2) como analyzer polimorfico."""

    label = "Eficiencia por terreno"

    def analyze(self, activity_id: str) -> dict:
        return efficiency_by_terrain(activity_id)

    def to_prompt(self, result: dict) -> Optional[str]:
        terr = result["by_terrain"]
        if not terr:
            return None
        partes = [f"{t}: {v['eficiencia']}" for t, v in terr.items()]
        linha = "Eficiencia (velocidade/FC) por terreno: " + ", ".join(partes) + "."
        drop = result["uphill_efficiency_drop_pct"]
        if drop is not None:
            linha += f" Queda na subida: {drop}%."
        return linha


class DurabilityAnalyzer(BaseAnalyzer):
    """Durabilidade aerobica (decoupling Pa:FC) — 'segura o ritmo sob fadiga?'. Modulo Corrida."""

    label = "Durabilidade aerobica"

    def analyze(self, activity_id: str) -> dict:
        return aerobic_decoupling(activity_id)

    def to_prompt(self, result: dict) -> Optional[str]:
        if not result.get("applicable"):
            return None
        pct = result["decoupling_pct"]
        como = ("Para melhorar: volume em Z2 (base aerobica) e longoes."
                if pct > 10 else "Boa resistencia a fadiga aerobica.")
        return (f"CONCLUSAO (durabilidade): desacoplamento aerobico de {pct}% entre 1a e 2a metade "
                f"(FC media {result['hr_first']}->{result['hr_second']}) — {result['label']}. {como} "
                f"(FONTE: {DECOUPLING_SOURCE})")


class TerrainContextAnalyzer(BaseAnalyzer):
    """Contextualiza a queda de ritmo pelo terreno: foi por SUBIDA (esperado) ou
    no PLANO (sugere fadiga/quebra de forma)? Degrada gracioso sem altitude."""

    label = "Contexto de terreno"

    def analyze(self, activity_id: str) -> dict:
        con = get_connection()
        # disponibilidade de altitude + ganho de elevacao (soma das subidas)
        n_alt, gain = con.execute(
            """WITH d AS (
                   SELECT altitude - LAG(altitude) OVER (ORDER BY timestamp) AS delta
                   FROM fact_telemetry WHERE activity_id = ? AND altitude IS NOT NULL
               )
               SELECT COUNT(*), COALESCE(SUM(CASE WHEN delta > 0 THEN delta END), 0) FROM d""",
            [activity_id],
        ).fetchone()
        if n_alt == 0:
            return {"has_elevation": False}

        bp = breaking_point(activity_id)
        grade = None
        if bp["breaking_point"]:
            # inclinacao no ponto de quebra: Δaltitude / Δdistancia nos ~10s anteriores
            row = con.execute(
                """WITH a AS (
                       SELECT timestamp,
                              altitude   - LAG(altitude, 10)   OVER (ORDER BY timestamp) AS d_alt,
                              distance_m - LAG(distance_m, 10) OVER (ORDER BY timestamp) AS d_dist
                       FROM fact_telemetry
                       WHERE activity_id = ? AND altitude IS NOT NULL AND distance_m IS NOT NULL
                   )
                   SELECT d_alt / d_dist FROM a
                   WHERE timestamp >= ? AND d_dist > 0
                   ORDER BY timestamp LIMIT 1""",
                [activity_id, bp["breaking_point"]],
            ).fetchone()
            grade = row[0] if row and row[0] is not None else None
        return {
            "has_elevation": True,
            "elevation_gain_m": round(gain, 1),
            "breaking_point": bp["breaking_point"],
            "grade_at_break": grade,
        }

    def to_prompt(self, result: dict) -> Optional[str]:
        if not result.get("has_elevation"):
            return None
        gain = result["elevation_gain_m"]
        if not result["breaking_point"] or result["grade_at_break"] is None:
            return f"Ganho de elevacao no treino: {gain} m."
        grade_pct = round(result["grade_at_break"] * 100, 1)
        if result["grade_at_break"] > 0.01:
            return (f"Ganho de elevacao: {gain} m. A queda de ritmo coincidiu com uma SUBIDA "
                    f"(inclinacao ~{grade_pct}%) — consistente com o terreno, nao necessariamente fadiga.")
        return (f"Ganho de elevacao: {gain} m. A queda de ritmo ocorreu em terreno aproximadamente "
                f"PLANO (inclinacao ~{grade_pct}%) — sugere fadiga ou quebra de forma, nao o terreno.")


class CadenceReferenceAnalyzer(BaseAnalyzer):
    """Compara a cadencia media com limiares CITADOS e entrega a CONCLUSAO pronta.

    O codigo faz a comparacao (deterministica); o LLM so redige — sem recalcular
    'acima/abaixo' e errar (como ja aconteceu com 162 vs 166).
    """

    label = "Cadencia vs. limiar"

    def analyze(self, activity_id: str) -> dict:
        con = get_connection()
        row = con.execute(
            """SELECT a.primary_type, c.avg_cadence
               FROM dim_activities a
               LEFT JOIN cache_workout_summary c ON c.activity_id = a.activity_id
               WHERE a.activity_id = ?""",
            [activity_id],
        ).fetchone()
        ptype, avg_cad = row
        if ptype != "RUN" or not avg_cad:
            return {"applicable": False}
        return {"applicable": True, "avg_cadence": round(avg_cad)}

    def to_prompt(self, result: dict) -> Optional[str]:
        if not result.get("applicable"):
            return None
        cad = result["avg_cadence"]
        if cad < CADENCE_PROTECTIVE_MIN:
            estado = (f"esta ABAIXO do limiar protetor de {CADENCE_PROTECTIVE_MIN} spm "
                      f"(associado a risco tibial 6-7x maior vs >= {CADENCE_PROTECTIVE_GOOD} spm)")
        elif cad < CADENCE_PROTECTIVE_GOOD:
            estado = (f"esta na faixa intermediaria ({CADENCE_PROTECTIVE_MIN}-{CADENCE_PROTECTIVE_GOOD} spm); "
                      f">= {CADENCE_PROTECTIVE_GOOD} e o benchmark mais protetor")
        else:
            estado = f"esta na faixa PROTETORA (>= {CADENCE_PROTECTIVE_GOOD} spm)"
        return f"CONCLUSAO (cadencia): cadencia media de {cad} spm {estado} (FONTE: {CADENCE_REF_SOURCE})."


if __name__ == "__main__":
    con = get_connection()
    runs = con.execute(
        "SELECT activity_id, activity_name FROM dim_activities WHERE primary_type='RUN'"
    ).fetchall()
    for aid, name in runs:
        print(f"\n=== {name} ===")
        r = breaking_point(aid)
        if r["breaking_point"]:
            print(f"  quebra em {r['breaking_point']} | cadencia {r['cadence_at_break']:.0f} "
                  f"(base {r['baseline_cadence']:.0f}, -{r['cadence_drop_pct']}%) | "
                  f"FC {r['hr_at_break']:.0f} (base {r['baseline_hr']:.0f})")
        else:
            print("  sem ponto de quebra (corrida estavel)")
        eff = efficiency_by_terrain(aid)
        for terreno, v in eff["by_terrain"].items():
            print(f"  eficiencia {terreno:8}: {v['eficiencia']:.2f}  ({v['segundos']}s)")
        if eff["uphill_efficiency_drop_pct"] is not None:
            print(f"  -> queda de eficiencia na subida: {eff['uphill_efficiency_drop_pct']}%")
