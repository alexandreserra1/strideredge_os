"""analytics/form_coach.py — Algoritmo Corretivo: do gap biomecânico -> exercícios citados.

Fecha o ciclo "vê o movimento -> entende -> age". Recebe as métricas do motor de vídeo
(FormMetrics) + o perfil do atleta, calcula os alvos ideais e o gap (analytics/biomechanics),
recupera a evidência do corpus (RAG) e o LLM local transforma isso em um plano de correção
COM fonte. Reusa a mesma disciplina do veredito: `GroundingGuard` (sem número inventado) e
`VerdictParser` (saída estruturada). Sem evidência no corpus, não inventa exercício.
"""

import re
from typing import Callable, Optional

from core.framework.interfaces import BaseLLMClient, BaseRetriever
from analytics.grounding import GroundingGuard
from analytics.biomechanics import ideal_targets, diagnose
from analytics.injury_risk import assess as assess_risk
from analytics.injury_quality import sanitize_metrics
from analytics.exercises import for_factors

# Cada fator desviado -> domínios do RAG a consultar (roteamento; evita bleed de calçado/nutrição
# numa query de cadência). Corretivo puxa biomecânica (o fato) + força/treino (a correção). Reusa
# as chaves de biomechanics.ideal_targets.
FACTOR_DOMAINS = {
    "cadence_spm": ["biomecanica", "treino"],
    "knee_contact_deg": ["biomecanica", "treino"],
    "pelvic_drop_deg": ["biomecanica", "forca"],
    "knee_valgus_deg": ["biomecanica", "forca"],
    "asymmetry_pct": ["biomecanica", "forca"],
    "vertical_oscillation_pct": ["biomecanica", "forca"],
    "ground_contact_ms": ["biomecanica", "forca"],
    "trunk_lean_deg": ["biomecanica"],
}


# O QUE corrigir (os desvios) ja vem estruturado do biomechanics.py — deterministico.
# O LLM faz SO uma coisa: propor os EXERCICIOS que corrigem, aterrado nas evidencias.
SYSTEM = (
    "Voce e um treinador de corrida que fala com o ATLETA de forma HUMANA, calorosa e didatica — "
    "nada de jargao seco. Recebe desvios biomecanicos ja medidos + EVIDENCIAS cientificas. Para "
    "CADA desvio listado, escreva UMA recomendacao, UMA POR LINHA comecando com '- ', e cada linha "
    "tem TRES partes numa frase natural e fluida: (1) O QUE fazer (acao concreta e simples); "
    "(2) POR QUE ajuda VOCE (explique o beneficio no seu corpo/corrida em lingua de gente — ex.: "
    "'passos mais curtos fazem o pe cair embaixo do corpo e amortecer melhor o impacto'); (3) COMO "
    "na pratica (dica de execucao: quando, quantas vezes, como comecar — ex.: 'comece 1x na semana "
    "numa corrida leve, com um app de metronomo'). Termine a linha com a fonte entre parenteses "
    "(Fonte: PMCxxxx). Regras: fale 'voce', tom encorajador; cada linha ataca UM desvio LISTADO; se "
    "a evidencia citar metrica que NAO esta na lista, IGNORE; NAO use markdown nem cabecalhos; use "
    "SOMENTE numeros que aparecem nos dados (nao invente numero); recomende SO o que a evidencia "
    "ampara e cite a FONTE. Sem evidencia p/ um desvio, nao invente exercicio."
)


class FormCoach:
    """Plano corretivo a partir das métricas de forma (composição: LLM + RAG + guarda)."""

    def __init__(self, llm: BaseLLMClient, knowledge: Optional[BaseRetriever] = None, k: int = 4,
                 risk_assessor: Optional[Callable] = None):
        self.llm = llm
        self.knowledge = knowledge
        self.k = k
        self.guard = GroundingGuard()
        # avaliador de risco (drop-in prior↔treinado). Default = prior da literatura (seguro).
        self._assess_risk = risk_assessor or assess_risk

    # remove o "(Fonte: PMCxxxx)" cru do texto do exercício — a fonte vira chip legível na UI
    _FONTE_RE = re.compile(r"\s*[\(\[]?\s*fonte:?\s*PMC\d+\s*[\)\]]?\.?\s*$", re.IGNORECASE)

    @classmethod
    def _drills(cls, text: str) -> list:
        """Extrai os exercícios (uma linha cada) da resposta do LLM, limpando bullets, o
        sufixo '(Fonte: PMC...)' e descartando cabeçalhos que o modelo eventualmente insira."""
        out = []
        for line in text.splitlines():
            s = line.strip().lstrip("-•*").strip()
            low = s.lower()
            if len(s) < 8:
                continue
            if low.startswith(("a melhorar", "o que fazer", "desvios", "exercicios", "exercícios")):
                continue
            s = cls._FONTE_RE.sub("", s).strip()   # tira "(Fonte: PMCxxxx)" do fim
            if s:
                out.append(s)
        return out

    @staticmethod
    def _predisposed(by_injury: list) -> Optional[dict]:
        """Lesão mais predisposta AVALIÁVEL com risco real (score > 0). Serve pro coach citá-la
        pelo nome + fonte da taxonomia — sem inventar (as não avaliáveis nunca viram alerta)."""
        for i in (by_injury or []):
            if i.get("evaluable") and i.get("score", 0.0) > 0.0:
                return i
        return None

    def _prompt(self, metrics: dict, devs: list, hits: list, lib: list,
                predisposed: Optional[dict] = None) -> str:
        linhas = ["Desvios medidos (medido vs faixa ideal):"]
        for d in devs[:4]:
            faixa = f"<= {d['hi']:g}" if d["side"] == "alto" else f">= {d['lo']:g}"
            linhas.append(f"- {d['label']}: medido {d['value']:g}{d['unit']} "
                          f"(ideal {faixa}{d['unit']}) [FONTE: {d['source']}]")
        # Biblioteca DETERMINÍSTICA de exercícios (fonte de verdade citada): o LLM PERSONALIZA a
        # entrega destes, não inventa exercício. Reusa analytics.exercises.for_factors.
        if lib:
            linhas.append("\nBiblioteca de exercicios recomendados (baseie-se NESTES, cada um com sua FONTE):")
            for e in lib:
                linhas.append(f"- {e['name']} [FONTE: {e['source']}]")
        if hits:
            linhas.append("\nEvidencias de apoio (cite a FONTE ao explicar o porque):")
            for i, h in enumerate(hits, 1):
                linhas.append(f"{i}. {h['text']} [FONTE: {h['source']}]")
        elif not lib:
            linhas.append("\n(Sem evidencia relevante na base — nao invente exercicios.)")
        # Lesao mais predisposta (do perfil por-lesao, ja aterrada na taxonomia). O coach PODE
        # menciona-la citando a FONTE — sem inventar; se nao houver, nao fala de lesao.
        if predisposed:
            linhas.append(f"\nLesao a qual estes desvios mais predispoem: {predisposed['label']} "
                          f"[FONTE: {predisposed['source']}]. Ao explicar o porque, voce PODE "
                          f"mencionar essa lesao citando a fonte — nunca afirme que o atleta a tem.")
        return "\n".join(linhas)

    def plan(self, metrics: dict, profile: Optional[dict] = None,
             history: Optional[dict] = None) -> dict:
        """Devolve {verdict, actions, citations, targets, deviations}. Os DESVIOS (o que
        corrigir) sao deterministicos; o LLM so gera os exercicios (aterrados + citados)."""
        targets = ideal_targets(profile, history)

        # Guarda de CONFIABILIDADE (app de prevencao de lesao): se o motor marcou a captura
        # como nao-confiavel (nao-lateral, atleta fora do quadro, rastreio incoerente), NAO
        # diagnosticamos nem tranquilizamos ("sua forma esta otima") em cima de dado ruim —
        # avisamos pra refilmar. Melhor nao opinar do que opinar errado sobre lesao.
        if metrics.get("reliable") is False:
            nota = metrics.get("quality_note") or "A captura nao ficou boa o bastante pra analisar."
            return {
                "verdict": f"Ainda nao da pra analisar sua forma com confianca: {nota} "
                           "Refaca a filmagem e envie de novo — assim o plano sai certo.",
                "actions": [], "citations": [], "targets": targets, "deviations": [],
                "unreliable": True,
            }

        # Defesa em profundidade: nulifica métrica impossível do motor (ex.: gct 2000ms) antes de
        # virar desvio/risco — não depende só do flag reliable. §7 (dado validado) no caminho vivo.
        metrics, _nulled = sanitize_metrics(metrics)

        devs = diagnose(metrics, targets)
        risk = self._assess_risk(metrics, profile, history)  # prior OU treinado (mesma interface)

        if not devs:
            return {
                "verdict": "Sua forma esta dentro das faixas ideais nas metricas medidas. "
                           "Mantenha o trabalho e refaca a analise conforme evoluir.",
                "actions": [], "citations": [], "targets": targets, "deviations": [], "risk": risk,
            }

        # Roteamento: consulta só os domínios relevantes aos desvios (evita bleed) + biblioteca
        # determinística de exercícios pros fatores desviados.
        top = devs[:3]
        query = " ".join(d["query"] for d in top)
        domains = sorted({dom for d in top for dom in FACTOR_DOMAINS.get(d["metric"], ["biomecanica"])})
        hits = self.knowledge.retrieve(query, k=self.k, domains=domains) if self.knowledge else []
        lib = for_factors([d["metric"] for d in devs])
        predisposed = self._predisposed(risk.get("by_injury"))
        prompt = self._prompt(metrics, devs, hits, lib, predisposed)

        text = self.guard.enforce(self.llm, SYSTEM, prompt)
        issues = self.guard.issues(text, prompt + " " + " ".join(h["text"] for h in hits))
        if issues["invented_numbers"] or issues["banned_causes"]:
            text = self.guard.enforce(self.llm, SYSTEM, prompt, first=text)

        return {
            "verdict": text,
            "actions": self._drills(text),
            "citations": self._cited(text, hits, lib),
            "targets": targets,
            "deviations": devs,
            "risk": risk,
            "injury_profile": risk.get("by_injury", []),   # risco decomposto POR LESAO (aditivo)
        }

    @staticmethod
    def _cited(text: str, hits: list, lib: list = None) -> list:
        """"Baseado em:" — fontes que embasam o plano, como IDs estáveis (source_id: PMC/PMID/DOI).
        Une (1) as fontes dos EXERCÍCIOS da biblioteca (base determinística da prescrição, sempre
        citadas) + (2) a EVIDÊNCIA: as que o LLM citou nominalmente pelo título, senão toda a
        recuperada. Nunca deixa ação sem fonte visível (ciência citável, constituição §14)."""
        def sid_of(source: str):
            return GroundingGuard.source_id(source)

        out: list = []
        for e in (lib or []):                          # (1) fontes da biblioteca de exercícios
            sid = sid_of(e["source"])
            if sid and sid not in out:
                out.append(sid)

        low = text.lower()                             # (2) evidência citada nominalmente...
        matched: list = []
        for h in hits:
            titulo = re.split(r"\s+[—–-]\s+|\s*\(", h["source"].strip())[0]  # parte distintiva
            if len(titulo) >= 8 and titulo.lower() in low:
                sid = sid_of(h["source"])
                if sid and sid not in matched:
                    matched.append(sid)
        evidencia = matched or [sid_of(h["source"]) for h in hits]   # ...senão toda a recuperada
        for sid in evidencia:
            if sid and sid not in out:
                out.append(sid)
        return out
