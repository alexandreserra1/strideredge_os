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

    @classmethod
    def citations(cls, text: str) -> list:
        """Fontes PMC citadas, unicas e NA ORDEM em que aparecem (reusada por parser e eval)."""
        seen: list = []
        for pmc in re.findall(r"PMC\d+", text, re.IGNORECASE):
            if pmc.upper() not in seen:
                seen.append(pmc.upper())
        return seen

    # DOI e PubMed ID em strings de FONTE (nem todo estudo real tem PMC — PMC e so full-text
    # aberto; JOSPT/Kinesiology tem DOI/PMID). O _DOI para no 1o espaco/parentese/virgula.
    _DOI_RE = re.compile(r"10\.\d{4,}/[^\s)\],]+")
    _PMID_RE = re.compile(r"pubmed\s*:?\s*(\d{6,})", re.IGNORECASE)

    @classmethod
    def source_id(cls, source: str) -> str:
        """ID ESTAVEL de uma string de FONTE autoritativa (do corpus), pra citar de forma
        verificavel. Preferencia: PMC > PMID > DOI. Sem nenhum, cai pro titulo curto (ate o
        travessao/parentese) — sempre devolve algo citavel, nunca vazio."""
        m = re.search(r"PMC\d+", source, re.IGNORECASE)
        if m:
            return m.group(0).upper()
        m = cls._PMID_RE.search(source)
        if m:
            return f"PMID:{m.group(1)}"
        m = cls._DOI_RE.search(source)
        if m:
            return f"DOI:{m.group(0)}"
        return re.split(r"\s+[—–-]\s+|\s*\(", source.strip())[0][:80]

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
