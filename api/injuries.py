"""api/injuries.py — log de lesão do atleta (auto-relato estruturado, OSTRC).

Uma linha por lesão (nível atleta, longitudinal). Vocabulário controlado em
`analytics.injury_taxonomy`. É a fonte de OUTCOME que a ponte de ML (`analytics.injury_dataset`)
correlaciona com o histórico de análises do atleta. Espelha o padrão do ProfileService.
"""

import uuid
from typing import Optional

from core.database import get_connection
from analytics.injury_taxonomy import valid_diagnosis, DIAGNOSES, REGIONS, SIDES

# As 4 perguntas do OSTRC (cada uma 0–3). A severidade 0–100 é a média normalizada (estilo OSTRC-BR).
_Q = ("q_participation", "q_volume", "q_performance", "q_pain")
_COLS = ("id, user_id, region, diagnosis, side, onset_date, q_participation, q_volume, "
         "q_performance, q_pain, notes, symptom_text, reported_at")


class InjuryError(Exception):
    """Entrada inválida (região/diagnóstico fora do vocabulário)."""


class InjuryService:

    @staticmethod
    def severity(answers: dict) -> int:
        """Severidade 0–100 a partir das 4 respostas OSTRC (0–3). Monotônica: mais alto = pior."""
        vals = [int(answers.get(q) or 0) for q in _Q]
        return round(sum(min(max(v, 0), 3) for v in vals) / 12 * 100)

    def log(self, user_id: str, report: dict) -> dict:
        """Registra uma lesão. Valida região/diagnóstico contra a taxonomia."""
        dx = report.get("diagnosis")
        region = report.get("region")
        side = report.get("side")
        if dx and not valid_diagnosis(dx):
            raise InjuryError(f"diagnóstico inválido: {dx}")
        if region and region not in REGIONS:
            raise InjuryError(f"região inválida: {region}")
        if side and side not in SIDES:
            raise InjuryError(f"lado inválido: {side}")
        # se o diagnóstico veio sem região, herda a região da taxonomia
        if dx and not region:
            region = DIAGNOSES[dx]["region"]

        rid = str(uuid.uuid4())
        get_connection().execute(
            "INSERT INTO injury_reports (id, user_id, region, diagnosis, side, onset_date, "
            "q_participation, q_volume, q_performance, q_pain, notes, symptom_text) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [rid, user_id, region, dx, side, report.get("onset_date"),
             report.get("q_participation"), report.get("q_volume"),
             report.get("q_performance"), report.get("q_pain"), report.get("notes"),
             report.get("symptom_text")])
        return self.get(rid)

    def get(self, injury_id: str) -> Optional[dict]:
        row = get_connection().execute(
            f"SELECT {_COLS} FROM injury_reports WHERE id = ?", [injury_id]).fetchone()
        return self._row(row) if row else None

    def list(self, user_id: str) -> list:
        rows = get_connection().execute(
            f"SELECT {_COLS} FROM injury_reports WHERE user_id = ? ORDER BY onset_date DESC NULLS LAST",
            [user_id]).fetchall()
        return [self._row(r) for r in rows]

    def classify(self, injury_id: str, classifier) -> Optional[dict]:
        """Coach-time: mapeia o texto livre → diagnóstico da taxonomia via LLM e PERSISTE só se
        veio um id válido (confiança alta). Não sobrescreve um diagnóstico já existente."""
        report = self.get(injury_id)
        if not report:
            return None
        if report.get("diagnosis"):
            return report                     # já rotulado — não reclassifica
        result = classifier.classify(report.get("symptom_text"), report.get("region"))
        if result["diagnosis"]:
            get_connection().execute(
                "UPDATE injury_reports SET diagnosis = ? WHERE id = ?",
                [result["diagnosis"], injury_id])
        return self.get(injury_id)

    @classmethod
    def _row(cls, r) -> dict:
        answers = {"q_participation": r[6], "q_volume": r[7], "q_performance": r[8], "q_pain": r[9]}
        return {
            "id": str(r[0]), "user_id": r[1], "region": r[2], "diagnosis": r[3], "side": r[4],
            "onset_date": str(r[5]) if r[5] else None, **answers, "notes": r[10],
            "symptom_text": r[11], "reported_at": str(r[12]), "severity": cls.severity(answers),
        }
