"""analytics/injury_classifier.py — texto livre do atleta → diagnóstico da taxonomia (via LLM).

Refina o rótulo: o `symptom_text` ("dói na frente ao descer escada") → um `diagnosis` (`pfp`). A
região já rotula sozinha, então isto é UPGRADE do rótulo, não bloqueador.

Design ANTI-ALUCINAÇÃO (espelha o `LLMJudge`): classificação de CONJUNTO FECHADO com ABSTENÇÃO.
- A região (do mapa corporal) é o PRIOR: só os diagnósticos daquela região são candidatos
  (`diagnoses_for_region`) — muitas vezes 1 só, o que torna o acerto trivial.
- O LLM devolve `{diagnosis|null, confidence}`; validamos contra os candidatos (string fora da
  lista → null). NUNCA confiamos na string crua.
- Default SEGURO (app de lesão): só grava com confiança ALTA; senão null (a região carrega o dado,
  e o guardrail de `build_dataset` já barra diagnosis nulo). Roda em coach-time (preguiçoso).
"""

import json
import re

from core.framework.interfaces import BaseLLMClient
from analytics.injury_taxonomy import DIAGNOSES, diagnoses_for_region, valid_diagnosis

SYSTEM = (
    "Voce classifica a QUEIXA de um corredor em UM diagnostico de uma LISTA FECHADA. Responda "
    "SOMENTE com JSON: {\"diagnosis\": \"<id da lista ou null>\", \"confidence\": \"alta|baixa\"}. "
    "Escolha um id APENAS se o texto claramente corresponder; na duvida use null e confidence baixa. "
    "NAO invente id fora da lista. NAO explique, so o JSON."
)


class DiagnosisClassifier:
    """Composição com um LLM (polimorfismo: Ollama local, ou qualquer BaseLLMClient)."""

    def __init__(self, llm: BaseLLMClient):
        self.llm = llm

    @staticmethod
    def _parse(raw: str) -> dict:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return {"diagnosis": None, "confidence": "baixa"}
        try:
            data = json.loads(m.group(0))
        except json.JSONDecodeError:
            return {"diagnosis": None, "confidence": "baixa"}
        return {"diagnosis": data.get("diagnosis"), "confidence": data.get("confidence", "baixa")}

    def classify(self, symptom_text: str, region: str = None) -> dict:
        """Texto → {diagnosis, confidence}. `diagnosis` só é preenchido se casar com um candidato
        da região E confiança alta; senão null (abstenção)."""
        candidates = diagnoses_for_region(region) if region else list(DIAGNOSES)
        if not (symptom_text and symptom_text.strip()) or not candidates:
            return {"diagnosis": None, "confidence": "baixa"}

        opcoes = "\n".join(f"- {dx}: {DIAGNOSES[dx]['label']}" for dx in candidates)
        prompt = f"LISTA FECHADA (id: descricao):\n{opcoes}\n\nQUEIXA DO ATLETA:\n{symptom_text.strip()}"
        parsed = self._parse(self.llm.chat(SYSTEM, prompt))

        dx = parsed.get("diagnosis")
        # validação dura: tem que ser um candidato REAL da região + vocabulário vigente
        if dx not in candidates or not valid_diagnosis(dx):
            dx = None
        if parsed.get("confidence") != "alta":   # default seguro: só grava com confiança alta
            dx = None
        return {"diagnosis": dx, "confidence": parsed.get("confidence", "baixa")}
