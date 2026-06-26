"""analytics/coach_eval.py — eval anti-alucinação do coach.

Mede, de forma DETERMINÍSTICA, se o veredito é fiel ao que foi fornecido:
- numeric_fidelity: fração dos números do veredito que aparecem no prompt.
  (pega número inventado E conta feita pelo LLM — princípio "conclusão pronta".)
- citation_validity: fração das fontes citadas (PMCxxxx) presentes nas evidências.

evaluate() roda o coach numa atividade e devolve as métricas + o veredito.
"""

import re

from analytics.coach import Coach


class CoachEvaluator:
    """Avalia a fidelidade do veredito ao prompt (dados + evidências)."""

    def __init__(self, coach: Coach):
        self.coach = coach

    @staticmethod
    def _numbers(text: str) -> set:
        return set(re.findall(r"\d+(?:\.\d+)?", text))

    @staticmethod
    def _citations(text: str) -> set:
        return set(m.upper() for m in re.findall(r"PMC\d+", text, re.IGNORECASE))

    def numeric_fidelity(self, verdict: str, prompt: str) -> float:
        nums = self._numbers(verdict)
        if not nums:
            return 1.0
        supported = nums & self._numbers(prompt)
        return round(len(supported) / len(nums), 3)

    def citation_validity(self, verdict: str, prompt: str) -> float:
        cited = self._citations(verdict)
        if not cited:
            return 1.0
        valid = cited & self._citations(prompt)
        return round(len(valid) / len(cited), 3)

    def evaluate(self, activity_id: str) -> dict:
        """Gera o veredito sobre o MESMO prompt e mede a fidelidade."""
        prompt = self.coach.build_user_prompt(activity_id)
        verdict = self.coach.llm.chat(self.coach.SYSTEM_PROMPT, prompt)
        return {
            "numeric_fidelity": self.numeric_fidelity(verdict, prompt),
            "citation_validity": self.citation_validity(verdict, prompt),
            "verdict": verdict,
        }
