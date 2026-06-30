"""analytics/grounding.py — guarda de ATERRAMENTO do veredito (GroundingGuard).

Garante que o texto do coach so use numeros presentes nos dados e nao cite causas nao
medidas (desidratacao, calor...). Herda BaseGuard: a base faz o loop de regeneracao
(enforce); aqui definimos O QUE e problema (issues) e COMO corrigir (_correction).

REUSO: o Coach COMPOE esta guarda (enforce via retry na geracao do veredito) e o
CoachEvaluator usa as MESMAS primitivas (numbers/banned) para medir — fonte unica.
"""

import re
from typing import Dict

from core.framework.interfaces import BaseGuard


class GroundingGuard(BaseGuard):
    """Aterramento: zero numero inventado + zero causa nao medida."""

    BANNED_CAUSES = ("desidrat", "calor", "glicog", "clima")  # causas que nunca medimos
    _NUM_RE = re.compile(r"\d+(?:[.,]\d+)?")

    @classmethod
    def numbers(cls, text: str) -> set:
        """Numeros do texto, normalizando virgula->ponto ('2,9' == '2.9')."""
        return {m.replace(",", ".") for m in cls._NUM_RE.findall(text)}

    @classmethod
    def banned(cls, text: str) -> list:
        """Causas nao medidas citadas no texto (extrapolacao)."""
        t = text.lower()
        return [b for b in cls.BANNED_CAUSES if b in t]

    def issues(self, output: str, reference: str) -> Dict[str, list]:
        return {
            "invented_numbers": sorted(self.numbers(output) - self.numbers(reference)),
            "banned_causes": self.banned(output),
        }

    def _correction(self, issues: Dict[str, list]) -> str:
        partes = []
        if issues["invented_numbers"]:
            partes.append(f"removendo os numeros que NAO estao nos dados ({', '.join(issues['invented_numbers'])})")
        if issues["banned_causes"]:
            partes.append(f"sem citar causas nao medidas ({', '.join(issues['banned_causes'])})")
        return ("CORRECAO: reescreva " + " e ".join(partes) +
                ". Use SOMENTE numeros que aparecem nos dados; descreva o resto em palavras.")
