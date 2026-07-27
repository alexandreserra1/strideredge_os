"""analytics/biomechanics.py — alvos biomecânicos PERSONALIZADOS + diagnóstico de gap.

Funções puras (fáceis de testar): partem das faixas da literatura (corpus RAG) e ajustam
pelo contexto do atleta (morfologia/histórico). O `diagnose` compara o MEDIDO (FormMetrics
do motor) com o IDEAL e devolve os desvios priorizados — insumo do algoritmo corretivo.

Nada de LLM aqui: é aritmética aterrada. O coach (form_coach.py) transforma os desvios em
exercícios citados. Cada alvo carrega a FONTE do corpus pra manter a rastreabilidade.
"""

from typing import Optional


# faixa-base da literatura + direção do "melhor" + fonte (PMC do corpus)
def ideal_targets(profile: Optional[dict] = None, history: Optional[dict] = None) -> dict:
    """Alvos ideais por métrica. Ajusta pelo atleta quando há perfil; senão usa defaults
    populacionais. Ex.: corredor mais alto tende naturalmente a cadência um pouco menor."""
    p = profile or {}
    height = p.get("height_cm")

    # piso de cadência cai ~0.3 spm por cm acima de 175 (mais alto = passada mais longa)
    cad_floor = 170.0
    if height:
        cad_floor = round(170.0 - max(0.0, (height - 175.0)) * 0.3, 1)

    return {
        "cadence_spm": {"lo": cad_floor, "hi": 190.0, "unit": "spm", "dir": "higher_better",
                        "source": "PMC12440572",
                        "label": "cadência"},
        "ground_contact_ms": {"lo": 0.0, "hi": 250.0, "unit": "ms", "dir": "lower_better",
                              "source": "PMC3944563", "label": "tempo de contato com o solo"},
        "vertical_oscillation_pct": {"lo": 0.0, "hi": 8.0, "unit": "%", "dir": "lower_better",
                                     "source": "PMC11127892", "label": "oscilação vertical"},
        "knee_contact_deg": {"lo": 0.0, "hi": 174.0, "unit": "°", "dir": "lower_better",
                             "source": "PMC9441414", "label": "flexão do joelho no apoio"},
        "trunk_lean_deg": {"lo": 5.0, "hi": 14.0, "unit": "°", "dir": "range",
                           "source": "PMC11135760", "label": "inclinação do tronco"},
        "asymmetry_pct": {"lo": 0.0, "hi": 10.0, "unit": "%", "dir": "lower_better",
                          "source": "PMC7241633", "label": "assimetria E/D"},
        # --- plano FRONTAL (vista frontal) — sinais de risco de lesão mais fortes ---
        "pelvic_drop_deg": {"lo": 0.0, "hi": 10.0, "unit": "°", "dir": "lower_better",
                            "source": "PMC6829001", "label": "queda pélvica contralateral"},
        "knee_valgus_deg": {"lo": 0.0, "hi": 10.0, "unit": "°", "dir": "lower_better",
                            "source": "PMC6829001", "label": "valgo dinâmico de joelho"},
    }


# explicação em LINGUAGEM DE GENTE do que o desvio significa (por métrica + lado).
# É o que a UI mostra pro atleta — sem jargão, sem número solto.
PLAIN = {
    ("cadence_spm", "baixo"): "Seus passos estão um pouco longos e lentos. Dar passos mais "
        "curtos e rápidos faz o pé cair embaixo do corpo e amortece melhor o impacto.",
    ("ground_contact_ms", "alto"): "Seu pé fica tempo demais no chão a cada passada — falta "
        "'mola'. Correr mais leve e reativo devolve energia mais rápido.",
    ("vertical_oscillation_pct", "alto"): "Você sobe e desce demais a cada passo. Essa energia "
        "está indo pra cima em vez de pra frente — dá pra correr mais 'rasante'.",
    ("knee_contact_deg", "alto"): "Seu joelho está quase reto quando o pé toca o chão (passada "
        "longa demais). Isso joga o impacto direto na articulação, sem amortecer.",
    ("trunk_lean_deg", "baixo"): "Você corre muito ereto, quase 'sentado'. Uma leve inclinação "
        "do tronco pra frente aproveita a gravidade e tira peso do freio.",
    ("trunk_lean_deg", "alto"): "Você inclina o tronco pra frente demais, o que sobrecarrega a "
        "lombar. O ideal é uma inclinação suave, a partir do tornozelo.",
    ("asymmetry_pct", "alto"): "Há uma diferença grande entre a perna esquerda e a direita — um "
        "lado está trabalhando mais que o outro (pode ser fadiga ou compensação).",
    ("pelvic_drop_deg", "alto"): "Sua bacia cai bastante pro lado a cada apoio — sinal de quadril "
        "fraco (glúteo médio). Isso puxa o joelho pra dentro e sobrecarrega a patela e a banda IT.",
    ("knee_valgus_deg", "alto"): "Seu joelho 'cai pra dentro' quando você apoia (valgo). Isso "
        "concentra carga na patela — é um dos padrões mais ligados a dor no joelho na corrida.",
}


# COMO MEDIR/CONFERIR cada métrica SOZINHO, sem equipamento — por métrica (o método independe do
# lado do desvio). É FATO determinístico (aritmética/observação, não alegação clínica): garante que
# toda recomendação diga "como você sabe se chegou lá", sem depender do LLM lembrar. Constituição
# §11 (o código conclui, o LLM só redige) e §12 (prescrever o COMO, não só descrever).
MEASURE_HOWTO = {
    "cadence_spm": "Pra medir a sua agora: conte quantas vezes UM pé toca o chão em 20 segundos e "
                   "multiplique por 6 — esse é o seu número de passos por minuto.",
    "ground_contact_ms": "Não dá pra cronometrar a olho, mas dá pra sentir: pé 'raspando' o chão e "
                         "saindo rápido é bom; pé 'socando' e demorando pra sair é o que evitar.",
    "vertical_oscillation_pct": "Filme-se de lado e olhe a cabeça: se ela sobe e desce muito a cada "
                                "passo, você está gastando energia pra cima. Quanto mais estável, melhor.",
    "knee_contact_deg": "No vídeo de lado, veja ONDE o pé aterra: se cai bem à frente do corpo, a "
                        "passada está longa demais. O alvo é o pé cair quase embaixo do quadril.",
    "trunk_lean_deg": "De lado, compare seu tronco com uma linha reta pra cima: o ideal é uma leve "
                      "inclinação pra frente (poucos graus), nem totalmente ereto nem curvado.",
    "asymmetry_pct": "Difícil medir sozinho no número, mas no vídeo dá pra ver se um lado parece "
                     "'mancar' ou trabalhar mais que o outro.",
    "pelvic_drop_deg": "Filme-se de FRENTE: repare se a bacia cai pro lado da perna que está no ar "
                       "a cada passo — quanto menos cai, mais firme está o quadril.",
    "knee_valgus_deg": "Filme-se de FRENTE: repare se o joelho 'cai pra dentro' no instante em que "
                       "o pé apoia. Ele deve apontar pra frente, alinhado com o pé.",
}


# tema de busca no corpus p/ cada (metrica, LADO do desvio) — a DIRECAO importa: numa metrica
# que erra pros dois lados (trunk_lean e `range`), "alto" e "baixo" pedem evidencia OPOSTA. Se a
# busca fosse so por metrica, o RAG traria a evidencia de UM lado e o LLM, fiel a ela, recomendaria
# o oposto do desvio medido — conselho invertido num app de lesao. Chave = (metrica, lado).
CORRECTIVE_QUERY = {
    ("cadence_spm", "baixo"): "aumentar cadencia frequencia de passos metronomo reeducacao de marcha",
    ("ground_contact_ms", "alto"): "reduzir tempo de contato com o solo pliometria rigidez elastica",
    ("vertical_oscillation_pct", "alto"): "reduzir oscilacao vertical correr rasante economia de corrida",
    ("knee_contact_deg", "alto"): "overstriding passada longa aterrar sob o quadril aumentar cadencia",
    ("trunk_lean_deg", "baixo"): "inclinacao do tronco postura leve pra frente eficiencia",
    ("trunk_lean_deg", "alto"): "inclinacao do tronco excessiva sobrecarga lombar postura",
    ("asymmetry_pct", "alto"): "assimetria contato solo fortalecer quadril gluteo medio",
    ("pelvic_drop_deg", "alto"): "queda pelvica contralateral fortalecer gluteo medio abdutores quadril reeducacao de marcha",
    ("knee_valgus_deg", "alto"): "valgo dinamico de joelho fortalecer quadril gluteo dor patelofemoral controle do joelho",
}


def metric_quality(metrics: dict, key: str) -> Optional[float]:
    """Confiabilidade [0,1] de UMA métrica medida, combinando confiança dos keypoints
    (fração de frames confiáveis) e variabilidade entre passadas (coeficiente de variação).

    Contrato (ver stride_vision/metrics.rs): `metrics["metric_confidence"]` e
    `metrics["metric_cv"]` são dicts opcionais chave=nome-da-métrica. Ausência de
    `metric_confidence` = "sem informação de qualidade" (dumps antigos/testes) -> None,
    e quem chama deve se comportar EXATAMENTE como antes (sem essa noção). Se a chave não
    estiver em `metric_confidence`, também é None (sem info pra ESSA métrica específica).
    Com confiança presente: `quality = confidence * (1 - min(cv, 1.0))` quando há CV pra
    essa chave (métricas de amostra única, tipo cadência, não têm CV entre passadas);
    senão `quality = confidence`."""
    confidence = metrics.get("metric_confidence")
    if confidence is None:
        return None
    conf = confidence.get(key)
    if conf is None:
        return None
    cv = (metrics.get("metric_cv") or {}).get(key)
    if cv is None:
        return conf
    return conf * (1 - min(cv, 1.0))


class Deviations(list):
    """Lista de desvios (mesmo shape de sempre) + canal lateral opcional com as métricas
    que baterim faixa mas foram SUPRIMIDAS por baixa confiabilidade de medição. `list`
    puro por fora (compara/itera igual, não quebra call-sites nem testes existentes) —
    quem quiser o detalhe lê `.low_quality_metrics` (lista de dicts: metric/label/value/
    quality/side). Vazio quando não há supressão (comportamento de hoje)."""
    def __init__(self, *args):
        super().__init__(*args)
        self.low_quality_metrics: list = []


def diagnose(metrics: dict, targets: dict) -> list:
    """Compara o medido × alvo. Devolve desvios (fora da faixa) ordenados do pior pro
    melhor. `severity` = quão longe da faixa, normalizado pela largura (comparável entre
    métricas de unidades diferentes).

    A DIREÇÃO do alvo (`dir`) decide o que conta como desvio — não basta "fora da faixa":
      - higher_better (cadência): só incomoda ficar ABAIXO do piso. Passar do topo NÃO é falha
        (cadência alta protege contra impacto); tratar o topo como teto rígido geraria conselho
        invertido ('reduza a cadência') num app de prevenção de lesão.
      - lower_better (contato, oscilação, joelho, assimetria): só incomoda passar do teto.
      - range (inclinação de tronco): fora da faixa nos dois lados.

    CONFIABILIDADE DA MEDIÇÃO (ex.: ângulo de joelho por pose tem MAE de 24-29° vs mocap —
    ver tools/pose_calibration/CALIBRATION_FINDINGS.md): uma métrica que bateria a faixa de
    desvio mas tem `metric_quality(metrics, key) < 0.6` NÃO entra nos desvios — o erro de
    medição pode ser maior que a margem de decisão clínica, e cravar o desvio seria alegação
    não aterrada (constituição §7). Ela some da lista mas fica visível em
    `out.low_quality_metrics` pro chamador sinalizar "medição incerta" (não é feedback
    silencioso). Sem `metric_confidence` no dict (dumps antigos/testes) -> `metric_quality`
    é None -> comportamento IDÊNTICO ao de antes desta mudança."""
    out = Deviations()
    for key, t in targets.items():
        v = metrics.get(key)
        if v is None:
            continue
        lo, hi, direction = t["lo"], t["hi"], t["dir"]
        if direction == "higher_better":
            if v >= lo:
                continue
            side, gap = "baixo", lo - v
        elif direction == "lower_better":
            if v <= hi:
                continue
            side, gap = "alto", v - hi
        else:  # range: erra pros dois lados
            if v < lo:
                side, gap = "baixo", lo - v
            elif v > hi:
                side, gap = "alto", v - hi
            else:
                continue

        quality = metric_quality(metrics, key)
        if quality is not None and quality < 0.6:
            out.low_quality_metrics.append({
                "metric": key, "label": t["label"], "value": v, "side": side,
                "quality": round(quality, 3),
            })
            continue

        width = max(hi - lo, 1e-6)
        out.append({
            "metric": key, "label": t["label"], "value": v, "lo": lo, "hi": hi,
            "unit": t["unit"], "side": side, "source": t["source"],
            "severity": round(gap / width, 3),
            "query": CORRECTIVE_QUERY.get((key, side), t["label"]),
            "plain": PLAIN.get((key, side), ""),   # explicação em linguagem de gente
            "how_to_measure": MEASURE_HOWTO.get(key, ""),  # como o atleta confere sozinho (§11/§12)
        })
    out.sort(key=lambda d: d["severity"], reverse=True)
    return out
