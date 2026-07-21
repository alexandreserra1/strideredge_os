"""analytics/shoe.py — Recomendação de tênis HONESTA e citada (EPIC D).

Mesma filosofia do coach (analytics/exercises.py + form_coach.py): a lógica é DETERMINÍSTICA
e aterrada no corpus (domínio `calcado`); o LLM só personaliza a "capa" humana, nunca inventa.
Entra pisada + oscilação + peso + histórico → sai faixa de amortecimento/drop + dicas + caveats
+ fontes. Regra de ouro do app de lesão: NUNCA prometer prevenção — tênis é ajuste de carga.

As regras espelham a evidência dos 12 chunks de `calcado` no corpus (PMC8833076 pisada↔drop,
DOI 19424280.2023.2180542 drop↔região, DOI fspor.2022.815675 peso/minimalista/transição,
PMC6516670 mito da pronação, PMC11481106 amortecimento protetor, Malisoux 2015 rodar ≥2 pares).
"""

from typing import Optional

from core.framework.interfaces import BaseLLMClient, BaseRetriever
from analytics.grounding import GroundingGuard

# Fontes autoritativas (strings idênticas às do corpus) — o source_id() extrai o ID estável.
SRC_STRIKE = "Acute Effects of Heel-to-Toe Drop and Speed on Running Biomechanics and Strike Pattern (PMC8833076)"
SRC_DROP_REGION = "Heel-to-Toe Drop of Running Shoes — Systematic Review (Footwear Science 2023, doi 10.1080/19424280.2023.2180542)"
SRC_PARADIGM = "Running Injury Paradigms and Their Influence on Footwear Design Features — Focused Review (Frontiers Sports Act Living 2022, doi 10.3389/fspor.2022.815675)"
SRC_PRONATION = "Effects of Anti-Pronation Shoes on Lower Limb Kinematics in Female Runners with Pronated Feet — Role of Fatigue (PMC6516670)"
SRC_CUSHION = "Running Shoe Cushioning at Rearfoot and Forefoot and Relationship to Injury — RCT Protocol (PMC11481106)"
SRC_ROTATE = "Malisoux et al., Parallel Use of Different Running Shoes Decreases Running-Related Injury Risk (Scand J Med Sci Sports 2015)"

# Caveats de HONESTIDADE — obrigatórios em toda recomendação (app de prevenção de lesão).
CAVEAT = (
    "Nenhum tipo de tênis previne lesão sozinho: ele é ajuste de carga, não cura. "
    "Estabilidade escolhida pelo tipo de arco (o 'mito da pronação') NÃO é amparada pela evidência. "
    "Rodar entre pelo menos 2 pares diferentes associa-se a ~39% menos risco. "
    "Toda troca de tênis (drop, amortecimento, placa) exige transição gradual. "
    "A sua pisada aqui é uma INFERÊNCIA do vídeo — o pose atual não tem keypoint de pé; confirme com uma loja/fisio."
)
_CAVEAT_SOURCES = [SRC_PRONATION, SRC_ROTATE, SRC_PARADIGM, SRC_STRIKE]

# Sistema do LLM: só redige a capa humana a partir do que já foi decidido (sem inventar número).
SYSTEM = (
    "Voce e um consultor de calcado de corrida que fala com o ATLETA de forma humana e honesta. "
    "Recebe uma recomendacao JA decidida (amortecimento, faixa de drop, dicas, caveats) + evidencias. "
    "Escreva 2-3 frases curtas explicando a escolha em lingua de gente e SEMPRE deixe claro que tenis "
    "e ajuste de carga, nao previne lesao sozinho. Use SOMENTE numeros que aparecem nos dados (nao "
    "invente); nao prometa prevencao; nao cite tipo de arco/pronacao como criterio. Sem markdown."
)


def _norm_strike(foot_strike: str) -> str:
    """Normaliza a pisada do motor ('antepé'/'médio'/'calcanhar') p/ a chave sem acento."""
    return (foot_strike or "").lower().replace("é", "e").replace("ê", "e").replace("í", "i")


def recommend(foot_strike: str, vertical_oscillation_pct: Optional[float] = None,
              weight_kg: Optional[float] = None, history: Optional[dict] = None) -> dict:
    """Regras DETERMINÍSTICAS aterradas no corpus → recomendação estruturada e honesta.

    Devolve `{cushioning, drop_mm, tips: [...], caveat, sources: [...]}`. Roda sem RAG/LLM
    (degrada gracioso); o `ShoeRecommender` só ENRIQUECE isso com fontes recuperadas + capa humana.
    """
    strike = _norm_strike(foot_strike)   # o motor emite "antepé"/"médio" (com acento) — normaliza
    tips: list = []
    used = [SRC_STRIKE]

    # 1) Pisada ↔ drop/amortecimento (PMC8833076). Antepé/médio usam arco+Aquiles → drop menor;
    #    calcanhar gera transiente no retropé → amortecimento estruturado atrás + drop maior.
    if strike in ("antepe", "medio"):
        cushioning, drop_mm = "espuma uniforme (amortecimento parelho)", "4-6"
        tips.append("Pisada de antepé/médio combina com espuma uniforme e drop menor (4-6mm): "
                    "seu arco e Aquiles já amortecem, e o calcanhar atrapalha menos.")
    else:  # calcanhar (default seguro)
        cushioning, drop_mm = "amortecimento estruturado no retropé", "8-10"
        tips.append("Pisada de calcanhar pede amortecimento estruturado atrás e drop 8-10mm, "
                    "que facilita a transição do impacto no retropé.")

    # 2) Peso > 85kg: 3x mais lesão em minimalista (DOI fspor 815675) → cautela, amortecimento moderado.
    if weight_kg is not None and weight_kg > 85:
        cushioning = "amortecimento moderado a alto (evite minimalista)"
        tips.append("Acima de 85kg houve ~3x mais lesão em minimalista: prefira amortecimento "
                    "moderado a alto e fuja do drop 0mm por ora.")
        used.append(SRC_PARADIGM)

    # 3) Histórico por região (DOI 19424280 2023): joelho → drop menor GRADUAL; panturrilha/Aquiles → maior.
    drop_mm, tips, used = _apply_history(history, strike, drop_mm, tips, used)

    # 4) Oscilação vertical alta: mais impacto por passo — amortecimento ajuda a filtrar (PMC11481106).
    if vertical_oscillation_pct is not None and vertical_oscillation_pct > 8:
        tips.append("Sua oscilação vertical está alta, então cada passo bate mais forte: um "
                    "amortecimento que filtre o impacto ajuda enquanto você trabalha a técnica.")
        used.append(SRC_CUSHION)

    used += _CAVEAT_SOURCES
    sources = _dedup_ids(used)
    return {"cushioning": cushioning, "drop_mm": drop_mm, "tips": tips,
            "caveat": CAVEAT, "sources": sources}


def _apply_history(history: Optional[dict], strike: str, drop_mm: str,
                   tips: list, used: list) -> tuple:
    """Histórico de lesão ajusta o drop por REGIÃO (drop redistribui a carga, DOI 19424280)."""
    regions = set((history or {}).get("regions", []))
    knee = any("joelho" in r for r in regions)
    calf_achilles = bool(regions & {"tornozelo", "canela"})  # Aquiles→tornozelo na taxonomia
    if knee and strike == "calcanhar":
        drop_mm = "8-10 (migrando GRADUALMENTE para menor)"
        tips.append("Como você já teve lesão no joelho, considere migrar aos poucos para um drop "
                    "menor — drop alto associa-se a mais carga no joelho. Nunca de uma vez.")
        used.append(SRC_DROP_REGION)
    elif calf_achilles and strike in ("antepe", "medio"):
        drop_mm = "6-8 (um pouco maior pela panturrilha/Aquiles)"
        tips.append("Histórico de panturrilha/Aquiles se beneficia de um drop um pouco MAIOR: "
                    "drop baixo desloca o impacto para essa região.")
        used.append(SRC_DROP_REGION)
    return drop_mm, tips, used


def _dedup_ids(sources: list) -> list:
    """Strings de fonte → IDs estáveis citáveis (PMC/DOI/PMID/título), sem repetição, ordem preservada."""
    out: list = []
    for s in sources:
        sid = GroundingGuard.source_id(s)
        if sid and sid not in out:
            out.append(sid)
    return out


class ShoeRecommender:
    """Recomendador de tênis (composição: regras determinísticas + RAG opcional + LLM opcional).

    COMPÕE um `BaseRetriever` (polimorfismo — não acopla ao KnowledgeBase concreto): busca no
    domínio `calcado` para enriquecer as fontes citadas, e opcionalmente usa o LLM (com
    GroundingGuard) pra redigir a capa humana. Sem RAG/LLM, cai nas regras determinísticas.
    """

    def __init__(self, llm: Optional[BaseLLMClient] = None,
                 knowledge: Optional[BaseRetriever] = None, k: int = 4):
        self.llm = llm
        self.knowledge = knowledge
        self.k = k
        self.guard = GroundingGuard()

    @staticmethod
    def _query(foot_strike: str, weight_kg: Optional[float]) -> str:
        strike = (foot_strike or "calcanhar").lower()
        base = f"tenis para pisada de {strike} drop amortecimento"
        if weight_kg is not None and weight_kg > 85:
            base += " peso corporal alto minimalista risco"
        return base

    def recommend(self, foot_strike: str, vertical_oscillation_pct: Optional[float] = None,
                  weight_kg: Optional[float] = None, history: Optional[dict] = None,
                  write_cover: bool = False) -> dict:
        """Regras determinísticas + fontes do RAG roteado (`domains=['calcado']`). `write_cover`
        aciona o LLM aterrado pra redigir a 'capa' humana (senão devolve só o estruturado)."""
        rec = recommend(foot_strike, vertical_oscillation_pct, weight_kg, history)
        hits = []
        if self.knowledge:
            query = self._query(foot_strike, weight_kg)
            hits = self.knowledge.retrieve(query, k=self.k, domains=["calcado"])
            rec["sources"] = self._merge_sources(rec["sources"], hits)
        if write_cover and self.llm:
            rec["cover"] = self._cover(rec, hits)
        return rec

    def _merge_sources(self, sources: list, hits: list) -> list:
        """Une as fontes das REGRAS (base determinística, sempre citadas) + as recuperadas do RAG."""
        out = list(sources)
        for h in hits:
            sid = GroundingGuard.source_id(h["source"])
            if sid and sid not in out:
                out.append(sid)
        return out

    def _cover(self, rec: dict, hits: list) -> str:
        """Capa humana redigida pelo LLM, aterrada (GroundingGuard barra número inventado)."""
        linhas = [f"Amortecimento: {rec['cushioning']}", f"Faixa de drop: {rec['drop_mm']}mm",
                  "Dicas decididas:"]
        linhas += [f"- {t}" for t in rec["tips"]]
        linhas.append(f"Caveats obrigatorios: {rec['caveat']}")
        if hits:
            linhas.append("\nEvidencias de apoio (cite ao explicar):")
            linhas += [f"- {h['text']} [FONTE: {h['source']}]" for h in hits]
        prompt = "\n".join(linhas)
        text = self.guard.enforce(self.llm, SYSTEM, prompt)
        issues = self.guard.issues(text, prompt)
        if issues["invented_numbers"] or issues["banned_causes"]:
            text = self.guard.enforce(self.llm, SYSTEM, prompt, first=text)
        return text
