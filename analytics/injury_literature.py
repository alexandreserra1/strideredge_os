"""analytics/injury_literature.py — parâmetros REAIS publicados p/ parametrizar o sintético.

A "conjuntura de estudos" que aterra o gerador: em vez de uma regra inventada, cada fator
DISCRIMINANTE usa média±DP por grupo (saudável vs lesionado) de estudo publicado, com fonte. A
sobreposição real (pelos DPs) é o que torna o RF honesto — AUC ~0.8, não 1.0.

HONESTIDADE (não maquiar):
- Só entra número REAL publicado. Fator sem split saudável/lesionado publicado = NÃO-discriminante
  (amostrado da faixa ideal p/ os dois grupos) — não fabricamos discriminação que não temos.
- Fonte principal do split de marcha é N=19 (PMC7664858) — amostra PEQUENA, médias ruidosas. É o
  melhor disponível p/ grupos saudável/lesionado; sinalizado aqui, não escondido.
- Frequência de tipo de lesão vem de N=1.798 (PMC11564798) — grande e confiável.
"""

# Fator → distribuição por grupo (média, DP) + fonte. Só os que têm split publicado real.
# healthy/injured em unidade da métrica (bate com biomechanics.ideal_targets).
LIT_PARAMS = {
    "pelvic_drop_deg": {
        "healthy": (2.0, 1.8), "injured": (4.2, 2.1),   # obliquidade pélvica: ~2x no lesionado
        "source": "PMC7664858", "note": "preditor mais forte; N=19",
    },
    "cadence_spm": {
        # NÍVEL calibrado com dado real (Fukuchi, 39 corredores recreativos @ 3.5 m/s: 161.5±10.7 spm
        # — o "180" era otimista). EFEITO (lesionado ~7 spm abaixo) preservado do estudo RF. Combinar
        # nível de um estudo + efeito de outro evita o domain shift de trocar médias de populações ≠.
        "healthy": (161.5, 10.7), "injured": (154.5, 10.7),
        "source": "PMC5426356+PMC7664858",
        "note": "nível: Fukuchi recreativo real; efeito -7 spm: estudo RF",
    },
}

# Frequência REAL dos tipos de lesão (contagem na coorte N=1.798) → normalizada. Só as 4 mapeadas
# na nossa taxonomia (osteoartrite do estudo não é lesão de corrida da nossa taxonomia → fora).
INJURY_FREQ = {
    "pfp": 137, "itbs": 100, "plantar": 54, "achilles": 52,
}
INJURY_FREQ_SOURCE = "PMC11564798"


def discriminative_factors() -> list:
    """Fatores com split saudável/lesionado publicado (os que o RF pode aprender de verdade)."""
    return list(LIT_PARAMS.keys())


def injury_type_weights() -> tuple:
    """(ids, pesos normalizados) p/ amostrar o tipo de lesão pela frequência real."""
    ids = list(INJURY_FREQ)
    total = sum(INJURY_FREQ.values())
    return ids, [INJURY_FREQ[i] / total for i in ids]
