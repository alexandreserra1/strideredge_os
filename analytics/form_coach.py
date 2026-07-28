"""analytics/form_coach.py — Algoritmo Corretivo: do gap biomecânico -> exercícios citados.

Fecha o ciclo "vê o movimento -> entende -> age". Recebe as métricas do motor de vídeo
(FormMetrics) + o perfil do atleta, calcula os alvos ideais e o gap (analytics/biomechanics),
recupera a evidência do corpus (RAG) e o LLM local transforma isso em um plano de correção
COM fonte. Reusa a mesma disciplina do veredito: `GroundingGuard` (sem número inventado) e
`VerdictParser` (saída estruturada). Sem evidência no corpus, não inventa exercício.
"""

import re
import unicodedata
from typing import Callable, Optional

from core.framework.interfaces import BaseLLMClient, BaseRetriever
from analytics.grounding import GroundingGuard
from analytics.biomechanics import ideal_targets, diagnose
from analytics.injury_risk import assess as assess_risk
from analytics.injury_quality import sanitize_metrics
from analytics.exercises import for_factors
from analytics.injury_taxonomy import DIAGNOSES

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
    "Voce e um treinador de corrida conversando com um CORREDOR AMADOR — alguem que corre pra ficar "
    "bem, nao um cientista do esporte. Fale como um bom treinador que te conhece: caloroso, "
    "encorajador, claro e direto. NADA de linguagem de artigo cientifico. Recebe desvios "
    "biomecanicos ja medidos + EVIDENCIAS cientificas. Para CADA desvio listado, escreva UMA "
    "recomendacao, UMA POR LINHA comecando com '- ', numa frase natural e fluida com TRES partes: "
    "(1) O QUE fazer (acao concreta e simples, em palavras do dia a dia); (2) POR QUE isso ajuda "
    "VOCE (o beneficio no seu corpo e na sua corrida, em lingua de gente — ex.: 'dar passos mais "
    "curtos e rapidos faz o pe cair embaixo do corpo e absorver melhor o tranco'); (3) COMO por em "
    "pratica de um jeito que a pessoa consiga FAZER e MEDIR SOZINHA, SEM equipamento de laboratorio "
    "— sempre de um metodo pratico de medir/conferir o proprio progresso com o corpo ou o celular. "
    "Ex. p/ cadencia: 'conte quantas vezes UM pe toca o chao em 20 segundos e multiplique por 6 — "
    "mire perto de X; se estiver baixo, abra um app de metronomo em X batidas e faca cada pisada "
    "bater junto com o bip, 1x na semana numa corrida leve'. Ex. p/ tempo de contato ou pisada: "
    "de uma referencia sensorial ('sinta o pe passando raspando o chao, nao socando'). Nunca mande "
    "so 'atinja o valor X' sem dizer COMO chegar e COMO saber que chegou. "
    "TRADUZA TODO termo tecnico: se precisar usar uma palavra do vocabulario de biomecanica "
    "(cadencia, oscilacao vertical, dorsiflexao, tempo de contato, queda pelvica, valgo, "
    "assimetria, economia de corrida, etc.), explique-a ali mesmo em 3-5 palavras entre parenteses, "
    "OU reformule sem o termo. Exemplos: 'sua cadencia (quantos passos voce da por minuto)', "
    "'oscilacao vertical (o quanto voce sobe e desce a cada passada)', 'economia de corrida (gastar "
    "menos energia pra manter o mesmo ritmo)'. Nunca deixe um jargao cru, sem traducao. "
    "Termine SEMPRE a linha com a fonte entre parenteses (Fonte: PMCxxxx) — isso e OBRIGATORIO em "
    "toda recomendacao, nunca omita. Quando o desvio vier com 'COMO O ATLETA MEDE ISSO SOZINHO' ou "
    "um exercicio vier com 'COMO FAZER', REAPROVEITE esse metodo pronto na sua frase (nao invente "
    "outro jeito de medir/fazer) — o atleta precisa saber como conferir sozinho. "
    "EXEMPLO de uma recomendacao boa (siga este formato): '- Aumente sua cadencia (quantos passos "
    "voce da por minuto). Pra saber a sua agora, conte quantas vezes um pe toca o chao em 20 "
    "segundos e multiplique por 6; se der menos de 170, abra um app de metronomo nesse numero e "
    "faca a pisada bater junto com o bip, 1x na semana numa corrida leve. Passos mais curtos fazem "
    "o pe cair embaixo do corpo e absorver melhor o tranco (Fonte: PMC10761631).' "
    "Regras: fale 'voce', tom de treinador que torce por voce; cada "
    "linha ataca UM desvio LISTADO; se a evidencia citar metrica que NAO esta na lista, IGNORE; NAO "
    "use markdown nem cabecalhos; use SOMENTE numeros que aparecem nos dados (nao invente numero nem "
    "causa); recomende SO o que a evidencia ampara e cite a FONTE. Sem evidencia p/ um desvio, nao "
    "invente exercicio."
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
    def _norm(text: str) -> str:
        """Minúsculas + sem acento — pra casar 'cadência' com 'cadencia' de forma robusta."""
        nfkd = unicodedata.normalize("NFKD", text or "")
        return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()

    @classmethod
    def _match_action(cls, actions: list, dev: dict) -> Optional[int]:
        """Índice da ação que fala DESTE desvio. Casa pelas palavras distintivas do rótulo
        (ex.: 'cadência' -> a ação que diz 'cadencia'). Escolhe a de maior sobreposição."""
        kws = [w for w in cls._norm(dev.get("label", "")).split() if len(w) >= 4]
        if not kws:
            return None
        best, best_hits = None, 0
        for i, a in enumerate(actions):
            na = cls._norm(a)
            hits = sum(1 for w in kws if w in na)
            if hits > best_hits:
                best, best_hits = i, hits
        return best

    @classmethod
    def _mentions_method(cls, action: str, howto: str) -> bool:
        """A ação já contém o método de medir? Mede a sobreposição das palavras significativas
        do how_to_measure — sem exigir a frase literal (o LLM parafraseia). Âncora >= 35%."""
        na = cls._norm(action)
        sig = [w for w in cls._norm(howto).split() if len(w) > 3]
        if not sig:
            return True
        hits = sum(1 for w in sig if w in na)
        return hits / len(sig) >= 0.35

    @classmethod
    def _ensure_measure_method(cls, actions: list, devs: list) -> list:
        """PÓS-PROCESSAMENTO determinístico (§11/§12): garante que toda ação de um desvio com
        'como medir sozinho' contenha ESSE método — venha o LLM como vier. Se a ação já traz o
        método (paráfrase), não duplica; senão anexa o texto pronto de biomechanics.MEASURE_HOWTO.
        Genérico p/ toda métrica; a cadência é só o caso mais crítico. Não inventa número nem
        afrouxa o grounding — só materializa o método que já está no código.

        1 método por ação: se dois desvios casarem com a MESMA ação (raro — uma frase que menciona
        duas métricas), só o primeiro anexa o método; senão a ação viraria uma frase corrida com
        dois 'como medir' emendados."""
        out = list(actions)
        used = set()                              # índices de ação que já receberam um método
        for d in devs:
            howto = d.get("how_to_measure")
            if not howto:
                continue                          # métrica sem método pronto: não mexe
            idx = cls._match_action(out, d)
            if idx is None or idx in used:
                continue                          # sem ação p/ o desvio, ou ação já tem 1 método
            if cls._mentions_method(out[idx], howto):
                used.add(idx)                     # LLM já incluiu: conta como método presente
                continue                          # já mencionou (não duplica)
            base = out[idx].rstrip()
            if base and base[-1] not in ".!?":
                base += "."
            out[idx] = f"{base} {howto}"          # anexa o método pronto, de forma natural
            used.add(idx)
        return out

    @staticmethod
    def _uncertain_entries(targets: dict, low_quality: list, nulled: list) -> list:
        """Unifica as métricas 'não avaliáveis' num formato único pro frontend: baixa confiança de
        medição + valor implausível anulado. Cada uma: {metric, label, reason}. Sem duplicar."""
        out, seen = [], set()
        for lq in low_quality:
            m = lq["metric"]
            if m in seen:
                continue
            seen.add(m)
            out.append({"metric": m, "label": lq.get("label", m),
                        "reason": "medição pouco confiável nesta captura"})
        for m in nulled:
            if m in seen:
                continue
            seen.add(m)
            label = targets.get(m, {}).get("label", m)
            out.append({"metric": m, "label": label,
                        "reason": "valor implausível — provável artefato de captura"})
        return out

    @staticmethod
    def _recurrence_watch(devs: list, history: Optional[dict]) -> list:
        """PREVENÇÃO DE RECAÍDA (loop pra frente): pra cada lesão que o atleta JÁ TEVE, se a forma
        ATUAL ainda mostra um fator que a literatura liga a ela, alerta pra priorizar. É a
        contraparte do retrospecto (que olha o passado): usa o histórico de lesão — 'preditor #1' —
        pra ligar o desvio de hoje ao que já machucou. Honesto: associação citada, não recidiva
        garantida. Vazio sem histórico (convidado) ou sem desvio coincidente."""
        diagnoses = (history or {}).get("diagnoses", [])
        if not diagnoses:
            return []
        deviated = {d["metric"]: d["label"] for d in devs}
        watch = []
        for dx in diagnoses:
            info = DIAGNOSES.get(dx)
            if not info or not info.get("source"):
                continue                       # só lesão mapeada à literatura
            hits = [deviated[f] for f in info["factors"] if f in deviated]
            if hits:
                watch.append({"diagnosis": dx, "label": info["label"],
                              "source": info["source"], "factors": hits})
        return watch

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
            # COMO MEDIR pronto (determinístico) — o LLM DEVE usar este método, não inventar outro.
            if d.get("how_to_measure"):
                linhas.append(f"    COMO O ATLETA MEDE ISSO SOZINHO (use exatamente): {d['how_to_measure']}")
        # Biblioteca DETERMINÍSTICA de exercícios (fonte de verdade citada): o LLM PERSONALIZA a
        # entrega destes, não inventa exercício. Reusa analytics.exercises.for_factors. Cada um traz
        # o COMO FAZER pronto — o LLM deve reaproveitar o método, não improvisar execução.
        if lib:
            linhas.append("\nBiblioteca de exercicios recomendados (baseie-se NESTES, cada um com sua FONTE):")
            for e in lib:
                linhas.append(f"- {e['name']} [FONTE: {e['source']}]")
                if e.get("how"):
                    linhas.append(f"    COMO FAZER (use este metodo): {e['how']}")
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
                "unreliable": True, "uncertain_metrics": [],
            }

        # Defesa em profundidade: nulifica métrica impossível do motor (ex.: gct 2000ms, oscilação
        # 22%) antes de virar desvio/risco — não depende só do flag reliable. §7 (dado validado).
        metrics, nulled = sanitize_metrics(metrics)

        devs = diagnose(metrics, targets)
        # Métricas que a gente NÃO pôde avaliar com confiança nesta captura, por dois motivos:
        # (a) baixa confiabilidade de medição (keypoints ruins/ruído entre passadas) e (b) valor
        # FISIOLOGICAMENTE IMPLAUSÍVEL, anulado pelo saneamento (provável artefato de câmera). Nos
        # dois casos NÃO viram desvio nem alegação do LLM — mas o atleta PRECISA saber que não deu
        # pra avaliar (num app de lesão, "não medido" != "está ótimo"). Vira selo na UI.
        uncertain = self._uncertain_entries(targets, getattr(devs, "low_quality_metrics", []), nulled)
        risk = self._assess_risk(metrics, profile, history)  # prior OU treinado (mesma interface)
        # Prevenção de recaída: desvio de hoje que coincide com lesão que o atleta já teve (loop pra frente).
        recurrence = self._recurrence_watch(devs, history)

        if not devs:
            # Sem desvio NAS MÉTRICAS AVALIÁVEIS. Se algo ficou sem avaliar, o veredito NÃO pode
            # dizer "está tudo ideal" — seria enganoso (e perigoso num app de lesão).
            if uncertain:
                nomes = ", ".join(u["label"] for u in uncertain)
                verdict = (f"As métricas que deram pra avaliar com confiança estão dentro das faixas "
                           f"ideais. Mas não consegui avaliar com segurança: {nomes} — a captura não "
                           f"permitiu. Vale refilmar de lado, corpo inteiro no quadro, pra eu conferir.")
            else:
                verdict = ("Sua forma esta dentro das faixas ideais nas metricas medidas. "
                           "Mantenha o trabalho e refaca a analise conforme evoluir.")
            return {
                "verdict": verdict,
                "actions": [], "citations": [], "targets": targets, "deviations": [], "risk": risk,
                "uncertain_metrics": uncertain, "recurrence_watch": [],
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
            "actions": self._ensure_measure_method(self._drills(text), devs),
            "citations": self._cited(text, hits, lib),
            "targets": targets,
            "deviations": devs,
            "risk": risk,
            "injury_profile": risk.get("by_injury", []),   # risco decomposto POR LESAO (aditivo)
            "uncertain_metrics": uncertain,   # suprimidas por baixa confiabilidade — selo na UI
            "recurrence_watch": recurrence,   # lesão prévia cujo fator ainda aparece — prevenir recaída
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
